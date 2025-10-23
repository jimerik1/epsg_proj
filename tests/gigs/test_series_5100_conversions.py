"""Scaffold tests for GIGS Series 5100 – Conversion tests."""
from pathlib import Path

import pytest


@pytest.mark.skip(reason="TODO: call /api/transform/direct and compare with GIGS_tfm outputs")
def test_conversion_accuracy(gigs_dataset_root: Path):
    data_dir = gigs_dataset_root / "GIGS 5100 Conversion test data" / "ASCII"
    assert data_dir.exists()
    # TODO: iterate ASCII files, POST to API, compare response with expected.
