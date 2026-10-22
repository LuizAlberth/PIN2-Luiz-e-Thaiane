from datetime import datetime, timedelta, timezone
from uuid import uuid4
import unicodedata
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import Session
from .models import Config, Reading, Event, Job, Scene, Attempt, Audit, now
from .adapters import ANAClient, CDSEClient, ProviderError, parsed_time, verify_png
from .satellite_demo import BBOX as DEMO_BBOX, TRIGGER as DEMO_TRIGGER, HISTORICAL_CONTEXT, load_pair
from .storage import put
import logging
import time

log = logging.getLogger(__name__)
PUBLIC = ('DISPONIVEL', 'PARCIAL')

class PermanentError(Exception):
    pass

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

def active_config(db: Session):
    return db.scalar(select(Config).where(Config.active == True).order_by(Config.version.desc()))

def audit(db, actor_id, action, entity_id, details=None):
    db.add(Audit(actor_id=actor_id, action=action, entity_id=entity_id, details=details or {}))

def validate_area(bbox, lat, lon):
    if len(bbox) != 4 or not all(isinstance(n, (float, int)) for n in bbox):
        raise ValueError('Área deve ser uma bounding box [oeste, sul, leste, norte]')
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Coordenadas inválidas para EPSG:4326')
    if not (west <= lon <= east and south <= lat <= north):
        raise ValueError('A área precisa conter a estação')
    width = (east - west) * 111.32 * __import__('math').cos(__import__('math').radians(lat))
    height = (north - south) * 111.32
    if width > 5.5 or height > 5.5 or width < 0.1 or height < 0.1:
        raise ValueError('A área piloto deve medir até cerca de 5 km por 5 km')

def has_recent_valid_level(readings):
    return any(r['level_cm'] is not None and r['quality'] == 'VALIDA' and
               timedelta(0) <= now() - parsed_time(r['observed_at']) <= timedelta(days=2) for r in readings)

def create_config(db, actor_id, data, ana=None):
    if data['threshold_cm'] <= 0 or not data['threshold_source'].strip() or not data['threshold_responsible'].strip():
        raise ValueError('Cota positiva, fonte e responsável são obrigatórios')
    if not (5 <= data['collection_interval_min'] <= 1440 and 0 < data['baseline_min_days'] < data['baseline_max_days'] <= 90 and 0 < data['post_window_days'] <= 30):
        raise ValueError('Intervalo ou janelas inválidas')
    if data['source_mode'] != 'ANA':
        raise ValueError('Configuração de produção exige fonte ANA; use o botão de demonstração para dados fictícios')
    ana = ana or ANAClient()
    station = ana.station(data['station_code'])
    if not station:
        raise ValueError('Estação não encontrada no inventário ANA')
    station_type = unicodedata.normalize('NFKD', str(station.get('Tipo_Estacao') or ''))
    station_type = ''.join(c for c in station_type if not unicodedata.combining(c)).lower()
    if str(station.get('Operando')) != '1' or not station_type.startswith('fluviometrica'):
        raise ValueError('A estação precisa estar operante e classificada como fluviométrica no inventário ANA')
    # Presence in the telemetric series is also checked: an inventory entry alone is insufficient.
    readings = ana.readings(data['station_code'])
    if not has_recent_valid_level(readings):
        raise ValueError('Estação sem cota telemétrica válida nas últimas 48 horas; ativação bloqueada')
    lat = float(station.get('Latitude'))
    lon = float(station.get('Longitude'))
    validate_area(data['bbox'], lat, lon)
    previous = active_config(db)
    instant = now()
    if previous:
        previous.active = False
        previous.valid_to = instant
    version = (db.scalar(select(func.max(Config.version))) or 0) + 1
    config = Config(version=version, station_code=data['station_code'],
        station_name=station.get('Estacao_Nome') or data['station_code'], river=data.get('river') or 'Rio Krauel',
        station_lat=lat, station_lon=lon, bbox=data['bbox'],
        threshold_cm=data['threshold_cm'], threshold_source=data['threshold_source'],
        threshold_valid_from=parsed_time(data['threshold_valid_from']),
        threshold_responsible=data['threshold_responsible'],
        collection_interval_min=data['collection_interval_min'], baseline_min_days=data['baseline_min_days'],
        baseline_max_days=data['baseline_max_days'], post_window_days=data['post_window_days'],
        source_mode='ANA', active=True, valid_from=instant, created_by=actor_id)
    db.add(config)
    db.flush()
    audit(db, actor_id, 'CONFIG_ATIVADA', config.id, {'version': version, 'station': config.station_code,
        'threshold_cm': config.threshold_cm, 'source': config.threshold_source})
    db.commit()
    return config

