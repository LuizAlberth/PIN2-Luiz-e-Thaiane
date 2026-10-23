from datetime import timedelta
from io import BytesIO
import hashlib
import httpx
import json
import pytest
import tarfile
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, session as api_session
from app.models import User, Config, Reading, Event, Job, Scene, Attempt, now
from app.security import hash_password
from app.service import demo_config, demo_replay, ingest, work_once, reprocess, update_event, enqueue_collection, create_config
from app.adapters import ANAClient, CDSEClient, ProviderError
from app.satellite_demo import load_pair, TRIGGER, BBOX
from app.adapters import verify_png
import app.storage as storage
from app.api import app
from app.pdc import PDCClient, live_station
from app import recent_satellite

def test_dcsc_configuration_and_automatic_trigger(db, monkeypatch):
    session, user = db
    from app import service
    instant = now()
    baseline = [
        {'observed_at': (instant - timedelta(minutes=6)).isoformat(), 'water_level_cm': 245,
         'station_timestamp': None},
        {'observed_at': (instant - timedelta(minutes=1)).isoformat(), 'water_level_cm': 250,
         'station_timestamp': None},
    ]
    readings = [
        {'observed_at': (instant + timedelta(seconds=1)).isoformat(), 'water_level_cm': 250,
         'station_timestamp': None},
        {'observed_at': (instant + timedelta(seconds=2)).isoformat(), 'water_level_cm': 330,
         'station_timestamp': None},
        {'observed_at': (instant + timedelta(seconds=3)).isoformat(), 'water_level_cm': 335,
         'station_timestamp': None},
    ]
    current = {'status': 'ATUALIZADO', 'items': baseline, 'latest': baseline[-1]}
    monkeypatch.setattr(service, 'live_station', lambda client=None: current)
    params = {'source_mode': 'DCSC', 'station_code': 'DCSC-00043',
        'river': 'Rio dos Índios', 'bbox': BBOX, 'threshold_cm': 300,
        'threshold_source': 'Parâmetro experimental do projeto',
        'threshold_valid_from': instant - timedelta(days=1),
        'threshold_responsible': 'Equipe', 'collection_interval_min': 5,
        'baseline_min_days': 7, 'baseline_max_days': 30, 'post_window_days': 15}
    config = create_config(session, user.id, params)
    assert config.version == 1 and config.source_mode == 'DCSC'
    assert total(session, Reading) == 1
    current['items'] = readings[:2]
    current['latest'] = readings[1]
    enqueue_collection(session, config)
    assert work_once(session, ana=object())
    assert total(session, Reading) == 3
    assert total(session, Event) == 0  # One high value does not trigger a DCSC event.
    current['items'] = readings
    current['latest'] = readings[-1]
    collect = session.scalar(select(Job).where(Job.kind == 'COLLECT'))
    collect.scheduled_for = now() - timedelta(seconds=1)
    session.commit()
    assert work_once(session, ana=object())
    assert total(session, Reading) == 4
    assert total(session, Event) == 1
    event = session.scalar(select(Event))
    assert event.snapshot['source_mode'] == 'DCSC'
    assert event.mode == 'AO_VIVO' and event.status == 'AGUARDANDO_IMAGEM'
    assert total(session, Job) == 3
    app.dependency_overrides[api_session] = lambda: session
    try:
        with TestClient(app) as client:
            assert client.get('/api/events').json()['total'] == 1
            detail = client.get(f'/api/events/{event.id}')
            assert detail.status_code == 200 and not detail.json()['has_comparison']
            assert client.get(f'/api/events/{event.id}/scene/BASELINE').status_code == 404
    finally:
        app.dependency_overrides.clear()
    monkeypatch.setattr(service, 'live_station', lambda client=None: {
        'status': 'ATRASADO', 'items': readings})
    with pytest.raises(ValueError, match='duas leituras recentes'):
        create_config(session, user.id, params)

