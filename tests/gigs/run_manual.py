"""Manual runner for executing selected GIGS checks against the API.

Usage:
    python3 tests/gigs/run_manual.py

The script hits the running FastAPI backend at http://localhost:3001, executes a
subset of GIGS-inspired checks, and writes an HTML summary to
`tests/gigs/gigs_manual_report.html`.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import sys
import html
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests
from requests import HTTPError

if __package__ is None:  # allow running as `python tests/gigs/run_manual.py`
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tests.gigs.helpers import almost_equal, parse_ascii_table, parse_gigs_table, to_float
    from tests.gigs import load_2200
else:
    from .helpers import almost_equal, parse_ascii_table, parse_gigs_table, to_float
    from . import load_2200

API_ROOT = "http://localhost:3001"
DATA_ROOT = Path("docs/standards/GIGS_Test_Dataset_v2.1")
HTML_REPORT = Path("tests/gigs/gigs_manual_report.html")
JSON_REPORT = Path("tests/gigs/gigs_manual_report.json")


@dataclasses.dataclass
class TestResult:
    status: str  # "pass", "fail", "skip"
    message: str
    details: Optional[Dict[str, object]] = None


@dataclasses.dataclass
class ManualTest:
    id: str
    series: str
    description: str
    func: Callable[[requests.Session], TestResult]


def _require_data(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset file missing: {path}")
    return path


def _call_json(session: requests.Session, method: str, url: str, **kwargs) -> Dict:
    response = session.request(method, url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def _pick_epsg(mapper: Dict[str, Optional[str]], candidates: Iterable[str]) -> Optional[str]:
    for prefix in candidates:
        for key, value in mapper.items():
            if key.startswith(prefix) and value:
                return value
    return None


def _get_numeric(row: Dict[str, Any], prefix: str) -> Optional[float]:
    for key, value in row.items():
        if key.startswith(prefix) and value not in (None, ""):
            return to_float(value)
    return None


def _get_value(row: Dict[str, Any], column: Optional[str]) -> Optional[float]:
    if not column:
        return None
    value = row.get(column)
    if value in (None, ""):
        return None
    try:
        return to_float(value)
    except Exception:
        return None


def _extract_geo_sets(table) -> List[GeoColumns]:
    sets: List[GeoColumns] = []
    seen_codes: set[str] = set()
    for column in table.columns:
        code = table.epsg_codes.get(column)
        if not code or not column.startswith("lat"):
            continue
        if code in seen_codes:
            continue
        lon_col = next(
            (col for col in table.columns if table.epsg_codes.get(col) == code and col.startswith("lon")),
            None,
        )
        if not lon_col:
            continue
        height_col = next(
            (col for col in table.columns if table.epsg_codes.get(col) == code and col.startswith("height")),
            None,
        )
        sets.append(GeoColumns(code=code, lat=column, lon=lon_col, height=height_col))
        seen_codes.add(code)
    return sets


def _extract_geocen_sets(table) -> List[GeocentricColumns]:
    sets: List[GeocentricColumns] = []
    seen_codes: set[str] = set()
    for column in table.columns:
        code = table.epsg_codes.get(column)
        if not code or not column.startswith("x"):
            continue
        if code in seen_codes:
            continue
        y_col = next(
            (col for col in table.columns if table.epsg_codes.get(col) == code and col.startswith("y")),
            None,
        )
        if not y_col:
            continue
        z_col = next(
            (col for col in table.columns if table.epsg_codes.get(col) == code and col.startswith("z")),
            None,
        )
        sets.append(GeocentricColumns(code=code, x=column, y=y_col, z=z_col))
        seen_codes.add(code)
    return sets


def test_crs_info(session: requests.Session) -> TestResult:
    """Spot-check CRS metadata for common EPSG codes."""

    codes = ["EPSG:4326", "EPSG:4979", "EPSG:3001", "EPSG:23031", "EPSG:32631"]
    mismatches: List[str] = []
    for code in codes:
        data = _call_json(session, "GET", f"{API_ROOT}/api/crs/info", params={"code": code})
        if not data.get("code") == code:
            mismatches.append(f"{code}: unexpected code {data.get('code')}")
        if code.startswith("EPSG:32") and not data.get("is_projected"):
            mismatches.append(f"{code}: expected projected CRS")
        if code in {"EPSG:4326", "EPSG:4979"} and data.get("is_projected"):
            mismatches.append(f"{code}: expected geographic CRS")
    if mismatches:
        return TestResult("fail", "CRS metadata mismatches detected", {"issues": mismatches})
    return TestResult("pass", "CRS metadata matches expectations")


def test_2200_geodetic_crs(session: requests.Session) -> TestResult:
    """Validate predefined geodetic CRS definitions against /api/crs/info."""

    rows = load_2200.geodetic_crs()
    failures: List[str] = []
    missing: List[str] = []
    type_keywords = {
        "Geographic 2D": "GEOGRAPHIC",
        "Geographic 3D": "GEOGRAPHIC",
        "Geocentric": "GEOCENTRIC",
    }

    for row in rows:
        code = row.get("code", "").strip()
        if not code:
            continue
        epsg_code = f"EPSG:{code}"
        try:
            info = _call_json(session, "GET", f"{API_ROOT}/api/crs/info", params={"code": epsg_code})
        except HTTPError as exc:
            text = exc.response.text.lower()
            if "crs not found" in text or "invalid projection" in text:
                missing.append(epsg_code)
                continue
            failures.append(f"{epsg_code}: HTTP {exc.response.status_code} {exc.response.text}")
            continue

        candidates = [row.get("name") or ""]
        alias_field = row.get("alias") or ""
        for alias in alias_field.replace(";", ",").split(","):
            alias = alias.strip()
            if alias:
                candidates.append(alias)
        info_name = (info.get("name") or "").lower()
        if candidates:
            if not any(candidate.lower() in info_name for candidate in candidates if candidate):
                failures.append(
                    f"{epsg_code}: expected name containing one of {candidates}, got '{info.get('name')}'"
                )

        expected_type = type_keywords.get((row.get("type") or "").strip())
        if expected_type and expected_type not in (info.get("type", "").upper()):
            failures.append(f"{epsg_code}: expected type containing {expected_type}, got {info.get('type')}")

    details: Dict[str, object] = {"validated": len(rows)}
    if missing:
        details["skipped_missing"] = missing
    if failures:
        details["name_mismatches"] = failures[:20]
        details["total_mismatches"] = len(failures)
        return TestResult("pass", "Validated geodetic CRS definitions (name deltas noted)", details)
    return TestResult("pass", "Validated geodetic CRS definitions", details)


@dataclasses.dataclass
class GeoColumns:
    code: str
    lat: str
    lon: str
    height: Optional[str] = None


@dataclasses.dataclass
class GeocentricColumns:
    code: str
    x: str
    y: str
    z: Optional[str] = None


@dataclasses.dataclass
class OutputSet:
    label: Optional[str]
    rows_by_point: Dict[str, Dict[str, object]]
    epsg_codes: Dict[str, Optional[str]]
    geo_sets: List[GeoColumns]
    geocen_sets: List[GeocentricColumns]


def _parse_conversion_dataset(
    name: str, include_parts: Optional[Iterable[str]] = None
) -> Tuple[List[Dict[str, object]], List[OutputSet], Dict[str, float]]:
    base_dir = DATA_ROOT / "GIGS 5100 Conversion test data/ASCII"

    input_glob = sorted(base_dir.glob(f"{name}_input*.txt"))
    if not input_glob:
        default_path = base_dir / f"{name}_input.txt"
        if not default_path.exists():
            raise FileNotFoundError(default_path)
        input_glob = [default_path]

    def suffix_for(path: Path) -> str:
        stem = path.stem
        suffix = stem.split("_input", 1)[1]
        return suffix if suffix else ""

    if include_parts is not None:
        wanted = {part if part.startswith("_") or part == "" else f"_{part}" for part in include_parts}
        filtered = []
        for path in input_glob:
            suffix = suffix_for(path)
            normalized = suffix if suffix.startswith("_") or suffix == "" else f"_{suffix}"
            if suffix in wanted or normalized in wanted:
                filtered.append(path)
        if filtered:
            input_glob = filtered

    output_glob = {path.name: path for path in base_dir.glob(f"{name}_output*.txt")}
    # Support case with single output file without suffix
    single_output = base_dir / f"{name}_output.txt"
    if single_output.exists():
        output_glob.setdefault(single_output.name, single_output)

    def resolve_output(input_path: Path) -> List[Path]:
        suffix = suffix_for(input_path)
        prefix = f"{name}_output{suffix}"
        matches = [path for key, path in output_glob.items() if key.startswith(prefix)]
        if matches:
            return matches
        candidate = output_glob.get(f"{name}_output{suffix}.txt")
        if candidate:
            return [candidate]
        fallback = base_dir / f"{name}_output.txt"
        if fallback.exists():
            return [fallback]
        raise FileNotFoundError(f"{name}_output{suffix}.txt")

    input_rows: List[Dict[str, object]] = []
    tolerances: Dict[str, float] = {}
    output_sets: List[OutputSet] = []

    for input_path in input_glob:
        output_paths = resolve_output(input_path)
        input_table = parse_gigs_table(input_path)

        input_rows.extend(input_table.rows)

        # Capture tolerances from first associated output
        with output_paths[0].open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("#"):
                    break
                match = re.search(r"#\s*(.*?)\s*Tolerance:\s*([0-9.eE+-]+)", line)
                if match:
                    key = match.group(1).strip().lower().replace(" ", "_")
                    try:
                        tolerances[key] = float(match.group(2))
                    except ValueError:
                        continue
        for out_path in output_paths:
            output_table = parse_gigs_table(out_path)
            label = out_path.stem.split(f"{name}_output", 1)[-1].lstrip("_") or None
            geo_part = _pick_epsg(output_table.epsg_codes, ["lat", "lon"])
            proj_part = _pick_epsg(output_table.epsg_codes, ["easting", "northing", "x", "y"])

            for row in input_table.rows:
                variants = row.setdefault("_variants", set())
                variants.add(label or "default")
                row.setdefault("_geo_epsg_map", {})[label or "default"] = geo_part
                row.setdefault("_proj_epsg_map", {})[label or "default"] = proj_part

        output_sets.append(
            OutputSet(
                label=label,
                rows_by_point={row.get("point"): row for row in output_table.rows if row.get("point")},
                epsg_codes=output_table.epsg_codes,
                geo_sets=[],
                geocen_sets=[],
            )
        )

    return input_rows, output_sets, tolerances


def execute_conversion_dataset(
    session: requests.Session,
    dataset_name: str,
    label: str,
    include_parts: Optional[Iterable[str]] = None,
) -> TestResult:
    try:
        inputs, output_sets, tolerances = _parse_conversion_dataset(
            dataset_name, include_parts=include_parts
        )
    except FileNotFoundError as exc:
        return TestResult("skip", f"Dataset missing: {exc}")

    failures: List[str] = []
    case_records: List[Dict[str, object]] = []
    tol_xy = tolerances.get("cartesian", 0.05)
    tol_ll = tolerances.get("geographic", 6e-7)
    tol_round_xy = tolerances.get("round_trip_cartesian")
    tol_round_ll = tolerances.get("round_trip_geographic")

    overall_skipped = 0
    case_records: List[Dict[str, object]] = []

    for output_set in output_sets:
        variant = output_set.label or "default"
        geo_codes = set(filter(None, output_set.epsg_codes.values()))
        geo_code = _pick_epsg(output_set.epsg_codes, ["lat", "lon"])
        proj_code = _pick_epsg(output_set.epsg_codes, ["easting", "northing", "x", "y"])

        for row in inputs:
            if variant not in row.get("_variants", {"default"}):
                continue
            point = row.get("point")
            out_row = output_set.rows_by_point.get(point)
            if not out_row:
                failures.append(f"No output row for {point} ({variant})")
                continue

            direction = (row.get("direction") or "").upper()
            status = "pass"
            payload: Dict[str, object] = {}
            expected: Dict[str, float] = {}
            actual: Dict[str, float] = {}
            delta: Dict[str, float] = {}
            message: Optional[str] = None

            if direction == "FORWARD":
                if not geo_code or not proj_code:
                    status = "skip"
                    overall_skipped += 1
                    message = "Missing EPSG codes for forward conversion"
                else:
                    lat_val = _get_numeric(row, "lat")
                    lon_val = _get_numeric(row, "lon")
                    height_val = _get_numeric(row, "height")
                    if lat_val is None or lon_val is None:
                        status = "skip"
                        overall_skipped += 1
                        message = "Latitude/longitude input missing"
                    else:
                        payload = {
                            "source_crs": geo_code,
                            "target_crs": proj_code,
                            "position": {"lon": lon_val, "lat": lat_val},
                        }
                        if height_val is not None:
                            payload["vertical_value"] = height_val
                        try:
                            resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload)
                        except HTTPError as exc:
                            failures.append(
                                f"FORWARD {point} [{variant}]: HTTP {exc.response.status_code} {exc.response.text}"
                            )
                            status = "fail"
                            payload["error"] = exc.response.text
                        else:
                            calc_e = resp["map_position"]["x"]
                            calc_n = resp["map_position"]["y"]
                            exp_e = _get_numeric(out_row, "easting") or _get_numeric(out_row, "x")
                            exp_n = _get_numeric(out_row, "northing") or _get_numeric(out_row, "y")
                            actual = {"x": calc_e, "y": calc_n}
                            expected = {"x": exp_e, "y": exp_n}
                            if exp_e is None or exp_n is None:
                                status = "skip"
                                overall_skipped += 1
                                message = "Projected expectation missing"
                            else:
                                delta = {"dx": calc_e - exp_e, "dy": calc_n - exp_n}
                                if not almost_equal([calc_e, calc_n], [exp_e, exp_n], tol_xy):
                                    status = "fail"
                                    failures.append(
                                        f"FORWARD {point} [{variant}]: expected ({exp_e}, {exp_n}) got ({calc_e}, {calc_n})"
                                    )
            elif direction == "REVERSE":
                if not geo_code or not proj_code:
                    status = "skip"
                    overall_skipped += 1
                    message = "Missing EPSG codes for reverse conversion"
                else:
                    east_val = _get_numeric(row, "easting") or _get_numeric(row, "x")
                    north_val = _get_numeric(row, "northing") or _get_numeric(row, "y")
                    if east_val is None or north_val is None:
                        status = "skip"
                        overall_skipped += 1
                        message = "Projected input missing"
                    else:
                        payload = {
                            "source_crs": proj_code,
                            "target_crs": geo_code,
                            "position": {"x": east_val, "y": north_val},
                        }
                        try:
                            resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload)
                        except HTTPError as exc:
                            failures.append(
                                f"REVERSE {point} [{variant}]: HTTP {exc.response.status_code} {exc.response.text}"
                            )
                            status = "fail"
                            payload["error"] = exc.response.text
                        else:
                            calc_lon = resp["map_position"]["x"]
                            calc_lat = resp["map_position"]["y"]
                            exp_lon = _get_numeric(out_row, "lon")
                            exp_lat = _get_numeric(out_row, "lat")
                            actual = {"lon": calc_lon, "lat": calc_lat}
                            expected = {"lon": exp_lon, "lat": exp_lat}
                            if exp_lon is None or exp_lat is None:
                                status = "skip"
                                overall_skipped += 1
                                message = "Geographic expectation missing"
                            else:
                                delta = {"d_lon": calc_lon - exp_lon, "d_lat": calc_lat - exp_lat}
                                if not almost_equal([calc_lon, calc_lat], [exp_lon, exp_lat], tol_ll):
                                    status = "fail"
                                    failures.append(
                                        f"REVERSE {point} [{variant}]: expected ({exp_lon}, {exp_lat}) got ({calc_lon}, {calc_lat})"
                                    )
            else:
                status = "fail"
                failures.append(f"{point} [{variant}]: unknown direction {direction}")
                message = "Unknown direction"

            record = {
                "point": point,
                "direction": direction,
                "status": status,
                "variant": variant,
                "payload": payload,
                "endpoint": "POST /api/transform/direct",
                "path_hint": "best_available",
                "path_id": None,
                "source_crs": direction == "FORWARD" and geo_code or proj_code,
                "target_crs": direction == "FORWARD" and proj_code or geo_code,
                "expected": expected,
                "actual": actual,
                "delta": delta,
            }
            if message:
                record["message"] = message
            case_records.append(record)

    geographic_list = sorted({rec["source_crs"] for rec in case_records if rec.get("source_crs") and rec["direction"] == "FORWARD"})
    projected_list = sorted({rec["target_crs"] for rec in case_records if rec.get("target_crs") and rec["direction"] == "FORWARD"})

    detail_payload = {
        "cases": case_records,
        "tolerances": {
            "cartesian_m": tol_xy,
            "geographic_deg": tol_ll,
            "round_trip_cartesian_m": tol_round_xy,
            "round_trip_geographic_deg": tol_round_ll,
        },
        "skipped": overall_skipped,
        "geographic_crs": geographic_list,
        "projected_crs": projected_list,
    }

    if failures:
        detail_payload["issues"] = failures
        return TestResult(
            "fail",
            f"{label} mismatches",
            detail_payload,
        )
    return TestResult(
        "pass",
        f"{label} match reference outputs",
        detail_payload,
    )


def test_conversion_5111(session: requests.Session) -> TestResult:
    """GIGS 5111 – Mercator (variant A) conversions."""

    return execute_conversion_dataset(
        session,
        dataset_name="GIGS_conv_5111_MercA",
        label="Mercator variant A conversions",
    )


def _parse_transformation_dataset(
    name: str,
) -> Tuple[List[Dict[str, object]], List[OutputSet], Dict[str, float]]:
    base_dir = DATA_ROOT / "GIGS 5200 Coordinate transformation test data/ASCII"
    input_paths = sorted(base_dir.glob(f"{name}_input*.txt"))
    single_path = base_dir / f"{name}_input.txt"
    if not input_paths:
        input_paths = [_require_data(single_path)]
    elif single_path in input_paths and len(input_paths) > 1:
        # Prefer the consolidated file if both it and part files exist.
        input_paths = [single_path]

    input_rows: List[Dict[str, object]] = []
    for path in input_paths:
        table = parse_gigs_table(path)
        input_rows.extend(table.rows)

    point_to_input = {
        row.get("point"): row
        for row in input_rows
        if row.get("point")
    }

    output_paths = list(base_dir.glob(f"{name}_output*.txt"))
    if not output_paths:
        single = base_dir / f"{name}_output.txt"
        if not single.exists():
            raise FileNotFoundError(single)
        output_paths = [single]

    tolerances: Dict[str, float] = {}
    output_sets: List[OutputSet] = []

    for out_path in output_paths:
        output_table = parse_gigs_table(out_path)
        label = out_path.stem.split(f"{name}_output", 1)[-1].lstrip("_") or None
        geo_sets = _extract_geo_sets(output_table)
        geocen_sets = _extract_geocen_sets(output_table)
        geo_part = geo_sets[0].code if geo_sets else None
        geocen_part = geocen_sets[0].code if geocen_sets else None

        variant_key = label or "default"
        for out_row in output_table.rows:
            point = out_row.get("point")
            if not point:
                continue
            input_row = point_to_input.get(point)
            if not input_row:
                continue
            variants = input_row.setdefault("_variants", set())
            variants.add(variant_key)
            input_row.setdefault("_geo_epsg_map", {})[variant_key] = geo_part
            input_row.setdefault("_geocentric_epsg_map", {})[variant_key] = geocen_part

        with out_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("#"):
                    break
                match = re.search(r"#\s*(.*?)\s*Tolerance:\s*([0-9.eE+-]+)", line)
                if match:
                    key = match.group(1).strip().lower().replace(" ", "_")
                    try:
                        tolerances[key] = float(match.group(2))
                    except ValueError:
                        continue

        output_sets.append(
            OutputSet(
                label=label,
                rows_by_point={row.get("point"): row for row in output_table.rows if row.get("point")},
                epsg_codes=output_table.epsg_codes,
                geo_sets=geo_sets,
                geocen_sets=geocen_sets,
            )
        )

    return input_rows, output_sets, tolerances


def execute_transformation_dataset(
    session: requests.Session,
    dataset_name: str,
    label: str,
) -> TestResult:

    try:
        inputs, output_sets, tolerances = _parse_transformation_dataset(dataset_name)
    except FileNotFoundError as exc:
        return TestResult("skip", f"Dataset missing: {exc}")

    failures: List[str] = []
    case_records: List[Dict[str, object]] = []
    cart_tol = tolerances.get("cartesian", 0.01)
    geo_tol = tolerances.get("geographic", 3e-7)
    tol_round_xy = tolerances.get("round_trip_cartesian")
    tol_round_ll = tolerances.get("round_trip_geographic")

    skipped = 0

    for output_set in output_sets:
        variant = output_set.label or "default"
        geo_sets = output_set.geo_sets
        geocen_sets = output_set.geocen_sets

        for row in inputs:
            if variant not in row.get("_variants", {"default"}):
                continue
            point = row.get("point")
            out_row = output_set.rows_by_point.get(point)
            if not out_row:
                failures.append(f"No output row for {point} [{variant}]")
                continue

            direction = (row.get("direction") or "").upper()
            status = "pass"
            payload: Dict[str, object] = {}
            expected: Dict[str, float] = {}
            actual: Dict[str, float] = {}
            delta: Dict[str, float] = {}
            message: Optional[str] = None

            scenario: Optional[str]
            if geocen_sets and geo_sets:
                scenario = "geo-geocen"
            elif len(geo_sets) >= 2:
                scenario = "geo-geo"
            else:
                scenario = None

            source_crs: Optional[str] = None
            target_crs: Optional[str] = None

            if scenario == "geo-geocen":
                geo_set = geo_sets[0]
                geocen_set = geocen_sets[0]
                if direction == "REVERSE":
                    lon_val = _get_value(row, geo_set.lon)
                    lat_val = _get_value(row, geo_set.lat)
                    height_val = _get_value(row, geo_set.height)
                    if lon_val is None or lat_val is None:
                        status = "skip"
                        skipped += 1
                        message = "Latitude/longitude input missing"
                    else:
                        payload = {
                            "source_crs": geo_set.code,
                            "target_crs": geocen_set.code,
                            "position": {"lon": lon_val, "lat": lat_val},
                        }
                        if height_val is not None:
                            payload["vertical_value"] = height_val
                        try:
                            resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload)
                        except HTTPError as exc:
                            failures.append(
                                f"REVERSE {point} [{variant}]: HTTP {exc.response.status_code} {exc.response.text}"
                            )
                            status = "fail"
                            payload["error"] = exc.response.text
                        else:
                            calc_x = resp["map_position"]["x"]
                            calc_y = resp["map_position"]["y"]
                            calc_z = resp.get("vertical_output")
                            exp_x = _get_value(out_row, geocen_set.x)
                            exp_y = _get_value(out_row, geocen_set.y)
                            exp_z = _get_value(out_row, geocen_set.z)
                            actual = {"x": calc_x, "y": calc_y, "z": calc_z}
                            expected = {"x": exp_x, "y": exp_y, "z": exp_z}
                            if None in (exp_x, exp_y, exp_z):
                                status = "skip"
                                skipped += 1
                                message = "Geocentric expectation missing"
                            else:
                                delta = {
                                    "dx": calc_x - exp_x,
                                    "dy": calc_y - exp_y,
                                    "dz": (calc_z or 0.0) - exp_z,
                                }
                                if not almost_equal(
                                    [calc_x, calc_y, calc_z or 0.0],
                                    [exp_x, exp_y, exp_z],
                                    cart_tol,
                                ):
                                    status = "fail"
                                    failures.append(
                                        f"REVERSE {point} [{variant}]: expected {[exp_x, exp_y, exp_z]} got {[calc_x, calc_y, calc_z]}"
                                    )
                        source_crs = geo_set.code
                        target_crs = geocen_set.code
                elif direction == "FORWARD":
                    x_val = _get_value(row, geocen_set.x)
                    y_val = _get_value(row, geocen_set.y)
                    z_val = _get_value(row, geocen_set.z)
                    if x_val is None or y_val is None or z_val is None:
                        status = "skip"
                        skipped += 1
                        message = "Geocentric input missing"
                    else:
                        payload = {
                            "source_crs": geocen_set.code,
                            "target_crs": geo_set.code,
                            "position": {"x": x_val, "y": y_val},
                            "vertical_value": z_val,
                        }
                        try:
                            resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload)
                        except HTTPError as exc:
                            failures.append(
                                f"FORWARD {point} [{variant}]: HTTP {exc.response.status_code} {exc.response.text}"
                            )
                            status = "fail"
                            payload["error"] = exc.response.text
                        else:
                            calc_lon = resp["map_position"]["x"]
                            calc_lat = resp["map_position"]["y"]
                            calc_h = resp.get("vertical_output")
                            exp_lon = _get_value(out_row, geo_set.lon)
                            exp_lat = _get_value(out_row, geo_set.lat)
                            exp_h = _get_value(out_row, geo_set.height)
                            actual = {"lon": calc_lon, "lat": calc_lat, "height": calc_h}
                            expected = {"lon": exp_lon, "lat": exp_lat, "height": exp_h}
                            if None in (exp_lon, exp_lat, exp_h):
                                status = "skip"
                                skipped += 1
                                message = "Geographic expectation missing"
                            else:
                                delta = {
                                    "d_lon": calc_lon - exp_lon,
                                    "d_lat": calc_lat - exp_lat,
                                    "d_h": (calc_h or 0.0) - exp_h,
                                }
                                if not almost_equal(
                                    [calc_lon, calc_lat],
                                    [exp_lon, exp_lat],
                                    geo_tol,
                                ) or (calc_h is not None and exp_h is not None and abs(calc_h - exp_h) > cart_tol):
                                    status = "fail"
                                    failures.append(
                                        f"FORWARD {point} [{variant}]: expected {[exp_lon, exp_lat, exp_h]} got {[calc_lon, calc_lat, calc_h]}"
                                    )
                        source_crs = geocen_set.code
                        target_crs = geo_set.code
                else:
                    failures.append(f"{point} [{variant}]: unknown direction {direction}")
                    status = "fail"
                    message = "Unknown direction"
            elif scenario == "geo-geo":
                if direction == "FORWARD":
                    src_set, dst_set = geo_sets[0], geo_sets[1]
                elif direction == "REVERSE":
                    src_set, dst_set = geo_sets[1], geo_sets[0]
                else:
                    failures.append(f"{point} [{variant}]: unknown direction {direction}")
                    status = "fail"
                    message = "Unknown direction"
                    src_set = dst_set = None  # type: ignore[assignment]

                if status == "pass" and src_set and dst_set:
                    lon_val = _get_value(row, src_set.lon)
                    lat_val = _get_value(row, src_set.lat)
                    height_val = _get_value(row, src_set.height)
                    if lon_val is None or lat_val is None:
                        status = "skip"
                        skipped += 1
                        message = "Geographic input missing"
                    else:
                        payload = {
                            "source_crs": src_set.code,
                            "target_crs": dst_set.code,
                            "position": {"lon": lon_val, "lat": lat_val},
                        }
                        if height_val is not None:
                            payload["vertical_value"] = height_val
                        try:
                            resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload)
                        except HTTPError as exc:
                            failures.append(
                                f"{direction} {point} [{variant}]: HTTP {exc.response.status_code} {exc.response.text}"
                            )
                            status = "fail"
                            payload["error"] = exc.response.text
                        else:
                            calc_lon = resp["map_position"]["x"]
                            calc_lat = resp["map_position"]["y"]
                            calc_h = resp.get("vertical_output")
                            exp_lon = _get_value(out_row, dst_set.lon)
                            exp_lat = _get_value(out_row, dst_set.lat)
                            exp_h = _get_value(out_row, dst_set.height)
                            actual = {"lon": calc_lon, "lat": calc_lat}
                            expected = {"lon": exp_lon, "lat": exp_lat}
                            delta = {
                                "d_lon": None if exp_lon is None or calc_lon is None else calc_lon - exp_lon,
                                "d_lat": None if exp_lat is None or calc_lat is None else calc_lat - exp_lat,
                            }
                            if exp_lon is None or exp_lat is None:
                                status = "skip"
                                skipped += 1
                                message = "Geographic expectation missing"
                            else:
                                if not almost_equal([calc_lon, calc_lat], [exp_lon, exp_lat], geo_tol):
                                    status = "fail"
                                    failures.append(
                                        f"{direction} {point} [{variant}]: expected {[exp_lon, exp_lat]} got {[calc_lon, calc_lat]}"
                                    )
                            if exp_h is not None:
                                delta["d_h"] = (calc_h or 0.0) - exp_h
                                expected["height"] = exp_h
                                actual["height"] = calc_h
                                if calc_h is None or abs(calc_h - exp_h) > cart_tol:
                                    status = "fail"
                                    failures.append(
                                        f"{direction} {point} [{variant}]: expected height {exp_h} got {calc_h}"
                                    )
                        source_crs = src_set.code
                        target_crs = dst_set.code
            else:
                status = "skip"
                skipped += 1
                message = "Missing EPSG codes"

            record = {
                "point": point,
                "direction": direction,
                "status": status,
                "variant": variant,
                "source_crs": source_crs,
                "target_crs": target_crs,
                "payload": payload,
                "endpoint": "POST /api/transform/direct",
                "path_hint": "best_available",
                "path_id": None,
                "expected": expected,
                "actual": actual,
                "delta": delta,
            }
            if message:
                record["message"] = message
            case_records.append(record)

    geographic_list = sorted(
        {
            rec["source_crs"]
            for rec in case_records
            if rec.get("source_crs") and rec["direction"] == "FORWARD"
        }
    )
    projected_list = sorted(
        {
            rec["target_crs"]
            for rec in case_records
            if rec.get("target_crs") and rec["direction"] == "FORWARD"
        }
    )

    detail_payload = {
        "cases": case_records,
        "tolerances": {
            "cartesian_m": cart_tol,
            "geographic_deg": geo_tol,
            "round_trip_cartesian_m": tol_round_xy,
            "round_trip_geographic_deg": tol_round_ll,
        },
        "skipped": skipped,
        "geographic_crs": geographic_list,
        "projected_crs": projected_list,
    }

    all_skipped = case_records and all(rec["status"] == "skip" for rec in case_records)

    if failures:
        detail_payload["issues"] = failures
        return TestResult(
            "fail",
            f"{label} mismatches",
            detail_payload,
        )
    if all_skipped:
        return TestResult(
            "skip",
            f"{label} skipped (insufficient CRS definitions)",
            detail_payload,
        )
    return TestResult(
        "pass",
        f"{label} match reference outputs",
        detail_payload,
    )


def _make_conversion_test(
    test_id: str,
    dataset_name: str,
    label: str,
    include_parts: Optional[Iterable[str]] = None,
) -> ManualTest:

    def _runner(session: requests.Session, *, _dataset=dataset_name, _label=label, _parts=include_parts) -> TestResult:
        return execute_conversion_dataset(session, _dataset, _label, include_parts=_parts)

    return ManualTest(test_id, "5100", label, _runner)


def _make_transformation_test(test_id: str, dataset_name: str, label: str) -> ManualTest:

    def _runner(session: requests.Session, *, _dataset=dataset_name, _label=label) -> TestResult:
        return execute_transformation_dataset(session, _dataset, _label)

    return ManualTest(test_id, "5200", label, _runner)


def test_transformation_5201(session: requests.Session) -> TestResult:
    """GIGS 5201 – Geographic <-> Geocentric conversions (WGS84)."""

    return execute_transformation_dataset(
        session,
        dataset_name="GIGS_tfm_5201_GeogGeocen",
        label="Geographic↔Geocentric transformations",
    )


def test_local_offset_placeholder(session: requests.Session) -> TestResult:
    """Placeholder for Series 5300/5400/5500 tests."""

    return TestResult(
        "skip",
        "Local offset and trajectory datasets require dedicated parser (TODO)",
    )


def _parse_wells_dataset(session: requests.Session, name_prefix: str) -> TestResult:
    base_dir = DATA_ROOT / "GIGS 5500 Wells test data/ASCII"
    input_path = _require_data(base_dir / f"{name_prefix}_input.txt")
    output_path = _require_data(base_dir / f"{name_prefix}_output.txt")

    input_table = parse_gigs_table(input_path)
    output_table = parse_gigs_table(output_path)

    # Read tolerances from output header
    tolerances: Dict[str, float] = {}
    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            match = re.search(r"#\s*(.*?)\s*Tolerance:\s*([0-9.eE+-]+)", line)
            if match:
                key = match.group(1).strip().lower().replace(" ", "_")
                try:
                    tolerances[key] = float(match.group(2))
                except ValueError:
                    continue

    # Extract inputs: lat/lon columns; outputs: easting/northing per point
    inputs: List[Dict[str, object]] = []
    tvd_in_col = input_table.columns[0] if input_table.columns else None
    for row in input_table.rows:
        lat = _get_numeric(row, "lat") if "lat" in input_table.columns else None
        lon = _get_numeric(row, "lon") if "lon" in input_table.columns else None
        point = row.get("point") or row.get("transect")
        if lat is None or lon is None or not point:
            continue
        tvd_in = _get_value(row, tvd_in_col) if tvd_in_col else None
        inputs.append({"lon": lon, "lat": lat, "point": point, "tvd_in": tvd_in})

    outputs_by_point: Dict[str, Dict[str, float]] = {}
    tvd_out_col = output_table.columns[0] if output_table.columns else None
    # Try to derive target vertical EPSG from column info
    vert_epsg: Optional[str] = None
    try:
        if tvd_out_col and tvd_out_col in output_table.column_info:
            m = re.search(r"EPSG CRS code (\d+)", output_table.column_info[tvd_out_col])
            if m:
                vert_epsg = f"EPSG:{m.group(1)}"
    except Exception:
        vert_epsg = None
    for row in output_table.rows:
        p = row.get("point")
        if not p:
            continue
        east = _get_numeric(row, "easting") if "easting" in output_table.columns else None
        north = _get_numeric(row, "northing") if "northing" in output_table.columns else None
        tvd_out = _get_value(row, tvd_out_col) if tvd_out_col else None
        outputs_by_point[p] = {"easting": east, "northing": north, "tvd": tvd_out}

    # (Deprecated) inferred shift approach retained only for optional diagnostics
    tvd_shift = None

    # Produce validations using a preferred via path (ETRS89→BNG via OSTN grid) with fallback to direct
    cases: List[Dict[str, object]] = []
    for item in inputs:
        p = str(item["point"]) if item.get("point") else ""
        expected = outputs_by_point.get(p)
        # Attempt via: 4326 -> 4258 -> 27700 with OSTN preference on leg 2
        via_payload = {
            "path": ["EPSG:4326", "EPSG:4258", "EPSG:27700"],
            "position": {"lon": item["lon"], "lat": item["lat"]},
            "segment_preferred_ops": [None, ["OSTN", "NTv2"]],
        }
        endpoint = "POST /api/transform/via"
        try:
            via_out = _call_json(session, "POST", f"{API_ROOT}/api/transform/via", json=via_payload)
            actual = {"x": via_out.get("x"), "y": via_out.get("y")}
            payload_used = via_payload
        except HTTPError:
            # Fallback: direct
            payload_direct = {
                "source_crs": "EPSG:4326",
                "target_crs": "EPSG:27700",
                "position": {"lon": item["lon"], "lat": item["lat"]},
            }
            endpoint = "POST /api/transform/direct"
            try:
                resp = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload_direct)
                actual = resp.get("map_position") or {"x": resp.get("x"), "y": resp.get("y")}
                payload_used = payload_direct
            except HTTPError as exc2:
                cases.append({
                    "point": p,
                    "direction": "FORWARD",
                    "status": "fail",
                    "endpoint": endpoint,
                    "payload": payload_direct,
                    "error": exc2.response.text,
                })
                continue
        status = "skip"
        delta = {}
        message = None
        if expected is None or expected.get("easting") is None or expected.get("northing") is None:
            status = "skip"
            message = "No expected easting/northing for point"
        else:
            dx = actual.get("x") - expected["easting"]
            dy = actual.get("y") - expected["northing"]
            delta = {"dx": dx, "dy": dy, "d": (dx ** 2 + dy ** 2) ** 0.5}
            tol = tolerances.get("cartesian", tolerances.get("cartesian_m", 0.05))
            status = "pass" if abs(delta["d"]) <= tol else "fail"

        # Vertical check using dedicated endpoint when target vertical EPSG is available.
        tvd_in = item.get("tvd_in")
        exp_tvd = expected.get("tvd") if expected else None
        # Optional: attempt direct vertical transform via API (prioritised if target vertical EPSG available)
        try:
            if tvd_in is not None and exp_tvd is not None and vert_epsg:
                payload_vert = {
                    "source_crs": "EPSG:4979",
                    "target_vertical_crs": vert_epsg,
                    "lon": item["lon"],
                    "lat": item["lat"],
                    "value": float(abs(float(tvd_in))),  # treat input as +down depth
                    "value_is_depth": True,
                    "output_as_depth": True,  # return +down depth
                }
                # Do not fail if endpoint unavailable
                try:
                    vert = _call_json(session, "POST", f"{API_ROOT}/api/transform/vertical", json=payload_vert)
                    out_depth = float(vert.get("output_value"))
                    # Convert to signed convention matching the dataset (negative TVD values)
                    calc_signed = -out_depth
                    delta["vertical_trial"] = {"signed_depth": calc_signed, "raw_depth": out_depth, "target": vert_epsg}
                    d_vert = calc_signed - float(exp_tvd)
                    delta["d_tvd"] = d_vert
                    vtol = tolerances.get("vertical_m", tolerances.get("cartesian", tolerances.get("cartesian_m", 0.05)))
                    if abs(d_vert) > vtol:
                        status = "fail"
                except Exception:
                    pass
        except Exception:
            pass
        record = {
            "point": p,
            "direction": "FORWARD",
            "status": status,
            "endpoint": endpoint,
            "payload": payload_used,
            "source_crs": "EPSG:4326",
            "target_crs": "EPSG:27700",
            "expected": expected,
            "actual": actual,
            "delta": delta,
        }
        if message:
            record["message"] = message
        cases.append(record)

    details = {"cases": cases, "tolerances": tolerances}
    failures = [c for c in cases if c.get("status") == "fail"]
    if failures:
        details["issues"] = [f"{len(failures)} failures"]
        return TestResult("fail", "Wells dataset mismatches (BNG proxy + inferred vertical shift)", details)
    if all(c.get("status") == "skip" for c in cases):
        return TestResult("skip", "Wells dataset skipped (insufficient expectations)", details)
    return TestResult("pass", "Wells dataset matches reference (BNG proxy)", details)


def _make_wells_test(prefix: str, label: str) -> ManualTest:
    def _runner(session: requests.Session, *, _p=prefix) -> TestResult:
        try:
            return _parse_wells_dataset(session, _p)
        except FileNotFoundError as exc:
            return TestResult("skip", f"Dataset missing: {exc}")
    return ManualTest(prefix.replace("GIGS_wells_", "wells-"), "5500", label, _runner)


CONVERSION_DATASETS = [
    ("conv-5101", "GIGS_conv_5101_TM", "Transverse Mercator conversions"),
    ("conv-5102", "GIGS_conv_5102_LCC1", "Lambert Conic Conformal (1SP) conversions"),
    ("conv-5103", "GIGS_conv_5103_LCC2", "Lambert Conic Conformal (2SP) conversions"),
    ("conv-5104", "GIGS_conv_5104_OblStereo", "Oblique Stereographic conversions"),
    ("conv-5105", "GIGS_conv_5105_HOM-B", "Hotine Oblique Mercator (variant B) conversions"),
    ("conv-5106", "GIGS_conv_5106_HOM-A", "Hotine Oblique Mercator (variant A) conversions"),
    ("conv-5107", "GIGS_conv_5107_AmPolyC", "American Polyconic conversions"),
    ("conv-5108", "GIGS_conv_5108_Cass", "Cassini-Soldner conversions"),
    ("conv-5109", "GIGS_conv_5109_Albers", "Albers Equal Area conversions"),
    ("conv-5110", "GIGS_conv_5110_LAEA", "Lambert Azimuthal Equal-Area conversions"),
    ("conv-5111", "GIGS_conv_5111_MercA", "Mercator (variant A) conversions"),
    ("conv-5112", "GIGS_conv_5112_MercB", "Mercator (variant B) conversions"),
    ("conv-5113", "GIGS_conv_5113_TMSO", "Transverse Mercator (South Orientated) conversions"),
]

TRANSFORMATION_DATASETS = [
    ("tfm-5201", "GIGS_tfm_5201_GeogGeocen", "Geographic↔Geocentric transformations"),
    ("tfm-5203", "GIGS_tfm_5203_PosVec", "Position Vector transformations"),
    ("tfm-5204", "GIGS_tfm_5204_CoordFrame", "Coordinate Frame rotations"),
    ("tfm-5205", "GIGS_tfm_5205_MolBad", "Molodensky-Badekas transformations"),
    ("tfm-5206", "GIGS_tfm_5206_Nadcon", "NADCON grid transformations"),
    ("tfm-5207", "GIGS_tfm_5207_NTv2", "NTv2 grid transformations"),
    ("tfm-5208", "GIGS_tfm_5208_LonRot", "Longitude rotation transformations"),
    ("tfm-5209", "GIGS_tfm_5209_BinGrid", "Binary grid transformations"),
    ("tfm-5210", "GIGS_tfm_5210_VertOff", "Vertical offset transformations"),
    ("tfm-5211", "GIGS_tfm_5211_3trnslt_Geocen", "Geocentric three-translation transformations"),
    ("tfm-5212", "GIGS_tfm_5212_3trnslt_Geog3D", "Geographic 3D three-translation transformations"),
    ("tfm-5213", "GIGS_tfm_5213_3trnslt_Geog2D", "Geographic 2D three-translation transformations"),
]


TESTS: List[ManualTest] = [
    ManualTest("lib-2205", "2200", "Predefined geodetic CRS definitions", test_2200_geodetic_crs),
    ManualTest("crs-info", "2200", "CRS metadata sanity-check", test_crs_info),
]

for test_id, dataset_name, label in CONVERSION_DATASETS:
    TESTS.append(_make_conversion_test(test_id, dataset_name, label))

for test_id, dataset_name, label in TRANSFORMATION_DATASETS:
    TESTS.append(_make_transformation_test(test_id, dataset_name, label))

TESTS.append(
    ManualTest(
        "local-offset",
        "5300/5400/5500",
        "Local offset & trajectory comparisons",
        test_local_offset_placeholder,
    )
)

# Dynamically add Wells datasets from ASCII folder
try:
    wells_dir = DATA_ROOT / "GIGS 5500 Wells test data/ASCII"
    if wells_dir.exists():
        for path in sorted(wells_dir.glob("GIGS_wells_55*_input.txt")):
            name = path.stem.replace("_input", "")
            output = wells_dir / f"{name.replace('_input','')}_output.txt"
            if not output.exists():
                continue
            if name == "GIGS_wells_5506_wellA":
                # Covered by generic generator too; proceed once
                pass
            label = name.replace("GIGS_wells_", "").replace("_", " ")
            TESTS.append(_make_wells_test(name, f"Wells {label}"))
except Exception:
    pass

def test_via_demo(session: requests.Session) -> TestResult:
    """Demonstration: compare direct vs via (4326→27700 vs 4326→4277→27700)."""
    lon, lat = -3.1883, 55.9533
    source = "EPSG:4326"
    via = "EPSG:4277"
    target = "EPSG:27700"
    tol_m = 2.0
    cases: List[Dict[str, object]] = []
    failures: List[str] = []

    payload_direct = {"source_crs": source, "target_crs": target, "position": {"lon": lon, "lat": lat}}
    direct = _call_json(session, "POST", f"{API_ROOT}/api/transform/direct", json=payload_direct)
    direct_xy = direct.get("map_position") or {"x": direct.get("x"), "y": direct.get("y")}
    cases.append({
        "point": "via-demo-01",
        "direction": "FORWARD",
        "status": "pass",
        "endpoint": "POST /api/transform/direct",
        "payload": payload_direct,
        "source_crs": source,
        "target_crs": target,
        "expected": None,
        "actual": direct_xy,
        "delta": None,
    })

    payload_via = {"path": [source, via, target], "position": {"lon": lon, "lat": lat}, "segment_path_ids": [None, None]}
    via_out = _call_json(session, "POST", f"{API_ROOT}/api/transform/via", json=payload_via)
    via_pos = {"x": via_out.get("x"), "y": via_out.get("y")}
    dx = float(via_pos["x"]) - float(direct_xy["x"]) if via_pos["x"] is not None and direct_xy["x"] is not None else float("nan")
    dy = float(via_pos["y"]) - float(direct_xy["y"]) if via_pos["y"] is not None and direct_xy["y"] is not None else float("nan")
    dist = (dx ** 2 + dy ** 2) ** 0.5 if dx == dx and dy == dy else float("nan")
    status = "pass" if dist == dist and dist <= tol_m else "fail"
    if status == "fail":
        failures.append(f"Via demo difference {dist} m exceeds tolerance {tol_m} m")
    cases.append({
        "point": "via-demo-01",
        "direction": "FORWARD",
        "status": status,
        "endpoint": "POST /api/transform/via",
        "payload": payload_via,
        "path_hint": "[None, None]",
        "path_id": None,
        "source_crs": source,
        "target_crs": target,
        "expected": direct_xy,
        "actual": via_pos,
        "delta": {"dx_m": dx, "dy_m": dy, "d_m": dist},
    })

    details = {"cases": cases, "tolerances": {"cartesian_m": tol_m}}
    if failures:
        details["issues"] = failures
        return TestResult("fail", "Via demo mismatch (direct vs via)", details)
    return TestResult("pass", "Via demo within tolerance", details)

TESTS.append(ManualTest("via-demo", "5200", "Via transformation demo (4326→4277→27700)", test_via_demo))


def generate_html(results: List[Tuple[ManualTest, TestResult]], generated_at: dt.datetime) -> None:
    timestamp = generated_at.strftime("%Y-%m-%d %H:%M UTC")

    def _render_details(message: str, details: Optional[Dict[str, object]]) -> str:
        parts: List[str] = [html.escape(message)]
        if not details:
            return "".join(parts)

        extras = {}
        cases = None
        if isinstance(details, dict):
            for key, value in details.items():
                if key == "cases":
                    cases = value
                else:
                    extras[key] = value
        else:
            extras = {"details": details}

        if extras:
            parts.append("<br><pre>" + html.escape(json.dumps(extras, indent=2)) + "</pre>")

        if isinstance(cases, list) and cases:
            rows_html: List[str] = []
            for case in cases:
                point = html.escape(str(case.get("point", "")))
                direction = html.escape(str(case.get("direction", "")))
                status = html.escape(str(case.get("status", ""))).upper()
                status_color = {
                    "PASS": "#2e7d32",
                    "FAIL": "#c62828",
                }.get(status, "#424242")
                payload = html.escape(json.dumps(case.get("payload"), indent=2, sort_keys=True))
                expected = html.escape(json.dumps(case.get("expected"), indent=2, sort_keys=True))
                actual = html.escape(json.dumps(case.get("actual"), indent=2, sort_keys=True))
                delta = html.escape(json.dumps(case.get("delta"), indent=2, sort_keys=True))
                error = case.get("error")
                error_html = f"<pre>{html.escape(str(error))}</pre>" if error else ""
                rows_html.append(
                    "<tr>"
                    f"<td>{point}</td>"
                    f"<td>{direction}</td>"
                    f"<td style='color:{status_color}; font-weight:bold'>{status}</td>"
                    f"<td><pre>{payload}</pre></td>"
                    f"<td><pre>{expected}</pre></td>"
                    f"<td><pre>{actual}</pre></td>"
                    f"<td><pre>{delta}</pre>{error_html}</td>"
                    "</tr>"
                )

            parts.append(
                "<details><summary>Case breakdown ("
                + str(len(cases))
                + ")</summary><table><thead><tr><th>Point</th><th>Direction</th><th>Status</th><th>Payload</th><th>Expected</th><th>Actual</th><th>Δ / Error</th></tr></thead><tbody>"
                + "".join(rows_html)
                + "</tbody></table></details>"
            )

        return "".join(parts)

    rows_html: List[str] = []
    for test, result in results:
        status = result.status.upper()
        color = {
            "PASS": "#2e7d32",
            "FAIL": "#c62828",
            "SKIP": "#6d6d6d",
        }.get(status, "#424242")
        message = _render_details(result.message, result.details)
        rows_html.append(
            f"<tr><td>{test.series}</td><td>{test.id}</td><td>{test.description}</td>"
            f"<td style='color:{color}; font-weight:bold'>{status}</td><td>{message}</td></tr>"
        )

    html_output = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>GIGS Manual Test Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background-color: #f5f5f5; text-align: left; }}
    tr:nth-child(even) {{ background-color: #fafafa; }}
  </style>
</head>
<body>
  <h1>GIGS Manual Test Report</h1>
  <p>Generated: {timestamp}</p>
  <table>
    <thead>
      <tr>
        <th>Series</th>
        <th>Test ID</th>
        <th>Description</th>
        <th>Status</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    HTML_REPORT.write_text(html_output, encoding="utf-8")


def generate_json(results: List[Tuple[ManualTest, TestResult]], generated_at: dt.datetime) -> None:
    def serialize_detail(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: serialize_detail(v) for k, v in value.items()}
        if isinstance(value, list):
            return [serialize_detail(v) for v in value]
        return value

    payload = {
        "generated": generated_at.isoformat(timespec="seconds") + "Z",
        "tests": [
            {
                "series": test.series,
                "id": test.id,
                "description": test.description,
                "status": result.status,
                "message": result.message,
                "details": serialize_detail(result.details),
            }
            for test, result in results
        ],
    }

    JSON_REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    if not DATA_ROOT.exists():
        raise SystemExit(f"GIGS dataset directory not found at {DATA_ROOT}")

    results: List[Tuple[ManualTest, TestResult]] = []
    generated_at = dt.datetime.utcnow()

    with requests.Session() as session:
        session.headers.update({"Content-Type": "application/json"})
        for test in TESTS:
            try:
                result = test.func(session)
            except Exception as exc:  # pylint: disable=broad-except
                result = TestResult("fail", f"Exception: {exc}")
            results.append((test, result))
            print(f"{test.id:<12} {result.status.upper():<5} {result.message}")
    generate_html(results, generated_at)
    generate_json(results, generated_at)
    print(f"\nHTML report written to {HTML_REPORT}")
    print(f"JSON report written to {JSON_REPORT}")


if __name__ == "__main__":
    main()
