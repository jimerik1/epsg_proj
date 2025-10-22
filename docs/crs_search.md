# CRS Search

**Method**: `GET`
**URL**: `/api/crs/search`

Search the CRS database by text, area of interest, and type.

## Request
```http
GET /api/crs/search?text=UTM&crs_type=PROJECTED_CRS
```

## Response
```json
[
  {"code": 32631, "name": "WGS 84 / UTM zone 31N", "type": "PROJECTED"},
  {"code": 32632, "name": "WGS 84 / UTM zone 32N", "type": "PROJECTED"}
]
```
