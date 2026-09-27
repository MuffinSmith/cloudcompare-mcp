from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.profile_topology import reconstruct_profile_topology_2d
from scripts.make_profile_topology_fixtures import generate


def _read_ply_xyz(path: Path) -> np.ndarray:
    lines = path.read_text().splitlines()
    end = lines.index("end_header")
    return np.asarray(
        [[float(value) for value in line.split()] for line in lines[end + 1 :]],
        dtype=float,
    )


def test_topology_fixture_generator_and_exact_reconstruction(tmp_path):
    output = tmp_path / "topology-fixtures"
    manifest = generate(output)
    assert json.loads((output / "manifest.json").read_text()) == manifest
    assert manifest["expected"]["loop_count"] == 3
    assert manifest["expected"]["roles"] == ["outer", "hole", "island"]

    settings = manifest["recommended"]
    for variant in manifest["variants"]:
        xyz = _read_ply_xyz(output / variant["file"])
        projection = project_points_to_section(
            xyz.tolist(),
            variant["origin_global"],
            variant["normal"],
            half_thickness=settings["half_thickness"],
        )
        topology = reconstruct_profile_topology_2d(
            projection["uv"],
            max_edge_length=settings["max_edge_length"],
            fit_tolerance=settings["fit_tolerance"],
            angular_tolerance_degrees=settings["angular_tolerance_degrees"],
            minimum_loop_points=settings["minimum_loop_points"],
            max_loops=settings["max_loops"],
        )

        assert topology["loop_count"] == 3
        assert [loop["role_candidate"] for loop in topology["loops"]] == [
            "outer",
            "hole",
            "island",
        ]
        assert [loop["nesting_depth"] for loop in topology["loops"]] == [0, 1, 2]
        assert topology["loops"][1]["parent_loop_id"] == "loop-0"
        assert topology["loops"][2]["parent_loop_id"] == "loop-1"
        assert topology["loops"][0]["area_abs"] == pytest.approx(
            manifest["expected"]["outer_area"], abs=2e-4
        )

        expected_counts = manifest["expected"]["source_point_counts"]
        assert topology["loops"][0]["source_point_count"] == expected_counts["outer"]
        assert topology["loops"][1]["source_point_count"] == expected_counts["hole"]
        assert topology["loops"][2]["source_point_count"] == expected_counts["island"]

        hole_candidate = next(
            candidate
            for candidate in topology["loops"][1]["profile"]["profile_candidates"]
            if candidate["type"] == "circle_profile_candidate"
        )
        island_candidate = next(
            candidate
            for candidate in topology["loops"][2]["profile"]["profile_candidates"]
            if candidate["type"] == "circle_profile_candidate"
        )
        assert hole_candidate["radius"] == pytest.approx(
            manifest["expected"]["hole_radius"], abs=2e-5
        )
        assert island_candidate["radius"] == pytest.approx(
            manifest["expected"]["island_radius"], abs=2e-5
        )
        assert topology["raw_points_returned"] is False


def test_topology_fixture_generator_refuses_overwrite(tmp_path):
    output = tmp_path / "topology-fixtures"
    generate(output)
    with pytest.raises(FileExistsError):
        generate(output)
