# Transform Direct

**Method**: `POST`
**URL**: `/api/transform/direct`

Single coordinate transformation between source and target CRS.

## Request

### Example: Geographic input (lon/lat keys)
The payload uses `lon`/`lat` because the source CRS is geographic. Unsure whether a CRS is geographic or projected? Call [`/api/crs/info`](crs_info.md) first and check the `is_geographic` / `is_projected` flags. The backend maps these fields internally before calling PROJ.

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

### Optional: Deterministic path selection
Use either a `path_id` (index from `/api/transform/available-paths`) or provide `preferred_ops` as a list of substrings to match a specific operation method/pipeline.

```json
{
  "source_crs": "EPSG:4326",
  "target_crs": "EPSG:4277",
  "position": {"lon": -3.1883, "lat": 55.9533},
  "path_id": 2,
  "preferred_ops": ["Position Vector", "NTv2"]
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
