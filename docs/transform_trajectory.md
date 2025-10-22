# Transform Trajectory

**Method**: `POST`  \n**URL**: `/api/transform/trajectory`

Batch transformation of trajectory points from CRS A to CRS B.

## Request
POST /api/transform/trajectory
{
  "source_crs": "EPSG:4326",
  "target_crs": "EPSG:32631",
  "trajectory_points": [
    {"id": "P1", "x": 2.2945, "y": 48.8584},
    {"id": "P2", "x": 2.2955, "y": 48.8589}
  ]
}

## Response
{
  "transformed_trajectory": [
    {"id": "P1", "x": 448249.35, "y": 5411932.67, "z": null},
    {"id": "P2", "x": 448350.02, "y": 5412033.41, "z": null}
  ],
  "units_used": {
    "source": {"horizontal": "degree"},
    "target": {"horizontal": "metre"}
  },
  "transformation_accuracy": 0.15
}
