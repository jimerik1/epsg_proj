# CRS Units

**Method**: `GET`  \n**URL**: `/api/crs/units/{epsg_code}`

Return axis units and conversion factors for a CRS.

## Request
GET /api/crs/units/EPSG:32631

## Response
{
  "epsg_code": "EPSG:32631",
  "units": {
    "horizontal": "metre",
    "horizontal_factor": 1.0
  }
}
