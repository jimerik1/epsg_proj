# CRS Units

**Method**: `GET`
**URL**: `/api/crs/units/{epsg_code}`

Return axis units and conversion factors for a CRS.

## Request
```http
GET /api/crs/units/EPSG:32631
```

## Response
```json
{
  "epsg_code": "EPSG:32631",
  "units": {
    "horizontal": "metre",
    "horizontal_factor": 1.0
  }
}
```
