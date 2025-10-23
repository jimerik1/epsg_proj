# GIGS Validation

This repository ships the IOGP GIGS v2.1 datasets under `docs/standards/GIGS_Test_Dataset_v2.1/` and a manual runner that exercises a representative subset against the API. Artifacts are JSON and HTML reports the frontend can display.

## Running

- Backend endpoint (dev): `POST /api/gigs/run` executes `tests/gigs/run_manual.py` and refreshes artifacts.
- Directly: `python3 tests/gigs/run_manual.py` writes:
  - `tests/gigs/gigs_manual_report.json`
  - `tests/gigs/gigs_manual_report.html`

Set `GIGS_REPORT_DIR` to change where the backend looks for artifacts (defaults to `tests/gigs`).

### Grids

Grid-based transformations (e.g., ETRS89→OSGB36 via OSTN15) require the corresponding grid files. The backend is configured to:

- Enable `PROJ_NETWORK=ON` (fetch grids on demand when possible)
- Use `/app/proj_data` (`PROJ_DATA`, `PROJ_LIB`, `PROJ_USER_WRITABLE_DIRECTORY`) for cache/storage

You can inspect requirements via:

- `GET /api/transform/required-grids?source_crs=EPSG:4258&target_crs=EPSG:27700`
  - Response lists the paths, the grid names, and whether they are found in the current PROJ data directories.

To vendor a grid (offline), place the file in `backend/proj_data/` and restart the backend.

You can also use:

- `backend/scripts/fetch_grids.sh` inside the backend container to pull common GB grids (OSTN15/OSGM15) into `/app/proj_data`.
- `POST /api/transform/prefetch-grids` with `{ "names": ["uk_os_OSTN15_NTv2_OSGBtoETRS.gsb"] }` to ask the backend to use `projsync` to download specific grids.

## Viewing

- Frontend: open the “GIGS Reports” tab. Features:
  - Series filter (2200/3200/5100/5200/5500/…)
  - Modal with per-case payloads, deltas, expected/actual, and endpoint/path info
  - Embedded HTML report for deep inspection
  - Run Tests and Refresh buttons; CSV export of the table

## Current Coverage

- 5100 (conversions): datasets parsed and validated using `/api/transform/direct` with dataset tolerances. Round-trip tolerances are recorded in the report.
- 5200 (transformations): selected datasets validated; support added for deterministic path selection (Helmert, Molodensky, grid). Via demos illustrate multi-leg selection.
- 5500 (wells): initial automated checks for horizontal easting/northing using BNG proxy and an inferred vertical shift when both TVD input and output are present.

## Path Selection

Deterministic pipelines are critical for some GIGS 5200 tests. Use:

- `path_id` and `preferred_ops` in `/api/transform/direct`
- `segment_path_ids` and `segment_preferred_ops` in `/api/transform/via`

Discover operations via:

- `GET /api/transform/available-paths` and `GET /api/transform/available-paths-via`

Each entry includes `accuracy`, `accuracy_unit`, `description`, and `operations_info` (EPSG method/code when known).
