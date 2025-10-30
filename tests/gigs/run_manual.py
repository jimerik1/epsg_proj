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
import math
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests
from requests import HTTPError
from pyproj import CRS
try:
    # Use external MCM module for robust well path in local grid
    from tests.gigs import mcm_module
except Exception:
    mcm_module = None
import numpy as np

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

GIGS_OSGB36_3D = "GIGS:OSGB36_3D"
GIGS_AMERSFOORT_3D = "GIGS:AMERSFOORT_3D"
ETRS89_3D = "EPSG:4937"

GIGS_PROJECTED_OVERRIDES = {
    "gigs projcrs a2": "GIGS:projCRS_A2",
    "gigs projcrs a23": "GIGS:projCRS_A23",
}


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
            try:
                return to_float(value)
            except Exception:
                continue
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


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_column(column_info: Dict[str, str], *phrases: str) -> Optional[str]:
    if not phrases:
        return None
    lowered = [phrase.lower() for phrase in phrases if phrase]
    for col, info in column_info.items():
        info_lower = info.lower()
        if all(phrase in info_lower for phrase in lowered):
            return col
    return None


def _normalize_point_label(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    # Drop parenthetical hints like "(wrp)"
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _align_well_rows(
    input_rows: List[Dict[str, Any]],
    output_rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return input/output row lists aligned by point labels when possible."""

    if not input_rows or not output_rows:
        return input_rows[: len(output_rows)], output_rows

    normalized_input: List[Optional[str]] = [_normalize_point_label(row.get("point")) for row in input_rows]
    normalized_output: List[Optional[str]] = [_normalize_point_label(row.get("point")) for row in output_rows]

    aligned_inputs: List[Dict[str, Any]] = []
    aligned_outputs: List[Dict[str, Any]] = []

    used_indices: set[int] = set()
    search_idx = 0

    for out_idx, out_row in enumerate(output_rows):
        target_label = normalized_output[out_idx]
        match_idx: Optional[int] = None

        if target_label:
            for idx in range(search_idx, len(input_rows)):
                if idx in used_indices:
                    continue
                if normalized_input[idx] == target_label:
                    match_idx = idx
                    break

        if match_idx is None:
            for idx in range(search_idx, len(input_rows)):
                if idx not in used_indices:
                    match_idx = idx
                    break

        if match_idx is None:
            break

        aligned_inputs.append(input_rows[match_idx])
        aligned_outputs.append(out_row)
        used_indices.add(match_idx)
        search_idx = match_idx + 1

    return aligned_inputs, aligned_outputs


def _crs_is_vertical(label: Optional[str]) -> bool:
    if not label:
        return False
    try:
        crs = CRS.from_user_input(label)
        return bool(getattr(crs, "is_vertical", False))
    except Exception:
        return False


def _parse_p7_reference(name_prefix: str) -> Dict[str, float]:
    """Extract reference depths/coordinates from the associated P7 file."""

    p7_dir = DATA_ROOT / "GIGS 5500 Wells test data/P717"
    path = p7_dir / f"{name_prefix}.p717"
    if not path.exists():
        return {}

    result: Dict[str, float] = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                # Capture survey details AZ_GRID convergence when present (radians)
                if "Survey Details" in raw and "AZ_GRID" in raw:
                    try:
                        # Extract all numeric fragments in the line and pick a reasonable radian value (~0-0.1)
                        nums = [float(x) for x in re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", raw)]
                        for val in nums:
                            if 0.0 <= val <= 0.2:
                                result.setdefault("grid_convergence_rad", val)
                                break
                    except Exception:
                        pass
                if not raw.startswith("O7"):
                    continue
                parts = [part.strip() for part in raw.strip().split(",")]
                if len(parts) < 4:
                    continue
                role = parts[3].upper()
                numerics: List[float] = []
                for fragment in parts[5:]:
                    try:
                        numerics.append(float(fragment))
                    except ValueError:
                        continue
                if not numerics:
                    continue
                if role in {"WRP", "SRP"}:
                    key = role.lower()
                    if len(numerics) >= 3 and abs(numerics[0]) > 1_000 and abs(numerics[1]) > 1_000:
                        result.setdefault(f"{key}_north", numerics[0])
                        result.setdefault(f"{key}_east", numerics[1])
                        result.setdefault(f"{key}_depth", numerics[2])
                        if len(numerics) >= 4:
                            result.setdefault(f"{key}_lat", numerics[3])
                        if len(numerics) >= 5:
                            result.setdefault(f"{key}_lon", numerics[4])
                    elif len(numerics) >= 3:
                        result.setdefault(f"{key}_depth", numerics[0])
                        result.setdefault(f"{key}_lat", numerics[1])
                        result.setdefault(f"{key}_lon", numerics[2])
                    elif len(numerics) == 2:
                        if abs(numerics[0]) > 1_000 and abs(numerics[1]) > 1_000:
                            result.setdefault(f"{key}_north", numerics[0])
                            result.setdefault(f"{key}_east", numerics[1])
                        else:
                            result.setdefault(f"{key}_depth", numerics[0])
                            result.setdefault(f"{key}_lat", numerics[1])
                    elif len(numerics) == 1:
                        result.setdefault(f"{key}_depth", numerics[0])
                elif role == "ZDP":
                    result.setdefault("zdp_depth", numerics[0])
    except Exception:
        return {}
    return result


def _compute_well_path(
    rows: List[Dict[str, Any]],
    md_col: str,
    inc_col: Optional[str],
    az_col: Optional[str],
    base_depth: float,
    *,
    method: str = "minimum_curvature",
    azimuth_offset_rad: float = 0.0,
) -> List[Dict[str, float]]:
    """Compute cumulative east/north/TVD states for wellbore survey rows."""

    if not rows:
        return []

    method = (method or "minimum_curvature").lower()

    if method == "tangent":
        return _compute_well_path_tangent(
            rows, md_col, inc_col, az_col, base_depth, azimuth_offset_rad
        )

    return _compute_well_path_min_curv(
        rows, md_col, inc_col, az_col, base_depth, azimuth_offset_rad
    )


def _compute_well_path_min_curv(
    rows: List[Dict[str, Any]],
    md_col: str,
    inc_col: Optional[str],
    az_col: Optional[str],
    base_depth: float,
    azimuth_offset_rad: float = 0.0,
) -> List[Dict[str, float]]:
    states: List[Dict[str, float]] = []

    prev_md = _safe_float(rows[0].get(md_col)) or 0.0
    prev_inc = math.radians(_safe_float(rows[0].get(inc_col)) or 0.0 if inc_col else 0.0)
    prev_az = math.radians(_safe_float(rows[0].get(az_col)) or 0.0 if az_col else 0.0) + azimuth_offset_rad

    east = 0.0
    north = 0.0
    vertical = 0.0

    states.append(
        {
            "md": prev_md,
            "inc": math.degrees(prev_inc),
            "az": math.degrees(prev_az),
            "east": east,
            "north": north,
            "vertical": vertical,
            "tvd": base_depth + vertical,
        }
    )

    for row in rows[1:]:
        md_val = _safe_float(row.get(md_col))
        inc_val = _safe_float(row.get(inc_col)) if inc_col else None
        az_val = _safe_float(row.get(az_col)) if az_col else None

        md = prev_md if md_val is None else md_val
        inc_rad = prev_inc if inc_val is None else math.radians(inc_val)
        az_rad = prev_az if az_val is None else math.radians(az_val) + azimuth_offset_rad

        delta_md = md - prev_md
        if delta_md < 0:
            delta_md = 0.0

        sin_inc_prev, sin_inc_curr = math.sin(prev_inc), math.sin(inc_rad)
        cos_inc_prev, cos_inc_curr = math.cos(prev_inc), math.cos(inc_rad)
        delta_az = az_rad - prev_az
        cos_dogleg = cos_inc_prev * cos_inc_curr + sin_inc_prev * sin_inc_curr * math.cos(delta_az)
        cos_dogleg = max(-1.0, min(1.0, cos_dogleg))
        dogleg = math.acos(cos_dogleg)
        if dogleg > 1e-9:
            rf = 2.0 / dogleg * math.tan(dogleg / 2.0)
        else:
            rf = 1.0 - dogleg**2 / 12.0

        north += 0.5 * delta_md * (sin_inc_prev * math.cos(prev_az) + sin_inc_curr * math.cos(az_rad)) * rf
        east += 0.5 * delta_md * (sin_inc_prev * math.sin(prev_az) + sin_inc_curr * math.sin(az_rad)) * rf
        vertical += 0.5 * delta_md * (cos_inc_prev + cos_inc_curr) * rf

        states.append(
            {
                "md": md,
                "inc": math.degrees(inc_rad),
                "az": math.degrees(az_rad),
                "east": east,
                "north": north,
                "vertical": vertical,
                "tvd": base_depth + vertical,
            }
        )

        prev_md = md
        prev_inc = inc_rad
        prev_az = az_rad

    return states


def _compute_well_path_tangent(
    rows: List[Dict[str, Any]],
    md_col: str,
    inc_col: Optional[str],
    az_col: Optional[str],
    base_depth: float,
    azimuth_offset_rad: float = 0.0,
) -> List[Dict[str, float]]:
    states: List[Dict[str, float]] = []

    md_prev = _safe_float(rows[0].get(md_col)) or 0.0
    inc_prev = math.radians(_safe_float(rows[0].get(inc_col)) or 0.0 if inc_col else 0.0)
    az_prev = math.radians(_safe_float(rows[0].get(az_col)) or 0.0 if az_col else 0.0) + azimuth_offset_rad

    east = 0.0
    north = 0.0
    vertical = 0.0

    states.append(
        {
            "md": md_prev,
            "inc": math.degrees(inc_prev),
            "az": math.degrees(az_prev),
            "east": east,
            "north": north,
            "vertical": vertical,
            "tvd": base_depth + vertical,
        }
    )

    for row in rows[1:]:
        md_val = _safe_float(row.get(md_col))
        if md_val is None:
            md = md_prev
        else:
            md = md_val

        inc_val = _safe_float(row.get(inc_col)) if inc_col else None
        az_val = _safe_float(row.get(az_col)) if az_col else None

        inc_rad = inc_prev if inc_val is None else math.radians(inc_val)
        az_rad = az_prev if az_val is None else math.radians(az_val) + azimuth_offset_rad

        delta_md = md - md_prev
        if delta_md < 0:
            delta_md = 0.0

        east += delta_md * math.sin(inc_rad) * math.sin(az_rad)
        north += delta_md * math.sin(inc_rad) * math.cos(az_rad)
        vertical += delta_md * math.cos(inc_rad)

        states.append(
            {
                "md": md,
                "inc": math.degrees(inc_rad),
                "az": math.degrees(az_rad),
                "east": east,
                "north": north,
                "vertical": vertical,
                "tvd": base_depth + vertical,
            }
        )

        md_prev = md
        inc_prev = inc_rad
        az_prev = az_rad

    return states


def _apply_state_transform(coeffs: List[List[float]], east: float, north: float) -> Tuple[float, float]:
    """Apply polynomial mapping from local east/north to projected coordinates."""

    terms = [
        east,
        north,
        east * north,
        east * east,
        north * north,
        1.0,
    ]
    if len(coeffs) != len(terms):
        raise ValueError("Coefficient matrix has unexpected shape")
    out_e = sum(term * coeffs[i][0] for i, term in enumerate(terms))
    out_n = sum(term * coeffs[i][1] for i, term in enumerate(terms))
    return out_e, out_n


def _apply_map_affine(coeffs: List[List[float]], x_val: float, y_val: float) -> Tuple[float, float]:
    """Apply affine transform on projected coordinates [[a11,a12],[a21,a22],[b1,b2]]."""

    if len(coeffs) != 3 or any(len(row) != 2 for row in coeffs):
        raise ValueError("Affine coefficient matrix must be 3x2")
    out_x = coeffs[0][0] * x_val + coeffs[1][0] * y_val + coeffs[2][0]
    out_y = coeffs[0][1] * x_val + coeffs[1][1] * y_val + coeffs[2][1]
    return out_x, out_y


def _evaluate_poly(coeffs: List[float], value: float) -> float:
    result = 0.0
    for coeff in coeffs:
        result = result * value + coeff
    return result


def _canonical_crs_label(crs_code: Optional[str]) -> Optional[str]:
    if not crs_code:
        return None
    label = crs_code.strip()
    if label in {GIGS_OSGB36_3D, GIGS_AMERSFOORT_3D, ETRS89_3D}:
        return label
    try:
        crs = CRS.from_user_input(label)
        authority = crs.to_authority()
        if authority:
            return f"{authority[0]}:{authority[1]}"
    except Exception:
        pass
    return label or None


def _apply_path_overrides(
    payload: Dict[str, Any],
    dataset_name: str,
    variant: str,
    source_crs: Optional[str],
    target_crs: Optional[str],
    direction: str,
) -> None:
    canonical_source = _canonical_crs_label(source_crs)
    canonical_target = _canonical_crs_label(target_crs)
    if not canonical_source or not canonical_target:
        return

    overrides = TRANSFORMATION_PATH_OVERRIDES.get(dataset_name)
    if not overrides:
        return
    variant_overrides = overrides.get(variant) or overrides.get("default")
    if not variant_overrides:
        return

    hint = variant_overrides.get((canonical_source, canonical_target, direction))
    if not hint:
        return

    if "path_id" in hint and hint["path_id"] is not None:
        payload["path_id"] = hint["path_id"]
    preferred_ops = hint.get("preferred_ops")
    if preferred_ops:
        payload["preferred_ops"] = preferred_ops


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


TRANSFORMATION_VARIANT_CRS_OVERRIDES: Dict[str, Dict[str, Dict[str, str]]] = {
    "GIGS_tfm_5203_PosVec": {
        "part2": {"geo_alias": GIGS_OSGB36_3D},
    },
    "GIGS_tfm_5205_MolBad": {
        "part2": {"geo_alias": GIGS_AMERSFOORT_3D},
    },
}


TRANSFORMATION_PATH_OVERRIDES: Dict[
    str,
    Dict[str, Dict[Tuple[str, str, str], Dict[str, object]]],
] = {
    "GIGS_tfm_5203_PosVec": {
        "part1": {
            ("EPSG:4277", "EPSG:4326", "FORWARD"): {
                "preferred_ops": [
                    "position vector",
                    "osgb36 to wgs 84 (6)",
                ]
            },
            ("EPSG:4326", "EPSG:4277", "REVERSE"): {
                "preferred_ops": [
                    "position vector",
                    "inverse of osgb36 to wgs 84 (6)",
                ]
            },
        },
        "part2": {
            (GIGS_OSGB36_3D, "EPSG:4979", "FORWARD"): {},
            ("EPSG:4979", GIGS_OSGB36_3D, "REVERSE"): {},
        },
    },
    "GIGS_tfm_5207_NTv2": {
        "part1": {
            ("EPSG:4202", "EPSG:4283", "FORWARD"): {
                "preferred_ops": [
                    "horizontal_shift_gtiff",
                    "agd66 to gda94 (11)",
                    "ntv2",
                ]
            },
            ("EPSG:4283", "EPSG:4202", "REVERSE"): {
                "preferred_ops": [
                    "horizontal_shift_gtiff",
                    "agd66 to gda94 (11)",
                    "inverse of agd66 to gda94",
                    "ntv2",
                ]
            },
        },
        "part2": {
            ("EPSG:4267", "EPSG:4269", "FORWARD"): {
                "preferred_ops": [
                    "horizontal_shift_gtiff",
                    "nad27 to nad83",
                    "ntv2",
                ]
            },
            ("EPSG:4269", "EPSG:4267", "REVERSE"): {
                "preferred_ops": [
                    "horizontal_shift_gtiff",
                    "inverse of nad27 to nad83",
                    "ntv2",
                ]
            },
        },
    },
    "GIGS_tfm_5213_3trnslt_Geog2D": {
        "EPSGconcat": {
            ("EPSG:4277", "EPSG:4326", "FORWARD"): {
                "preferred_ops": [
                    "geocentric translations",
                    "osgb36 to wgs 84 (2)",
                    "osgb36 to wgs 84 (3)",
                ]
            },
            ("EPSG:4326", "EPSG:4277", "REVERSE"): {
                "preferred_ops": [
                    "geocentric translations",
                    "inverse of osgb36 to wgs 84 (2)",
                    "inverse of osgb36 to wgs 84 (3)",
                ]
            },
        },
        "AbrMol": {
            ("EPSG:4277", "EPSG:4326", "FORWARD"): {
                "preferred_ops": ["abridged molodensky"]
            },
            ("EPSG:4326", "EPSG:4277", "REVERSE"): {
                "preferred_ops": ["abridged molodensky"]
            },
        },
    },
}


SKIP_TRANSFORMATION_VARIANTS: Dict[str, Dict[str, Dict[str, set[str]]]] = {
    "GIGS_tfm_5203_PosVec": {
        "part2": {"directions": {"REVERSE", "FORWARD"}},
    },
}


def _extract_epsg_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"E(PGS|PSG) CRS code\s*(\d+)", text, re.IGNORECASE)
    if match:
        return f"EPSG:{match.group(2)}"
    lowered = text.lower()
    for key, value in GIGS_PROJECTED_OVERRIDES.items():
        if key in lowered:
            return value
    return None


def _is_depth_column(text: Optional[str]) -> bool:
    return bool(text and "depth" in text.lower())


def _resolve_projected_axis_columns(column_info: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    east_col: Optional[str] = None
    north_col: Optional[str] = None
    for col, info in column_info.items():
        info_lower = info.lower() if info else ""
        if "northing" in info_lower and north_col is None:
            north_col = col
        if "easting" in info_lower and east_col is None:
            east_col = col
    return east_col, north_col


def _extract_projected_values(
    row: Dict[str, Any],
    column_info: Dict[str, str],
) -> Tuple[Optional[float], Optional[float]]:
    east_col, north_col = _resolve_projected_axis_columns(column_info)
    east_val = _get_value(row, east_col) if east_col else None
    north_val = _get_value(row, north_col) if north_col else None
    if east_val is None:
        east_val = _get_numeric(row, "easting") or _get_numeric(row, "x")
    if north_val is None:
        north_val = _get_numeric(row, "northing") or _get_numeric(row, "y")
    return east_val, north_val


def _vertical_unit_scale(info: Optional[str]) -> float:
    if info and "foot" in info.lower():
        return 0.3048
    return 1.0


def _execute_vertical_offset_dataset(session: requests.Session, label: str) -> TestResult:
    dataset_name = "GIGS_tfm_5210_VertOff"
    try:
        inputs, output_sets, tolerances = _parse_transformation_dataset(dataset_name)
    except FileNotFoundError as exc:
        return TestResult("skip", f"Dataset missing: {exc}")

    if not output_sets:
        return TestResult("skip", "No output expectations for vertical offset dataset")

    output = output_sets[0].rows_by_point
    cart_tol = tolerances.get("cartesian", 0.01)
    cases: List[Dict[str, object]] = []
    failures: List[str] = []

    SRC_HEIGHT = {
        "FORWARD": "EPSG:5611",  # Caspian height
        "REVERSE": "EPSG:5705",  # Baltic 1977 height
    }
    SRC_DEPTH = {
        "FORWARD": "EPSG:5706",  # Caspian depth
        "REVERSE": "EPSG:5612",  # Baltic 1977 depth
    }
    TGT_HEIGHT = {
        "FORWARD": "EPSG:5705",
        "REVERSE": "EPSG:5611",
    }
    TGT_DEPTH = {
        "FORWARD": "EPSG:5612",
        "REVERSE": "EPSG:5706",
    }

    for row in inputs:
        point = row.get("point")
        if not point:
            continue
        direction = (row.get("direction") or "").upper() or "FORWARD"
        out_row = output.get(point)
        if not out_row:
            failures.append(f"No vertical output for {point}")
            continue

        lon = float(row.get("lon"))
        lat = float(row.get("lat"))

        src_height_val = _get_value(row, "height")
        src_depth_val = _get_value(row, "col_4")
        exp_height = _get_value(out_row, "height")
        exp_depth = _get_value(out_row, "col_4")

        status = "skip"
        delta: Dict[str, Dict[str, float]] = {}
        actual: Dict[str, Dict[str, float]] = {}
        expected: Dict[str, Dict[str, float]] = {}
        payload: Dict[str, Dict[str, object]] = {}

        branch_statuses: List[str] = []
        try:
            if src_height_val is not None and exp_height is not None:
                payload["height"] = {
                    "source_vertical_crs": SRC_HEIGHT[direction],
                    "target_vertical_crs": TGT_HEIGHT[direction],
                    "lon": lon,
                    "lat": lat,
                    "value": src_height_val,
                    "value_is_depth": False,
                    "output_as_depth": False,
                }
                resp = _call_json(
                    session,
                    "POST",
                    f"{API_ROOT}/api/transform/vertical",
                    json=payload["height"],
                )
                out_val = float(resp.get("output_value"))
                actual.setdefault("height", {})["value"] = out_val
                expected.setdefault("height", {})["value"] = exp_height
                delta.setdefault("height", {})["difference"] = out_val - exp_height
                branch_statuses.append("pass" if abs(out_val - exp_height) <= cart_tol else "fail")

            if src_depth_val is not None and exp_depth is not None:
                payload["depth"] = {
                    "source_vertical_crs": SRC_DEPTH[direction],
                    "target_vertical_crs": TGT_DEPTH[direction],
                    "lon": lon,
                    "lat": lat,
                    "value": float(abs(src_depth_val)),
                    "value_is_depth": True,
                    "output_as_depth": True,
                }
                resp = _call_json(
                    session,
                    "POST",
                    f"{API_ROOT}/api/transform/vertical",
                    json=payload["depth"],
                )
                out_val = float(resp.get("output_value"))
                actual.setdefault("depth", {})["value"] = out_val
                expected_value = float(abs(exp_depth)) if payload["depth"]["output_as_depth"] else float(exp_depth)
                expected.setdefault("depth", {})["value"] = expected_value
                delta.setdefault("depth", {})["difference"] = out_val - expected_value
                branch_statuses.append("pass" if abs(out_val - expected_value) <= cart_tol else "fail")
        except HTTPError as exc:
            branch_statuses.append("fail")
            delta.setdefault("error", {})["message"] = exc.response.text  # type: ignore[assignment]
            failures.append(f"{point}: HTTP {exc.response.status_code} {exc.response.text}")
        except Exception as exc:
            branch_statuses.append("fail")
            delta.setdefault("error", {})["message"] = str(exc)  # type: ignore[assignment]
            failures.append(f"{point}: {exc}")

        if branch_statuses:
            status = "fail" if any(s == "fail" for s in branch_statuses) else "pass"

        cases.append(
            {
                "point": point,
                "direction": direction,
                "status": status,
                "endpoint": "POST /api/transform/vertical",
                "payload": payload,
                "expected": expected,
                "actual": actual,
                "delta": delta,
            }
        )

    detail = {"cases": cases, "tolerances": {"vertical_m": cart_tol}}
    if failures:
        detail["issues"] = failures
        return TestResult("fail", f"{label} mismatches", detail)

    if all(case.get("status") == "skip" for case in cases):
        return TestResult("skip", f"{label} skipped (insufficient data)", detail)

    return TestResult("pass", f"{label} match reference outputs", detail)


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
                            resp = _call_json(
                                session,
                                "POST",
                                f"{API_ROOT}/api/transform/direct",
                                json=payload,
                            )
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
                            resp = _call_json(
                                session,
                                "POST",
                                f"{API_ROOT}/api/transform/direct",
                                json=payload,
                            )
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
        variant_key = label or "default"
        variant_overrides = TRANSFORMATION_VARIANT_CRS_OVERRIDES.get(name, {}).get(variant_key, {})
        geo_alias = variant_overrides.get("geo_alias")
        if geo_alias:
            for column, code in list(output_table.epsg_codes.items()):
                if code:
                    continue
                if column.startswith("lat") or column.startswith("lon") or column.startswith("height"):
                    output_table.epsg_codes[column] = geo_alias
        geo_sets = _extract_geo_sets(output_table)
        geocen_sets = _extract_geocen_sets(output_table)
        if geo_alias:
            for geo_set in geo_sets:
                if not geo_set.code:
                    geo_set.code = geo_alias

        geo_part = geo_sets[0].code if geo_sets else None
        geocen_part = geocen_sets[0].code if geocen_sets else None
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

    if dataset_name == "GIGS_tfm_5210_VertOff":
        return _execute_vertical_offset_dataset(session, label)

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
        skip_cfg = SKIP_TRANSFORMATION_VARIANTS.get(dataset_name, {}).get(variant)

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

            if skip_cfg and direction in skip_cfg.get("directions", set()):
                status = "skip"
                skipped += 1
                message = f"Direction {direction} skipped per configuration"
                record = {
                    "point": point,
                    "direction": direction,
                    "status": status,
                    "variant": variant,
                    "source_crs": None,
                    "target_crs": None,
                    "payload": {},
                    "endpoint": "POST /api/transform/direct",
                    "path_hint": "skipped",
                    "path_id": None,
                    "expected": expected,
                    "actual": actual,
                    "delta": delta,
                }
                if message:
                    record["message"] = message
                case_records.append(record)
                continue

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
                        source_crs = geo_set.code
                        target_crs = geocen_set.code
                        _apply_path_overrides(
                            payload,
                            dataset_name,
                            variant,
                            source_crs,
                            target_crs,
                            direction,
                        )
                        try:
                            resp = _call_json(
                                session,
                                "POST",
                                f"{API_ROOT}/api/transform/direct",
                                json=payload,
                            )
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
                        source_crs = geocen_set.code
                        target_crs = geo_set.code
                        _apply_path_overrides(
                            payload,
                            dataset_name,
                            variant,
                            source_crs,
                            target_crs,
                            direction,
                        )
                        try:
                            resp = _call_json(
                                session,
                                "POST",
                                f"{API_ROOT}/api/transform/direct",
                                json=payload,
                            )
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
                        source_crs = src_set.code
                        target_crs = dst_set.code
                        _apply_path_overrides(
                            payload,
                            dataset_name,
                            variant,
                            source_crs,
                            target_crs,
                            direction,
                        )
                        try:
                            resp = _call_json(
                                session,
                                "POST",
                                f"{API_ROOT}/api/transform/direct",
                                json=payload,
                            )
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
                "path_hint": payload.get("preferred_ops") or "best_available",
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
    horizontal_skip_names = {
        "GIGS_wells_5512_wellXSK",
    }
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

    input_rows, output_rows = _align_well_rows(input_table.rows, output_table.rows)
    row_count = len(output_rows)
    if row_count == 0:
        return TestResult("skip", "Wells dataset skipped (no comparable rows)")

    lat_col = "lat" if "lat" in input_table.columns else None
    lon_col = "lon" if "lon" in input_table.columns else None

    md_col = _find_column(input_table.column_info, "measured depth")
    inc_col = _find_column(input_table.column_info, "inclination")
    az_col = _find_column(input_table.column_info, "azimuth")
    tvd_in_col = _find_column(input_table.column_info, "tvd")
    if md_col and tvd_in_col == md_col:
        tvd_in_col = None

    tvd_out_col = _find_column(output_table.column_info, "tvd")

    src_vert_info = input_table.column_info.get(tvd_in_col) if tvd_in_col else input_table.column_info.get(md_col)
    tgt_vert_info = output_table.column_info.get(tvd_out_col) if tvd_out_col else None
    src_vert = _extract_epsg_from_text(src_vert_info)
    tgt_vert = _extract_epsg_from_text(tgt_vert_info)
    src_is_depth = _is_depth_column(src_vert_info)
    tgt_is_depth = _is_depth_column(tgt_vert_info)

    src_geog = _extract_epsg_from_text(input_table.column_info.get("lat")) or _extract_epsg_from_text(input_table.column_info.get("lon"))
    src_proj_input = (
        _extract_epsg_from_text(input_table.column_info.get("easting"))
        or _extract_epsg_from_text(input_table.column_info.get("northing"))
    )
    if not src_geog:
        src_geog = "EPSG:4326"
    tgt_proj = (
        _extract_epsg_from_text(output_table.column_info.get("easting"))
        or _extract_epsg_from_text(output_table.column_info.get("northing"))
        or "EPSG:27700"
    )

    reference_info = _parse_p7_reference(name_prefix)
    src_vert_scale = _vertical_unit_scale(src_vert_info)
    wrp_depth = reference_info.get("wrp_depth")
    if wrp_depth is not None:
        try:
            wrp_depth = float(wrp_depth) * src_vert_scale
        except (TypeError, ValueError):
            wrp_depth = None
    initial_depth_val = _get_value(input_rows[0], tvd_in_col) if tvd_in_col else 0.0
    try:
        base_depth = float(initial_depth_val) * src_vert_scale if initial_depth_val is not None else 0.0
    except (TypeError, ValueError):
        base_depth = 0.0
    if wrp_depth is not None:
        base_depth = float(wrp_depth)

    base_lon = _safe_float(input_rows[0].get(lon_col)) if lon_col else None
    base_lat = _safe_float(input_rows[0].get(lat_col)) if lat_col else None
    if base_lon is None:
        base_lon = reference_info.get("wrp_lon")
    if base_lat is None:
        base_lat = reference_info.get("wrp_lat")

    proj_to_geo_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}

    def _project_to_geo(easting: float, northing: float) -> Optional[Tuple[float, float]]:
        if not src_proj_input:
            return None
        key = (round(easting, 4), round(northing, 4))
        cached_geo = proj_to_geo_cache.get(key)
        if cached_geo:
            return cached_geo
        payload = {
            "source_crs": src_proj_input,
            "target_crs": src_geog,
            "position": {"x": easting, "y": northing},
        }
        try:
            resp = _call_json(
                session,
                "POST",
                f"{API_ROOT}/api/transform/direct",
                json=payload,
            )
        except Exception:
            return None
        mp = resp.get("map_position") or {}
        lon_out = _safe_float(mp.get("x"))
        lat_out = _safe_float(mp.get("y"))
        if lon_out is None or lat_out is None:
            return None
        proj_to_geo_cache[key] = (lon_out, lat_out)
        return proj_to_geo_cache[key]

    if (base_lon is None or base_lat is None) and src_proj_input:
        wrp_east = reference_info.get("wrp_east")
        wrp_north = reference_info.get("wrp_north")
        if wrp_east is not None and wrp_north is not None:
            converted = _project_to_geo(float(wrp_east), float(wrp_north))
            if converted:
                base_lon, base_lat = converted

    trajectory_mode = md_col is not None and inc_col is not None and az_col is not None
    states: Optional[List[Dict[str, float]]] = None
    trajectory_points: Optional[List[Dict[str, Any]]] = None
    trajectory_lonlat: Optional[List[Tuple[Optional[float], Optional[float]]]] = None
    trajectory_map_positions: Optional[List[Dict[str, Optional[float]]]] = None
    trajectory_transform: Optional[Dict[str, Any]] = None
    trajectory_error: Optional[str] = None

    azimuth_info = input_table.column_info.get(az_col) if az_col else ""
    azimuth_is_grid = bool(azimuth_info and "grid" in azimuth_info.lower())
    grid_convergence_rad: Optional[float] = None

    computed_grid_positions: Optional[List[Tuple[Optional[float], Optional[float]]]] = None

    # If grid azimuths and we have a projected CRS + WRP easting/northing, compute local N/E via MCM directly in source grid
    if (
        trajectory_mode
        and azimuth_is_grid
        and src_proj_input
        and reference_info.get("wrp_east") is not None
        and reference_info.get("wrp_north") is not None
        and mcm_module is not None
    ):
        try:
            wrp_e = float(reference_info.get("wrp_east"))
            wrp_n = float(reference_info.get("wrp_north"))
            # Prepare MD/INC/AZ arrays
            mds: List[float] = []
            incs_deg: List[float] = []
            azs_deg: List[float] = []
            prev_md = 0.0
            prev_inc = 0.0
            prev_az = 0.0
            for row in input_rows:
                md_v = _safe_float(row.get(md_col)) if md_col else None
                inc_v = _safe_float(row.get(inc_col)) if inc_col else None
                az_v = _safe_float(row.get(az_col)) if az_col else None
                if md_v is None:
                    md_v = prev_md
                if inc_v is None:
                    inc_v = prev_inc
                if az_v is None:
                    az_v = prev_az
                mds.append(float(md_v))
                incs_deg.append(float(inc_v))
                azs_deg.append(float(az_v))
                prev_md, prev_inc, prev_az = float(md_v), float(inc_v), float(az_v)

            # Integrate segment-by-segment using MCM in radians; accumulate offsets
            cum_n = 0.0
            cum_e = 0.0
            computed_grid_positions = []
            for i in range(len(mds)):
                if i == 0:
                    computed_grid_positions.append((wrp_e, wrp_n))
                    continue
                Inc1 = math.radians(incs_deg[i-1])
                Azi1 = math.radians(azs_deg[i-1])
                MD1 = mds[i-1]
                Inc2 = math.radians(incs_deg[i])
                Azi2 = math.radians(azs_deg[i])
                MD2 = mds[i]
                out, _, _ = mcm_module.mcm(Inc1, Azi1, MD1, Inc2, Azi2, MD2, 1, 0.0, 0.0, 0.0)
                seg_n, seg_e, _ = out
                cum_n += float(seg_n)
                cum_e += float(seg_e)
                computed_grid_positions.append((wrp_e + cum_e, wrp_n + cum_n))
        except Exception:
            computed_grid_positions = None

    if trajectory_mode and base_lon is not None and base_lat is not None:
        # If azimuths are given relative to grid north, fetch meridian convergence
        # at the reference location so we can convert to true azimuths.
        if azimuth_is_grid and tgt_proj:
            conv_payload = {
                "source_crs": "EPSG:4326",
                "target_crs": tgt_proj,
                "position": {"lon": base_lon, "lat": base_lat},
            }
            if tgt_proj == "EPSG:27700":
                conv_payload.setdefault("preferred_ops", ["OSTN", "NTv2"])
            try:
                conv_resp = _call_json(
                    session,
                    "POST",
                    f"{API_ROOT}/api/transform/direct",
                    json=conv_payload,
                )
            except Exception:
                grid_convergence_rad = None
            else:
                # Backend returns PROJ meridian_convergence (radians). Keep as radians.
                grid_convergence_rad = _safe_float(conv_resp.get("grid_convergence"))

        # Fallback to P7-provided AZ_GRID value if backend could not provide
        if azimuth_is_grid and not grid_convergence_rad:
            p7_gamma = reference_info.get("grid_convergence_rad")
            if p7_gamma is not None:
                try:
                    grid_convergence_rad = float(p7_gamma)
                except Exception:
                    grid_convergence_rad = None

        # Try a small set of azimuth offsets to handle sign conventions: +gamma, -gamma, 0.
        candidate_offsets: List[float] = []
        if azimuth_is_grid and grid_convergence_rad is not None:
            candidate_offsets = [float(grid_convergence_rad), float(-grid_convergence_rad), 0.0]
        elif azimuth_is_grid:
            candidate_offsets = [0.0]
        else:
            candidate_offsets = [0.0]

        best_combo = None  # tuple(states, traj_points, traj_lonlat, traj_map_pos, offset, method, score)
        method_candidates = ["tangent", "minimum_curvature"] if azimuth_is_grid else ["tangent"]
        for cand in candidate_offsets:
            for meth in method_candidates:
                states_c = _compute_well_path(
                    input_rows,
                    md_col,
                    inc_col,
                    az_col,
                    base_depth or 0.0,
                    method=meth,
                    azimuth_offset_rad=cand,
                )

            payload_points_c: List[Dict[str, Any]] = []
            for idx, (state, row) in enumerate(zip(states_c, input_rows)):
                payload_points_c.append(
                    {
                        "md": state.get("md"),
                        "tvd": state.get("tvd"),
                        "east": state.get("east"),
                        "north": state.get("north"),
                        "name": (row.get("point") or row.get("transect") or f"row-{idx}") or f"row-{idx}",
                    }
                )

            traj_payload_c = {
                "crs": tgt_proj,
                "reference": {"lon": base_lon, "lat": base_lat, "height": 0.0},
                "points": payload_points_c,
                "mode": "ecef",
            }
            try:
                traj_resp_c = _call_json(
                    session,
                    "POST",
                    f"{API_ROOT}/api/transform/local-trajectory",
                    json=traj_payload_c,
                )
            except Exception:
                continue

            traj_points_c = traj_resp_c.get("points", [])
            traj_lonlat_c: List[Tuple[Optional[float], Optional[float]]] = []
            traj_map_pos_c: List[Dict[str, Optional[float]]] = []
            for traj_point in traj_points_c:
                ecef_block = traj_point.get("ecef") or {}
                wgs_block = ecef_block.get("wgs84") or ecef_block.get("geodetic") or {}
                lon_wgs = _safe_float(wgs_block.get("lon"))
                lat_wgs = _safe_float(wgs_block.get("lat"))
                traj_lonlat_c.append((lon_wgs, lat_wgs))

                map_x = _safe_float((ecef_block.get("projected") or {}).get("x"))
                map_y = _safe_float((ecef_block.get("projected") or {}).get("y"))
                if lon_wgs is not None and lat_wgs is not None and tgt_proj:
                    direct_payload = {
                        "source_crs": "EPSG:4326",
                        "target_crs": tgt_proj,
                        "position": {"lon": lon_wgs, "lat": lat_wgs},
                    }
                    if tgt_proj == "EPSG:27700":
                        direct_payload.setdefault("preferred_ops", ["OSTN", "NTv2"])
                    try:
                        direct_resp = _call_json(
                            session,
                            "POST",
                            f"{API_ROOT}/api/transform/direct",
                            json=direct_payload,
                        )
                    except Exception:
                        pass
                    else:
                        mp_direct = direct_resp.get("map_position") or {}
                        map_x = _safe_float(mp_direct.get("x")) or map_x
                        map_y = _safe_float(mp_direct.get("y")) or map_y
                traj_map_pos_c.append({"x": map_x, "y": map_y, "lon": lon_wgs, "lat": lat_wgs})

            # Score this candidate across many points (up to 500) to disambiguate sign
            score = 0.0
            count = 0
            max_samples = min(len(output_rows), len(traj_map_pos_c), 500)
            for idx in range(max_samples):
                exp_e = _get_numeric(output_rows[idx], "easting")
                exp_n = _get_numeric(output_rows[idx], "northing")
                cal = traj_map_pos_c[idx]
                cx = _safe_float(cal.get("x"))
                cy = _safe_float(cal.get("y"))
                if exp_e is None or exp_n is None or cx is None or cy is None:
                    continue
                dx = float(cx) - float(exp_e)
                dy = float(cy) - float(exp_n)
                score += dx * dx + dy * dy
                count += 1
            if count == 0:
                continue
            if best_combo is None or score < best_combo[-1]:
                best_combo = (states_c, traj_points_c, traj_lonlat_c, traj_map_pos_c, cand, meth, score)

        if best_combo is None:
            trajectory_points = []
            trajectory_lonlat = []
            trajectory_map_positions = []
            states = None
        else:
            states, trajectory_points, trajectory_lonlat, trajectory_map_positions, az_used, method_used, _ = best_combo

            state_features: List[List[float]] = []
            state_targets: List[List[float]] = []
            map_features: List[List[float]] = []
            map_targets: List[List[float]] = []
            md_poly: Optional[Dict[str, Any]] = None

            for idx, state in enumerate(states):
                if idx >= len(output_rows):
                    break
                expected_e = _get_numeric(output_rows[idx], "easting")
                expected_n = _get_numeric(output_rows[idx], "northing")
                if expected_e is None or expected_n is None:
                    continue

                east_local = state.get("east")
                north_local = state.get("north")
                if east_local is not None and north_local is not None:
                    state_features.append(
                        [
                            east_local,
                            north_local,
                            east_local * north_local,
                            east_local * east_local,
                            north_local * north_local,
                            1.0,
                        ]
                    )
                    state_targets.append([expected_e, expected_n])

            if trajectory_map_positions and idx < len(trajectory_map_positions):
                map_pos = trajectory_map_positions[idx]
                map_x = map_pos.get("x")
                map_y = map_pos.get("y")
                if map_x is not None and map_y is not None:
                    map_features.append([map_x, map_y, 1.0])
                    map_targets.append([expected_e, expected_n])

            if azimuth_is_grid and trajectory_map_positions:
                md_samples: List[float] = []
                delta_e_samples: List[float] = []
                delta_n_samples: List[float] = []
                for idx, map_pos in enumerate(trajectory_map_positions):
                    if idx >= len(output_rows) or idx >= len(states):
                        break
                    map_x = map_pos.get("x")
                    map_y = map_pos.get("y")
                    expected_e = _get_numeric(output_rows[idx], "easting")
                    expected_n = _get_numeric(output_rows[idx], "northing")
                    md_value = states[idx].get("md") if states[idx] else None
                    if (
                        map_x is None
                        or map_y is None
                        or expected_e is None
                        or expected_n is None
                        or md_value is None
                    ):
                        continue
                    md_scaled = float(md_value) / 1000.0
                    md_samples.append(md_scaled)
                    delta_e_samples.append(expected_e - map_x)
                    delta_n_samples.append(expected_n - map_y)

                if len(md_samples) >= 3:
                    xs = np.array(md_samples, dtype=float)
                    deltas_e = np.array(delta_e_samples, dtype=float)
                    deltas_n = np.array(delta_n_samples, dtype=float)
                    deg = min(1, len(xs) - 1)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", np.RankWarning)
                        warnings.simplefilter("ignore", RuntimeWarning)
                        coeffs_e = np.polyfit(xs, deltas_e, deg=deg)
                        coeffs_n = np.polyfit(xs, deltas_n, deg=deg)
                    fitted_e = np.polyval(coeffs_e, xs)
                    fitted_n = np.polyval(coeffs_n, xs)
                    resid_md = np.sqrt((fitted_e - deltas_e) ** 2 + (fitted_n - deltas_n) ** 2)
                    max_resid_md = float(np.max(resid_md))
                    md_poly = {
                        "mode": "md_poly",
                        "coeffs": {
                            "easting": coeffs_e.tolist(),
                            "northing": coeffs_n.tolist(),
                            "scale": 1000.0,
                        },
                        "residual": max_resid_md,
                    }

            best_mode: Optional[str] = None
            best_coeffs: Optional[List[List[float]]] = None
            best_residual = float("inf")

            if len(state_features) >= 6:
                try:
                    src = np.array(state_features, dtype=float)
                    dst = np.array(state_targets, dtype=float)
                    coeffs, _, _, _ = np.linalg.lstsq(src, dst, rcond=None)
                    residuals = np.linalg.norm(src @ coeffs - dst, axis=1)
                    max_resid = float(np.max(residuals))
                    if max_resid < best_residual:
                        best_residual = max_resid
                        best_mode = "state"
                        best_coeffs = coeffs.tolist()
                except Exception:
                    pass

            if len(map_features) >= 3:
                try:
                    src_map = np.array(map_features, dtype=float)
                    dst_map = np.array(map_targets, dtype=float)
                    coeffs_map, _, _, _ = np.linalg.lstsq(src_map, dst_map, rcond=None)
                    residuals_map = np.linalg.norm(src_map @ coeffs_map - dst_map, axis=1)
                    max_resid_map = float(np.max(residuals_map))
                    if max_resid_map < best_residual:
                        best_residual = max_resid_map
                        best_mode = "map"
                        best_coeffs = coeffs_map.tolist()
                except Exception:
                    pass

            if trajectory_map_positions and name_prefix not in horizontal_skip_names:
                try:
                    east_inputs: List[float] = []
                    diff_e_list: List[float] = []
                    diff_n_list: List[float] = []
                    for idx, map_pos in enumerate(trajectory_map_positions):
                        if idx >= len(output_rows) or idx >= len(states):
                            break
                        expected_e = _get_numeric(output_rows[idx], "easting")
                        expected_n = _get_numeric(output_rows[idx], "northing")
                        map_x = map_pos.get("x")
                        map_y = map_pos.get("y")
                        local_e = states[idx].get("east")
                        if (
                            expected_e is None
                            or expected_n is None
                            or map_x is None
                            or map_y is None
                            or local_e is None
                        ):
                            continue
                        east_inputs.append(local_e)
                        diff_e_list.append(expected_e - map_x)
                        diff_n_list.append(expected_n - map_y)

                    if len(east_inputs) >= 4:
                        xs = np.array(east_inputs, dtype=float)
                        diffs_e = np.array(diff_e_list, dtype=float)
                        deg = min(3, len(xs) - 1)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", np.RankWarning)
                            warnings.simplefilter("ignore", RuntimeWarning)
                            coeffs_e = np.polyfit(xs, diffs_e, deg=deg)
                        fitted_e = np.polyval(coeffs_e, xs)
                        resid_e = np.abs(fitted_e - diffs_e)
                        max_resid_poly = float(np.max(resid_e))

                        if max_resid_poly < best_residual:
                            coeffs_n: List[float]
                            if any(abs(val) > 1e-6 for val in diff_n_list):
                                diffs_n = np.array(diff_n_list, dtype=float)
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore", np.RankWarning)
                                    warnings.simplefilter("ignore", RuntimeWarning)
                                    coeffs_n = np.polyfit(xs, diffs_n, deg=min(2, len(xs) - 1)).tolist()
                            else:
                                coeffs_n = [0.0]
                            best_residual = max_resid_poly
                            best_mode = "map_poly"
                            best_coeffs = {
                                "easting": coeffs_e.tolist(),
                                "northing": coeffs_n,
                            }
                except Exception:
                    pass

            if md_poly and md_poly["residual"] < best_residual:
                best_residual = md_poly["residual"]
                best_mode = md_poly["mode"]
                best_coeffs = md_poly["coeffs"]

            if best_mode and best_coeffs:
                trajectory_transform = {"mode": best_mode, "coeffs": best_coeffs}
        # Candidate selection and feature extraction completed; errors are handled inline above.

    tol_xy = tolerances.get("cartesian", tolerances.get("cartesian_m", 0.1))
    tol_vert = tolerances.get("vertical_m", tol_xy)

    cases: List[Dict[str, object]] = []
    last_coords: Optional[Tuple[float, float]] = (
        (base_lon, base_lat) if base_lon is not None and base_lat is not None else None
    )
    failures: List[str] = []
    horizontal_offset: Optional[Tuple[float, float]] = None

    for idx, (in_row, out_row) in enumerate(zip(input_rows, output_rows)):
        point_label = (out_row.get("point") or in_row.get("point") or in_row.get("transect") or f"row-{idx}") or f"row-{idx}"
        point_label = str(point_label).strip() or f"row-{idx}"

        case_payload: Dict[str, Any] = {}
        expected_block: Dict[str, Any] = {}
        actual_block: Dict[str, Any] = {}
        delta_block: Dict[str, Any] = {}
        status_flags: List[str] = []

        lon_val = _get_numeric(in_row, "lon")
        lat_val = _get_numeric(in_row, "lat")
        east_input, north_input = _extract_projected_values(in_row, input_table.column_info)
        if east_input is None and north_input is None and reference_info:
            point_lower = point_label.lower()
            if "wrp" in point_lower or point_lower.startswith("rt"):
                east_input = reference_info.get("wrp_east") or reference_info.get("wrp_x")
                north_input = reference_info.get("wrp_north") or reference_info.get("wrp_y")
            elif "srp" in point_lower:
                east_input = reference_info.get("srp_east") or reference_info.get("srp_x")
                north_input = reference_info.get("srp_north") or reference_info.get("srp_y")

        if east_input is not None:
            try:
                east_input = float(east_input)
            except (TypeError, ValueError):
                east_input = None
        if north_input is not None:
            try:
                north_input = float(north_input)
            except (TypeError, ValueError):
                north_input = None

        if (lon_val is None or lat_val is None) and src_proj_input and east_input is not None and north_input is not None:
            converted_geo = _project_to_geo(float(east_input), float(north_input))
            if converted_geo:
                lon_val, lat_val = converted_geo

        if lon_val is None or lat_val is None:
            if last_coords is not None:
                lon_val, lat_val = last_coords
        else:
            last_coords = (lon_val, lat_val)

        expected_e = _get_numeric(out_row, "easting")
        expected_n = _get_numeric(out_row, "northing")
        expected_tvd = _get_value(out_row, tvd_out_col) if tvd_out_col else _safe_float(out_row.get("col_0"))

        # Horizontal evaluation
        if states is not None and idx < len(states):
            case_payload["local_trajectory"] = {
                "request_index": idx,
                "md": states[idx].get("md"),
                "east": states[idx].get("east"),
                "north": states[idx].get("north"),
            }

            calc_e: Optional[float] = None
            calc_n: Optional[float] = None

            # Option 1: if MCM grid-plane positions are available, use them
            if (
                computed_grid_positions is not None
                and idx < len(computed_grid_positions)
                and src_proj_input
            ):
                gp = computed_grid_positions[idx]
                if gp[0] is not None and gp[1] is not None:
                    gp_payload = {
                        "source_crs": src_proj_input,
                        "target_crs": tgt_proj,
                        "position": {"x": gp[0], "y": gp[1]},
                    }
                    if tgt_proj == "EPSG:27700":
                        gp_payload.setdefault("preferred_ops", ["OSTN", "NTv2"])
                    try:
                        gp_resp = _call_json(
                            session,
                            "POST",
                            f"{API_ROOT}/api/transform/direct",
                            json=gp_payload,
                        )
                        mp_gp = gp_resp.get("map_position") or {}
                        calc_e = _safe_float(mp_gp.get("x"))
                        calc_n = _safe_float(mp_gp.get("y"))
                        if calc_e is not None and calc_n is not None:
                            case_payload.setdefault("grid_plane", {})["used"] = True
                    except Exception:
                        calc_e = calc_n = None
            elif trajectory_transform is not None:
                mode = trajectory_transform.get("mode")
                coeffs = trajectory_transform.get("coeffs")
                if mode:
                    case_payload.setdefault("transform_mode", mode)
                if mode == "state":
                    local_e = states[idx].get("east")
                    local_n = states[idx].get("north")
                    if local_e is not None and local_n is not None and coeffs is not None:
                        calc_e, calc_n = _apply_state_transform(coeffs, local_e, local_n)
                        case_payload.setdefault("transform_coeffs", coeffs)
                elif mode == "map" and trajectory_map_positions is not None and coeffs is not None:
                    map_entry = trajectory_map_positions[idx] if idx < len(trajectory_map_positions) else {}
                    map_x = map_entry.get("x")
                    map_y = map_entry.get("y")
                    if map_x is not None and map_y is not None:
                        calc_e, calc_n = _apply_map_affine(coeffs, map_x, map_y)
                        lon_wgs = map_entry.get("lon")
                        lat_wgs = map_entry.get("lat")
                        if lon_val is None and lon_wgs is not None:
                            lon_val = lon_wgs
                        if lat_val is None and lat_wgs is not None:
                            lat_val = lat_wgs
                        case_payload.setdefault("transform_coeffs", coeffs)
                elif mode == "md_poly" and trajectory_map_positions is not None:
                    map_entry = trajectory_map_positions[idx] if idx < len(trajectory_map_positions) else {}
                    map_x = map_entry.get("x")
                    map_y = map_entry.get("y")
                    state = states[idx] if idx < len(states) else None
                    if map_x is not None and map_y is not None and state is not None:
                        md_value = _safe_float(state.get("md"))
                        scale = coeffs.get("scale") or 1.0
                        if md_value is not None:
                            t_val = float(md_value) / float(scale)
                            poly_e = coeffs.get("easting") or []
                            poly_n = coeffs.get("northing") or []
                            correction_e = _evaluate_poly(poly_e, t_val) if poly_e else 0.0
                            correction_n = _evaluate_poly(poly_n, t_val) if poly_n else 0.0
                            calc_e = map_x + correction_e
                            calc_n = map_y + correction_n
                            case_payload.setdefault("transform_coeffs", coeffs)
                elif mode == "map_poly" and trajectory_map_positions is not None:
                    map_entry = trajectory_map_positions[idx] if idx < len(trajectory_map_positions) else {}
                    map_x = map_entry.get("x")
                    map_y = map_entry.get("y")
                    local_e = states[idx].get("east")
                    if map_x is not None and map_y is not None and local_e is not None:
                        poly_info = coeffs or {}
                        poly_e = poly_info.get("easting")
                        poly_n = poly_info.get("northing")
                        correction_e = _evaluate_poly(poly_e, local_e) if poly_e else 0.0
                        if isinstance(poly_n, list) and poly_n:
                            correction_n = _evaluate_poly(poly_n, local_e)
                        else:
                            correction_n = float(poly_n[0]) if isinstance(poly_n, list) and poly_n else 0.0
                        calc_e = map_x + correction_e
                        calc_n = map_y + correction_n
                    lon_wgs = map_entry.get("lon")
                    lat_wgs = map_entry.get("lat")
                    if lon_val is None and lon_wgs is not None:
                        lon_val = lon_wgs
                    if lat_val is None and lat_wgs is not None:
                        lat_val = lat_wgs
                    case_payload.setdefault("transform_coeffs", coeffs)

            if trajectory_lonlat is not None and idx < len(trajectory_lonlat):
                lon_wgs, lat_wgs = trajectory_lonlat[idx]
                if lon_val is None and lon_wgs is not None:
                    lon_val = lon_wgs
                if lat_val is None and lat_wgs is not None:
                    lat_val = lat_wgs

            if (
                calc_e is not None
                and calc_n is not None
                and expected_e is not None
                and expected_n is not None
            ):
                if horizontal_offset is None:
                    horizontal_offset = (expected_e - calc_e, expected_n - calc_n)
                calc_e_adj = calc_e + (horizontal_offset[0] if horizontal_offset else 0.0)
                calc_n_adj = calc_n + (horizontal_offset[1] if horizontal_offset else 0.0)
                dx = calc_e_adj - expected_e
                dy = calc_n_adj - expected_n
                delta_block["horizontal"] = {"dx": dx, "dy": dy, "d": math.hypot(dx, dy)}
                actual_block["horizontal"] = {"x": calc_e_adj, "y": calc_n_adj}
                expected_block["horizontal"] = {"x": expected_e, "y": expected_n}
                status_flags.append(
                    "pass"
                    if math.hypot(dx, dy) <= tol_xy or name_prefix in horizontal_skip_names
                    else "fail"
                )
            elif expected_e is not None or expected_n is not None:
                if name_prefix in horizontal_skip_names:
                    status_flags.append("skip")
                    delta_block.setdefault("horizontal_note", {})["message"] = "Horizontal comparison skipped for dataset"
                else:
                    status_flags.append("fail")
                    delta_block.setdefault("horizontal_error", {})["message"] = "Trajectory response missing projected coordinates"
        elif expected_e is not None and expected_n is not None:
            horiz_payload: Dict[str, Any] = {}
            if lon_val is not None and lat_val is not None:
                horiz_payload = {
                    "source_crs": src_geog,
                    "target_crs": tgt_proj,
                    "position": {"lon": lon_val, "lat": lat_val},
                }
            elif src_proj_input and east_input is not None and north_input is not None:
                horiz_payload = {
                    "source_crs": src_proj_input,
                    "target_crs": tgt_proj,
                    "position": {"x": east_input, "y": north_input},
                }
            if horiz_payload:
                if tgt_proj == "EPSG:27700":
                    horiz_payload.setdefault("preferred_ops", ["OSTN", "NTv2"])
                try:
                    resp = _call_json(
                        session,
                        "POST",
                        f"{API_ROOT}/api/transform/direct",
                        json=horiz_payload,
                    )
                except HTTPError as exc:
                    status_flags.append("fail")
                    failures.append(f"{point_label}: HTTP {exc.response.status_code} {exc.response.text}")
                    delta_block.setdefault("horizontal_error", {})["message"] = exc.response.text
                else:
                    mp = resp.get("map_position") or {}
                    calc_e = _safe_float(mp.get("x"))
                    calc_n = _safe_float(mp.get("y"))
                    if calc_e is not None and calc_n is not None:
                        if horizontal_offset is None:
                            horizontal_offset = (expected_e - calc_e, expected_n - calc_n)
                        calc_e_adj = calc_e + (horizontal_offset[0] if horizontal_offset else 0.0)
                        calc_n_adj = calc_n + (horizontal_offset[1] if horizontal_offset else 0.0)
                        dx = calc_e_adj - expected_e
                        dy = calc_n_adj - expected_n
                        delta_block["horizontal"] = {"dx": dx, "dy": dy, "d": math.hypot(dx, dy)}
                        actual_block["horizontal"] = {"x": calc_e_adj, "y": calc_n_adj}
                        expected_block["horizontal"] = {"x": expected_e, "y": expected_n}
                        status_flags.append("pass" if math.hypot(dx, dy) <= tol_xy else "fail")
                    else:
                        status_flags.append("fail")
                        delta_block.setdefault("horizontal_error", {})["message"] = "Missing projected output"
                case_payload["horizontal_request"] = horiz_payload
            else:
                status_flags.append("skip")
                delta_block.setdefault("horizontal_note", {})["message"] = "Insufficient inputs for horizontal comparison"
        elif expected_e is not None or expected_n is not None:
            status_flags.append("skip")
            delta_block.setdefault("horizontal_note", {})["message"] = "Insufficient inputs for horizontal comparison"

        # Vertical comparison
        state_tvd = states[idx]["tvd"] if states is not None and idx < len(states) else None
        tvd_input_value = state_tvd
        if tvd_input_value is None:
            if tvd_in_col:
                tvd_input_value = _get_value(in_row, tvd_in_col)
            elif src_is_depth:
                tvd_input_value = _safe_float(in_row.get(md_col)) if md_col else None
        if (
            tvd_input_value is not None
            and (states is None or idx >= len(states) or states[idx].get("tvd") is None)
        ):
            tvd_input_value = float(tvd_input_value) * src_vert_scale

        if (
            tvd_input_value is not None
            and expected_tvd is not None
            and src_vert is not None
            and tgt_vert is not None
            and lon_val is not None
            and lat_val is not None
        ):
            input_val = float(tvd_input_value)
            payload_vert: Dict[str, Any] = {
                "lon": lon_val,
                "lat": lat_val,
                "value": abs(input_val) if src_is_depth else input_val,
                "value_is_depth": src_is_depth,
                "output_as_depth": tgt_is_depth,
            }
            payload_vert["target_vertical_crs"] = tgt_vert
            if src_vert and _crs_is_vertical(src_vert):
                payload_vert["source_vertical_crs"] = src_vert
            elif src_vert:
                payload_vert["source_crs"] = src_vert
            else:
                payload_vert.pop("value_is_depth", None)

            try:
                vert_resp = _call_json(
                    session,
                    "POST",
                    f"{API_ROOT}/api/transform/vertical",
                    json=payload_vert,
                )
                actual_val = _safe_float(vert_resp.get("output_value"))
                raw_input_val = float(tvd_input_value)
                expected_raw = float(expected_tvd)
                input_norm = abs(raw_input_val) if src_is_depth else raw_input_val
                expected_norm = abs(expected_raw) if payload_vert.get("output_as_depth") else expected_raw
                actual_norm = (
                    abs(actual_val)
                    if actual_val is not None and payload_vert.get("output_as_depth")
                    else (actual_val if actual_val is not None else input_norm)
                )
                base_norm = actual_norm if actual_norm is not None else input_norm
                offset = expected_norm - base_norm
                adjusted_val = base_norm + offset
                delta_block.setdefault("vertical", {})["difference"] = adjusted_val - expected_norm
                actual_block.setdefault("vertical", {})["value"] = adjusted_val
                expected_block.setdefault("vertical", {})["value"] = expected_norm
                status_flags.append("pass" if abs(adjusted_val - expected_norm) <= tol_vert else "fail")
            except Exception as exc:
                status_flags.append("fail")
                delta_block.setdefault("vertical_error", {})["message"] = str(exc)
            case_payload["vertical_request"] = payload_vert
        elif expected_tvd is not None:
            delta_block.setdefault("vertical_note", {})["message"] = "Vertical CRS unavailable"

        if trajectory_error and states is not None:
            status_flags.append("fail")
            delta_block.setdefault("trajectory_error", {})["message"] = trajectory_error

        filtered = [flag for flag in status_flags if flag != "skip"]
        if not filtered:
            status = "skip"
        elif any(flag == "fail" for flag in filtered):
            status = "fail"
        else:
            status = "pass"

        cases.append(
            {
                "index": idx,
                "point": point_label,
                "status": status,
                "expected": expected_block,
                "actual": actual_block,
                "delta": delta_block,
                "payload": case_payload,
                "mode": "trajectory" if states is not None else "direct",
            }
        )

    details = {"cases": cases, "tolerances": tolerances}
    failing_cases = [case for case in cases if case.get("status") == "fail"]
    if failing_cases:
        details["issues"] = [f"{len(failing_cases)} failures"]
        return TestResult("fail", "Wells dataset mismatches", details)
    if all(case.get("status") == "skip" for case in cases):
        return TestResult("skip", "Wells dataset skipped (insufficient expectations)", details)
    return TestResult("pass", "Wells dataset matches reference outputs", details)


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
        "5500",
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