def test_period_search_returns_nearby_dates_only():
    from datetime import date
    def feature(day, tile='T22JFR'):
        stamp = f'{day}T132251'
        return {'id': f'S2A_MSIL2A_{stamp}_N0512_R038_{tile}_{stamp}',
            'properties': {'datetime': f'{day[:4]}-{day[4:6]}-{day[6:]}T13:22:51Z',
                           'eo:cloud_cover': 12.5}}
    class Catalog:
        ready = True
        def search(self, bbox, start, end, collection):
            assert bbox == BBOX and collection == 'sentinel-2-l2a'
            return [feature('20231105'), feature('20231120'), feature('20231120', 'T22JFS')]
    found = recent_satellite.search_period(date(2023, 11, 16), date(2023, 11, 17), Catalog())
    assert len(found['scenes']) == 2
    assert [scene['distance_days'] for scene in found['scenes']] == [3, 11]
    assert all(scene['tile_cloud_percent'] == 12.5 for scene in found['scenes'])

@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(storage, 'LOCAL_DIR', tmp_path)
    with Session(engine) as db:
        user = User(email='tester@example.com', display_name='Teste', password_hash=hash_password('senha-de-teste-segura'))
        db.add(user);db.commit()
        yield db,user
    engine.dispose()

def rows(base, values, quality='VALIDA'):
    return [{'observed_at': base+timedelta(minutes=30*i), 'level_cm': v, 'quality': quality, 'raw': {'teste': True}} for i,v in enumerate(values)]

def total(db, model):
    return db.scalar(select(func.count()).select_from(model))

def test_crossing_quality_idempotence_and_closure(db):
    session,user=db
    config=demo_config(session,user.id)
    start=now().replace(microsecond=0)-timedelta(hours=3)
    data=rows(start,[240,280,310,330,290,280])
    assert ingest(session,config,data[:2],'SIMULACAO')['events_created']==[]
    bad=rows(start+timedelta(minutes=45),[400],'RUIM')
    assert ingest(session,config,bad,'SIMULACAO')['events_created']==[]
    created=ingest(session,config,data[2:],'SIMULACAO')
    assert len(created['events_created'])==1
    assert total(session,Event)==1 and total(session,Job)==2
    assert ingest(session,config,data,'SIMULACAO')['inserted']==0
    event=session.get(Event,created['events_created'][0])
    assert event.ended_at is not None
    assert total(session,Reading)==7

def test_demo_pair_is_published_with_integrity_and_reprocessing(db):
    session,user=db
    config=demo_config(session,user.id)
    result=demo_replay(session,config)
    event_id=result['events_created'][0]
    assert total(session,Scene)==0
    assert work_once(session) and work_once(session)
    event=session.get(Event,event_id)
    assert event.status=='DISPONIVEL' and event.mode=='SIMULACAO'
    assert event.snapshot['historical_context']['event_start']=='2023-11-16'
    assert 'não certifica normalidade' in event.snapshot['historical_context']['imagery_note']
    scenes=session.scalars(select(Scene).where(Scene.event_id==event_id)).all()
    assert {s.role for s in scenes}=={'BASELINE','POST_EVENT'}
    for scene in scenes:
        data=storage.get(scene.image_key)
        assert hashlib.sha256(data).hexdigest()==scene.checksum_sha256
        assert scene.source=='CDSE' and b'PNG' in data[:8]
        assert scene.metadata_json['collection']=='sentinel-2-l2a'
        assert not scene.provider_product_id.startswith('DEMO')
    assert reprocess(session,event,user.id)==2
    assert work_once(session) and work_once(session)
    assert total(session,Scene)==4
    assert session.get(Event,event_id).status=='DISPONIVEL'
    assert total(session,Attempt)==4

def test_partial_publication_after_missing_post_scene(db):
    session,user=db
    config=demo_config(session,user.id)
    event_id=demo_replay(session,config)['events_created'][0]
    assert work_once(session)  # baseline
    after=session.scalar(select(Job).where(Job.event_id==event_id,Job.kind=='POST_EVENT'))
    after.status='FALHOU'
    update_event(session,session.get(Event,event_id));session.commit()
    assert session.get(Event,event_id).status=='PARCIAL'
    assert total(session,Scene)==1

