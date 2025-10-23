# Available Paths (Via)

Method: `GET`
URL: `/api/transform/available-paths-via`

Return the list of available transformation paths for each leg of a via transform: `source → via` and `via → target`.

## Query Parameters
- `source_crs`: CRS code/string for the source (e.g., `EPSG:4326`).
- `via_crs`: Intermediate CRS code/string.
- `target_crs`: Final CRS code/string.

## Example
```
GET /api/transform/available-paths-via?source_crs=EPSG:4326&via_crs=EPSG:4277&target_crs=EPSG:27700
```

## Response
```json
{
  "source_crs": "EPSG:4326",
  "via_crs": "EPSG:4277",
  "target_crs": "EPSG:27700",
  "leg1_paths": [
    {
      "path_id": 0,
      "description": "...",
      "accuracy": 0.0,
      "accuracy_unit": "meter",
      "operations": ["..."],
      "operations_info": [
        { "method_name": "Position Vector", "authority": "EPSG", "code": "1037" }
      ]
    }
  ],
  "leg2_paths": [
    {
      "path_id": 0,
      "description": "...",
      "accuracy": 0.0,
      "accuracy_unit": "meter",
      "operations": ["..."],
      "operations_info": [
        { "method_name": "NTv2", "authority": "EPSG", "code": "9615" }
      ]
    }
  ]
}
```

Use the returned `path_id` values with `segment_path_ids` in [`/api/transform/via`](transform_via.md) to select a deterministic path for each leg.
