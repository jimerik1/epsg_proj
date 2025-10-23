"""Utility helpers shared by GIGS compliance tests."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np


def parse_ascii_table(path: Path, columns: List[str], pad: bool = False) -> List[Dict[str, Any]]:
    """Parse a GIGS ASCII table using explicit column names.

    The dataset files mix tabs and spaces; this helper normalises whitespace and
    ignores comment lines.  Missing values expressed as ``NULL`` are converted to
    ``None``.
    """

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip() or raw.startswith("#"):
                continue
            parts = [part for part in raw.strip().split("\t") if part != ""]
            if pad and len(parts) < len(columns):
                parts += [""] * (len(columns) - len(parts))
            if len(parts) != len(columns):
                parts = [part for part in raw.strip().split() if part]
                if pad and len(parts) < len(columns):
                    parts += [""] * (len(columns) - len(parts))
            if len(parts) != len(columns):
                raise ValueError(
                    f"Row has {len(parts)} columns, expected {len(columns)} in {path}: {raw}"
                )
            row: Dict[str, Any] = {}
            for key, value in zip(columns, parts):
                row[key] = None if value.upper() == "NULL" else value
            rows.append(row)
    return rows


@dataclass
class ParsedTable:
    columns: List[str]
    rows: List[Dict[str, Any]]
    column_info: Dict[str, str]
    epsg_codes: Dict[str, Optional[str]]


def _sanitize_column(label: str, idx: int, used: Dict[str, int]) -> str:
    lower = label.lower()
    if "latitude" in lower:
        base = "lat"
    elif "longitude" in lower:
        base = "lon"
    elif "geocentric x" in lower:
        base = "x"
    elif "geocentric y" in lower:
        base = "y"
    elif "geocentric z" in lower:
        base = "z"
    elif "easting" in lower and "false" not in lower:
        base = "easting"
    elif "northing" in lower and "false" not in lower:
        base = "northing"
    elif "height" in lower:
        base = "height"
    elif "conversion direction" in lower or "transformation direction" in lower:
        base = "direction"
    elif "transect" in lower:
        base = "transect"
    elif "remarks" in lower:
        base = "remarks"
    elif "point" in lower:
        base = "point"
    elif "ellipsoidal" in lower:
        base = "height"
    else:
        base = f"col_{idx}"

    count = used.get(base, 0)
    used[base] = count + 1
    if count == 0:
        return base
    return f"{base}_{count+1}"


def parse_gigs_table(path: Path) -> ParsedTable:
    """Parse a GIGS ASCII table capturing column metadata and EPSG codes."""

    column_defs: List[tuple[int, str]] = []
    column_info: Dict[str, str] = {}
    epsg_codes: Dict[str, Optional[str]] = {}
    used: Dict[str, int] = {}

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if raw.startswith("# ["):
                match = re.match(r"# \[(\d+)\]:\s*(.+)", raw.strip())
                if match:
                    idx = int(match.group(1))
                    info = match.group(2)
                    column_defs.append((idx, info))
            elif raw.startswith("#"):
                continue
            else:
                break

    column_defs.sort(key=lambda item: item[0])
    columns: List[str] = []
    for idx, info in column_defs:
        name = _sanitize_column(info, idx, used)
        columns.append(name)
        column_info[name] = info
        epsg_match = re.search(r"EPSG CRS code (\d+)", info)
        if epsg_match:
            epsg_codes[name] = f"EPSG:{epsg_match.group(1)}"
        elif "no direct epsg equivalent" in info.lower():
            epsg_codes[name] = None

    rows = parse_ascii_table(path, columns, pad=True)
    return ParsedTable(columns=columns, rows=rows, column_info=column_info, epsg_codes=epsg_codes)


def to_float(value: Any) -> float:
    if value is None:
        raise ValueError("Expected numeric value but got None")
    return float(value)


def almost_equal(actual: Iterable[float], expected: Iterable[float], tol: float) -> bool:
    """Return True if two numeric sequences are within tolerance of each other."""

    a = np.array(list(actual), dtype=float)
    b = np.array(list(expected), dtype=float)
    return np.allclose(a, b, atol=tol)


def dump_failure(context: Dict[str, Any], path: Path) -> None:
    """Persist debug information for failed comparisons to help GIGS reporting."""

    path.write_text(json.dumps(context, indent=2), encoding="utf-8")
