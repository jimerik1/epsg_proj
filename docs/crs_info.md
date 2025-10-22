# CRS Info

**Method**: `GET`
**URL**: `/api/crs/info`

Retrieve metadata for a CRS (name, datum, axes, ellipsoid).

## Request
```http
GET /api/crs/info?code=EPSG:32631
```

## Response
```json
{
  "code": "EPSG:32631",
  "name": "WGS 84 / UTM zone 31N",
  "type": "PROJECTED",
  "is_geographic": false,
  "is_projected": true,
  "area_of_use": "World - N hemisphere - 0°E to 6°E",
  "datum_name": "World Geodetic System 1984",
  "ellipsoid": {"name": "WGS 84", "semi_major_m": 6378137.0}
}
```
