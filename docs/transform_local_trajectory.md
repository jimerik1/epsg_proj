# Transform Local Trajectory

**Method**: `POST`
**URL**: `/api/transform/local-trajectory`

Apply the ECEF and/or scale-factor pipeline to an entire trajectory expressed in true ENU offsets.

## Request

### Example: Geographic reference + true-distance trajectory
Supply lon/lat for the anchor point and true ENU offsets for every survey station.

```http
POST /api/transform/local-trajectory
Content-Type: application/json
```

```json
{
  "crs": "EPSG:32040",
  "reference": {"lon": -99.2053, "lat": 29.3513, "height": 0},
  "points": [
    {"md": 0, "tvd": 0, "east": 0, "north": 0},
    {"md": 420, "tvd": 420, "east": -31.912, "north": 0.0875}
  ],
  "mode": "both"
}
```

### Example: Projected reference + true-distance trajectory
Use `x`/`y` for the reference if you already work in a grid system; offsets remain true distances.

```http
POST /api/transform/local-trajectory
Content-Type: application/json
```

```json
{
  "crs": "EPSG:32040",
  "reference": {"x": 1934594.06, "y": 551965.15, "height": 0},
  "points": [
    {"md": 0, "tvd": 0, "east": 0, "north": 0},
    {"md": 420, "tvd": 420, "east": -31.912, "north": 0.0875}
  ],
  "mode": "ecef"
}
```

## Response
```json
{
  "points": [
    {
      "index": 0,
      "ecef": {"projected": {"x": 1934594.06, "y": 551965.15}},
      "scale": {"projected": {"x": 1934594.06, "y": 551965.15}}
    },
    {
      "index": 1,
      "ecef": {"projected": {"x": 1934562.14, "y": 551985.90}},
      "scale": {"projected": {"x": 1934562.17, "y": 551985.94}},
      "difference": {"d_m": 0.05}
    }
  ]
}
```
