"""Scaffold tests for GIGS Series 5500 – Wells deviation data."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: validate well trajectories with both ECEF and scale-factor pipelines")
def test_well_trajectories(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 5500 Wells test data"
    assert data_dir.exists()
    # TODO: parse deviation survey files, reuse local trajectory endpoint, confirm outputs.
