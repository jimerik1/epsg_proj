from pyproj import Transformer


def test_wgs84_to_utm31n_basic():
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32631", always_xy=True)
    # Paris approx: lon=2.2945, lat=48.8584 (Eiffel Tower)
    x, y = tr.transform(2.2945, 48.8584)
    # Expect UTM 31N Easting around ~448251, Northing ~5411932
    assert 400000 < x < 500000
    assert 5300000 < y < 5500000

