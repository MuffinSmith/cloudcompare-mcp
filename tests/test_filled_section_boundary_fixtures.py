from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.section_boundary import (
    extract_section_boundary_evidence_2d,
    reconstruct_filled_section_profile_2d,
)
from scripts.make_filled_section_boundary_fixtures import generate


def _read_ply_xyz(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="ascii").splitlines()
    end = lines.index("end_header")
    return np.asarray(
        [[float(value) for value in line.split()] for line in lines[end + 1 :]],
        dtype=np.float64,
    )


def _variant(manifest: dict, name: str) -> dict:
    return next(item for item in manifest["variants"] if item["name"] == name)


def _project(path: Path, variant: dict, half_thickness: float) -> dict:
    xyz = _read_ply_xyz(path)
    return project_points_to_section(
        xyz.tolist(),
        variant["origin_global"],
        variant["normal"],
        half_thickness=half_thickness,
    )


def _extract(uv, settings):
    return extract_section_boundary_evidence_2d(
        uv,
        cell_size=settings["cell_size"],
        min_cell_support=settings["min_cell_support"],
        min_component_cells=settings["min_component_cells"],
        max_cells=settings["max_cells"],
        max_boundary_points=settings["max_boundary_points"],
        check_grid_origin_sensitivity=True,
    )


def _reconstruct(uv, settings):
    return reconstruct_filled_section_profile_2d(
        uv,
        cell_size=settings["cell_size"],
        max_edge_length=settings["max_edge_length"],
        fit_tolerance=settings["fit_tolerance"],
        min_cell_support=settings["min_cell_support"],
        min_component_cells=settings["min_component_cells"],
        max_cells=settings["max_cells"],
        max_boundary_points=settings["max_boundary_points"],
        angular_tolerance_degrees=settings["angular_tolerance_degrees"],
        minimum_loop_points=settings["minimum_loop_points"],
        max_loops=settings["max_loops"],
        require_grid_stability=settings["require_grid_stability"],
    )


def test_filled_section_fixture_generator_and_exact_file_reconstruction(tmp_path):
    output = tmp_path / "filled-section-fixtures"
    manifest = generate(output)
    assert json.loads((output / "manifest.json").read_text()) == manifest

    settings = manifest["recommended"]
    for name in ("original", "rotated_translated"):
        variant = _variant(manifest, name)
        projection = _project(
            output / variant["file"],
            variant,
            settings["half_thickness"],
        )
        assert projection["selected_count"] == variant["point_count"]

        result = _reconstruct(projection["uv"], settings)
        assert result["extraction"]["connected_contour_count"] == 3
        assert result["extraction"]["material_component_count"] == 2
        assert result["topology"]["loop_count"] == 3
        assert [loop["role_candidate"] for loop in result["topology"]["loops"]] == [
            "outer",
            "hole",
            "island",
        ]
        assert [loop["nesting_depth"] for loop in result["topology"]["loops"]] == [
            0,
            1,
            2,
        ]
        assert result["raw_points_returned"] is False
        assert "points_uv" not in json.dumps(result)


def test_nonuniform_density_fixture_retains_topology_or_reports_support(tmp_path):
    output = tmp_path / "filled-section-fixtures"
    manifest = generate(output)
    settings = manifest["recommended"]
    variant = _variant(manifest, "nonuniform_density")
    projection = _project(
        output / variant["file"],
        variant,
        settings["half_thickness"],
    )
    evidence = _extract(projection["uv"], settings)
    assert evidence.public["connected_contour_count"] == 3
    assert evidence.public["material_component_count"] == 2
    assert evidence.public["support_statistics"]["coefficient_of_variation"] >= 0
    assert evidence.public["raw_points_returned"] is False


def test_narrow_feature_fixture_is_not_silently_erased(tmp_path):
    output = tmp_path / "filled-section-fixtures"
    manifest = generate(output)
    settings = manifest["recommended"]
    variant = _variant(manifest, "narrow_feature")
    projection = _project(
        output / variant["file"],
        variant,
        settings["half_thickness"],
    )
    evidence = _extract(projection["uv"], settings)
    assert evidence.public["connected_contour_count"] == 1
    assert evidence.public["material_component_count"] == 1

    contour = evidence.public["contours"][0]
    bounds = contour["bounds_uv"]
    bounding_area = (
        (bounds["u"][1] - bounds["u"][0])
        * (bounds["v"][1] - bounds["v"][0])
    )
    # The open notch removes real material from the outer rectangle. Grid area
    # must therefore remain measurably below the contour's bounding rectangle.
    assert abs(contour["signed_grid_area"]) < bounding_area - 1.0


def test_overlapping_layer_fixture_contains_real_depth_ambiguity(tmp_path):
    output = tmp_path / "filled-section-fixtures"
    manifest = generate(output)
    variant = _variant(manifest, "overlapping_layers")
    projection = _project(
        output / variant["file"],
        variant,
        manifest["overlapping_layers_half_thickness"],
    )
    offsets = np.asarray(projection["signed_offsets"], dtype=np.float64)
    assert projection["selected_count"] == variant["point_count"]
    assert float(np.min(offsets)) == pytest.approx(-0.45, abs=1e-12)
    assert float(np.max(offsets)) == pytest.approx(0.45, abs=1e-12)
    assert float(np.percentile(offsets, 10)) < -0.4
    assert float(np.percentile(offsets, 90)) > 0.4


def test_filled_section_fixture_generator_refuses_overwrite(tmp_path):
    output = tmp_path / "filled-section-fixtures"
    generate(output)
    with pytest.raises(FileExistsError):
        generate(output)
