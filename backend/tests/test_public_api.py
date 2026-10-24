"""Public image diagnostics and GIS search are available without an admin token."""
from fastapi.testclient import TestClient

from app import api
from app.recent_satellite import search_bbox


def test_search_inspection_reports_missing_pixels_not_tile_clouds(monkeypatch):
    product = 'S2A_MSIL2A_20260904T131301_N0512_R138_T23KNR_20260904T222757'
    area = search_bbox(-22.51128, -44.19629)
    record = {'product_id': product, 'bbox': area, 'unavailable': True,
              'reason': 'Sem dados Sentinel-2 em 30.58% do recorte',
              'local_cloud_percent': 0.0, 'local_no_data_percent': 30.58,
              'local_obscured_percent': 30.58, 'river_obscured_percent': None}
    monkeypatch.setattr(api, 'load_search_preview', lambda product_id, bbox: record)
    monkeypatch.setattr(api, 'create_search_preview', lambda *_args, **_kwargs: None)
    with TestClient(api.app) as client:
        inspected = client.get(f'/api/satellite/search/inspect/{product}?lat=-22.51128&lon=-44.19629')
        assert inspected.status_code == 200
        assert inspected.json()['available'] is False
        assert inspected.json()['local_no_data_percent'] == 30.58
        preview = client.get(f'/api/satellite/search/preview/{product}?lat=-22.51128&lon=-44.19629')
        assert preview.status_code == 404
        assert 'Sem dados' in preview.json()['detail']


def test_gis_area_uses_searched_coordinates(monkeypatch):
    area = search_bbox(-22.51128, -44.19629)
    monkeypatch.setattr(api, 'area_geojson', lambda bbox: {'bbox': bbox, 'status': 'available',
        'waterways': {'type': 'FeatureCollection', 'features': []},
        'roads': {'type': 'FeatureCollection', 'features': []}})
    with TestClient(api.app) as client:
        response = client.get('/api/gis/area?lat=-22.51128&lon=-44.19629')
        assert response.status_code == 200
        assert response.json()['bbox'] == area
        assert client.get('/api/gis/area?lat=90&lon=0').status_code == 422