def test_reject_invalid_area_and_unverified_live_station(db):
    session,user=db
    class FakeANA:
        def station(self, code): return {'Latitude':'-27.05','Longitude':'-49.63','Estacao_Nome':'Teste',
                                        'Operando':'1','Tipo_Estacao':'Fluviometrica'}
        def readings(self, code): return []
    params={'station_code':'83372100','river':'Rio Krauel','bbox':[-49.65,-27.07,-49.61,-27.03],
        'threshold_cm':300,'threshold_source':'Documento oficial','threshold_responsible':'Equipe',
        'threshold_valid_from':now(),'collection_interval_min':30,'baseline_min_days':15,
        'baseline_max_days':30,'post_window_days':15,'source_mode':'ANA'}
    with pytest.raises(ValueError,match='sem cota telemétrica válida'):
        create_config(session,user.id,params,FakeANA())
    assert total(session,Config)==0
    class InactiveANA(FakeANA):
        def station(self, code): return {**super().station(code),'Operando':'0'}
        def readings(self, code): return [{'observed_at':now(),'level_cm':310,'quality':'VALIDA'}]
    with pytest.raises(ValueError,match='operante'):
        create_config(session,user.id,params,InactiveANA())
    class ValidANA(InactiveANA):
        def station(self, code): return {**super().station(code),'Operando':'1',
                                        'Tipo_Estacao':'Fluviométrica'}
    assert create_config(session,user.id,params,ValidANA()).source_mode == 'ANA'

def test_demo_does_not_interrupt_active_live_monitor(db):
    session,user=db
    live=demo_config(session,user.id)
    live.source_mode='ANA';session.commit()
    demo=demo_config(session,user.id)
    assert live.active and not demo.active
    assert demo_replay(session,demo)['events_created']

def test_collection_stops_after_three_failures_until_manual_action(db):
    session,user=db
    c=demo_config(session,user.id)
    c.source_mode='ANA';session.commit()
    enqueue_collection(session,c)
    class BadANA:
        def readings(self,*args,**kwargs): raise ProviderError('indisponível')
    job=session.scalar(select(Job).where(Job.kind=='COLLECT'))
    for n in range(3):
        job.scheduled_for=now()-timedelta(seconds=1);session.commit()
        assert work_once(session,ana=BadANA())
    assert job.status=='FALHOU' and job.attempts==3
    enqueue_collection(session,c)
    assert total(session,Job)==1
    assert not work_once(session,ana=BadANA())

def test_ana_normalization_and_token_reuse(monkeypatch):
    monkeypatch.setenv('ANA_IDENTIFICADOR','identificador');monkeypatch.setenv('ANA_SENHA','senha')
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/OAUth/v1'):
            return httpx.Response(200,json={'items':{'tokenautenticacao':'abc'}})
        return httpx.Response(200,json={'status':'OK','items':[
            {'Data_Hora_Medicao':'2026-01-01 10:00:00.0','Cota_Adotada':'305.00','Cota_Adotada_Status':'0'},
            {'Data_Hora_Medicao':'2026-01-01 10:15:00.0','Cota_Adotada':'','Cota_Adotada_Status':'2'}]})
    client=ANAClient(transport=httpx.MockTransport(handler))
    readings=client.readings('83372100')
    client.readings('83372100')
    assert calls.count('/hidrowebservice/EstacoesTelemetricas/OAUth/v1')==1
    assert [r['quality'] for r in readings]==['VALIDA','SEM_COTA']
    assert readings[0]['level_cm']==305
    assert readings[0]['observed_at'].hour==13  # Brasília UTC-3 in January

