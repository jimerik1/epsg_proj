"""Scaffold tests for GIGS Series 3200 – User-defined Geodetic Data Objects."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: implement /api/crs/parse-custom and /api/transform/custom checks")
def test_user_defined_objects(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 3200 User-defined Geodetic Data Objects test data"
    assert data_dir.exists()
    # TODO: parse XML/WKT definitions, POST to endpoints, and compare against expected outputs.
