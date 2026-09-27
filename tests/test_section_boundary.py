from __future__ import annotations

import json
import math

import numpy as np
import pytest

from cloudcompare_mcp.section_boundary import (
    SectionBoundaryError,
    extract_section_boundary_evidence_2d,
    reconstruct_filled_section_profile_2d,
)


def _inside_outer(x: float, y: float) -> bool:
    return (
        -10.0 <= x <= 10.0
        and -8.0 <= y <= 8.0
        and not (-4.0 < x < 4.0 and 2.0 < y <= 8.0)
    )


def filled_fixture(
    *,
    spacing: float = 0.2,
    hole: bool = True,
    island: bool = True,
    angle_degrees: float = 0.0,
) -> np.ndarray:
    xs = np.arange(-10.0, 10.0 + spacing * 0.25, spacing)
    ys = np.arange(-8.0, 8.0 + spacing * 0.25, spacing)
    points = []
    for y in ys:
        for x in xs:
            if not _inside_outer(float(x), float(y)):
                continue
            radius = math.hypot(float(x), float(y) + 2.0)
            if hole and radius < 2.5 and not (island and radius <= 0.8):
                continue
            points.append((float(x), float(y)))
    array = np.asarray(points, dtype=np.float64)
    if angle_degrees:
        angle = math.radians(angle_degrees)
        rotation = np.asarray(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]],
            dtype=np.float64,
        )
        array = array @ rotation.T
    return array


def extract(points: np.ndarray, **kwargs):
    options = {
        "cell_size": 0.5,
        "min_cell_support": 1,
        "min_component_cells": 2,
        "max_cells": 20_000,
        "max_boundary_points": 2048,
    }
    options.update(kwargs)
    return extract_section_boundary_evidence_2d(points, **options)


def test_filled_outer_loop_extracts_one_contour():
    evidence = extract(filled_fixture(hole=False, island=False))
    assert evidence.public["connected_contour_count"] == 1
    assert evidence.public["material_component_count"] == 1
    assert evidence.public["contours"][0]["facing_candidate"] == "material_exterior"
    assert evidence.public["raw_points_returned"] is False
    assert evidence.boundary_points_uv.shape[1] == 2


def test_filled_outer_hole_and_island_extract_three_contours():
    evidence = extract(filled_fixture())
    public = evidence.public
    assert public["connected_contour_count"] == 3
    assert public["material_component_count"] == 2
    assert [item["facing_candidate"] for item in public["contours"]].count(
        "enclosed_empty_region"
    ) == 1
    assert public["ambiguity"]["topology_stable_under_half_cell_origin_shifts"] is True
    assert public["boundary_edge_count"] > 0
    assert public["source_boundary_evidence"]["point_count"] <= 2048


def test_two_disjoint_material_regions_remain_separate_outer_contours():
    spacing = 0.2
    regions = []
    for xmin, xmax in ((-7.0, -3.0), (3.0, 7.0)):
        xs = np.arange(xmin, xmax + spacing * 0.25, spacing)
        ys = np.arange(-2.0, 2.0 + spacing * 0.25, spacing)
        regions.extend((float(x), float(y)) for y in ys for x in xs)
    evidence = extract(np.asarray(regions, dtype=np.float64))
    assert evidence.public["material_component_count"] == 2
    assert evidence.public["connected_contour_count"] == 2
    assert all(
        contour["facing_candidate"] == "material_exterior"
        for contour in evidence.public["contours"]
    )


def test_boundary_extraction_does_not_mutate_source_array():
    points = filled_fixture()
    before = points.copy()
    extract(points)
    assert np.array_equal(points, before)


def test_arbitrary_point_permutation_preserves_geometry_diagnostics():
    points = filled_fixture()
    shuffled = points[np.random.default_rng(15201).permutation(len(points))]
    a = extract(points).public
    b = extract(shuffled).public
    for key in (
        "occupied_cell_count",
        "material_component_count",
        "boundary_cell_count",
        "boundary_edge_count",
        "connected_contour_count",
    ):
        assert a[key] == b[key]
    assert [round(abs(c["signed_grid_area"]), 8) for c in a["contours"]] == [
        round(abs(c["signed_grid_area"]), 8) for c in b["contours"]
    ]


def test_arbitrary_2d_rotation_preserves_three_loop_topology():
    evidence = extract(filled_fixture(angle_degrees=31.0))
    assert evidence.public["connected_contour_count"] == 3
    assert evidence.public["material_component_count"] == 2


def test_rotated_filled_section_hands_off_to_accepted_topology():
    result = reconstruct_filled_section_profile_2d(
        filled_fixture(angle_degrees=31.0),
        cell_size=0.5,
        max_edge_length=1.05,
        fit_tolerance=0.35,
        min_cell_support=1,
        max_cells=20_000,
        max_boundary_points=2048,
        angular_tolerance_degrees=2.0,
        minimum_loop_points=6,
        max_loops=8,
        require_grid_stability=True,
    )
    assert result["topology"]["loop_count"] == 3
    assert [loop["role_candidate"] for loop in result["topology"]["loops"]] == [
        "outer",
        "hole",
        "island",
    ]


def test_nonuniform_density_is_preserved_or_warned_without_repair():
    points = filled_fixture()
    keep = np.ones(len(points), dtype=bool)
    # Thin one side deterministically while retaining enough samples per cell.
    mask = points[:, 0] > 1.0
    thinning = np.flatnonzero(mask)[::3]
    keep[thinning] = False
    evidence = extract(points[keep])
    assert evidence.public["connected_contour_count"] == 3
    assert evidence.public["support_statistics"]["coefficient_of_variation"] >= 0
    assert any(
        "no morphological repair" in assumption.lower()
        for assumption in evidence.public["assumptions"]
    )
    assert evidence.public["ambiguity"]["one_cell_perturbation"][
        "applied_to_reconstruction"
    ] is False