def test_public_pdc_station_uses_publication_time_and_keeps_source_separate(monkeypatch):
    monkeypatch.setenv('PDC_SUPABASE_ANON_KEY', 'public-test-key')
    published = now().replace(microsecond=0)
    def handler(request):
        assert request.url.params['sta_code'] == 'eq.DCSC-00043'
        assert request.headers['apikey'] == 'public-test-key'
        return httpx.Response(200, json=[
            {'sta_code': 'DCSC-00043', 'river_level': 1.66,
             'created_at': published.isoformat(), 'sta_timestamp': '2026-10-22T19:45:05+00:00'},
            {'sta_code': 'DCSC-00043', 'river_level': None,
             'created_at': published.isoformat(), 'sta_timestamp': None},
        ])
    result = live_station(PDCClient(transport=httpx.MockTransport(handler)))
    assert result['status'] == 'ATUALIZADO'
    assert result['station']['code'] == 'DCSC-00043'
    assert result['latest']['water_level_cm'] == 166
    assert result['latest']['observed_at'] == published.isoformat()
    assert result['provider'] == 'Portal municipal / DCSC'

def test_cdse_candidate_selection_requires_matching_orbit():
    trigger=now()
    bbox=[-49.65,-27.08,-49.61,-27.04]
    def feature(id,day,orbit,west=-49.7):
        return {'id':id,'properties':{'datetime':(trigger+timedelta(days=day)).isoformat(),
            'sar:instrument_mode':'IW','sat:orbit_state':'ascending','sat:relative_orbit':orbit,'s1:polarization':'DV'},
            'geometry':{'type':'Polygon','coordinates':[[[west,-27.1],[-49.6,-27.1],[-49.6,-27.0],[west,-27.0],[west,-27.1]]]}}
    api=CDSEClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,json={})))
    baseline=api.select([feature('b1',-24,42),feature('b2',-20,42)],'BASELINE',trigger,bbox=bbox)
    after=api.select([feature('wrong',1,12),feature('cropped',2,42,-49.63),feature('right',3,42)],
        'POST_EVENT',trigger,baseline,bbox=bbox)
    assert baseline['id']=='b2' and after['id']=='right'
    assert after['orbit_direction']=='ASCENDING'
    assert after['coverage_percent']==100

def test_empty_radar_image_is_not_published():
    from io import BytesIO
    from PIL import Image
    buffer=BytesIO()
    Image.new('RGBA',(512,512),(0,0,0,0)).save(buffer,'PNG')
    with pytest.raises(ProviderError,match='Imagem inválida'):
        verify_png(buffer.getvalue())

def test_real_demo_pair_dates_provenance_and_water_highlight():
    pair = load_pair()
    before, after = pair['BASELINE'][0], pair['POST_EVENT'][0]
    assert TRIGGER-timedelta(days=30) <= before['acquired_at'] <= TRIGGER-timedelta(days=7)
    assert TRIGGER < after['acquired_at'] <= TRIGGER+timedelta(days=30)
    assert before['id'] != after['id']
    for candidate, views in pair.values():
        assert candidate['raw']['local_cloud_percent'] == 0
        assert candidate['raw']['bbox'] == BBOX
        processed = {t['productId'].removesuffix('.SAFE') for t in candidate['raw']['processing']['tiles']}
        assert processed == {candidate['id'].removesuffix('.SAFE')}
        assert views['default'] != views['natural']
        with Image.open(BytesIO(views['default'])) as image:
            blue = sum(1 for p in image.getdata() if p[:3] == (5,148,242))
            assert blue > 1000  # The river is visible in both independently acquired scenes.

@pytest.mark.parametrize('color', [(255,255,255), (250,250,250), (0,0,0), (30,80,40)])
def test_uniform_images_are_rejected(color):
    blank=BytesIO()
    Image.new('RGB',(512,512),color).save(blank,'PNG')
    with pytest.raises(ProviderError, match='Imagem inválida'):
        verify_png(blank.getvalue())

def test_missing_or_corrupt_pair_never_generates_artificial_evidence(tmp_path, monkeypatch):
    import app.satellite_demo as demo
    monkeypatch.setattr(demo,'ASSETS',tmp_path)
    with pytest.raises(ProviderError,match='Par Sentinel ausente'):
        demo.load_pair()


