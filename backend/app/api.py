from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import hashlib
import os
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session
from .db import initialize, session
from .models import User, Config, Reading, Event, Job, Scene, Attempt, Audit, now
from .security import hash_password, verify_password, sign, current_admin
from .service import active_config, create_config, demo_config, demo_replay, ingest, reprocess, displayed_scenes, enqueue_collection, has_recent_valid_level, PUBLIC, utc, work_once
from .adapters import ANAClient, CDSEClient, ProviderError, parsed_time
from .storage import get
from .station_reference import OFFICIAL_STATION
from .pdc import PDCClient, live_station
from .recent_satellite import load_latest, search_period, load_search_preview, create_search_preview, search_bbox
from .satellite_demo import load_pair, HISTORICAL_CONTEXT
from .image_export import presentation_png

def exported_png(blob: bytes, scale: int) -> bytes:
    if scale not in (1, 2, 4):
        raise HTTPException(422, 'Ampliação deve ser 1×, 2× ou 4×')
    return presentation_png(blob, scale)

@asynccontextmanager
async def lifespan(app):
    initialize()
    email = os.getenv('ADMIN_EMAIL', '').strip().lower()
    password = os.getenv('ADMIN_PASSWORD', '')
    if password.startswith('replace-with') or os.getenv('APP_SECRET', '').startswith('replace-with'):
        raise RuntimeError('Substitua as credenciais de exemplo no arquivo .env')
    if os.getenv('APP_SECRET') and len(os.getenv('APP_SECRET')) < 32:
        raise RuntimeError('APP_SECRET deve ter ao menos 32 caracteres')
    if os.getenv('PUBLIC_DEPLOYMENT') == '1' and (len(password) < 16 or len(os.getenv('APP_SECRET', '')) < 32):
        raise RuntimeError('Publicação exige ADMIN_PASSWORD com ao menos 16 caracteres e APP_SECRET com ao menos 32')
    from .db import SessionLocal
    with SessionLocal() as db:
        if email and password:
            if len(password) < 4:
                raise RuntimeError('ADMIN_PASSWORD deve ter ao menos 4 caracteres')
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                db.add(User(email=email, display_name='Administrador', password_hash=hash_password(password)))
            elif not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
            db.commit()
    yield

app = FastAPI(title='DSS Mancha de Inundação', version='0.1.0', lifespan=lifespan,
              docs_url='/api/docs', openapi_url='/api/openapi.json')
