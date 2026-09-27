from __future__ import annotations

import math

import numpy as np
import pytest

from cloudcompare_mcp.profile_topology import (
    ProfileTopologyError,
    reconstruct_profile_topology_2d,
)


def sample_polygon(vertices, spacing=0.4):
    vertices = np.asarray(vertices, dtype=float)
    output = []
    for index in range(len(vertices)):
        start = vertices[index]
        end = vertices[(index + 1) % len(vertices)]
        length = float(np.linalg.norm(end - start))
        count = max(1, int(math.ceil(length / spacing)))
        for t in np.linspace(0.0, 1.0, count, endpoint=False):
            output.append(start * (1.0 - t) + end * t)
    return np.asarray(output, dtype=float)


def circle_points(radius, count, center=(0.0, 0.0)):
    theta = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    return np.column_stack(
        (
            center[0] + radius * np.cos(theta),
            center[1] + radius * np.sin(theta),
        )
    )


def shuffle(points, seed=15100):
    rng = np.random.default_rng(seed)
    return np.asarray(points)[rng.permutation(len(points))]


def profile_types(loop):
    return [primitive["type"] for primitive in loop["profile"]["primitives"]]


def test_concave_non_star_shaped_loop_reconstructs_without_polar_ordering():
    # U-shaped boundary: deliberately non-star-shaped around its centroid.
    points = sample_polygon(
        [(0, 0), (8, 0), (8, 8), (5, 8), (5, 3), (3, 3), (3, 8), (0, 8)],
        spacing=0.4,
    )
    out = reconstruct_profile_topology_2d(
        shuffle(points),
        max_edge_length=0.75,
        fit_tolerance=1e-8,
        angular_tolerance_degrees=0.2,
    )
    assert out["loop_count"] == 1
    loop = out["loops"][0]
    assert loop["role_candidate"] == "outer"
    assert loop["nesting_depth"] == 0
    assert loop["signed_area"] > 0
    assert set(profile_types(loop)) == {"line"}
    assert loop["profile"]["ordering"]["method"] == "input"
    assert out["raw_points_returned"] is False
    assert any("boundary curves" in item for item in out["assumptions"])


def test_outer_and_hole_are_extracted_and_oriented_by_nesting():
    outer = sample_polygon([(-10, -8), (10, -8), (10, 8), (-10, 8)], spacing=0.5)
    hole = circle_points(3.0, 48)
    points = shuffle(np.vstack((outer, hole)), seed=15101)

    out = reconstruct_profile_topology_2d(
        points,
        max_edge_length=0.9,
        fit_tolerance=1e-7,
        angular_tolerance_degrees=0.2,
    )
    assert out["loop_count"] == 2
    outer_loop, hole_loop = out["loops"]
    assert outer_loop["role_candidate"] == "outer"
    assert outer_loop["parent_loop_id"] is None
    assert outer_loop["signed_area"] > 0
    assert hole_loop["role_candidate"] == "hole"
    assert hole_loop["parent_loop_id"] == outer_loop["loop_id"]
    assert hole_loop["nesting_depth"] == 1
    assert hole_loop["signed_area"] < 0
    assert any(
        candidate["type"] == "rectangle_candidate"
        for candidate in outer_loop["profile"]["profile_candidates"]
    )
    assert any(
        candidate["type"] == "circle_profile_candidate"
        for candidate in hole_loop["profile"]["profile_candidates"]
    )


def test_nested_island_role_is_preserved():
    outer = sample_polygon([(-12, -10), (12, -10), (12, 10), (-12, 10)], spacing=0.5)
    hole = circle_points(5.0, 72)
    island = circle_points(1.5, 36)
    out = reconstruct_profile_topology_2d(
        shuffle(np.vstack((outer, hole, island)), seed=15102),
        max_edge_length=0.9,
        fit_tolerance=1e-7,
    )
    assert [loop["role_candidate"] for loop in out["loops"]] == [
        "outer",
        "hole",
        "island",
    ]
    assert [loop["nesting_depth"] for loop in out["loops"]] == [0, 1, 2]
    assert out["loops"][1]["parent_loop_id"] == "loop-0"
    assert out["loops"][2]["parent_loop_id"] == "loop-1"


def test_two_disjoint_outer_loops_remain_separate():
    left = circle_points(2.0, 36, center=(-6.0, 0.0))
    right = circle_points(2.5, 42, center=(6.0, 0.0))
    out = reconstruct_profile_topology_2d(
        shuffle(np.vstack((left, right)), seed=15103),
        max_edge_length=0.8,
        fit_tolerance=1e-8,
    )
    assert out["loop_count"] == 2
    assert all(loop["role_candidate"] == "outer" for loop in out["loops"])
    radii = sorted(
        candidate["radius"]
        for loop in out["loops"]
        for candidate in loop["profile"]["profile_candidates"]
        if candidate["type"] == "circle_profile_candidate"
    )
    assert radii == pytest.approx([2.0, 2.5], abs=1e-9)