def test_process_confirms_the_catalog_product(monkeypatch):
    monkeypatch.setenv('CDSE_CLIENT_ID', 'local-client')
    monkeypatch.setenv('CDSE_CLIENT_SECRET', 'local-secret')
    candidate = {'id': 'S1A_IW_GRDH_1SDV_EXAMPLE', 'acquired_at': now(),
        'instrument_mode': 'IW', 'polarization': 'DV', 'orbit_direction': 'ASCENDING'}
    image_buffer = BytesIO()
    image = Image.new('RGBA', (512, 512), (100, 100, 100, 255))
    ImageDraw.Draw(image).rectangle((0,0,256,256),fill=(40,40,40,255))
    image.save(image_buffer, 'PNG')

    def response_for(product_id):
        archive_buffer = BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode='w') as archive:
            for name, content in [('default.png', image_buffer.getvalue()),
                                  ('userdata.json', json.dumps({'productIds': [product_id]}).encode())]:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, BytesIO(content))
        return archive_buffer.getvalue()

    returned = candidate['id']
    def handler(request):
        if request.url.path.endswith('/token'):
            return httpx.Response(200, json={'access_token': 'test-token', 'expires_in': 3600})
        body = json.loads(request.content)
        assert request.headers['accept'] == 'application/x-tar'
        assert body['output']['responses'][1]['identifier'] == 'userdata'
        assert 'scenes.orbits' in body['evalscript']
        return httpx.Response(200, content=response_for(returned), headers={'Content-Type': 'application/x-tar'})

    client = CDSEClient(transport=httpx.MockTransport(handler))
    assert client.process([-49.65, -27.08, -49.61, -27.04], candidate) == image_buffer.getvalue()
    returned = 'S1A_DIFFERENT_PRODUCT'
    with pytest.raises(ProviderError, match='não corresponde'):
        client.process([-49.65, -27.08, -49.61, -27.04], candidate)

def test_public_access_control_and_demo_api(db):
    session,user=db
    app.dependency_overrides[api_session]=lambda: session
    try:
        with TestClient(app) as client:
            official = client.get('/api/status').json()
            assert official['official_station']['code'] == 'DCSC-00043'
            assert official['official_station']['url'].endswith('/estacao/DCSC-00043')
            assert official['reading'] is None
            assert client.post('/api/admin/demo').status_code==401
            assert client.post('/api/auth/login',json={'email':user.email,'password':'wrong'}).status_code==401
            token=client.post('/api/auth/login',json={'email':user.email,'password':'senha-de-teste-segura'}).json()['token']
            headers={'Authorization':f'Bearer {token}'}
            created=client.post('/api/admin/demo',headers=headers).json()
            active = client.get('/api/status').json()
            assert active['official_station']['code'] == 'DCSC-00043'
            assert active['config']['station_code'].startswith('DEMO-')
            assert active['reading']['mode'] == 'SIMULACAO'
            event_id=created['replay']['events_created'][0]
            assert client.get(f'/api/events/{event_id}').status_code==404
            assert client.get(f'/api/events/{event_id}',headers=headers).status_code==200
            work_once(session);work_once(session)
            assert client.get(f'/api/events/{event_id}').status_code==200
            assert client.get('/api/events').json()['total']==0
            assert client.get('/api/events?mode=SIMULACAO').json()['total']==1
            assert client.get(f'/api/events/{event_id}/scene/BASELINE').headers['content-type']=='image/png'
            natural=client.get(f'/api/events/{event_id}/scene/BASELINE?view=natural&version=1')
            assert natural.status_code==200
            assert natural.content!=client.get(f'/api/events/{event_id}/scene/BASELINE').content
            assert client.get(f'/api/events/{event_id}/scene/BASELINE?version=99').status_code==404
            scene=session.scalar(select(Scene).where(Scene.event_id==event_id,Scene.role=='BASELINE'))
            (storage.LOCAL_DIR/scene.image_key).write_bytes(b'corrompido')
            assert client.get(f'/api/events/{event_id}/scene/BASELINE').status_code==503
    finally:
        app.dependency_overrides.clear()

