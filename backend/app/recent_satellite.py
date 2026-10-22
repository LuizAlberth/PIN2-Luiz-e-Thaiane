"""Latest usable Sentinel-2 passes over the fixed Rio dos Índios study area.

The pair is a visual comparison of two acquisition dates, not flood evidence.
Only complete, cloud-checked pairs are published in shared object storage.
"""
from datetime import timedelta
from io import BytesIO
import hashlib
import json
import tarfile

from PIL import Image, ImageDraw
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from .adapters import CDSEClient, ProviderError, checked, parsed_time, verify_png
from .models import now
from .satellite_demo import BBOX, OPTICAL_SCRIPT, VISUALIZATION
from .storage import get, put

MANIFEST_KEY = 'latest-sentinel/manifest.json'
COLLECTION = 'sentinel-2-l2a'
SCREEN_SCRIPT = '''//VERSION=3
function setup() { return {input:["SCL","dataMask"], mosaicking:Mosaicking.TILE,
  output:[{id:"quality",bands:1,sampleType:"UINT8"}]}; }
function evaluatePixel(samples) { let s=samples[0]; return {quality:[s && s.dataMask ? s.SCL : 0]}; }
function updateOutputMetadata(scenes,inputMetadata,outputMetadata) {
  outputMetadata.userData={tiles:scenes.tiles.map(t=>({productId:t.sentinel2ProductId}))};
}'''
UNUSABLE_SCL = (0, 1, 3, 8, 9, 10, 11)
# Approximate river corridors in the fixed BBOX, measured on the pilot imagery.
# If the study area changes, these paths must be revalidated before use.
RIVER_PATHS = (
    ((.99, .49), (.75, .52), (.62, .47), (.51, .43), (.42, .48),
     (.41, .61), (.38, .71), (.37, .85), (.26, .98)),
    ((.42, .48), (.29, .52), (.19, .50), (.18, .34)),
)


def load_latest():
    try:
        manifest = json.loads(get(MANIFEST_KEY))
        if manifest['bbox'] != BBOX or manifest['collection'] != COLLECTION:
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


def _river_mask(size):
    width, height = size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    for path in RIVER_PATHS:
        draw.line([(round(x * (width - 1)), round(y * (height - 1))) for x, y in path],
            fill=255, width=max(5, round(width * .055)), joint='curve')
    return mask


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


def _river_visible(blob):
    with Image.open(BytesIO(blob)) as image:
        rgb = image.convert('RGB')
        mask = _river_mask(rgb.size)
        pixels = rgb.load()
        inside = mask.load()
        count = water = 0
        for y in range(rgb.height):
            for x in range(rgb.width):
                if inside[x, y]:
                    count += 1
                    r, g, b = pixels[x, y]
                    water += r < 40 and 110 < g < 190 and b > 200
        return count > 0 and water / count >= .02


def _request(client, feature, script, resolution, outputs):
    acquired = parsed_time(feature['properties']['datetime'])
    start = acquired.replace(hour=0, minute=0, second=0, microsecond=0)
    payload = {'input': {'bounds': {'bbox': BBOX,
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
    if product_ids != {feature['id'].removesuffix('.SAFE')}:
        raise ProviderError('Produto processado difere da passagem escolhida')
    return blobs


def _scene(client, feature):
    screening = _request(client, feature, SCREEN_SCRIPT, 256, ('quality', 'userdata'))
    if _quality(screening['quality']) > 10 or _river_obscured(screening['quality']) > 10:
        return None
    images = _request(client, feature, OPTICAL_SCRIPT, 1024,
        ('default', 'natural', 'quality', 'userdata'))
    cloud = _quality(images['quality'])
    river_obscured = _river_obscured(images['quality'])
    if cloud > 10 or river_obscured > 10 or not _river_visible(images['default']):
        return None
    product_id = feature['id'].removesuffix('.SAFE')
    record = {'product_id': product_id,
        'acquired_at': parsed_time(feature['properties']['datetime']).isoformat(),
        'cloud_percent': cloud, 'river_obscured_percent': river_obscured,
        'tile': 'T22JFR', 'orbit': 'R038', 'images': {}}
    for view in ('default', 'natural'):
        blob = images[view]
        if verify_png(blob) != (1024, 1024):
            raise ProviderError('Cena Sentinel-2 com dimensões inesperadas')
        key = f'latest-sentinel/{product_id}/{view}.png'
        record['images'][view] = {'key': key, 'sha256': put(key, blob)}
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
    if existing and any('river_obscured_percent' not in scene for scene in existing['scenes']):
        existing = None  # Recheck pairs produced before the river-corridor validation.
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
        'bbox': BBOX, 'visualization': VISUALIZATION,
        'checked_at': now().isoformat(), 'latest_pass': latest_pass,
        'rejected': rejected, 'scenes': scenes}
    put(MANIFEST_KEY, json.dumps(manifest, ensure_ascii=False).encode(), content_type='application/json')
    return manifest
