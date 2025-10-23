"""Scaffold tests for GIGS Series 5200 – Coordinate transformation tests."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: implement Helmert/grid transformation validation via API endpoints")
def test_transformation_accuracy(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 5200 Coordinate transformation test data" / "ASCII"
    assert data_dir.exists()
    # TODO: implement per-test logic depending on the transformation type.
