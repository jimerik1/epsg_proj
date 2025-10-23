# Project Status – October 2025

## Where Things Stand
- **Backend & Frontend**: Core CRS matching, transformation, custom CRS, and local-offset comparison pages are live. Map plotting, tooltip help, and multi-tab custom CRS builders are in place.
- **GIGS Harness**: Manual runner exercises Series 5100 conversions and Series 5200 transformations. Reports (HTML + JSON + Tailwind viewer) capture tolerances, payloads, and per-row deltas.
- **Docs**: README lists all API endpoints with per-endpoint markdown in `docs/`. Geodetic workflow notes live in `epsg_proj/geodetic_workflow.md`.

## Test Coverage Snapshot
- **Pass**: Series 5100, Series 5200 tests `tfm-5201`, `tfm-5204`, `tfm-5206`, `tfm-5208` align with GIGS reference values.
- **Skip (pending features)**: `tfm-5209`–`tfm-5212` require user-defined CRS/bin-grid support. Local offset (Series 5300/5400/5500) parser not implemented.
- **Fail (needs backend capability)**:
  - `tfm-5203` Position Vector (EPSG 1037) – API returns identity; needs proper 7-parameter WGS84↔OSGB36 pipeline.
  - `tfm-5205` Molodensky-Badekas – centimetre-level deltas; likely pipeline/rounding mismatch.
  - `tfm-5207` NTv2 – grid application missing (values come back unshifted).
  - `tfm-5213` Geo 2D three-translation – API cannot reproduce EPSG concatenated/Abridged Molodensky outputs.

## What’s Missing Backend-Side
1. **Transformation Pipelines**
   - Ship explicit PROJ pipelines or notebooks that match GIGS definitions (e.g. OSGB36 ↔ WGS84 via Helmert params, NTv2 grid loading).
   - Ensure `/api/transform/direct` selects the same path the tests expect (maybe via `preferred_ops`).
2. **User-Defined CRS / Bin Grid**
   - Implement minimal support for GIGS “bin grid” & seismic CRS definitions so Series 5209–5212 can run (likely separate endpoint or expanded parsing).
3. **Series 5300/5400/5500 Parser**
   - Build data loaders for the seismic & well ASCII/P-files, reuse helper scaffolds, and extend the manual runner.

## Next Possible Steps
1. **Address failing Series 5200 datasets**
   - Load required grid files (NTv2, NADCON) and configure PROJ data path.
   - Add deterministic pipeline selection (pyproj `TransformerGroup`, custom operation choice).
2. **Implement user-defined CRS handling**
   - Parse P6/P111 bin-grid configurations; expose API to register these temporary CRSs.
   - Update `/api/transform/direct` to accept session-specific CRS definitions.
3. **Complete remaining GIGS suites**
   - Parser + harness for Series 3200 (user-defined) using metadata already in repo.
   - Implement 5300/5400/5500 local-offset/trajectory comparisons (hooks already stubbed).
4. **Automation & CI**
   - Convert manual runner into pytest-integrated suite; optionally add GitHub Actions job that spins up backend and posts the HTML/JSON artifacts.
5. **Frontend Enhancements**
   - Surface failing/passing GIGS stats inside the Tailwind report app.
   - Add UI toggles for choosing PROJ pipelines (once backend supports them).

## Useful Files & Commands
- Manual harness: `python3 tests/gigs/run_manual.py`
- Reports: `tests/gigs/gigs_manual_report.html`, `tests/gigs/gigs_manual_report.json`, `tests/gigs/report_app/index.html`
- Reference datasets: `docs/standards/GIGS_Test_Dataset_v2.1/`

Keep this file in sync when new datasets or backend features land so the next Codex session can pick up instantly.
