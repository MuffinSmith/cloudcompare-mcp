from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.make_profile_fixtures import generate
from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.profile_reconstruction import reconstruct_profile_2d


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


def test_generated_profile_fixtures_reconstruct_as_documented_slots(tmp_path):
    out = tmp_path / "reconstruct-fixtures"
    manifest = generate(out)

    for variant in manifest["variants"]:
        xyz = _read_ply_xyz(out / variant["file"])
        projection = project_points_to_section(
            xyz.tolist(),
            variant["origin_global"],
            variant["normal"],
            half_thickness=manifest["recommended"]["half_thickness"],
        )
        profile = reconstruct_profile_2d(
            projection["uv"],
            closed=True,
            fit_tolerance=manifest["recommended"]["fit_tolerance"],
            ordering_method=manifest["recommended"]["ordering_method"],
            angular_tolerance_degrees=manifest["recommended"]["angular_tolerance_degrees"],
        )

        assert [p["type"] for p in profile["primitives"]] == [
            "line", "arc", "line", "arc"
        ]
        candidate, = [
            item for item in profile["profile_candidates"]
            if item["type"] == "slot_candidate"
        ]
        assert abs(candidate["radius"] - 5.0) <= 0.01
        assert abs(candidate["width"] - 10.0) <= 0.02
        assert abs(candidate["centerline_length"] - 20.0) <= 0.02
        assert abs(candidate["overall_length"] - 30.0) <= 0.03
        assert candidate["line_parallel_error_degrees"] <= 0.2
        assert max(candidate["arc_semicircle_error_degrees"]) <= 0.5
        assert all(
            primitive["fit_residuals"]["max_abs"]
            <= manifest["recommended"]["fit_tolerance"]
            for primitive in profile["primitives"]
        )
