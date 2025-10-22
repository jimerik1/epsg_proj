# Transform Direct

**Method**: `POST`
**URL**: `/api/transform/direct`

Single coordinate transformation between source and target CRS.

## Request

### Example: Geographic input (lon/lat keys)
The payload uses `lon`/`lat` because the source CRS is geographic. The backend maps these fields internally before calling PROJ.

```http
POST /api/transform/direct
Content-Type: application/json
```

```json
{
  "source_crs": "EPSG:4326",
  "target_crs": "EPSG:32631",
  "position": {"lon": 2.2945, "lat": 48.8584},
  "vertical_value": null
}
```

### Example: Projected input (x/y keys)
When the source CRS is projected, send `x`/`y` (easting/northing or similar). The same endpoint handles the conversion.

```http
POST /api/transform/direct
Content-Type: application/json
```

```json
{
  "source_crs": "EPSG:32631",
  "target_crs": "EPSG:4326",
  "position": {"x": 448249.35, "y": 5411932.67}
}
```

## Response
```json
{
  "map_position": {"x": 448249.35, "y": 5411932.67},
  "vertical_output": null,
  "units_used": {
    "source": {"horizontal": "degree", "horizontal_factor": 0.017453292519943295},
    "target": {"horizontal": "metre", "horizontal_factor": 1.0}
  },
  "transformation_accuracy": 0.0001,
  "grid_convergence": 0.999,
  "scale_factor": {
    "meridional_scale": 0.9996,
    "parallel_scale": 0.9996,
    "areal_scale": 0.9992
  }
}
```
