"""Real, reproducible Sentinel-2 evidence; only the hydrometric series is simulated."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import json
import tarfile
import httpx
from .adapters import CDSEClient, ProviderError, checked, parsed_time, verify_png

ASSETS = Path(__file__).resolve().parent / 'assets' / 'sentinel-2023'
BBOX = [-49.632, -27.048, -49.610, -27.0285]
TRIGGER = datetime(2023, 11, 16, 15, tzinfo=timezone.utc)
DATES = {'BASELINE': '2023-11-05', 'POST_EVENT': '2023-12-15'}
HISTORICAL_CONTEXT = {
    'id': 'getulio-novembro-2023', 'title': 'Enchentes de novembro de 2023',
    'event_start': '2023-11-16', 'event_end': '2023-11-17',
    'summary': 'O TJSC registra a persistência da emergência por inundação em Presidente Getúlio e a suspensão do atendimento em 16 e 17 de novembro de 2023.',
    'imagery_note': '05/11 é uma referência anterior e 15/12 uma referência posterior com o rio visível. Nenhuma dessas cenas captura o pico da enchente. A imagem posterior não certifica normalidade hidrológica: não há medições ANA nesta simulação.',
    'cloud_note': 'No catálogo Copernicus, as passagens de 15/11 e 20/11/2023 têm 100% de nuvens no tile T22JFR. Essas cenas não foram usadas como evidência visual da cheia.',
    'labels': {'BASELINE': 'Referência antes da enchente', 'POST_EVENT': 'Referência após a enchente'},
    'timeline': [
        {'date': '2023-11-05', 'title': 'Antes da enchente', 'detail': 'Imagem real do Sentinel-2', 'kind': 'reference'},
        {'date': '2023-11-16', 'end': '2023-11-17', 'title': 'Enchente documentada', 'detail': 'Registro oficial; níveis simulados', 'kind': 'flood'},
        {'date': '2023-12-15', 'title': 'Referência posterior', 'detail': 'Imagem real; cota ANA não aferida', 'kind': 'reference'}],
    'sources': [
        {'title': 'TJSC · Portaria 115 de 16/11/2023', 'url': 'https://www2.tjsc.jus.br/web/tjsc/atos-normativos-e-suspensao-de-prazos-e-expediente/presidente-getulio/portaria_2023115.pdf'},
        {'title': 'Defesa Civil SC · Registro de emergência por inundação em 04/10/2023', 'url': 'https://estado.sc.gov.br/wp-content/uploads/sites/3/2023/10/emergencia-12.10.pdf'}],
}
VISUALIZATION = 'Cor natural (ganho 3,5); água em azul por SCL=6 ou NDWI>0 e NIR<0,15, excluindo sombra/nuvem. Resolução nativa 10–20 m.'

OPTICAL_SCRIPT = '''//VERSION=3
function setup() {
  return {input: ["B02", "B03", "B04", "B08", "SCL", "dataMask"],
    mosaicking: Mosaicking.TILE,
    output: [{id:"default", bands:4}, {id:"natural", bands:4},
      {id:"quality", bands:1, sampleType:"UINT8"}]};
}
function evaluatePixel(samples) {
  let s = samples[0];
  if (!s) return {default:[0,0,0,0], natural:[0,0,0,0], quality:[0]};
  let ndwi = (s.B03-s.B08)/(s.B03+s.B08+0.00001);
  let water = s.SCL === 6 || (ndwi > 0 && s.B08 < 0.15 && s.SCL !== 3 && s.SCL < 7);
  let rgb = [3.5*s.B04, 3.5*s.B03, 3.5*s.B02];
  return {default:[...(water ? [0.02,0.58,0.95] : rgb),s.dataMask], natural:[...rgb,s.dataMask], quality:[s.SCL]};
}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = {tiles: scenes.tiles.map(t => ({productId:t.sentinel2ProductId,
    date:t.date, dataPath:t.dataPath, cloudCoverage:t.cloudCoverage}))};
}'''

def load_pair():
    try:
        manifest = json.loads((ASSETS / 'manifest.json').read_text())
        if manifest['bbox'] != BBOX:
            raise ValueError('Área divergente')
        result = {}
        for role in DATES:
            entry = manifest['scenes'][role]
            if not entry['feature']['properties']['datetime'].startswith(DATES[role]):
                raise ValueError('Data divergente')
            if entry['local_cloud_percent'] > 10:
                raise ValueError('Nuvens em excesso na área de comparação')
            blobs = {}
            for view in ('default', 'natural'):
                blob = (ASSETS / f'{role.lower()}-{view}.png').read_bytes()
                if hashlib.sha256(blob).hexdigest() != entry['checksums'][view]:
                    raise ValueError('Checksum divergente')
                if verify_png(blob) != (1024, 1024):
                    raise ValueError('Dimensão divergente')
                blobs[view] = blob
            candidate = {'id': entry['feature']['id'],
                'acquired_at': parsed_time(entry['feature']['properties']['datetime']),
                'instrument_mode': 'MSI', 'orbit_direction': 'DESCENDING',
                'relative_orbit': 38, 'polarization': 'ÓPTICO',
                'raw': {**entry, 'collection': 'sentinel-2-l2a', 'bbox': BBOX,
                    'label': HISTORICAL_CONTEXT['labels'][role],
                    'visualization': VISUALIZATION, 'hydrometry_simulated': True}}
            result[role] = (candidate, blobs)
        return result
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise ProviderError('Par Sentinel ausente ou inválido. Execute: .venv/bin/python scripts/prepare_sentinel_demo.py') from exc

def prepare_pair(client=None):
    client = client or CDSEClient()
    entries, images = {}, {}
    for role, day in DATES.items():
        start = parsed_time(day + 'T00:00:00Z')
        features = client.search(BBOX, start, start + timedelta(days=1), collection='sentinel-2-l2a')
        features = [f for f in features if '_T22JFR_' in f['id'] and
                    f['properties'].get('eo:cloud_cover', 100) < 10]
        if not features:
            raise ProviderError(f'Nenhuma cena clara Sentinel-2 em {day}')
        feature = min(features, key=lambda f: f['properties']['eo:cloud_cover'])
        payload = {'input': {'bounds': {'bbox': BBOX,
            'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}},
            'data': [{'type': 'sentinel-2-l2a', 'dataFilter': {'timeRange': {
                'from': start.isoformat(), 'to': (start + timedelta(days=1)).isoformat()},
                'maxCloudCoverage': 10}, 'processing': {'upsampling': 'NEAREST'}}]},
            'output': {'width': 1024, 'height': 1024, 'responses': [
                {'identifier': 'default', 'format': {'type': 'image/png'}},
                {'identifier': 'natural', 'format': {'type': 'image/png'}},
                {'identifier': 'quality', 'format': {'type': 'image/png'}},
                {'identifier': 'userdata', 'format': {'type': 'application/json'}}]},
            'evalscript': OPTICAL_SCRIPT}
        try:
            response = checked(client.http.post('https://sh.dataspace.copernicus.eu/api/v1/process',
                json=payload, headers={**client.headers(), 'Accept': 'application/x-tar'}))
        except httpx.RequestError as exc:
            raise ProviderError('Falha ao obter cenas Sentinel-2') from exc
        with tarfile.open(fileobj=BytesIO(response.content), mode='r:*') as archive:
            metadata = json.load(archive.extractfile('userdata.json'))
            from PIL import Image
            with Image.open(BytesIO(archive.extractfile('quality.png').read())) as quality:
                hist = quality.histogram()
                cloud_percent = round(sum(hist[i] for i in (8, 9, 10)) / sum(hist) * 100, 2)
            if cloud_percent > 10:
                raise ProviderError(f'Nuvens em excesso na área: {cloud_percent}%')
            for view in ('default', 'natural'):
                blob = archive.extractfile(f'{view}.png').read()
                if verify_png(blob) != (1024, 1024):
                    raise ProviderError('Dimensão óptica inválida')
                images[(role, view)] = blob
        products = {t.get('productId', '').removesuffix('.SAFE') for t in metadata['tiles']}
        if products != {feature['id'].removesuffix('.SAFE')}:
            raise ProviderError(f'Produto Sentinel-2 divergente do catálogo: {sorted(products)}')
        entries[role] = {'feature': feature, 'processing': metadata, 'local_cloud_percent': cloud_percent,
            'checksums': {v: hashlib.sha256(images[(role, v)]).hexdigest() for v in ('default', 'natural')}}
    # Publish the manifest last; incomplete pairs are never accepted.
    ASSETS.mkdir(parents=True, exist_ok=True)
    for (role, view), blob in images.items():
        (ASSETS / f'{role.lower()}-{view}.png').write_bytes(blob)
    manifest = {'provider': 'CDSE', 'collection': 'sentinel-2-l2a', 'bbox': BBOX,
        'fetched_at': datetime.now(timezone.utc).isoformat(), 'evalscript': OPTICAL_SCRIPT,
        'visualization': VISUALIZATION, 'historical_context': HISTORICAL_CONTEXT, 'scenes': entries}
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return load_pair()
