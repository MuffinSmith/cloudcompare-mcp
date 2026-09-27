from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.make_profile_fixtures import generate


def _read_ply_xyz(path: Path) -> np.ndarray:
    lines = path.read_text().splitlines()
    end = lines.index("end_header")
    return np.asarray([[float(v) for v in line.split()] for line in lines[end+1:]], dtype=float)


def test_profile_fixture_generator_is_separate_and_transformed(tmp_path):
    out = tmp_path / "fixtures"
    manifest = generate(out)
    loaded = json.loads((out / "manifest.json").read_text())
    assert loaded == manifest
    assert manifest["expected"]["candidate_type"] == "slot_candidate"
    assert len(manifest["variants"]) == 2
    original = _read_ply_xyz(out / "slot_original.ply")
    transformed = _read_ply_xyz(out / "slot_rotated_translated.ply")
    assert original.shape == transformed.shape
    assert original.shape[0] == manifest["variants"][0]["point_count"]
    assert np.ptp(original[:,2]) == 0
    assert np.max(np.abs(transformed)) > 1e8
    assert not np.allclose(original, transformed)