def demo_config(db, actor_id):
    previous = active_config(db)
    instant = now()
    # A demonstration must never switch off a running ANA monitor.
    keep_live = bool(previous and previous.source_mode == 'ANA')
    if previous and not keep_live:
        previous.active = False
        previous.valid_to = instant
    version = (db.scalar(select(func.max(Config.version))) or 0) + 1
    config = Config(version=version, station_code=f'DEMO-{version}-83372100', station_name='Estação simulada · Presidente Getúlio',
        river='Rios Krauel e dos Índios', station_lat=-27.038, station_lon=-49.624,
        bbox=DEMO_BBOX, threshold_cm=300,
        threshold_source='Valor simulado; não é cota oficial ANA', threshold_valid_from=DEMO_TRIGGER - timedelta(days=60),
        threshold_responsible='Sistema de demonstração', collection_interval_min=30,
        baseline_min_days=7, baseline_max_days=30, post_window_days=30,
        source_mode='DEMO', active=not keep_live, valid_from=instant, created_by=actor_id)
    db.add(config)
    db.flush()
    audit(db, actor_id, 'DEMO_ATIVADA', config.id, {'version': version})
    db.commit()
    return config

def create_jobs(db, event, version=1):
    for kind in ('BASELINE', 'POST_EVENT'):
        db.add(Job(event_id=event.id, kind=kind, version=version,
            scheduled_for=now(), correlation_id=str(uuid4())))

def ingest(db: Session, config: Config, readings: list[dict], mode='AO_VIVO', correlation_id=None):
    correlation_id = correlation_id or str(uuid4())
    count = 0
    events = []
    for item in sorted(readings, key=lambda x: parsed_time(x['observed_at'])):
        observed = parsed_time(item['observed_at'])
        if observed < utc(config.valid_from) and mode == 'AO_VIVO':
            continue
        existing = db.scalar(select(Reading).where(Reading.station_code == config.station_code,
            Reading.observed_at == observed, Reading.mode == mode))
        if existing:
            continue
        previous = db.scalar(select(Reading).where(Reading.station_code == config.station_code,
            Reading.mode == mode, Reading.observed_at < observed, Reading.quality_status == 'VALIDA',
            Reading.water_level_cm.is_not(None)).order_by(Reading.observed_at.desc()).limit(1))
        reading = Reading(station_code=config.station_code, observed_at=observed,
            water_level_cm=item.get('level_cm'), quality_status=item.get('quality', 'SEM_COTA'),
            raw_payload=item.get('raw') or {}, correlation_id=correlation_id, mode=mode)
        db.add(reading)
        db.flush()
        count += 1
        if reading.quality_status != 'VALIDA' or reading.water_level_cm is None or observed < utc(config.threshold_valid_from):
            continue
        open_event = db.scalar(select(Event).where(Event.config_id == config.id, Event.mode == mode,
            Event.ended_at.is_(None), Event.started_at <= observed).order_by(Event.started_at.desc()).limit(1))
        if open_event:
            if reading.water_level_cm < config.threshold_cm:
                open_event.below_streak += 1
                if open_event.below_streak >= 2:
                    open_event.ended_at = observed
            else:
                open_event.below_streak = 0
        if previous and previous.water_level_cm < config.threshold_cm <= reading.water_level_cm and not open_event:
            event = Event(config_id=config.id, trigger_reading_id=reading.id,
                trigger_level_cm=reading.water_level_cm, started_at=observed, mode=mode,
                status='AGUARDANDO_IMAGEM', snapshot={
                    'station_code': config.station_code, 'station_name': config.station_name,
                    'river': config.river, 'bbox': config.bbox, 'threshold_cm': config.threshold_cm,
                    'threshold_source': config.threshold_source, 'config_version': config.version,
                    'source_mode': config.source_mode})
            db.add(event)
            db.flush()
            create_jobs(db, event)
            events.append(event.id)
    db.commit()
    return {'inserted': count, 'events_created': events}

def demo_replay(db, config):
    if config.source_mode != 'DEMO':
        raise ValueError('Ative a configuração de demonstração primeiro')
    existing = db.scalars(select(Event).where(Event.config_id == config.id, Event.mode == 'SIMULACAO')).all()
    if existing:
        return {'inserted': 0, 'events_created': [e.id for e in existing]}
    # Fictional levels follow the documented episode; they are never ANA readings.
    offsets = [-27, -9, -3, 0, 6, 18, 45, 69, 93, 699]
    levels = [225, 260, 295, 308, 355, 378, 322, 289, 270, 235]
    readings = [{'observed_at': DEMO_TRIGGER + timedelta(hours=offset), 'level_cm': level,
        'quality': 'VALIDA', 'raw': {'origem': 'cenário didático', 'ficticio': True}} for offset, level in zip(offsets, levels)]
    result = ingest(db, config, readings, 'SIMULACAO')
    for event_id in result['events_created']:
        event = db.get(Event, event_id)
        event.snapshot = {**event.snapshot, 'historical_context': HISTORICAL_CONTEXT}
    db.commit()
    return result

