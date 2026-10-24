"""Focused checks for local Sentinel quality and georeferenced GIS guidance."""
from datetime import date
from io import BytesIO

from PIL import Image

from app import gis_area, recent_satellite


def png(image):
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def test_local_clouds_and_missing_coverage_are_separate():
    quality = Image.new('L', (10, 10), 4)
    for x in range(3):
        for y in range(10):
            quality.putpixel((x, y), 0)
    quality.putpixel((9, 9), 9)
    metrics = recent_satellite._quality_metrics(png(quality))
    assert metrics == {'local_cloud_percent': 1.0, 'local_no_data_percent': 30.0,
                       'local_obscured_percent': 31.0}
    assert 'Sem dados' in recent_satellite._quality_reason(metrics, None, False)


def test_search_prefers_full_footprint_over_tile_cloud_percent():
    bbox = [0.0, 0.0, 1.0, 1.0]
    def feature(satellite, west, cloud):
        product = f'{satellite}_MSIL2A_20260904T131301_N0512_R138_T23KNR_20260904T222757'
        return {'id': product, 'geometry': {'type': 'Polygon',
            'coordinates': [[[west, 0], [1, 0], [1, 1], [west, 1], [west, 0]]]},
            'properties': {'datetime': '2026-09-04T13:13:01Z', 'eo:cloud_cover': cloud}}
    class Catalog:
        ready = True
        def search(self, *_args, **_kwargs):
            return [feature('S2A', .3, 0.0), feature('S2B', 0, .02)]
    result = recent_satellite.search_period(date(2026, 9, 4), date(2026, 9, 4),
                                             Catalog(), bbox=bbox)
    assert result['scenes'][0]['product_id'].startswith('S2B_')
    assert result['scenes'][0]['footprint_coverage_percent'] == 100.0


def test_gis_water_guides_only_observed_pixels():
    natural = Image.new('RGBA', (100, 100), (200, 200, 200, 255))
    water = Image.new('L', (100, 100), 0)
    water.putpixel((50, 50), 128)  # weak spectral evidence, mapped river
    water.putpixel((50, 0), 128)   # weak evidence away from river
    water.putpixel((60, 0), 255)   # strong SCL water away from river
    river = {'geometry': {'type': 'LineString', 'coordinates': [[0, .5], [1, .5]]}}
    highlighted, percent = recent_satellite._integrated_water_image(
        png(natural), png(water), [0, 0, 1, 1], [river])
    with Image.open(BytesIO(highlighted)) as image:
        assert image.getpixel((50, 50))[:3] == (5, 148, 242)
        assert image.getpixel((50, 0))[:3] == (200, 200, 200)
        assert image.getpixel((60, 0))[:3] == (5, 148, 242)
        assert image.getpixel((20, 50))[:3] == (200, 200, 200)
    assert percent == .02


def test_gis_extracts_named_roads_and_waterways_with_stable_ids():
    xml = b'''<osm><node id="1" lon="0" lat="0.5"/><node id="2" lon="1" lat="0.5"/>
      <node id="3" lon="0" lat="0.2"/><node id="4" lon="1" lat="0.2"/>
      <way id="123"><nd ref="1"/><nd ref="2"/><tag k="waterway" v="river"/><tag k="name" v="Rio Teste"/></way>
      <way id="456"><nd ref="3"/><nd ref="4"/><tag k="highway" v="residential"/><tag k="name" v="Rua A"/></way></osm>'''
    rivers, roads = gis_area._from_osm_xml(xml, [0, 0, 1, 1])
    assert rivers[0]['id'] == 'way/123'
    assert roads[0]['id'] == 'way/456'
    assert roads[0]['properties'] == {'name': 'Rua A', 'highway': 'residential'}
