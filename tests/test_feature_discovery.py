from __future__ import annotations

import math

import numpy as np
import pytest

from cloudcompare_mcp.feature_discovery import (
    discover_circles,
    discover_cylinders,
    discover_planes,
    enrich_region_grid,
    occupancy_grid_2d,
)
from cloudcompare_mcp.feature_fit import FeatureFitError


def test_enrich_region_grid_shape_metrics() -> None:
    grid = {
        "matched_count": 10,
        "cells": [
            {
                "index": [0, 0, 0],
                "count": 10,
                "fraction_of_matches": 1.0,
                "centroid": [1.0, 2.0, 3.0],
                "point_bounds": {
                    "min": [0.0, 0.0, 0.0],
                    "max": [2.0, 4.0, 6.0],
                    "extent": [2.0, 4.0, 6.0],
                },
                "covariance": [
                    [9.0, 0.0, 0.0],
                    [0.0, 4.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
            }
        ],
    }
    enriched = enrich_region_grid(grid)
    cell = enriched["cells"][0]
    assert "covariance" not in cell
    assert cell["principal_variances"] == pytest.approx([9.0, 4.0, 1.0])
    assert cell["shape_metrics"]["linearity"] == pytest.approx(5.0 / 9.0)
    assert cell["shape_metrics"]["planarity"] == pytest.approx(3.0 / 9.0)
    assert cell["shape_metrics"]["scattering"] == pytest.approx(1.0 / 9.0)
    assert cell["rms_thickness"] == pytest.approx(1.0)


def test_plane_discovery_finds_three_dominant_planes() -> None:
    rng = np.random.default_rng(261001)
    p1 = np.column_stack(
        (
            rng.uniform(-10, 10, 1000),
            rng.uniform(-10, 10, 1000),
            rng.normal(0, 0.02, 1000),
        )
    )
    p2 = np.column_stack(
        (
            np.full(500, 5.0) + rng.normal(0, 0.02, 500),
            rng.uniform(-8, 8, 500),
            rng.uniform(-5, 5, 500),
        )
    )
    p3 = np.column_stack(
        (
            rng.uniform(-5, 5, 300),
            np.full(300, -4.0) + rng.normal(0, 0.02, 300),
            rng.uniform(-5, 5, 300),
        )
    )
    noise = rng.uniform(-10, 10, (200, 3))
    points = np.vstack((p1, p2, p3, noise))

    result = discover_planes(
        points,
        max_planes=4,
        min_points=100,
        min_inlier_fraction=0.1,
        iterations=500,
        random_seed=123,
    )

    assert result["candidate_count"] == 3
    normals = [np.asarray(item["plane"]["normal"]) for item in result["candidates"]]
    expected = np.eye(3)
    matched = []
    for normal in normals:
        matched.append(max(abs(float(np.dot(normal, axis))) for axis in expected))
    assert min(matched) > 0.999
    counts = [item["support_count"] for item in result["candidates"]]
    assert 950 <= counts[0] <= 1050
    assert 450 <= counts[1] <= 550
    assert 250 <= counts[2] <= 350


def test_plane_discovery_is_deterministic() -> None:
    rng = np.random.default_rng(261002)
    xy = rng.uniform(-5, 5, (500, 2))
    points = np.column_stack((xy, rng.normal(0, 0.01, 500)))
    kwargs = dict(
        max_planes=2,
        min_points=50,
        min_inlier_fraction=0.1,
        iterations=250,
        random_seed=99,
    )
    a = discover_planes(points, **kwargs)
    b = discover_planes(points, **kwargs)
    assert a == b


@pytest.mark.parametrize("seed", [261003, 261004, 261005])
def test_plane_discovery_rotation_invariance(seed: int) -> None:
    rng = np.random.default_rng(seed)
    normal = rng.normal(size=3)
    normal /= np.linalg.norm(normal)
    basis_seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = basis_seed - normal * float(np.dot(basis_seed, normal))
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    center = rng.uniform(-100, 100, 3)
    a = rng.uniform(-20, 20, 800)
    b = rng.uniform(-12, 12, 800)
    surface = (
        center
        + a[:, None] * u
        + b[:, None] * v
        + rng.normal(0, 0.015, 800)[:, None] * normal
    )
    outliers = rng.uniform(-150, 150, (200, 3))
    result = discover_planes(
        np.vstack((surface, outliers)),
        distance_threshold=0.05,
        max_planes=1,
        min_points=500,
        min_inlier_fraction=0.5,
        iterations=500,
        random_seed=seed,
    )
    assert result["candidate_count"] == 1
    fitted = np.asarray(result["candidates"][0]["plane"]["normal"])
    angle = math.degrees(
        math.acos(np.clip(abs(float(np.dot(fitted, normal))), -1.0, 1.0))
    )
    assert angle < 0.02
    assert result["candidates"][0]["support_fraction_of_sample"] > 0.75


def test_plane_discovery_rejects_invalid_controls() -> None:
    points = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]]
    # Keep min_points valid when exercising independent controls so the test
    # reaches the validation branch it actually intends to assert.
    with pytest.raises(FeatureFitError, match="distance_threshold"):
        discover_planes(points, distance_threshold=0, min_points=3)
    with pytest.raises(FeatureFitError, match="min_points exceeds"):
        discover_planes(points, min_points=100)
    with pytest.raises(FeatureFitError, match="min_inlier_fraction"):
        discover_planes(points, min_inlier_fraction=0, min_points=3)


