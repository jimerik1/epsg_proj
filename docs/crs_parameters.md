# CRS Parameters

**Method**: `GET`  \n**URL**: `/api/crs/parameters`

Return key projection parameters (method, standard parallels, etc.).

## Request
GET /api/crs/parameters?code=EPSG:23031

## Response
{
  "method": "Transverse Mercator",
  "parameters": {
    "false_easting": {"value": 500000.0, "unit": "metre"},
    "false_northing": {"value": 0.0, "unit": "metre"},
    "scale_factor": {"value": 0.9996, "unit": "unity"},
    "central_meridian": {"value": 3.0, "unit": "degree"}
  }
}
