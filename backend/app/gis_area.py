"""Cached OpenStreetMap waterway and named-road geometry for a small search area.

The lines are cartographic context. They do not assert that a street is flooded
or that a mapped waterway contains visible water in a satellite acquisition.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from xml.etree import ElementTree as ET

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from shapely.geometry import LineString, box, mapping

from .storage import get, put

OVERPASS = 'https://overpass-api.de/api/interpreter'
OSM_MAP = 'https://api.openstreetmap.org/api/0.6/map'
ATTRIBUTION = '© OpenStreetMap contributors'
LICENSE = 'ODbL 1.0 — https://www.openstreetmap.org/copyright'
USER_AGENT = 'PIN2-Mancha-Inundacao-MVP/1.0 (+https://github.com/LuizAlberth/PIN2-Luiz-e-Thaiane)'
WATERWAYS = {'river', 'stream', 'canal', 'drain'}
CACHE_AGE = timedelta(days=30)


def _cache_key(bbox):
    digest = hashlib.sha256(json.dumps(bbox, separators=(',', ':')).encode()).hexdigest()[:20]
    return f'gis/area/{digest}.json'


def _feature(osm_id, tags, coordinates, bounds):
    if len(coordinates) < 2:
        return None
    clipped = LineString(coordinates).intersection(bounds)
    if clipped.is_empty or clipped.geom_type not in {'LineString', 'MultiLineString'}:
        return None
    clipped = clipped.simplify(.000005, preserve_topology=True)
    return {'type': 'Feature', 'id': f'way/{osm_id}',
            'properties': {key: tags[key] for key in ('name', 'highway', 'waterway') if tags.get(key)},
            'geometry': mapping(clipped)}


def _from_elements(elements, bbox):
    bounds = box(*bbox)
    rivers, roads = [], []
    for element in elements:
        if element.get('type') != 'way':
            continue
        tags = element.get('tags') or {}
        river = tags.get('waterway') in WATERWAYS
        road = bool(tags.get('highway') and tags.get('name'))
        if not (river or road):
            continue
        geometry = element.get('geometry') or []
        feature = _feature(element['id'], tags,
                           [(node['lon'], node['lat']) for node in geometry], bounds)
        if feature:
            if river:
                rivers.append(feature)
            if road:
                roads.append(feature)
    return rivers, roads


def _from_osm_xml(content, bbox):
    root = ET.fromstring(content)
    nodes = {node.attrib['id']: (float(node.attrib['lon']), float(node.attrib['lat']))
             for node in root.findall('node')}
    elements = []
    for way in root.findall('way'):
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        if tags.get('waterway') not in WATERWAYS and not (tags.get('highway') and tags.get('name')):
            continue
        geometry = [nodes[ref.attrib['ref']] for ref in way.findall('nd') if ref.attrib['ref'] in nodes]
        elements.append({'type': 'way', 'id': way.attrib['id'], 'tags': tags,
                         'geometry': [{'lon': lon, 'lat': lat} for lon, lat in geometry]})
    return _from_elements(elements, bbox)


def _download(bbox):
    west, south, east, north = bbox
    query = ('[out:json][timeout:20];('
             f'way["waterway"~"^(river|stream|canal|drain)$"]({south},{west},{north},{east});'
             f'way["highway"]["name"]({south},{west},{north},{east}););out geom;')
    headers = {'User-Agent': USER_AGENT}
    try:
        response = httpx.post(OVERPASS, data={'data': query}, timeout=25, headers=headers)
        response.raise_for_status()
        return (*_from_elements(response.json()['elements'], bbox), OVERPASS)
    except (httpx.HTTPError, ValueError, KeyError):
        # Small, infrequent read-only fallback. The result is persisted for 30 days.
        response = httpx.get(OSM_MAP, params={'bbox': ','.join(map(str, bbox))},
                             timeout=40, headers=headers)
        response.raise_for_status()
        if len(response.content) > 25_000_000:
            raise ValueError('Resposta cartográfica excedeu o limite seguro')
        return (*_from_osm_xml(response.content, bbox), OSM_MAP)


def area_geojson(bbox):
    """Return cached GIS geometry and an explicit status if the source is unavailable."""
    if len(bbox) != 4 or not all(isinstance(v, (int, float)) for v in bbox):
        raise ValueError('Área GIS inválida')
    key = _cache_key(bbox)
    cached = None
    try:
        cached = json.loads(get(key))
        downloaded = datetime.fromisoformat(cached['downloaded_at'])
        if cached['bbox'] == bbox and datetime.now(timezone.utc) - downloaded < CACHE_AGE:
            return cached
    except (OSError, ValueError, KeyError, TypeError, BotoCoreError, ClientError):
        cached = None
    try:
        rivers, roads, source = _download(bbox)
        data = {'bbox': bbox, 'source': source, 'attribution': ATTRIBUTION,
                'license': LICENSE, 'downloaded_at': datetime.now(timezone.utc).isoformat(),
                'status': 'available',
                'waterways': {'type': 'FeatureCollection', 'features': rivers},
                'roads': {'type': 'FeatureCollection', 'features': roads}}
        try:
            put(key, json.dumps(data, ensure_ascii=False).encode(), content_type='application/json')
        except (OSError, BotoCoreError, ClientError):
            data['message'] = 'Cartografia disponível; cache temporariamente indisponível.'
        return data
    except (httpx.HTTPError, ET.ParseError, ValueError, KeyError, OSError):
        if cached and cached.get('bbox') == bbox:
            return {**cached, 'status': 'stale',
                    'message': 'Cartografia temporariamente indisponível; exibindo dados salvos.'}
        return {'bbox': bbox, 'source': None, 'attribution': ATTRIBUTION,
                'license': LICENSE, 'downloaded_at': None, 'status': 'unavailable',
                'message': 'Cartografia de rios e ruas indisponível para este recorte.',
                'waterways': {'type': 'FeatureCollection', 'features': []},
                'roads': {'type': 'FeatureCollection', 'features': []}}
