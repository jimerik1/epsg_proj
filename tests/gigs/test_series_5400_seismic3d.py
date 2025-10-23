"""Scaffold tests for GIGS Series 5400 – 3D seismic position data."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: convert 3D seismic trajectories via /api/transform/local-trajectory")
def test_seismic_3d(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 5400 3D seismic test data"
    assert data_dir.exists()
    # TODO: implement ingestion of true-distance trajectories and compare endpoints.
