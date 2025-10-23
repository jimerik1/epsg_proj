"""Utilities to load GIGS 3200 user-defined geodetic data objects."""
from pathlib import Path
from typing import Dict, List

from .helpers import parse_ascii_table

DATA_DIR = Path("docs/standards/GIGS_Test_Dataset_v2.1/GIGS 3200 User-defined Geodetic Data Objects test data/ASCII")


def _read(file_name: str, columns: List[str]) -> List[Dict[str, str]]:
    path = DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(path)
    return parse_ascii_table(path, columns, pad=True)


def projected_crs() -> List[Dict[str, str]]:
    return _read(
        "GIGS_user_3207_ProjectedCRS.txt",
        [
            "code",
            "source",
            "name",
            "base_crs_code",
            "base_crs_name",
            "conversion_code",
            "conversion_name",
            "cs_code",
            "axis1_name",
            "axis1_abbrev",
            "axis1_orientation",
            "axis1_unit",
            "axis2_name",
            "axis2_abbrev",
            "axis2_orientation",
            "axis2_unit",
            "equivalent_epsg",
            "equivalent_name",
            "remarks",
        ],
    )


def geodetic_crs() -> List[Dict[str, str]]:
    return _read(
        "GIGS_user_3205_GeodeticCRS.txt",
        [
            "code",
            "source",
            "name",
            "type",
            "datum_code",
            "cs_code",
            "equivalent_epsg",
            "equivalent_name",
            "early_binding_tfm",
            "remarks",
        ],
    )