def enqueue_collection(db, config):
    # A failed collection stays failed until an administrator explicitly requests a new attempt.
    due = db.scalar(select(Job).where(Job.kind == 'COLLECT'))
    if not due:
        db.add(Job(kind='COLLECT', scheduled_for=now(), correlation_id=str(uuid4())))
        db.commit()

def scene_for(db, event_id, role, version=None):
    q = select(Scene).where(Scene.event_id == event_id, Scene.role == role)
    if version is not None:
        q = q.where(Scene.version == version)
    return db.scalar(q.order_by(Scene.version.desc()).limit(1))

def displayed_scenes(db, event_id):
    before = scene_for(db, event_id, 'BASELINE')
    after = scene_for(db, event_id, 'POST_EVENT')
    if before and after and before.version != after.version:
        common = min(before.version, after.version)
        before = scene_for(db, event_id, 'BASELINE', common) or before
        after = scene_for(db, event_id, 'POST_EVENT', common) or after
    return before, after

def update_event(db, event):
    before, after = displayed_scenes(db, event.id)
    pending = db.scalar(select(Job).where(Job.event_id == event.id, Job.status.in_(['PENDENTE','AGUARDANDO_RETRY','EM_EXECUCAO'])).limit(1))
    if before and after:
        event.status = 'DISPONIVEL' if before.compatibility_status == after.compatibility_status == 'COMPATIVEL' else 'PARCIAL'
        event.failure_summary = None
    elif pending:
        event.status = 'AGUARDANDO_IMAGEM'
    elif before or after:
        event.status = 'PARCIAL'
        event.failure_summary = 'Uma das imagens está indisponível; comparação parcial.'
    else:
        event.status = 'FALHOU'
        event.failure_summary = 'Não foi possível obter evidências na janela definida.'

