# Calculate Scale Factor

**Method**: `POST`
**URL**: `/api/calculate/scale-factor`

Return meridional/parallel/areal scale factors for a projected CRS.

## Request
```http
POST /api/calculate/scale-factor
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
  "meridional_scale": 0.9998633,
  "parallel_scale": 0.9998633,
  "areal_scale": 0.9997266
}
```
