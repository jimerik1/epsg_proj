CRS Transformation Platform (PyProj + FastAPI + React)

Overview
- Cloud-ready backend + frontend stack for high-accuracy coordinate transforms (including custom CRS definitions and local trajectory handling).
- Backend exposes FastAPI endpoints powered by PyProj/PROJ 9.x; frontend React UI visualises and validates results.
- Supports ECEF-based local offsets, EPSG lookups, custom CRS parsing/matching, grid factors, and projected/geodetic analytics.
- Docker-first workflow: `docker-compose up --build` brings up backend, frontend, and Redis.

Quick Start
- Requirements: Docker + Docker Compose with network access for grid downloads.
- Run: `docker-compose up --build`
- Backend: http://localhost:3001 (FastAPI/OpenAPI at `/docs`)
- Frontend: http://localhost:3000

Environment
- Backend enables `PROJ_NETWORK=ON` to fetch grids on the fly.
- Redis (optional caching) exposed as `redis:6379` inside the compose network.

Development Notes
- Hot reload via bind mounts for both backend and frontend containers.
- Python deps in `backend/requirements.txt`; Node deps in `frontend/package.json`.

Testing
- Example PyProj smoke test in `backend/tests/test_transformations.py`.
- Run inside backend container: `pytest -q`.

API Reference (summary – see `docs/` for full details)

| Endpoint | Method | Description |
| --- | --- | --- |
| [`/api/transform/direct`](docs/transform_direct.md) | POST | Transform single position from source CRS to target CRS. |
| [`/api/transform/trajectory`](docs/transform_trajectory.md) | POST | Bulk transform a trajectory between two CRS. |
| [`/api/transform/via`](docs/transform_via.md) | POST | Step through a user-defined CRS path (A → B → C). |
| [`/api/transform/custom`](docs/transform_custom.md) | POST | Transform using a custom CRS supplied as XML. |
| [`/api/transform/local-offset`](docs/transform_local_offset.md) | POST | Apply ECEF + scale-factor comparison for a single ENU offset. |
| [`/api/transform/local-trajectory`](docs/transform_local_trajectory.md) | POST | Apply ECEF/scale pipelines to an entire trajectory. |
| [`/api/crs/info`](docs/crs_info.md) | GET | Retrieve CRS metadata (datum, ellipsoid, axes). |
| [`/api/crs/units`](docs/crs_units.md) | GET | Fetch axis units and conversion factors. |
| [`/api/crs/search`](docs/crs_search.md) | GET | Search CRS definitions by text, AOI, or type. |
| [`/api/crs/parameters`](docs/crs_parameters.md) | GET | Inspect projection parameters for a CRS. |
| [`/api/crs/match`](docs/crs_match.md) | POST | Score best EPSG matches for custom XML definitions. |
| [`/api/crs/parse-custom`](docs/crs_parse_custom.md) | POST | Parse XML into PROJ string and summarised metadata. |
| [`/api/calculate/grid-convergence`](docs/calc_grid_convergence.md) | POST | Compute meridian convergence at a location. |
| [`/api/calculate/scale-factor`](docs/calc_scale_factor.md) | POST | Return meridional/parallel/areal scale factors. |

