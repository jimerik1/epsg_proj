# Transform Via

**Method**: `POST`
**URL**: `/api/transform/via`

Transform through a user-defined sequence of CRS codes.

## Request
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

## Response
```json
{
  "x": 448249.30,
  "y": 5411932.60,
  "z": null,
  "cumulative_accuracy": 0.25
}
```
