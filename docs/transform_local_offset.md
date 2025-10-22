# Transform Local Offset

**Method**: `POST`
**URL**: `/api/transform/local-offset`

Convert a true-distance local offset (ENU) using the ECEF pipeline and scale-factor approximation.

## Request
```http
POST /api/transform/local-offset
Content-Type: application/json
```

```json
{
  "crs": "EPSG:32040",
  "reference": {"lon": -99.2053, "lat": 29.3513, "height": 0},
  "offset": {"east": 10, "north": 10, "up": 0}
}
```

## Response
```json
{
  "reference": {
    "geodetic": {"lon": -99.2053, "lat": 29.3513},
    "projected": {"x": 1934594.06, "y": 551965.15},
    "wgs84": {"lon": -99.2056401, "lat": 29.3515111}
  },
  "ecef_pipeline": {
    "geodetic": {"lon": -99.2052167, "lat": 29.3513677},
    "projected": {"x": 1934626.92, "y": 551997.90}
  },
  "scale_factor": {
    "projected": {"x": 1934626.86, "y": 551997.96},
    "scales": {"meridional_scale": 0.9998633, "parallel_scale": 0.9998633}
  },
  "difference": {
    "dx_m": 0.0174,
    "dy_m": -0.0176,
    "d_m": 0.0248
  }
}
```
