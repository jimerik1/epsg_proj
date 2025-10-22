# CRS Match

**Method**: `POST`
**URL**: `/api/crs/match`

Match a custom XML definition to likely EPSG codes with heuristic scoring.

## Request
```http
POST /api/crs/match
Content-Type: application/json
```

```json
{
  "xml": "<CD_GEO_SYSTEM ...>"
}
```

## Response
```json
{
  "matches": [
    {"epsg_code": "EPSG:23031", "name": "ED50 / UTM zone 31N", "score": 130},
    {"epsg_code": "EPSG:32631", "name": "WGS 84 / UTM zone 31N", "score": 85}
  ]
}
```
