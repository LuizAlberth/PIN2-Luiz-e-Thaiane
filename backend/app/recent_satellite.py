"""Latest usable Sentinel-2 passes over the fixed Rio dos Índios study area.

The pair is a visual comparison of two acquisition dates, not flood evidence.
Only complete, cloud-checked pairs are published in shared object storage.
"""
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
import hashlib
import json
import math
import tarfile
import re
import threading
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from shapely.geometry import box, shape

from .adapters import CDSEClient, ProviderError, checked, parsed_time, verify_png
from .models import now
from .satellite_demo import BBOX, OPTICAL_SCRIPT, VISUALIZATION
from .storage import get, put
from .gis_area import area_geojson

MANIFEST_KEY = 'latest-sentinel/manifest.json'
COLLECTION = 'sentinel-2-l2a'
_preview_lock = threading.Lock()
ALGORITHM_VERSION = 4
RIVER_DATA = Path(__file__).resolve().parent / 'assets/pilot_rivers.geojson'
PRODUCT_PATTERN = re.compile(r'^S2[ABC]_MSIL2A_\d{8}T\d{6}_N\d{4}_R038_T22JFR_\d{8}T\d{6}$')
SEARCH_PRODUCT_PATTERN = re.compile(r'^S2[ABC]_MSIL2A_\d{8}T\d{6}_N\d{4}_R\d{3}_T\d{2}[A-Z]{3}_\d{8}T\d{6}$')
SCREEN_SCRIPT = '''//VERSION=3
function setup() { return {input:["SCL","dataMask"], mosaicking:Mosaicking.TILE,
  output:[{id:"quality",bands:1,sampleType:"UINT8"}]}; }
function evaluatePixel(samples) { let s=samples[0]; return {quality:[s && s.dataMask ? s.SCL : 0]}; }
function updateOutputMetadata(scenes,inputMetadata,outputMetadata) {
  outputMetadata.userData={tiles:scenes.tiles.map(t=>({productId:t.sentinel2ProductId}))};
}'''
UNUSABLE_SCL = (0, 1, 3, 7, 8, 9, 10, 11)
CLOUD_SCL = (8, 9, 10)

@lru_cache(maxsize=1)
def river_geojson():
    data = json.loads(RIVER_DATA.read_text())
    if data['bbox'] != BBOX or {f['properties']['name'] for f in data['features']} != {'Rio Krauel', 'Rio dos Índios'}:
        raise ProviderError('Geometria GIS dos rios da área piloto inválida')
    return data


def load_latest():
    try:
        manifest = json.loads(get(MANIFEST_KEY))
        if manifest['bbox'] != BBOX or manifest['collection'] != COLLECTION or manifest.get('algorithm_version') != ALGORITHM_VERSION:
            return None
        if len(manifest['scenes']) != 2:
            return None
        for scene in manifest['scenes']:
            if not scene['product_id'] or not scene['acquired_at']:
                return None
            for view in ('default', 'natural'):
                blob = get(scene['images'][view]['key'])
                if hashlib.sha256(blob).hexdigest() != scene['images'][view]['sha256']:
                    return None
                if verify_png(blob) != (1024, 1024):
                    return None
        return manifest
    except (OSError, KeyError, TypeError, ValueError, ProviderError, BotoCoreError, ClientError):
        return None


def _quality(blob):
    with Image.open(BytesIO(blob)) as image:
        counts = image.convert('L').histogram()
    pixels = sum(counts)
    return round(100 * sum(counts[i] for i in UNUSABLE_SCL) / pixels, 2) if pixels else 100.0


def _quality_metrics(blob):
    with Image.open(BytesIO(blob)) as image:
        counts = image.convert('L').histogram()
    pixels = sum(counts)
    if not pixels:
        return {'local_cloud_percent': 0.0, 'local_no_data_percent': 100.0,
                'local_obscured_percent': 100.0}
    pct = lambda n: round(100 * n / pixels, 2)
    return {'local_cloud_percent': pct(sum(counts[i] for i in CLOUD_SCL)),
            'local_no_data_percent': pct(counts[0]),
            'local_obscured_percent': pct(sum(counts[i] for i in UNUSABLE_SCL))}


def _river_mask(size):
    return _waterway_mask(size, BBOX, river_geojson()['features'], corridor_ratio=.035)


