# Project Status – October 2025 (updated)

## Where Things Stand
- Backend & Frontend
  - Deterministic path selection for transforms (direct: `path_id`, `preferred_ops`; via: `segment_path_ids`, `segment_preferred_ops`).
  - “Transform Via” supports multi-hop paths, leg-wise path picking, via suggestions, and quick testing of individual legs.
  - Styling upgraded to Tailwind across pages; consistent inputs/buttons; new “GIGS Reports” and “Docs” pages.
- GIGS Harness
  - Series 5100 conversions validated with dataset tolerances.
  - Series 5200: selected datasets validated; via-demo added for path selection; UI shows per-case payload/expected/actual/delta + endpoint/crs path.
  - Series 5500: dynamic wells tests (horizontal easting/northing via BNG proxy) and inferred vertical shift validation where TVD present.
  - Artifacts served via backend (`/api/gigs/report`, `/api/gigs/report/html`) and can be regenerated from UI (`POST /api/gigs/run`).
- Docs
  - README and `docs/gigs.md` describe the runner, reports, and path-selection features. Frontend “Docs” page embeds report and renders docs/readme.

## Test Coverage Snapshot
- Pass: Series 5100, Series 5200 tests `tfm-5201`, `tfm-5204`, `tfm-5206`, `tfm-5208` align with GIGS reference values.
- New: Series 5500 wells – initial validations for multiple datasets (horizontal via BNG proxy; inferred vertical validation when TVD available).
- Skip (pending features): `tfm-5209`–`tfm-5212` require user-defined CRS/bin-grid; more complete vertical datum pipelines for wells.
- Needs deterministic/backend capability:
  - `tfm-5203` Position Vector (EPSG 1037) – select explicit Helmert PV pipeline and verify sign conventions.
  - `tfm-5205` Molodensky‑Badekas – ensure pivot and rounding match EPSG; pin operation.
  - `tfm-5207` NTv2 – ensure grids load and the chosen transformer uses them; document required grid set.
  - `tfm-5213` Geo 2D three‑translation – prefer Abridged Molodensky or concatenated pipelines per dataset.

## What’s Missing Backend-Side
1. Transformation Pipelines
   - Provide curated PROJ pipelines for GIGS transforms (Helmert PV/CF, MB, grid/NADCON/NTv2) and select them deterministically.
2. User-Defined CRS / Bin Grid
   - Minimal support for GIGS binary grid & seismic CRS so `tfm-5209`–`tfm-5212` can run; consider ephemeral CRS registration API.
3. Vertical Transformations
   - True vertical datum transformations (ellipsoidal ↔ chart/sounding depth) using PROJ where definitions exist; remove reliance on inferred TVD shifts.

## Next Steps
1. Address failing Series 5200 datasets
   - Curate PV/MB/NTv2/NADCON pipelines and pin via `preferred_ops`/`path_id`; record choices in report.
   - Ensure required grids are present; document list and location.
2. Implement user-defined CRS / bin-grid
   - Minimal loader + ephemeral registration to unlock `tfm-5209`–`tfm-5212`.
3. Expand 5500 coverage
   - Parse all ASCII inputs, validate horizontal + vertical (prefer real vertical transform when available).
   - Add trajectory-style checks via `/api/transform/local-trajectory` where appropriate.
4. Automation & CI
   - Optionally run the GIGS runner in CI and publish artifacts; fail on regressions for required series.
5. Frontend enhancements
   - Deep link from a failing case to the “Transform Via” page prefilled with the same parameters.
   - Optional: highlight deltas that exceed per-test tolerances directly in the modal.

## Useful Files & Commands
- Manual harness: `python3 tests/gigs/run_manual.py`
- Reports: `tests/gigs/gigs_manual_report.html`, `tests/gigs/gigs_manual_report.json`
- Frontend viewer: GIGS Reports tab; includes Run/Refresh/CSV and details modal
- Backend endpoints: `/api/gigs/report`, `/api/gigs/report/html`, `/api/gigs/run`
- Reference datasets: `docs/standards/GIGS_Test_Dataset_v2.1/`

Keep this file in sync when new datasets or backend features land so the next Codex session can pick up instantly.