app.add_middleware(CORSMiddleware,
    allow_origins=[os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')],
    allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Authorization','Content-Type'])

class Login(BaseModel):
    email: str
    password: str

class PasswordLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)

class ConfigIn(BaseModel):
    station_code: str = Field(min_length=5, max_length=30)
    river: str = 'Rio Krauel'
    bbox: list[float] = Field(min_length=4, max_length=4)
    threshold_cm: float = Field(gt=0)
    threshold_source: str = Field(min_length=5)
    threshold_valid_from: datetime
    threshold_responsible: str = Field(min_length=2)
    collection_interval_min: int = Field(default=30, ge=5, le=1440)
    baseline_min_days: int = Field(default=15, ge=1, le=89)
    baseline_max_days: int = Field(default=30, ge=2, le=90)
    post_window_days: int = Field(default=15, ge=1, le=30)
    source_mode: Literal['ANA', 'DCSC'] = 'DCSC'

class ReplayIn(BaseModel):
    date: datetime | None = None


def iso(dt):
    return utc(dt).isoformat() if dt else None

def config_json(c):
    if not c: return None
    return {'id': c.id, 'version': c.version, 'station_code': c.station_code,
        'station_name': c.station_name, 'river': c.river, 'station_lat': c.station_lat,
        'station_lon': c.station_lon, 'bbox': c.bbox, 'threshold_cm': c.threshold_cm,
        'threshold_source': c.threshold_source, 'threshold_valid_from': iso(c.threshold_valid_from),
        'threshold_responsible': c.threshold_responsible, 'collection_interval_min': c.collection_interval_min,
        'baseline_min_days': c.baseline_min_days, 'baseline_max_days': c.baseline_max_days,
        'post_window_days': c.post_window_days, 'source_mode': c.source_mode,
        'active': c.active, 'valid_from': iso(c.valid_from), 'valid_to': iso(c.valid_to)}

def reading_json(r):
    if not r: return None
    return {'id': r.id, 'observed_at': iso(r.observed_at), 'water_level_cm': r.water_level_cm,
        'quality_status': r.quality_status, 'mode': r.mode, 'collected_at': iso(r.collected_at)}

def event_json(db, e, detailed=False):
    result = {'id': e.id, 'mode': e.mode, 'status': e.status, 'started_at': iso(e.started_at),
        'ended_at': iso(e.ended_at), 'trigger_level_cm': e.trigger_level_cm,
        'station_name': e.snapshot['station_name'], 'station_code': e.snapshot['station_code'],
        'threshold_cm': e.snapshot['threshold_cm'], 'config_version': e.snapshot['config_version'],
        'source_mode': e.snapshot['source_mode'],
        'scenario_title': e.snapshot.get('historical_context', {}).get('title'),
        'has_comparison': e.status in PUBLIC, 'failure_summary': e.failure_summary}
    if detailed:
        before, after = displayed_scenes(db, e.id)
        def scene_json(s):
            return None if not s else {'id': s.id, 'role': s.role, 'version': s.version,
                'provider_product_id': s.provider_product_id, 'acquired_at': iso(s.acquired_at),
                'instrument_mode': s.instrument_mode, 'orbit_direction': s.orbit_direction,
                'relative_orbit': s.relative_orbit, 'polarization': s.polarization,
                'selection_reason': s.selection_reason, 'compatibility_status': s.compatibility_status,
                'source': s.source, 'width': s.width, 'height': s.height, 'checksum_sha256': s.checksum_sha256,
                'coverage_percent': s.metadata_json.get('coverage_percent'),
                'collection': s.metadata_json.get('collection', 'sentinel-1-grd'),
                'visualization': s.metadata_json.get('visualization'),
                'has_natural': bool(s.metadata_json.get('natural_key')),
                'label': s.metadata_json.get('label'),
                'local_cloud_percent': s.metadata_json.get('local_cloud_percent'),
                'image_url': f'/api/events/{e.id}/scene/{s.role}?version={s.version}'}
        result.update(snapshot=e.snapshot, scenes={'BASELINE': scene_json(before), 'POST_EVENT': scene_json(after)},
            trigger_reading=reading_json(db.get(Reading, e.trigger_reading_id)),
            jobs=[{'id': j.id, 'kind': j.kind, 'version': j.version, 'status': j.status,
                'attempts': j.attempts, 'last_error': j.last_error, 'scheduled_for': iso(j.scheduled_for)}
                for j in db.scalars(select(Job).where(Job.event_id == e.id).order_by(Job.created_at)).all()])
    return result

def optionally_admin(req, db):
    from .security import current_admin
    from fastapi.security import HTTPAuthorizationCredentials
    header = req.headers.get('authorization', '')
    if not header.startswith('Bearer '): return False
    try:
        return bool(current_admin(HTTPAuthorizationCredentials(scheme='Bearer', credentials=header[7:]), db))
    except HTTPException:
        return False

def allowed(e, admin):
    return admin or e.status in PUBLIC or (e.mode == 'AO_VIVO' and e.snapshot.get('source_mode') == 'DCSC')

@app.get('/api/health')
def health():
    return {'status': 'ok', 'time': iso(now())}

@app.post('/api/auth/login')
def login(payload: Login, db: Session = Depends(session)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Credenciais inválidas')
    return {'token': sign(user.id), 'user': {'email': user.email, 'display_name': user.display_name}}

@app.get('/api/auth/me')
def me(user: User = Depends(current_admin)):
    return {'email': user.email, 'display_name': user.display_name}

@app.post('/api/auth/admin')
def password_login(payload: PasswordLogin, db: Session = Depends(session)):
    email = os.getenv('ADMIN_EMAIL', '').strip().lower()
    user = db.scalar(select(User).where(User.email == email)) if email else None
    if not user or not user.active or user.role != 'ADMIN' or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Senha inválida')
    return {'token': sign(user.id), 'user': {'email': user.email, 'display_name': user.display_name}}

@app.get('/api/status')
def status(db: Session = Depends(session)):
    c = active_config(db)
    if not c:
        return {'config': None, 'reading': None, 'data_status': 'INDISPONIVEL',
            'official_station': OFFICIAL_STATION, 'updated_at': iso(now()), 'recent_events': []}
    mode = 'SIMULACAO' if c.source_mode == 'DEMO' else 'AO_VIVO'
    reading = db.scalar(select(Reading).where(Reading.station_code == c.station_code, Reading.mode == mode,
        Reading.quality_status == 'VALIDA').order_by(Reading.observed_at.desc()).limit(1))
    if reading:
        hours = (now() - utc(reading.observed_at)).total_seconds() / 3600
        state = 'SIMULADA' if c.source_mode == 'DEMO' else 'ATUALIZADO' if hours <= max(2, c.collection_interval_min / 30) else 'ATRASADO'
    else:
        state = 'INDISPONIVEL'
    events = db.scalars(select(Event).where(Event.status.in_(PUBLIC), Event.mode == mode)
        .order_by(Event.created_at.desc()).limit(4)).all()
    collection = db.scalar(select(Job).where(Job.kind == 'COLLECT').order_by(Job.created_at.desc()).limit(1))
    integration_status = ('SIMULADA' if c.source_mode == 'DEMO' else
        'SEM_CREDENCIAIS' if c.source_mode == 'ANA' and not ANAClient().ready else
        'SEM_CREDENCIAIS' if c.source_mode == 'DCSC' and not PDCClient().ready else
        'FALHA' if collection and collection.status == 'FALHOU' else
        'AGUARDANDO_DADOS' if not reading else 'DISPONIVEL')
    return {'config': config_json(c), 'reading': reading_json(reading), 'data_status': state,
        'integration_status': integration_status, 'official_station': OFFICIAL_STATION,
        'updated_at': iso(now()),
        'recent_events': [event_json(db, e) for e in events]}

@app.get('/api/stations/dcsc-00043')
def dcsc_station():
    try:
        return live_station()
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get('/api/satellite/latest')
def latest_satellite():
    manifest = load_latest()
    if not manifest:
        return {'available': False, 'reason': 'Aguardando duas passagens Sentinel-2 com baixa nebulosidade na área do rio.'}
    return {'available': True, 'provider': manifest['provider'], 'collection': manifest['collection'],
        'bbox': manifest['bbox'], 'checked_at': manifest['checked_at'],
        'latest_pass': manifest.get('latest_pass'),
        'rejected': ({'acquired_at': manifest['rejected']['acquired_at'],
            'obscured_percent': manifest['rejected']['obscured_percent'],
            'river_obscured_percent': manifest['rejected'].get('river_obscured_percent'),
            'image_url': '/api/satellite/latest/rejected'} if manifest.get('rejected') else None),
        'scenes': [{'product_id': scene['product_id'], 'acquired_at': scene['acquired_at'],
            'cloud_percent': scene['cloud_percent'], 'river_obscured_percent': scene.get('river_obscured_percent'),
            'tile': scene['tile'], 'orbit': scene['orbit'],
            'images': {view: f'/api/satellite/latest/image/{index}?view={view}' for view in ('default', 'natural')}}
            for index, scene in enumerate(manifest['scenes'])]}

def chosen_bbox(lat: float | None, lon: float | None):
    try:
        return search_bbox(lat, lon)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/satellite/search')
def satellite_search(start: date, end: date, lat: float | None = None, lon: float | None = None):
    if end < start or (end - start).days > 60 or start.year < 2017 or end > now().date():
        raise HTTPException(422, 'Escolha um período válido de até 60 dias, entre 2017 e hoje')
    try:
        return search_period(start, end, bbox=chosen_bbox(lat, lon))
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get('/api/satellite/search/preview/{product_id}')
def satellite_search_preview(product_id: str, view: Literal['default', 'natural'] = 'default',
                             scale: int = 1, lat: float | None = None, lon: float | None = None):
    try:
        bbox = chosen_bbox(lat, lon)
        preview = load_search_preview(product_id, bbox) or create_search_preview(product_id, bbox=bbox)
        if not preview or preview.get('unavailable'):
            raise HTTPException(404, 'Passagem encoberta no recorte ou rio não visível')
        record = preview['images'][view]
        blob = get(record['key'])
        if hashlib.sha256(blob).hexdigest() != record['sha256']:
            raise HTTPException(503, 'Arquivo corrompido')
        return Response(exported_png(blob, scale), media_type='image/png',
            headers={'Cache-Control': 'public, max-age=86400'})
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get('/api/satellite/latest/image/{index}')
def latest_satellite_image(index: int, view: Literal['default', 'natural'] = 'default',
                           scale: int = 1):
    manifest = load_latest()
    if not manifest or index not in (0, 1):
        raise HTTPException(404, 'Imagem não disponível')
    record = manifest['scenes'][index]['images'][view]
    image = get(record['key'])
    if hashlib.sha256(image).hexdigest() != record['sha256']:
        raise HTTPException(503, 'Checksum da imagem divergente')
    return Response(exported_png(image, scale), media_type='image/png',
        headers={'Cache-Control': 'public, max-age=300'})

@app.get('/api/satellite/latest/rejected')
def latest_rejected_image():
    manifest = load_latest()
    if not manifest or not manifest.get('rejected'):
        raise HTTPException(404, 'Prévia encoberta não disponível')
    record = manifest['rejected']['image']
    try:
        image = get(record['key'])
    except Exception as exc:
        raise HTTPException(503, 'Prévia encoberta indisponível') from exc
    if hashlib.sha256(image).hexdigest() != record['sha256']:
        raise HTTPException(503, 'Checksum da prévia divergente')
    return Response(image, media_type='image/png', headers={'Cache-Control': 'public, max-age=300'})

@app.get('/api/historical/2023')
def historical_2023():
    try:
        pair = load_pair()
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {'mode': 'SIMULACAO', 'snapshot': {'historical_context': HISTORICAL_CONTEXT},
        'scenes': {role: {'acquired_at': iso(candidate['acquired_at']), 'has_natural': True,
            'image_url': f'/api/historical/2023/image/{role}'}
            for role, (candidate, _) in pair.items()}}

@app.get('/api/historical/2023/image/{role}')
def historical_2023_image(role: Literal['BASELINE', 'POST_EVENT'],
                          view: Literal['default', 'natural'] = 'default', scale: int = 1):
    try:
        image = load_pair()[role][1][view]
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(exported_png(image, scale), media_type='image/png',
        headers={'Cache-Control': 'public, max-age=86400'})

@app.get('/api/events')
def events(mode: Literal['AO_VIVO','SIMULACAO'] = 'AO_VIVO', page: int = 1, db: Session = Depends(session)):
    page = max(1, page)
    visible = or_(Event.status.in_(PUBLIC), and_(Event.mode == 'AO_VIVO', Config.source_mode == 'DCSC'))
    q = select(Event).join(Config, Event.config_id == Config.id).where(Event.mode == mode, visible)
    total = db.scalar(select(func.count()).select_from(Event).join(Config, Event.config_id == Config.id)
        .where(Event.mode == mode, visible))
    items = db.scalars(q.order_by(Event.created_at.desc()).offset((page-1)*20).limit(20)).all()
    return {'items': [event_json(db, e) for e in items], 'total': total, 'page': page}

@app.get('/api/readings')
def recent_readings(db: Session = Depends(session)):
    c = active_config(db)
    if not c:
        return {'items': []}
    mode = 'SIMULACAO' if c.source_mode == 'DEMO' else 'AO_VIVO'
    items = db.scalars(select(Reading).where(Reading.station_code == c.station_code,
        Reading.mode == mode, Reading.quality_status == 'VALIDA')
        .order_by(Reading.observed_at.desc()).limit(48)).all()
    return {'items': [reading_json(r) for r in items]}

@app.get('/api/events/{event_id}')
def event_detail(event_id: str, req: Request, db: Session = Depends(session)):
    e = db.get(Event, event_id)
    if not e or not allowed(e, optionally_admin(req, db)):
        raise HTTPException(404, 'Evento não encontrado')
    return event_json(db, e, True)

@app.get('/api/events/{event_id}/scene/{role}')
def scene_image(event_id: str, role: Literal['BASELINE','POST_EVENT'], req: Request,
                view: Literal['default', 'natural'] = 'default', scale: int = 1,
                version: int | None = None,
                db: Session = Depends(session)):
    e = db.get(Event, event_id)
    if not e or not allowed(e, optionally_admin(req, db)):
        raise HTTPException(404, 'Imagem não encontrada')
    before, after = displayed_scenes(db, event_id)
    scene = before if role == 'BASELINE' else after
    if version is not None:
        scene = db.scalar(select(Scene).where(Scene.event_id == event_id, Scene.role == role, Scene.version == version))
    if not scene:
        raise HTTPException(404, 'Imagem pendente')
    key, checksum = scene.image_key, scene.checksum_sha256
    if view == 'natural':
        key, checksum = scene.metadata_json.get('natural_key'), scene.metadata_json.get('natural_checksum')
        if not key or not checksum:
            raise HTTPException(404, 'Cor natural indisponível para esta cena')
    try:
        blob = get(key)
    except (FileNotFoundError, OSError, Exception) as exc:
        raise HTTPException(503, 'Arquivo indisponível') from exc
    if hashlib.sha256(blob).hexdigest() != checksum:
        raise HTTPException(503, 'Arquivo corrompido')
    return Response(content=exported_png(blob, scale), media_type='image/png',
        headers={'Cache-Control': 'private, max-age=60'})

@app.get('/api/admin/configs')
def configs(db: Session = Depends(session), user: User = Depends(current_admin)):
    return [config_json(c) for c in db.scalars(select(Config).order_by(Config.version.desc())).all()]

@app.post('/api/admin/configs')
def activate_config(payload: ConfigIn, db: Session = Depends(session), user: User = Depends(current_admin)):
    try:
        config = create_config(db, user.id, payload.model_dump())
        enqueue_collection(db, config)
        return config_json(config)
    except (ValueError, ProviderError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc

@app.get('/api/admin/station/{code}')
def inspect_station(code: str, user: User = Depends(current_admin)):
    try:
        ana = ANAClient()
        station = ana.station(code)
        readings = ana.readings(code)
        return {'station': station, 'recent_readings': len(readings),
            'has_level': has_recent_valid_level(readings)}
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.post('/api/admin/demo')
def create_demo(db: Session = Depends(session), user: User = Depends(current_admin)):
    c = demo_config(db, user.id)
    result = demo_replay(db, c)
    return {'config': config_json(c), 'replay': result}

@app.post('/api/admin/replay')
def replay(payload: ReplayIn, db: Session = Depends(session), user: User = Depends(current_admin)):
    c = active_config(db)
    if not c: raise HTTPException(422, 'Ative uma configuração primeiro')
    try:
        if c.source_mode == 'DEMO':
            result = demo_replay(db, c)
        else:
            if c.source_mode != 'ANA':
                raise ValueError('Replay ANA indisponível para a configuração DCSC')
            if not payload.date: raise ValueError('Informe a data histórica para consulta ANA')
            if parsed_time(payload.date) < utc(c.threshold_valid_from):
                raise ValueError('A data histórica é anterior à validade da cota configurada')
            readings = ANAClient().readings(c.station_code, parsed_time(payload.date), 'DIAS_30')
            if not readings: raise ValueError('Nenhuma leitura retornada pela ANA no período')
            result = ingest(db, c, readings, 'SIMULACAO')
        from .service import audit
        audit(db, user.id, 'REPLAY', c.id, result)
        db.commit()
        return result
    except (ProviderError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc

@app.post('/api/admin/collect')
def collect(db: Session = Depends(session), user: User = Depends(current_admin)):
    c = active_config(db)
    if not c or c.source_mode not in ('ANA', 'DCSC'): raise HTTPException(422, 'Configure uma integração de coleta')
    j = db.scalar(select(Job).where(Job.kind == 'COLLECT', Job.status.in_(['PENDENTE','AGUARDANDO_RETRY'])).limit(1))
    if j:
        j.scheduled_for = now()
        j.status = 'PENDENTE'
        j.attempts = 0
    else:
        from .models import uid
        j = Job(kind='COLLECT', scheduled_for=now(), correlation_id=uid())
        db.add(j)
    from .service import audit
    audit(db, user.id, 'COLETA_SOLICITADA', c.id)
    db.commit()
    return {'job_id': j.id}

@app.get('/api/admin/events')
def admin_events(db: Session = Depends(session), user: User = Depends(current_admin)):
    items = db.scalars(select(Event).order_by(Event.created_at.desc()).limit(100)).all()
    return [event_json(db, e) for e in items]

@app.post('/api/admin/events/{event_id}/reprocess')
def reprocess_event(event_id: str, db: Session = Depends(session), user: User = Depends(current_admin)):
    e = db.get(Event, event_id)
    if not e: raise HTTPException(404, 'Evento não encontrado')
    return {'version': reprocess(db, e, user.id)}

@app.get('/api/admin/jobs')
def jobs(db: Session = Depends(session), user: User = Depends(current_admin)):
    items = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
    return [{'id': j.id, 'event_id': j.event_id, 'kind': j.kind, 'status': j.status,
        'version': j.version, 'attempts': j.attempts, 'scheduled_for': iso(j.scheduled_for),
        'last_error': j.last_error} for j in items]

@app.get('/api/admin/audit')
def audits(db: Session = Depends(session), user: User = Depends(current_admin)):
    items = db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100)).all()
    return [{'action': a.action, 'entity_id': a.entity_id,
        'actor': db.get(User, a.actor_id).email if db.get(User, a.actor_id) else a.actor_id,
        'details': a.details,
        'created_at': iso(a.created_at)} for a in items]

@app.get('/api/admin/integrations')
def integrations(user: User = Depends(current_admin)):
    satellite = load_latest()
    return {'ana_configured': ANAClient().ready, 'cdse_configured': CDSEClient().ready,
        'dcsc_configured': PDCClient().ready,
        'satellite_checked_at': satellite['checked_at'] if satellite else None,
        'object_storage': 'MinIO / S3' if os.getenv('S3_ENDPOINT') else 'Local'}
