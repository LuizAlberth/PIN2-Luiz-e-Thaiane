"""Refresh the pilot river centerlines from OpenStreetMap (ODbL)."""
from datetime import datetime, timezone
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
from shapely.geometry import LineString, box, mapping

from app.satellite_demo import BBOX

NAMES = {'Rio Krauel', 'Rio dos Índios'}
SOURCE = 'https://api.openstreetmap.org/api/0.6/map'
OUTPUT = Path(__file__).resolve().parents[1] / 'backend/app/assets/pilot_rivers.geojson'


def refresh():
    response = httpx.get(SOURCE, params={'bbox': ','.join(map(str, BBOX))}, timeout=40,
        headers={'User-Agent': 'PIN2-Mancha-Inundacao-MVP/1.0 (+https://github.com/LuizAlberth/PIN2-Luiz-e-Thaiane)'})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    nodes = {node.attrib['id']: (float(node.attrib['lon']), float(node.attrib['lat']))
             for node in root.findall('node')}
    area = box(*BBOX)
    features = []
    for way in root.findall('way'):
        tags = {tag.attrib['k']: tag.attrib['v'] for tag in way.findall('tag')}
        if tags.get('waterway') != 'river' or tags.get('name') not in NAMES:
            continue
        points = [nodes[ref.attrib['ref']] for ref in way.findall('nd') if ref.attrib['ref'] in nodes]
        if len(points) < 2:
            continue
        clipped = LineString(points).intersection(area).simplify(.000005, preserve_topology=True)
        if not clipped.is_empty:
            features.append({'type': 'Feature', 'id': f"osm-way-{way.attrib['id']}",
                'properties': {'name': tags['name'], 'waterway': 'river'},
                'geometry': mapping(clipped)})
    if {feature['properties']['name'] for feature in features} != NAMES:
        raise RuntimeError('Os dois rios da área piloto não foram encontrados; arquivo anterior preservado')
    data = {'type': 'FeatureCollection', 'bbox': BBOX,
        'source': SOURCE, 'attribution': '© OpenStreetMap contributors',
        'license': 'ODbL 1.0 — https://www.openstreetmap.org/copyright',
        'downloaded_at': datetime.now(timezone.utc).isoformat(), 'features': features}
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{len(features)} trechos de rios salvos em {OUTPUT}')


if __name__ == '__main__':
    refresh()
