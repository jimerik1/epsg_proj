"""Utilities to load GIGS 2200 predefined geodetic data objects."""
from pathlib import Path
from typing import Dict, Iterable, List

from .helpers import parse_ascii_table

DATA_DIR = Path("docs/standards/GIGS_Test_Dataset_v2.1/GIGS 2200 Predefined Geodetic Data Objects test data/ASCII")


def _read(file_name: str, columns: List[str]) -> List[Dict[str, str]]:
    path = DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(path)
    return parse_ascii_table(path, columns, pad=True)


def units() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2201_Unit.txt",
        ["code", "name", "type", "factor", "remarks"],
    )


def ellipsoids() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2202_Ellipsoid.txt",
        ["code", "name", "alias", "semi_major", "inv_flattening", "remarks"],
    )


def prime_meridians() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2203_PrimeMeridian.txt",
        ["code", "name", "alias", "longitude", "remarks"],
    )


def datums() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2204_GeodeticDatum.txt",
        ["code", "name", "alias", "ellipsoid", "prime_meridian", "extent", "remarks"],
    )


def geodetic_crs() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2205_GeodeticCRS.txt",
        ["code", "type", "name", "alias", "datum", "extent", "remarks"],
    )


def conversions() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2206_Conversion.txt",
        ["code", "name", "alias", "method", "extent", "remarks"],
    )


def projected_crs() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2207_ProjectedCRS.txt",
        [
            "code",
            "name",
            "base_crs_code",
            "base_crs_name",
            "conversion_code",
            "conversion_name",
            "extent",
            "remarks",
        ],
    )


def coordinate_transformations() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2208_CoordTfm.txt",
        ["code", "name", "source", "target", "method", "extent", "remarks"],
    )


def vertical_datums() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2209_VerticalDatum.txt",
        ["code", "name", "alias", "type", "extent", "remarks"],
    )


def vertical_crs() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2210_VerticalCRS.txt",
        ["code", "name", "alias", "datum", "extent", "remarks"],
    )


def vertical_transformations() -> List[Dict[str, str]]:
    return _read(
        "GIGS_lib_2211_VertTfm.txt",
        ["code", "name", "source", "target", "method", "extent", "remarks"],
    )
