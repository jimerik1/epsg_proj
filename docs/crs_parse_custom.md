# Parse Custom CRS

**Method**: `POST`  \n**URL**: `/api/crs/parse-custom`

Convert custom XML CRS fields into a PROJ string and quick summary.

## Request
POST /api/crs/parse-custom
{
  "xml": "<CD_GEO_SYSTEM ...>"
}

## Response
{
  "proj": "+proj=utm +zone=31 ...",
  "system": {"geo_system_id": "UTM", "geo_system_name": "Universal Transverse Mercator"},
  "zone": {...},
  "datum": {...},
  "ellipsoid": {...}
}