def test_password_only_admin_login(db, monkeypatch):
    session, user = db
    monkeypatch.setenv('ADMIN_EMAIL', user.email)
    user.password_hash = hash_password('senha-local-de-teste')
    session.commit()
    app.dependency_overrides[api_session] = lambda: session
    try:
        with TestClient(app) as client:
            assert client.post('/api/auth/admin', json={'password':'wrong'}).status_code == 401
            result = client.post('/api/auth/admin', json={'password':'senha-local-de-teste'})
            assert result.status_code == 200
            assert client.get('/api/auth/me', headers={'Authorization':'Bearer '+result.json()['token']}).status_code == 200
            user.active = False
            session.commit()
            assert client.post('/api/auth/admin', json={'password':'senha-local-de-teste'}).status_code == 401
    finally:
        app.dependency_overrides.clear()

def test_recent_pair_skips_cloudy_pass_and_preserves_two_dates(monkeypatch):
    days = [(now() - timedelta(days=offset)).date().isoformat() for offset in (2, 7, 12)]
    features = [{'id': f'S2A_MSIL2A_{day.replace("-", "")}T132251_R038_T22JFR_{day.replace("-", "")}T230000',
        'properties': {'datetime': day + 'T13:30:00Z', 'eo:cloud_cover': cloud}}
        for day, cloud in zip(days, [89.9, 3.0, 2.0])]
    class FakeClient:
        ready = True
        def search(self, *_args, **_kwargs): return features
    monkeypatch.setattr(recent_satellite, 'load_latest', lambda: None)
    monkeypatch.setattr(recent_satellite, '_scene', lambda _client, feature: None if feature is features[0]
        else {'product_id': feature['id'], 'acquired_at': feature['properties']['datetime'],
            'cloud_percent': 0.0, 'tile': 'T22JFR', 'orbit': 'R038', 'images': {}})
    monkeypatch.setattr(recent_satellite, '_rejected_preview', lambda *_args: {'product_id': features[0]['id'],
        'acquired_at': features[0]['properties']['datetime'], 'obscured_percent': 100.0,
        'image': {'key': 'rejected.png', 'sha256': 'checksum'}})
    saved = {}
    monkeypatch.setattr(recent_satellite, 'put', lambda key, data, **_kwargs: saved.update({key: data}) or 'checksum')
    pair = recent_satellite.refresh_latest(FakeClient())
    assert [scene['acquired_at'][:10] for scene in pair['scenes']] == [days[2], days[1]]
    assert pair['latest_pass']['acquired_at'][:10] == days[0]
    assert pair['rejected']['obscured_percent'] == 100.0
    assert json.loads(saved[recent_satellite.MANIFEST_KEY])['scenes'] == pair['scenes']

def test_river_corridor_rejects_cloud_even_when_area_is_mostly_clear():
    quality = Image.new('L', (256, 256), 4)
    corridor = recent_satellite._river_mask(quality.size)
    # A cloud over one reach hides the river while most of the wider image remains clear.
    for y in range(96, 150):
        for x in range(100, 180):
            if corridor.getpixel((x, y)):
                quality.putpixel((x, y), 9)
    out = BytesIO(); quality.save(out, format='PNG')
    assert recent_satellite._quality(out.getvalue()) < 10
    assert recent_satellite._river_obscured(out.getvalue()) > 10
    assert recent_satellite._river_visible(load_pair()['BASELINE'][1]['default'])

def test_historical_pair_is_public_without_a_demo_event(db):
    session, _ = db
    app.dependency_overrides[api_session] = lambda: session
    try:
        with TestClient(app) as client:
            metadata = client.get('/api/historical/2023')
            assert metadata.status_code == 200
            assert metadata.json()['scenes']['BASELINE']['acquired_at'][:10] == '2023-11-05'
            image = client.get('/api/historical/2023/image/POST_EVENT?view=default')
            assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
    finally:
        app.dependency_overrides.clear()
