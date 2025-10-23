# Transform Via

**Method**: `POST`
**URL**: `/api/transform/via`

Transform through a user-defined sequence of CRS codes.

## Request

### Example: Lon/lat seed into multi-step path
The first CRS in `path` is geographic, so the payload uses lon/lat names. Hit [`/api/crs/info`](crs_info.md) if you need to confirm the CRS type before building the path.

```http
POST /api/transform/via
Content-Type: application/json
```

```json
{
  "path": ["EPSG:4326", "EPSG:23031", "EPSG:32631"],
  "position": {"lon": 2.2945, "lat": 48.8584}
}
```

### Example: Projected starting point
When the first CRS is projected, pass `x`/`y`. The remainder of the path can mix CRS types.

```http
POST /api/transform/via
Content-Type: application/json
```

```json
{
  "path": ["EPSG:32631", "EPSG:23031", "EPSG:4326"],
  "position": {"x": 448249.35, "y": 5411932.67}
}
```

### Optional: Per-segment path selection
Control which TransformerGroup path is used on each leg by passing `segment_path_ids`, aligned to `len(path) - 1`. You may also provide `segment_preferred_ops` to hint operation names per leg.

```json
{
  "path": ["EPSG:4326", "EPSG:4277", "EPSG:27700"],
  "position": {"lon": -3.1883, "lat": 55.9533},
  "segment_path_ids": [1, 0],
  "segment_preferred_ops": [["Position Vector"], ["OSTN15", "NTv2"]]
}
```

## Response
```json
{
  "x": 448249.30,
  "y": 5411932.60,
  "z": null,
  "cumulative_accuracy": 0.25
}
```
