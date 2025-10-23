"""Scaffold tests for GIGS Series 2200 – Predefined Geodetic Data Objects."""
from pathlib import Path

import pytest

from .helpers import load_ascii_table


@pytest.mark.skip(reason="TODO: implement validation against /api/crs/info and /api/crs/parameters")
def test_predefined_objects_metadata(gigs_dataset_root: Path):
    table_path = gigs_dataset_root / "GIGS 2200 Predefined Geodetic Data Objects test data" / "ASCII"
    assert table_path.exists()
    # Example of how to iterate test cases once implemented.
    for txt in table_path.glob("*.txt"):
        rows = load_ascii_table(txt)
        assert rows  # placeholder to enforce parsing
