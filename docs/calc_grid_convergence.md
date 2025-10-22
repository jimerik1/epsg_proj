# Calculate Grid Convergence

**Method**: `POST`  \n**URL**: `/api/calculate/grid-convergence`

Compute meridian convergence at a location for a projected CRS.

## Request
POST /api/calculate/grid-convergence
{
  "crs": "EPSG:32631",
  "lon": 3,
  "lat": 61
}

## Response
{
  "meridian_convergence": -0.1004
}