def _basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = normal / np.linalg.norm(normal)
    seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = seed - normal * float(np.dot(seed, normal))
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return u, v


def _circle_points(
    center: np.ndarray,
    normal: np.ndarray,
    radius: float,
    count: int,
    *,
    radial_noise: float = 0.0,
    plane_noise: float = 0.0,
    seed: int = 261010,
) -> np.ndarray:
    normal = normal / np.linalg.norm(normal)
    u, v = _basis(normal)
    theta = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    rng = np.random.default_rng(seed)
    radial = radius + rng.normal(0.0, radial_noise, count)
    axial = rng.normal(0.0, plane_noise, count)
    return (
        center
        + radial[:, None] * np.cos(theta)[:, None] * u
        + radial[:, None] * np.sin(theta)[:, None] * v
        + axial[:, None] * normal
    )


def _cylinder_points(
    center: np.ndarray,
    axis: np.ndarray,
    radius: float,
    length: float,
    *,
    theta_count: int = 24,
    axial_count: int = 7,
    radial_noise: float = 0.0,
    seed: int = 261011,
) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    u, v = _basis(axis)
    theta = np.linspace(0.0, 2.0 * math.pi, theta_count, endpoint=False)
    axial = np.linspace(-length / 2.0, length / 2.0, axial_count)
    rng = np.random.default_rng(seed)
    points = []
    for z in axial:
        for angle in theta:
            noisy_radius = radius + rng.normal(0.0, radial_noise)
            points.append(
                center
                + z * axis
                + noisy_radius * math.cos(angle) * u
                + noisy_radius * math.sin(angle) * v
            )
    return np.asarray(points)


def test_circle_discovery_finds_two_noisy_circles() -> None:
    rng = np.random.default_rng(261012)
    normal_a = np.array([0.3, -0.4, 0.8660254])
    normal_a /= np.linalg.norm(normal_a)
    center_a = np.array([2.0, -3.0, 4.0])
    center_b = np.array([-8.0, 4.0, -2.0])
    normal_b = np.array([0.0, 0.0, 1.0])

    circle_a = _circle_points(
        center_a,
        normal_a,
        5.0,
        180,
        radial_noise=0.004,
        plane_noise=0.003,
        seed=261013,
    )
    circle_b = _circle_points(
        center_b,
        normal_b,
        2.5,
        100,
        radial_noise=0.003,
        plane_noise=0.002,
        seed=261014,
    )
    outliers = rng.uniform(-15, 15, (100, 3))
    points = np.vstack((circle_a, circle_b, outliers))

    result = discover_circles(
        points,
        distance_threshold=0.025,
        max_circles=3,
        min_points=60,
        min_inlier_fraction=0.15,
        iterations=700,
        min_arc_coverage_degrees=180.0,
        min_radius=1.0,
        max_radius=8.0,
        random_seed=44,
    )

    assert result["candidate_count"] == 2
    candidates = sorted(
        result["candidates"],
        key=lambda item: item["circle"]["radius"],
        reverse=True,
    )
    large, small = candidates
    assert np.linalg.norm(np.asarray(large["circle"]["center"]) - center_a) < 0.02
    assert large["circle"]["radius"] == pytest.approx(5.0, abs=0.02)
    assert abs(
        float(np.dot(np.asarray(large["circle"]["normal"]), normal_a))
    ) > 0.99999
    assert large["support_count"] >= 170

    assert np.linalg.norm(np.asarray(small["circle"]["center"]) - center_b) < 0.02
    assert small["circle"]["radius"] == pytest.approx(2.5, abs=0.02)
    assert abs(
        float(np.dot(np.asarray(small["circle"]["normal"]), normal_b))
    ) > 0.99999
    assert small["support_count"] >= 95


