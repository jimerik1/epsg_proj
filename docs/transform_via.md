# Transform Via

**Method**: `POST`
**URL**: `/api/transform/via`

Transform through a user-defined sequence of CRS codes.

## Request

### Example: Lon/lat seed into multi-step path
The first CRS in `path` is geographic, so the payload uses lon/lat names.

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

## Response
```json
{
  "x": 448249.30,
  "y": 5411932.60,
  "z": null,
  "cumulative_accuracy": 0.25
}
```
