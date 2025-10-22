# Calculate Grid Convergence

**Method**: `POST`
**URL**: `/api/calculate/grid-convergence`

Compute meridian convergence at a location for a projected CRS.

## Request
```http
POST /api/calculate/grid-convergence
Content-Type: application/json
```

```json
{
  "crs": "EPSG:32631",
  "lon": 3,
  "lat": 61
}
```

## Response
```json
{
  "meridian_convergence": -0.1004
}
```