def test_circle_discovery_radius_and_coverage_controls() -> None:
    points = _circle_points(
        np.zeros(3),
        np.array([0.0, 0.0, 1.0]),
        5.0,
        80,
    )
    excluded = discover_circles(
        points,
        distance_threshold=0.01,
        min_points=20,
        iterations=100,
        min_radius=6.0,
    )
    assert excluded["candidate_count"] == 0

    with pytest.raises(FeatureFitError, match="max_radius"):
        discover_circles(
            points,
            min_points=20,
            min_radius=6.0,
            max_radius=5.0,
        )
    with pytest.raises(FeatureFitError, match="min_arc_coverage"):
        discover_circles(
            points,
            min_points=20,
            min_arc_coverage_degrees=361.0,
        )


def test_cylinder_discovery_recovers_dominant_noisy_cylinder() -> None:
    rng = np.random.default_rng(261015)
    axis = np.array([0.2, 0.4, 0.89442719])
    axis /= np.linalg.norm(axis)
    center = np.array([3.0, -2.0, 1.0])
    cylinder = _cylinder_points(
        center,
        axis,
        5.0,
        18.0,
        theta_count=24,
        axial_count=7,
        radial_noise=0.008,
        seed=261016,
    )
    outliers = rng.uniform(-12, 12, (60, 3))
    points = np.vstack((cylinder, outliers))

    result = discover_cylinders(
        points,
        distance_threshold=0.04,
        max_cylinders=1,
        min_points=100,
        min_inlier_fraction=0.5,
        restarts=8,
        subset_size=48,
        min_angular_coverage_degrees=180.0,
        min_radius=3.0,
        max_radius=7.0,
        random_seed=17,
    )

    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    fit = candidate["cylinder"]
    got_axis = np.asarray(fit["axis_direction"])
    angle = math.degrees(
        math.acos(np.clip(abs(float(np.dot(got_axis, axis))), -1.0, 1.0))
    )
    axis_offset = np.linalg.norm(
        np.cross(np.asarray(fit["axis_point"]) - center, axis)
    )
    assert angle < 0.15
    assert axis_offset < 0.05
    assert fit["radius"] == pytest.approx(5.0, abs=0.03)
    assert candidate["support_count"] >= 160
    assert candidate["support_fraction_of_sample"] > 0.7


def test_cylinder_discovery_controls_are_validated() -> None:
    points = _cylinder_points(
        np.zeros(3),
        np.array([0.0, 0.0, 1.0]),
        2.0,
        6.0,
        theta_count=8,
        axial_count=3,
    )
    with pytest.raises(FeatureFitError, match="distance_threshold"):
        discover_cylinders(points, distance_threshold=0, min_points=6)
    with pytest.raises(FeatureFitError, match="subset_size"):
        discover_cylinders(points, subset_size=5, min_points=6)
    with pytest.raises(FeatureFitError, match="max_radius"):
        discover_cylinders(
            points,
            min_points=6,
            min_radius=3.0,
            max_radius=2.0,
        )


def test_occupancy_grid_2d_counts_and_truncation() -> None:
    uv = [
        [0.0, 0.0],
        [0.1, 0.1],
        [0.2, 0.2],
        [0.9, 0.9],
        [1.0, 1.0],
    ]
    grid = occupancy_grid_2d(uv, divisions=(2, 2), max_cells=1)
    assert grid["sample_count"] == 5
    assert grid["nonempty_cell_count"] == 2
    assert grid["returned_cell_count"] == 1
    assert grid["cells_truncated"]
    assert grid["cells"][0]["count"] == 3


def test_occupancy_grid_handles_flat_extent() -> None:
    uv = [[2.0, y] for y in range(5)]
    grid = occupancy_grid_2d(uv, divisions=(8, 5))
    assert grid["effective_divisions"][0] == 1
    assert grid["effective_divisions"][1] == 5
    assert sum(cell["count"] for cell in grid["cells"]) == 5


def test_occupancy_grid_rejects_invalid_inputs() -> None:
    with pytest.raises(FeatureFitError):
        occupancy_grid_2d([])
    with pytest.raises(FeatureFitError, match="divisions"):
        occupancy_grid_2d([[0, 0]], divisions=(0, 4))
