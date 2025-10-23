# GIGS Compliance Test Framework

This folder lays out a repeatable plan for validating the CRS Transformation Platform against the GIGS test suite bundled in `docs/standards/`.

## Step-by-step plan

1. **Prepare environment**  
   - Ensure Docker stack is running so the FastAPI endpoints are reachable at `http://localhost:3001`.  
   - Confirm PROJ grids referenced by the GIGS dataset (NTv2, NADCON, etc.) are installed. List required grid files with `projinfo --dump-grids`.  
   - Export `GIGS_DATA_ROOT=docs/standards/GIGS_Test_Dataset_v2.1` so tests can resolve input files.

2. **Sanity-check CRS metadata endpoints (Series 0000/1000/2100/2200)**  
   - For each CRS listed in the `GIGS 2200 Predefined Geodetic Data Objects` directory, call:  
     - `GET /api/crs/info?code=…` to verify `is_projected`, datum, and area-of-use.  
     - `GET /api/crs/parameters?code=…` and match parameters and units to the dataset definition.  
   - Record results in the Series checklist and capture JSON responses as evidence.

3. **Validate user-defined CRS handling (Series 3100/3200)**  
   - Parse each XML/WKT definition in `GIGS 3200 User-defined Geodetic Data Objects test data`.  
   - Use `/api/crs/parse-custom` to confirm parsing matches expected components.  
   - Feed the same definition into `/api/transform/custom` using the dataset’s sample coordinates and compare outputs to the provided answers.

4. **Exercise conversion endpoints (Series 5100)**  
   - Read each ASCII file in `GIGS 5100 Conversion test data`.  
   - POST to `/api/transform/direct`, matching the dataset’s source/target CRS pair and input coordinates.  
   - Assert that results match the reference outputs within the stated tolerance (typically 1e-6 metres).  
   - For multi-step conversions, use `/api/transform/via` with the intermediate CRS chain.

5. **Exercise transformation endpoints (Series 5200)**  
   - The dataset provides separate tests for Helmert, Molodensky-Badekas, NADCON, NTv2, etc.  
   - Use `/api/transform/direct` for single-step tests and `/api/transform/via` for concatenated operations.  
   - Ensure grids such as `GIGS_tfm_5207_NTv2` resolve; if they do not, document the missing grid and skip with justification.  
   - Validate that both geographic→geocentric and 3D variants are covered by including `vertical_value` where supplied.

6. **Trajectory and local-offset comparisons (Series 5300/5400/5500)**  
   - Map `2D seismic`, `3D seismic`, and `Wells` datasets onto `/api/transform/local-offset` and `/api/transform/local-trajectory`.  
   - For each trajectory file, treat the first station as the reference point and apply the provided ENU offsets; compare both the ECEF pipeline output and the scale-factor approximation to the expected coordinates.  
   - Record discrepancies larger than the tolerance and flag for investigation.

7. **Deprecation and audit evidence (Series 6000/7000)**  
   - Document existing backend logic that flags deprecated EPSG codes (e.g., via `/api/crs/info` response metadata).  
   - Capture log samples or API responses demonstrating audit trail behaviour when transformations are requested.  
   - Update the GIGS checklist with links to the evidence.

8. **Summarise and report**  
   - Populate the `GIGS Test Series v2.1.xlsb` workbook with pass/fail, level, and references to test artefacts.  
   - Export JSON/CSV of automated test runs for record keeping.  
   - Add findings and remediation items to the project’s docs so customers can review.

## Folder layout

This directory will hold automated tests and helpers that implement the plan above:

```
tests/
└── gigs/
    ├── README.md          # This plan
    ├── conftest.py        # Shared fixtures (dataset root, HTTP client)
    ├── helpers.py         # Parsing and comparison utilities (to be implemented)
    ├── test_series_2200_predefined.py   # Metadata validation tests
    ├── test_series_3200_user_defined.py # Custom CRS tests
    ├── test_series_5100_conversions.py  # Conversion accuracy tests
    ├── test_series_5200_transformations.py
    ├── test_series_5300_seismic2d.py
    ├── test_series_5400_seismic3d.py
    └── test_series_5500_wells.py
```

Each test module starts as a scaffold with TODOs for wiring the specific GIGS datasets to our endpoints.

## Manual runner

Run `python3 tests/gigs/run_manual.py` to execute the currently automated checks and produce `tests/gigs/gigs_manual_report.html`.  The report lists each configured test, its GIGS series, and pass/fail status together with any mismatches captured during execution.

The runner now also writes `tests/gigs/gigs_manual_report.json`. Open `tests/gigs/report_app/index.html` in a browser to explore the JSON interactively—the Tailwind-based UI summarises totals and lets you drill down into each case’s payload and delta.