def _waterway_mask(size, bbox, features, corridor_ratio=.018):
    width, height = size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    west, south, east, north = bbox
    for feature in features:
        geometry = feature['geometry']
        lines = [geometry['coordinates']] if geometry['type'] == 'LineString' else geometry['coordinates']
        for line in lines:
            points = [(round((lon - west) / (east - west) * (width - 1)),
                       round((north - lat) / (north - south) * (height - 1))) for lon, lat in line]
            if len(points) > 1:
                draw.line(points, fill=255, width=max(5, round(width * corridor_ratio)), joint='curve')
    return mask


def _integrated_water_image(natural_blob, water_blob, bbox, waterways):
    """Highlight observed water; GIS supports weak spectral detections near rivers.

    Water is never painted from a mapped line alone. SCL=6 is retained anywhere;
    the weaker NDWI/MNDWI test is accepted in a mapped waterway corridor. Where
    OSM has no mapped waterway, keep the satellite result and report that limit.
    """
    with Image.open(BytesIO(natural_blob)) as image:
        natural = image.convert('RGBA')
    with Image.open(BytesIO(water_blob)) as image:
        water = image.convert('L')
    if natural.size != water.size:
        raise ProviderError('Máscara de água incompatível com a imagem Sentinel-2')
    corridor = _waterway_mask(natural.size, bbox, waterways) if waterways else None
    pixels = natural.load()
    detected = water.load()
    near_river = corridor.load() if corridor else None
    count = 0
    for y in range(natural.height):
        for x in range(natural.width):
            value = detected[x, y]
            if pixels[x, y][3] and (value == 255 or value and (near_river is None or near_river[x, y])):
                pixels[x, y] = (5, 148, 242, pixels[x, y][3])
                count += 1
    output = BytesIO()
    natural.save(output, format='PNG', optimize=True)
    return output.getvalue(), round(100 * count / (natural.width * natural.height), 2)


def _river_obscured(blob):
    with Image.open(BytesIO(blob)) as image:
        quality = image.convert('L')
        mask = _river_mask(quality.size)
        pixels = quality.load()
        inside = mask.load()
        count = blocked = 0
        for y in range(quality.height):
            for x in range(quality.width):
                if inside[x, y]:
                    count += 1
                    blocked += pixels[x, y] in UNUSABLE_SCL
        return round(100 * blocked / count, 2) if count else 100.0


def _river_visible(blob, classified=False):
    with Image.open(BytesIO(blob)) as image:
        mask = _river_mask(image.size)
        decoded = image.convert('L' if classified else 'RGB')
        pixels = decoded.load()
        inside = mask.load()
        count = water = 0
        for y in range(image.height):
            for x in range(image.width):
                if inside[x, y]:
                    count += 1
                    if classified:
                        water += pixels[x, y] > 0
                    else:
                        r, g, b = pixels[x, y]
                        water += r < 40 and 110 < g < 190 and b > 200
        return count > 0 and water / count >= .02


def search_bbox(lat=None, lon=None):
    if lat is None and lon is None:
        return BBOX
    if lat is None or lon is None or not all(math.isfinite(value) for value in (lat, lon)):
        raise ValueError('Informe latitude e longitude válidas')
    if not (-56 <= lat <= 83 and -179.98 <= lon <= 179.98):
        raise ValueError('Coordenadas fora da cobertura Sentinel-2')
    return [round(lon - .011, 6), round(lat - .00975, 6),
            round(lon + .011, 6), round(lat + .00975, 6)]


def search_key(product_id, bbox):
    area = hashlib.sha256(json.dumps(bbox).encode()).hexdigest()[:16]
    return f'search-sentinel/{area}/{product_id}'


