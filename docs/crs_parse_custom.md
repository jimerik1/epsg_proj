# Parse Custom CRS

**Method**: `POST`
**URL**: `/api/crs/parse-custom`

Convert custom XML CRS fields into a PROJ string and quick summary.

## Request
```http
POST /api/crs/parse-custom
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
  "proj": "+proj=utm +zone=31 ...",
  "system": {"geo_system_id": "UTM", "geo_system_name": "Universal Transverse Mercator"},
  "zone": {...},
  "datum": {...},
  "ellipsoid": {...}
}
```