def run_job(db, job, ana=None, cdse=None):
    begin = time.monotonic()
    provider = 'ANA' if job.kind == 'COLLECT' else 'CDSE'
    try:
        if job.kind == 'COLLECT':
            config = active_config(db)
            if config and config.source_mode == 'ANA':
                ana = ana or ANAClient()
                ingest(db, config, ana.readings(config.station_code, window='DIAS_2'), 'AO_VIVO', job.correlation_id)
                job.scheduled_for = now() + timedelta(minutes=config.collection_interval_min)
                job.status = 'PENDENTE'
            else:
                job.status = 'CONCLUIDO'
            job.attempts = 0
        else:
            event = db.get(Event, job.event_id)
            config = db.get(Config, event.config_id)
            role = job.kind
            trigger = utc(event.started_at)
            if role == 'POST_EVENT':
                baseline = scene_for(db, event.id, 'BASELINE', job.version)
                baseline_job = db.scalar(select(Job).where(Job.event_id == event.id,
                    Job.kind == 'BASELINE', Job.version == job.version))
                if not baseline and baseline_job and baseline_job.status in ('PENDENTE', 'AGUARDANDO_RETRY', 'EM_EXECUCAO'):
                    job.status = 'PENDENTE'
                    job.scheduled_for = now() + timedelta(seconds=20)
                    db.commit()
                    return
            if config.source_mode == 'DEMO':
                if config.bbox != DEMO_BBOX or abs((trigger - DEMO_TRIGGER).total_seconds()) > 1:
                    raise PermanentError('Demonstração antiga: inicie uma nova demonstração para usar o par Sentinel real e suas datas.')
                candidate, views = load_pair()[role]
                blob = views['default']
                provider = 'CDSE'
            else:
                cdse = cdse or CDSEClient()
                if role == 'BASELINE':
                    start = trigger - timedelta(days=config.baseline_max_days)
                    end = trigger - timedelta(days=config.baseline_min_days)
                    baseline = None
                else:
                    start = trigger + timedelta(seconds=1)
                    end = min(now(), trigger + timedelta(days=config.post_window_days))
                    baseline = scene_for(db, event.id, 'BASELINE', job.version)
                    if end <= start and now() < trigger + timedelta(days=config.post_window_days):
                        job.status = 'PENDENTE'
                        job.scheduled_for = now() + timedelta(hours=6)
                        db.commit()
                        return
                features = cdse.search(config.bbox, start, end) if end > start else []
                selected_baseline = None if not baseline else {
                    'instrument_mode': baseline.instrument_mode, 'orbit_direction': baseline.orbit_direction,
                    'polarization': baseline.polarization, 'relative_orbit': baseline.relative_orbit}
                candidate = cdse.select(features, role, trigger, selected_baseline, config.bbox)
                if not candidate:
                    if role == 'POST_EVENT' and now() < trigger + timedelta(days=config.post_window_days):
                        job.status = 'PENDENTE'
                        job.scheduled_for = min(now() + timedelta(hours=6), trigger + timedelta(days=config.post_window_days))
                        db.commit()
                        return
                    raise PermanentError('Nenhuma cena compatível na janela temporal')
                blob = cdse.process(config.bbox, candidate)
            width, height = verify_png(blob)
            key = f'{event.id}/{role.lower()}-v{job.version}.png'
            checksum = put(key, blob)
            extra = {}
            if config.source_mode == 'DEMO':
                natural_key = f'{event.id}/{role.lower()}-natural-v{job.version}.png'
                extra = {'natural_key': natural_key, 'natural_checksum': put(natural_key, views['natural'])}
            scene = Scene(event_id=event.id, role=role, version=job.version,
                provider_product_id=candidate['id'], acquired_at=candidate['acquired_at'],
                instrument_mode=candidate['instrument_mode'], orbit_direction=candidate['orbit_direction'],
                relative_orbit=candidate['relative_orbit'], polarization=candidate['polarization'],
                selection_reason=(HISTORICAL_CONTEXT['labels'][role] + '; cena clara, fora do pico da enchente') if config.source_mode == 'DEMO' else ('Mais recente na janela anterior' if role == 'BASELINE' else 'Primeira cena compatível após o gatilho'),
                source=provider, image_key=key, checksum_sha256=checksum, width=width, height=height,
                metadata_json={**candidate['raw'], **extra, 'coverage_percent': candidate.get('coverage_percent', 100.0)})
            db.add(scene)
            db.flush()
            job.status = 'CONCLUIDO'
            job.last_error = None
            update_event(db, event)
        db.add(Attempt(job_id=job.id, provider=provider, status='SUCESSO',
            duration_ms=int((time.monotonic()-begin)*1000), correlation_id=job.correlation_id))
        job.locked_until = None
        db.commit()
    except (Exception) as exc:
        db.rollback()
        job = db.get(Job, job.id)
        job.attempts += 1
        delay = min(getattr(exc, 'retry_after', None) or 60 * (2 ** (job.attempts-1)), 86400)
        job.status = 'FALHOU' if isinstance(exc, PermanentError) or job.attempts >= 3 else 'AGUARDANDO_RETRY'
        job.scheduled_for = now() + timedelta(seconds=delay)
        job.locked_until = None
        job.last_error = str(exc)[:500]
        db.add(Attempt(job_id=job.id, provider=provider, status='FALHA', detail=job.last_error,
            duration_ms=int((time.monotonic()-begin)*1000), correlation_id=job.correlation_id))
        if job.event_id:
            update_event(db, db.get(Event, job.event_id))
        db.commit()
        log.warning('job_failed', extra={'job': job.id, 'correlation': job.correlation_id, 'error': job.last_error})

def work_once(db, ana=None, cdse=None):
    instant = now()
    # Atomic claim. A crashed worker's lease expires and can be claimed again.
    due = db.scalar(select(Job).where(or_(Job.status.in_(['PENDENTE','AGUARDANDO_RETRY']),
        (Job.status == 'EM_EXECUCAO') & (Job.locked_until < instant)), Job.scheduled_for <= instant)
        .order_by(Job.scheduled_for, Job.created_at).limit(1))
    if not due:
        return False
    claimed = db.execute(update(Job).where(Job.id == due.id, or_(Job.status.in_(['PENDENTE','AGUARDANDO_RETRY']),
        (Job.status == 'EM_EXECUCAO') & (Job.locked_until < instant))).values(
        status='EM_EXECUCAO', locked_until=instant + timedelta(minutes=5)))
    db.commit()
    if not claimed.rowcount:
        return False
    run_job(db, db.get(Job, due.id), ana, cdse)
    return True

def reprocess(db, event, actor_id):
    version = (db.scalar(select(func.max(Job.version)).where(Job.event_id == event.id)) or 0) + 1
    create_jobs(db, event, version)
    audit(db, actor_id, 'REPROCESSAMENTO', event.id, {'version': version})
    db.commit()
    return version
