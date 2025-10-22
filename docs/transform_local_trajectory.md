# Transform Local Trajectory

**Method**: `POST`  \n**URL**: `/api/transform/local-trajectory`

Apply the ECEF and/or scale-factor pipeline to an entire trajectory expressed in true ENU offsets.

## Request
POST /api/transform/local-trajectory
{
  "crs": "EPSG:32040",
  "reference": {"lon": -99.2053, "lat": 29.3513, "height": 0},
  "points": [
    {"md": 0, "tvd": 0, "east": 0, "north": 0},
    {"md": 420, "tvd": 420, "east": -31.912, "north": 0.0875}
  ],
  "mode": "both"
}

## Response
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