def test_arbitrary_input_permutation_preserves_geometry():
    outer = sample_polygon([(-8, -6), (8, -6), (8, 6), (-8, 6)], spacing=0.5)
    hole = circle_points(2.0, 40)
    a = reconstruct_profile_topology_2d(
        shuffle(np.vstack((outer, hole)), seed=15104),
        max_edge_length=0.85,
        fit_tolerance=1e-7,
    )
    b = reconstruct_profile_topology_2d(
        shuffle(np.vstack((outer, hole)), seed=15105),
        max_edge_length=0.85,
        fit_tolerance=1e-7,
    )
    assert [loop["role_candidate"] for loop in a["loops"]] == [
        loop["role_candidate"] for loop in b["loops"]
    ]
    assert [loop["source_point_count"] for loop in a["loops"]] == [
        loop["source_point_count"] for loop in b["loops"]
    ]
    assert [loop["area_abs"] for loop in a["loops"]] == pytest.approx(
        [loop["area_abs"] for loop in b["loops"]], abs=1e-10
    )
    assert [profile_types(loop) for loop in a["loops"]] == [
        profile_types(loop) for loop in b["loops"]
    ]


def test_large_translation_and_rotation_preserve_loop_geometry():
    outer = sample_polygon([(-7, -5), (7, -5), (7, 5), (-7, 5)], spacing=0.5)
    hole = circle_points(2.0, 48)
    points = np.vstack((outer, hole))
    angle = 0.71
    rotation = np.asarray(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
    )
    transformed = points @ rotation.T + np.asarray([1.2e8, -2.4e8])
    out = reconstruct_profile_topology_2d(
        shuffle(transformed, seed=15106),
        max_edge_length=0.9,
        fit_tolerance=1e-4,
        angular_tolerance_degrees=0.2,
    )
    assert out["loop_count"] == 2
    assert out["coordinate_precision_floor"] < out["fit_tolerance"]
    assert out["loops"][0]["area_abs"] == pytest.approx(140.0, abs=2e-5)
    hole_candidate = next(
        candidate
        for candidate in out["loops"][1]["profile"]["profile_candidates"]
        if candidate["type"] == "circle_profile_candidate"
    )
    assert hole_candidate["radius"] == pytest.approx(2.0, abs=2e-6)


def test_too_small_edge_limit_rejects_open_graph():
    points = circle_points(3.0, 24)
    with pytest.raises(ProfileTopologyError, match="open or undersampled"):
        reconstruct_profile_topology_2d(
            shuffle(points),
            max_edge_length=0.1,
            fit_tolerance=1e-8,
        )


def test_overlarge_edge_limit_that_connects_loops_fails_instead_of_guessing():
    left = circle_points(2.0, 32, center=(-2.5, 0.0))
    right = circle_points(2.0, 32, center=(2.5, 0.0))
    with pytest.raises(ProfileTopologyError, match="ambiguous|dead-ended|intersect"):
        reconstruct_profile_topology_2d(
            shuffle(np.vstack((left, right)), seed=15107),
            max_edge_length=1.5,
            fit_tolerance=1e-7,
        )


def test_self_intersecting_loop_is_rejected():
    bow = sample_polygon([(-3, -2), (3, 2), (-3, 2), (3, -2)], spacing=0.35)
    with pytest.raises(ProfileTopologyError, match="self-intersects|touches|ambiguous|dead-ended"):
        reconstruct_profile_topology_2d(
            shuffle(bow, seed=15108),
            max_edge_length=0.7,
            fit_tolerance=1e-7,
        )


def test_duplicate_coordinates_are_rejected():
    points = circle_points(2.0, 20)
    duplicated = np.vstack((points, points[0]))
    with pytest.raises(ProfileTopologyError, match="duplicate"):
        reconstruct_profile_topology_2d(
            duplicated,
            max_edge_length=1.0,
            fit_tolerance=1e-7,
        )


def test_loop_budget_is_enforced():
    points = np.vstack(
        [
            circle_points(1.0, 24, center=(-6, 0)),
            circle_points(1.0, 24, center=(0, 0)),
            circle_points(1.0, 24, center=(6, 0)),
        ]
    )
    with pytest.raises(ProfileTopologyError, match="max_loops"):
        reconstruct_profile_topology_2d(
            shuffle(points, seed=15109),
            max_edge_length=0.5,
            fit_tolerance=1e-7,
            max_loops=2,
        )


def test_repeat_is_deterministic_for_same_input():
    points = shuffle(
        np.vstack(
            (
                sample_polygon([(-5, -4), (5, -4), (5, 4), (-5, 4)], spacing=0.5),
                circle_points(1.5, 36),
            )
        ),
        seed=15110,
    )
    kwargs = dict(max_edge_length=0.9, fit_tolerance=1e-7)
    assert reconstruct_profile_topology_2d(points, **kwargs) == reconstruct_profile_topology_2d(
        points, **kwargs
    )
