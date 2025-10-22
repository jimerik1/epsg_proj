# Local Trajectory → Geographic → Projected Workflow

This note outlines the recommended route for converting a 3D local trajectory into map coordinates without relying on grid scale approximations.

## Overview
1. **Local ENU / Wellpath** – Trajectory points are defined relative to a reference origin (e.g., wellhead) in East/North/Up metres.
2. **ECEF bridge** – Convert the reference geodetic coordinate into Earth-Centred Earth-Fixed (ECEF) XYZ. Transform local ENU offsets into ECEF deltas and add them to the origin vector. This yields absolute XYZ coordinates for every point.
3. **Back to Geodetic (WGS84 or datum CRS)** – Convert each ECEF XYZ to latitude, longitude, and ellipsoidal height in the desired datum.
4. **Projected CRS** – If required, transform those geodetic points into a map grid (e.g., State Plane, UTM) using PROJ/pyproj.

## Why this path
- **No scale-factor juggling**: 3D offsets are applied directly in Euclidean space; the projection does the heavy lifting.
- **Handles any CRS**: Works for conformal, equal-area, and custom projections without special cases.
- **Elevation-aware**: Uses ellipsoidal height, so large vertical variations don’t bias the projection.

## Using pyproj
```python
from pyproj import CRS, Transformer
import numpy as np

def enu_to_map(points_enu, ref_lat, ref_lon, ref_h, target_crs):
    """points_enu: array of [E, N, U] offsets in metres."""
    # Step 1: build transformers
    wgs84 = CRS.from_epsg(4979)  # WGS 84 3D
    ecef = CRS.from_epsg(4978)

    enu_to_ecef = Transformer.from_pipeline(
        f"+proj=enu +lat_0={ref_lat} +lon_0={ref_lon} +h_0={ref_h}"
    )
    ecef_to_geo = Transformer.from_crs(ecef, wgs84, always_xy=True)
    geo_to_target = Transformer.from_crs(wgs84, CRS.from_string(target_crs), always_xy=True)

    # Step 2: origin in ECEF
    origin_ecef = Transformer.from_crs(wgs84, ecef, always_xy=True).transform(ref_lon, ref_lat, ref_h)
    origin_ecef = np.array(origin_ecef)

    # Step 3: iterate points
    out_geo = []
    out_map = []
    for e, n, u in points_enu:
        dX, dY, dZ = enu_to_ecef.transform(e, n, u, radians=False)
        point_ecef = origin_ecef + np.array([dX, dY, dZ])
        lon, lat, h = ecef_to_geo.transform(*point_ecef)
        out_geo.append((lon, lat, h))
        x, y = geo_to_target.transform(lon, lat)
        out_map.append((x, y))
    return out_geo, out_map
```

- `+proj=enu` handles the ENU → ECEF delta using the reference origin.
- `ecef_to_geo` and `geo_to_target` handle datum and map-projection conversions.

## Notes
- If the reference datum isn’t WGS 84, supply the correct geodetic CRS (e.g., `EPSG:4267`). Replace the intermediate WGS 84 steps with the appropriate CRS.
- pyproj >= 3 supports pipelines combining geographic 3D + vertical datums; chain the vertical transformations before the final projection if needed.
- For performance, vectorise the transformations with NumPy arrays or use `Transformer.itransform` on bulk data.

## Validation
1. Verify that a zero-length offset returns the original projected coordinate.
2. Compare against authoritative software for known trajectories; residuals should drop to centimetres (limited by CRS accuracy) even in high-distortion areas.
3. Document the datum/ellipsoid used for the ENU frame; mixing datums introduces metre-level errors.

### Worked Examples

- **UTM Zone 31N (EPSG:32631)** – Offsetting 10 km east and north from E 500 000 m, N 6 800 000 m yields only ~1.8 cm difference between the ECEF pipeline and the scale-factor shortcut. Transverse Mercator is conformal, so meridional and parallel scales match and the approximation behaves well.
- **NAD83 / Quebec Lambert (EPSG:3175)** – The same 10 km × 10 km step produces a ~14.5 km separation (ΔX ≈ −13.8 km, ΔY ≈ 4.3 km) and ~15.1 km of geographic drift. Albers equal-area is non-conformal; meridional and parallel scale factors differ by ~10%, so the simple scaling approach fails dramatically.

### API Support
- `POST /api/transform/local-offset` converts a single true-distance offset from a reference point using both the ECEF pipeline and the scale-factor approximation.
- `POST /api/transform/local-trajectory` accepts an entire trajectory (easting/northing/TVD offsets) and returns per-station projected and geographic coordinates for the requested mode (`ecef`, `scale`, or `both`).