def test_one_cell_bridge_reports_topology_sensitivity_without_repair():
    occupied_cells = {
        *[(i, j) for i in range(3) for j in range(3)],
        *[(i, j) for i in range(5, 8) for j in range(3)],
        (3, 1),
        (4, 1),
    }
    points = []
    for i, j in sorted(occupied_cells):
        for du, dv in ((0.10, 0.10), (0.20, 0.10), (0.10, 0.20), (0.20, 0.20)):
            points.append((i * 0.5 + du, j * 0.5 + dv))
    evidence = extract_section_boundary_evidence_2d(
        np.asarray(points, dtype=np.float64),
        cell_size=0.5,
        min_component_cells=1,
        check_grid_origin_sensitivity=False,
    )
    diagnostic = evidence.public["ambiguity"]["one_cell_perturbation"]
    assert diagnostic["applied_to_reconstruction"] is False
    assert diagnostic["topology_stable"] is False
    assert diagnostic["base"]["material_component_count"] == 1
    assert any(
        "one-cell" in warning
        for warning in evidence.public["ambiguity"]["warnings"]
    )


def test_disconnected_one_cell_noise_is_rejected_not_discarded():
    points = filled_fixture(hole=False, island=False)
    noise = np.asarray([[30.0, 30.0], [30.05, 30.05]], dtype=np.float64)
    with pytest.raises(SectionBoundaryError, match="disconnected components"):
        extract(np.vstack((points, noise)), min_component_cells=2)


def test_diagonal_only_connectivity_is_rejected():
    # Two 2x2 material blocks touch only at one lattice corner. Each occupied
    # cell has several source samples so the ambiguity reaches the connectivity gate.
    cells = [
        (0, 0), (1, 0), (0, 1), (1, 1),
        (2, 2), (3, 2), (2, 3), (3, 3),
    ]
    points = []
    for i, j in cells:
        for du, dv in ((0.10, 0.10), (0.20, 0.10), (0.10, 0.20), (0.20, 0.20)):
            points.append((i * 0.5 + du, j * 0.5 + dv))
    points = np.asarray(points, dtype=np.float64)
    with pytest.raises(SectionBoundaryError, match="diagonal-only"):
        extract_section_boundary_evidence_2d(
            points,
            cell_size=0.5,
            min_component_cells=1,
            check_grid_origin_sensitivity=False,
        )


def test_too_small_cell_size_is_rejected_at_large_coordinates():
    base = 1.0e12
    points = filled_fixture(hole=False, island=False) + base
    with pytest.raises(SectionBoundaryError, match="precision floor"):
        extract_section_boundary_evidence_2d(points, cell_size=1.0e-8)


def test_too_large_cell_size_is_rejected_instead_of_inventing_outline():
    with pytest.raises(SectionBoundaryError, match="Too few supported occupied cells"):
        extract_section_boundary_evidence_2d(
            filled_fixture(hole=False, island=False),
            cell_size=1000.0,
        )


def test_repeat_determinism_and_no_raw_sample_arrays_in_public_output():
    points = filled_fixture()
    first = extract(points).public
    second = extract(points).public
    assert first == second
    dumped = json.dumps(first)
    assert "points_uv" not in dumped
    assert "boundary_points_uv" not in dumped


def test_composite_reuses_accepted_topology_for_outer_hole_island():
    result = reconstruct_filled_section_profile_2d(
        filled_fixture(),
        cell_size=0.5,
        max_edge_length=0.95,
        fit_tolerance=0.35,
        min_cell_support=1,
        max_cells=20_000,
        max_boundary_points=2048,
        angular_tolerance_degrees=2.0,
        minimum_loop_points=6,
        max_loops=8,
        require_grid_stability=True,
    )
    assert result["topology"]["loop_count"] == 3
    assert [loop["role_candidate"] for loop in result["topology"]["loops"]] == [
        "outer",
        "hole",
        "island",
    ]
    assert result["extraction"]["connected_contour_count"] == 3
    assert result["state"] == "inferred_candidate"
    assert result["manufacturing_intent_confirmed"] is False
    assert "points_uv" not in json.dumps(result)


def test_boundary_budget_refuses_silent_thinning():
    with pytest.raises(SectionBoundaryError, match="max_boundary_points"):
        extract_section_boundary_evidence_2d(
            filled_fixture(),
            cell_size=0.2,
            max_boundary_points=20,
        )


def test_exact_cell_boundary_coordinates_follow_half_open_grid_policy():
    points = np.asarray(
        [
            [0.0, 0.0], [0.5, 0.0], [1.0, 0.0], [1.5, 0.0],
            [0.0, 0.5], [0.5, 0.5], [1.0, 0.5], [1.5, 0.5],
            [0.0, 1.0], [0.5, 1.0], [1.0, 1.0], [1.5, 1.0],
            [0.0, 1.5], [0.5, 1.5], [1.0, 1.5], [1.5, 1.5],
        ],
        dtype=np.float64,
    )
    evidence = extract_section_boundary_evidence_2d(
        points,
        cell_size=0.5,
        min_component_cells=1,
        check_grid_origin_sensitivity=False,
    )
    assert evidence.public["grid_origin_uv"] == [0.0, 0.0]
    assert evidence.public["grid_index_bounds"] == {"i": [0, 3], "j": [0, 3]}