def _request(client, feature, script, resolution, outputs, bbox=None):
    acquired = parsed_time(feature['properties']['datetime'])
    start = acquired.replace(hour=0, minute=0, second=0, microsecond=0)
    selected_product = feature['id'].removesuffix('.SAFE')
    # A calendar day can contain overlapping Sentinel-2 products. Restrict the
    # TILE samples to the catalog product the visitor selected; samples[0]
    # otherwise may belong to a different, partly empty product.
    script = (script + '\nfunction preProcessScenes(collections) {'
              'collections.scenes.tiles = collections.scenes.tiles.filter(t => '
              'String(t.sentinel2ProductId).split(".SAFE")[0] === '
              + json.dumps(selected_product) + '); return collections; }')
    payload = {'input': {'bounds': {'bbox': bbox or BBOX,
        'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}},
        'data': [{'type': COLLECTION, 'dataFilter': {'timeRange': {
            'from': start.isoformat(), 'to': (start + timedelta(days=1)).isoformat()}},
            'processing': {'upsampling': 'NEAREST'}}]},
        'output': {'width': resolution, 'height': resolution,
            'responses': [{'identifier': name, 'format': {'type': 'application/json' if name == 'userdata' else 'image/png'}}
                for name in outputs]}, 'evalscript': script}
    try:
        response = checked(client.http.post('https://sh.dataspace.copernicus.eu/api/v1/process',
            json=payload, headers={**client.headers(), 'Accept': 'application/x-tar'}))
        with tarfile.open(fileobj=BytesIO(response.content), mode='r:*') as archive:
            blobs = {name: archive.extractfile(f'{name}.{ "json" if name == "userdata" else "png"}').read()
                for name in outputs}
    except (httpx.RequestError, tarfile.TarError, OSError, AttributeError, TypeError, KeyError) as exc:
        raise ProviderError('Falha ao processar passagem Sentinel-2') from exc
    metadata = json.loads(blobs.pop('userdata'))
    product_ids = {t.get('productId', '').removesuffix('.SAFE') for t in metadata['tiles']}
    if product_ids != {selected_product}:
        raise ProviderError('Produto processado difere da passagem escolhida')
    return blobs


def _scene(client, feature, key_prefix='latest-sentinel', bbox=None, require_river=True,
           diagnostics=None):
    diagnostics = diagnostics if diagnostics is not None else {}
    screening = _request(client, feature, SCREEN_SCRIPT, 256, ('quality', 'userdata'), bbox=bbox)
    diagnostics.update(_quality_metrics(screening['quality']))
    river_screen = _river_obscured(screening['quality']) if require_river else None
    diagnostics['river_obscured_percent'] = river_screen
    if diagnostics['local_obscured_percent'] > 10 or (require_river and river_screen > 10):
        diagnostics['reason'] = _quality_reason(diagnostics, river_screen, require_river)
        return None
    images = _request(client, feature, OPTICAL_SCRIPT, 1024,
        ('default', 'natural', 'quality', 'water', 'userdata'), bbox=bbox)
    diagnostics.update(_quality_metrics(images['quality']))
    river_obscured = _river_obscured(images['quality']) if require_river else None
    diagnostics['river_obscured_percent'] = river_obscured
    if diagnostics['local_obscured_percent'] > 10 or (require_river and river_obscured > 10):
        diagnostics['reason'] = _quality_reason(diagnostics, river_obscured, require_river)
        return None
    if require_river and not _river_visible(images['water'], classified=True):
        diagnostics['reason'] = 'O rio mapeado não foi detectado nesta passagem; escolha outra data.'
        return None
    area = bbox or BBOX
    if area == BBOX:
        waterways = river_geojson()['features']
        gis_status = 'available'
    else:
        gis = area_geojson(area)
        waterways = gis['waterways']['features']
        gis_status = gis['status']
    highlighted, water_percent = _integrated_water_image(images['natural'], images['water'],
                                                          area, waterways)
    product_id = feature['id'].removesuffix('.SAFE')
    record = {'product_id': product_id,
        'algorithm_version': ALGORITHM_VERSION,
        'acquired_at': parsed_time(feature['properties']['datetime']).isoformat(),
        'cloud_percent': diagnostics['local_cloud_percent'],
        'local_cloud_percent': diagnostics['local_cloud_percent'],
        'local_no_data_percent': diagnostics['local_no_data_percent'],
        'local_obscured_percent': diagnostics['local_obscured_percent'],
        'river_obscured_percent': river_obscured,
        'gis_status': gis_status, 'gis_waterway_count': len(waterways),
        'highlighted_water_percent': water_percent,
        'tile': product_id.split('_')[5], 'orbit': product_id.split('_')[4], 'images': {}}
    for view in ('default', 'natural'):
        blob = highlighted if view == 'default' else images['natural']
        if verify_png(blob) != (1024, 1024):
            raise ProviderError('Cena Sentinel-2 com dimensões inesperadas')
        key = f'{key_prefix}/{product_id}/{view}.png'
        record['images'][view] = {'key': key, 'sha256': put(key, blob)}
    return record


def _quality_reason(metrics, river_obscured, require_river):
    if metrics['local_no_data_percent'] > 10:
        return (f"Sem dados Sentinel-2 em {metrics['local_no_data_percent']}% do recorte "
                '(o percentual de nuvens do tile não mede essa lacuna). Escolha outra passagem.')
    if metrics['local_cloud_percent'] > 10:
        return f"Nuvens em {metrics['local_cloud_percent']}% do recorte escolhido; escolha outra passagem."
    if require_river and river_obscured is not None and river_obscured > 10:
        return (f'Rio mapeado encoberto ou sem dados em {river_obscured}% do seu corredor; '
                'escolha outra passagem.')
    return (f"{metrics['local_obscured_percent']}% do recorte sem leitura confiável "
            '(sombras, pixels sem classe ou dados inválidos); escolha outra passagem.')


def search_period(start: date, end: date, client=None, bbox=None):
    """Catalog dates are discovery metadata; local visibility is checked on preview."""
    client = client or CDSEClient()
    if not client.ready:
        raise ProviderError('Credenciais Copernicus não configuradas')
    window_start = datetime.combine(start - timedelta(days=15), time.min, timezone.utc)
    window_end = min(now(), datetime.combine(end + timedelta(days=16), time.min, timezone.utc))
    area = bbox or BBOX
    features = client.search(area, window_start, window_end, collection=COLLECTION)
    bounds = box(*area)
    def coverage(feature):
        try:
            footprint = shape(feature['geometry'])
            return footprint.intersection(bounds).area / bounds.area
        except (TypeError, ValueError, KeyError):
            return 0.0
    def tile_cloud(feature):
        value = feature['properties'].get('eo:cloud_cover')
        return float(value) if value is not None else 100.0
    # Multiple products can exist on one date. Prefer one covering the whole
    # search area; tile-wide cloud percentage is only a secondary tie-breaker.
    features.sort(key=lambda feature: (-coverage(feature), tile_cloud(feature)))
    found = []
    seen_dates = set()
    for feature in features:
        product_id = feature.get('id', '').removesuffix('.SAFE')
        if not SEARCH_PRODUCT_PATTERN.fullmatch(product_id):
            continue
        acquired = parsed_time(feature['properties']['datetime'])
        day = acquired.date()
        if day in seen_dates:
            continue
        seen_dates.add(day)
        distance = (start - day).days if day < start else (day - end).days if day > end else 0
        found.append({'product_id': product_id, 'acquired_at': acquired.isoformat(),
            'distance_days': distance, 'in_period': distance == 0,
            'tile_cloud_percent': feature['properties'].get('eo:cloud_cover'),
            'footprint_coverage_percent': round(100 * coverage(feature), 2)})
    found.sort(key=lambda x: (x['distance_days'], x['acquired_at']))
    return {'start': start.isoformat(), 'end': end.isoformat(), 'margin_days': 15,
        'bbox': area, 'checked_at': now().isoformat(), 'scenes': found[:24],
        'note': 'Nuvens do catálogo referem-se ao tile inteiro; a prévia verifica nuvens e cobertura do recorte escolhido.'}


def load_search_preview(product_id, bbox=None):
    if not SEARCH_PRODUCT_PATTERN.fullmatch(product_id):
        raise ProviderError('Identificador Sentinel-2 inválido')
    area = bbox or BBOX
    try:
        record = json.loads(get(f'{search_key(product_id, area)}/manifest.json'))
        if record['product_id'] != product_id or record['bbox'] != area or record.get('algorithm_version') != ALGORITHM_VERSION:
            return None
        if record.get('unavailable'):
            return record
        for view in ('default', 'natural'):
            image = record['images'][view]
            blob = get(image['key'])
            if hashlib.sha256(blob).hexdigest() != image['sha256'] or verify_png(blob) != (1024, 1024):
                return None
        return record
    except (OSError, KeyError, TypeError, ValueError, BotoCoreError, ClientError):
        return None


def create_search_preview(product_id, client=None, bbox=None):
    if not SEARCH_PRODUCT_PATTERN.fullmatch(product_id):
        raise ProviderError('Identificador Sentinel-2 inválido')
    area = bbox or BBOX
    with _preview_lock:
        cached = load_search_preview(product_id, area)
        if cached:
            return cached
        client = client or CDSEClient()
        acquired = datetime.strptime(product_id.split('_')[2], '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
        if acquired > now() or acquired.year < 2017:
            raise ProviderError('Data Sentinel-2 inválida')
        day = acquired.replace(hour=0, minute=0, second=0)
        features = client.search(area, day, day + timedelta(days=1), collection=COLLECTION)
        feature = next((f for f in features if f.get('id', '').removesuffix('.SAFE') == product_id), None)
        if not feature:
            raise ProviderError('Produto não encontrado no catálogo Copernicus')
        diagnostics = {}
        record = _scene(client, feature, key_prefix=search_key(product_id, area),
            bbox=area, require_river=area == BBOX, diagnostics=diagnostics)
        if record is None:
            record = {'product_id': product_id, 'unavailable': True,
                'reason': diagnostics.get('reason', 'Cena sem leitura confiável no recorte'),
                'local_cloud_percent': diagnostics.get('local_cloud_percent'),
                'local_no_data_percent': diagnostics.get('local_no_data_percent'),
                'local_obscured_percent': diagnostics.get('local_obscured_percent'),
                'river_obscured_percent': diagnostics.get('river_obscured_percent'),
                'gis_status': None}
        record['bbox'] = area
        record['algorithm_version'] = ALGORITHM_VERSION
        put(f'{search_key(product_id, area)}/manifest.json',
            json.dumps(record, ensure_ascii=False).encode(), content_type='application/json')
        return record


def _rejected_preview(client, feature, existing):
    product_id = feature['id'].removesuffix('.SAFE')
    previous = existing.get('rejected') if existing else None
    if previous and previous['product_id'] == product_id:
        try:
            blob = get(previous['image']['key'])
            if hashlib.sha256(blob).hexdigest() == previous['image']['sha256']:
                return previous
        except (OSError, BotoCoreError, ClientError):
            pass
    images = _request(client, feature, OPTICAL_SCRIPT, 512,
        ('natural', 'quality', 'userdata'))
    obscured = _quality(images['quality'])
    river_obscured = _river_obscured(images['quality'])
    if obscured <= 10 and river_obscured <= 10:
        return None
    blob = images['natural']
    try:
        with Image.open(BytesIO(blob)) as image:
            image.verify()
        with Image.open(BytesIO(blob)) as image:
            if image.format != 'PNG' or image.size != (512, 512):
                raise ValueError('Prévia inválida')
    except (OSError, ValueError) as exc:
        raise ProviderError('Prévia da última passagem inválida') from exc
    key = f'latest-sentinel/rejected/{product_id}.png'
    return {'product_id': product_id,
        'acquired_at': parsed_time(feature['properties']['datetime']).isoformat(),
        'obscured_percent': obscured, 'river_obscured_percent': river_obscured,
        'image': {'key': key, 'sha256': put(key, blob)}}


def refresh_latest(client=None):
    client = client or CDSEClient()
    if not client.ready:
        raise ProviderError('Credenciais Copernicus não configuradas')
    existing = load_latest()
    start = now() - timedelta(days=365)
    features = client.search(BBOX, start, now(), collection=COLLECTION)
    features = sorted((f for f in features if '_T22JFR_' in f['id'] and '_R038_' in f['id']),
        key=lambda f: f['properties']['datetime'], reverse=True)
    latest_pass = ({'acquired_at': parsed_time(features[0]['properties']['datetime']).isoformat(),
        'tile_cloud_percent': features[0]['properties'].get('eo:cloud_cover')}
        if features else None)
    scenes = list(existing['scenes']) if existing else []
    latest_date = parsed_time(scenes[-1]['acquired_at']) if scenes else start
    new_scenes = []
    for feature in features:
        if parsed_time(feature['properties']['datetime']) <= latest_date:
            break
        scene = _scene(client, feature)
        if scene:
            new_scenes.append(scene)
            if len(new_scenes) == 2:
                break
    scenes = sorted(scenes + new_scenes, key=lambda s: s['acquired_at'])[-2:]
    if len(scenes) != 2:
        raise ProviderError('Ainda não há duas passagens recentes com até 10% de nuvens no recorte')
    rejected = None
    if features and features[0]['id'].removesuffix('.SAFE') != scenes[-1]['product_id']:
        rejected = _rejected_preview(client, features[0], existing)
    manifest = {'provider': 'Copernicus Data Space Ecosystem', 'collection': COLLECTION,
        'bbox': BBOX, 'algorithm_version': ALGORITHM_VERSION, 'visualization': VISUALIZATION,
        'checked_at': now().isoformat(), 'latest_pass': latest_pass,
        'rejected': rejected, 'scenes': scenes}
    put(MANIFEST_KEY, json.dumps(manifest, ensure_ascii=False).encode(), content_type='application/json')
    return manifest
