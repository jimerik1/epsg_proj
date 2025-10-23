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
- Series 5100 (conversions)
  - Status: green for all currently wired datasets with dataset tolerances.
  - Action: keep green; no special work beyond regression checks.
- Series 5200 (transformations)
  - Status: green for `tfm-5201` (Geog↔Geocen), `tfm-5204` (Coord Frame), `tfm-5206` (NADCON), `tfm-5208` (Longitude rotation).
  - TODOs to green remaining tests:
    - `tfm-5203` (Position Vector): pin explicit PV Helmert pipeline and test sign conventions.
    - `tfm-5205` (Molodensky‑Badekas): ensure pivot point/rounding matches EPSG; pin operation.
    - `tfm-5207` (NTv2): verify grids are present; choose grid-based path deterministically; document grid set.
    - `tfm-5213` (Geo 2D three‑translation): select Abridged Molodensky/concatenated path per dataset.
  - `tfm-5209`–`tfm-5212`: require bin-grid/user-defined CRS; schedule after above.
- Series 5500 (wells)
  - Status: significant improvement — horizontal via 4326→4258→27700 with OSTN15 preference; vertical via dedicated endpoint using dataset vertical EPSG; grids bundled in image; checklist shows presence.
  - TODOs to green:
    - Confirm vertical EPSG detection for all 55xx; add fallback mapping where headers omit codes.
    - Ensure OSTN15/OSGM15 present (now bundled; keep checklist green); add any extra grids if datasets require them.
    - Tighten tolerance usage per dataset (if specific vertical tolerances are stated).

## What’s Missing Backend-Side
1. Transformation Pipelines
   - Curated PROJ pipelines and deterministic selection for 5203/5205/5207/5213.
2. User-Defined CRS / Bin Grid
   - Minimal loader for bin-grid/seismic CRS + ephemeral registration to unlock `tfm-5209`–`tfm-5212`.
3. Vertical Transformations
   - DONE: `/api/transform/vertical` endpoint. Next: expand vertical CRS mapping for 5500 and add any required geoid grids.

## Way Forward to Full GIGS Support (5100/5200/5500)
1. Series 5100 – keep green
   - Track regressions in CI; no additional work required.
2. Series 5200 – targeted pipeline pinning
   - 5203 PV: PV Helmert; verify sign conventions; add `preferred_ops` hints and record `path_id`.
   - 5205 Molodensky‑Badekas: pin MB with correct pivot; align rounding.
   - 5207 NTv2: confirm grid presence (checklist); pin grid path.
   - 5213 Geo 2D three‑translation: select Abridged Molodensky/concatenated chains per dataset.
   - Document and bundle any additional grids used.
3. Series 5500 – wells to green
   - Confirm vertical EPSG extraction for all files; add fallback mapping list where missing.
   - Keep grid checklist green (OSTN15/OSGM15 now bundled; add others as needed).
   - Use `/api/transform/vertical` for TVD; mark pass/fail against dataset vertical tolerances when available (fallback to cartesian).
   - Add optional local-trajectory validations using `/api/transform/local-trajectory` where datasets align.
4. CI Automation
   - Run GIGS runner in CI; attach JSON/HTML artifacts; fail on regressions for 5100/5200-required/5500.
5. Frontend/UX
   - Deep link to Transform Via (DONE) and show grids/vertical info for failing cases; keep tolerance highlight badges; optional per-series summary banners.

## Useful Files & Commands
- Manual harness: `python3 tests/gigs/run_manual.py`
- Reports: `tests/gigs/gigs_manual_report.html`, `tests/gigs/gigs_manual_report.json`
- Frontend viewer: GIGS Reports tab; includes Run/Refresh/CSV and details modal
- Backend endpoints: `/api/gigs/report`, `/api/gigs/report/html`, `/api/gigs/run`
- Reference datasets: `docs/standards/GIGS_Test_Dataset_v2.1/`
 - Grids: `/api/transform/required-grids`, `/api/transform/prefetch-grids`, `backend/scripts/fetch_grids.sh` (OSTN15/OSGM15)

Keep this file in sync when new datasets or backend features land so the next Codex session can pick up instantly.
