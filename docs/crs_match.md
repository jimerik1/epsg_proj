# CRS Match

**Method**: `POST`  \n**URL**: `/api/crs/match`

Match a custom XML definition to likely EPSG codes with heuristic scoring.

## Request
POST /api/crs/match
{
  "xml": "<CD_GEO_SYSTEM ...>"
}

## Response
{
  "matches": [
    {"epsg_code": "EPSG:23031", "name": "ED50 / UTM zone 31N", "score": 130},
    {"epsg_code": "EPSG:32631", "name": "WGS 84 / UTM zone 31N", "score": 85}
  ]
}
