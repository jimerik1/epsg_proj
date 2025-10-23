"""Scaffold tests for GIGS Series 5300 – 2D seismic position data."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: use /api/transform/local-offset to reproduce expected 2D seismic coordinates")
def test_seismic_2d(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 5300 2D seismic test data"
    assert data_dir.exists()
    # TODO: parse survey files, feed offsets into endpoint, compare responses.
