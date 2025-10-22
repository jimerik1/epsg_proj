# Calculate Scale Factor

**Method**: `POST`  \n**URL**: `/api/calculate/scale-factor`

Return meridional/parallel/areal scale factors for a projected CRS.

## Request
POST /api/calculate/scale-factor
{
  "crs": "EPSG:32631",
  "lon": 3,
  "lat": 61
}

## Response
{
  "meridional_scale": 0.9998633,
  "parallel_scale": 0.9998633,
  "areal_scale": 0.9997266
}
