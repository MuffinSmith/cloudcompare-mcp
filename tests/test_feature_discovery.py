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


def _circle_points(
    center: np.ndarray,
    normal: np.ndarray,
    radius: float,
    count: int,
) -> np.ndarray:
    normal = normal / np.linalg.norm(normal)
    seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = seed - normal * float(np.dot(seed, normal))
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    theta = np.linspace(0, 2 * math.pi, count, endpoint=False)
    return (
        center
        + radius * np.cos(theta)[:, None] * u
        + radius * np.sin(theta)[:, None] * v
    )


def test_circle_discovery_finds_two_known_circles() -> None:
    rng = np.random.default_rng(261010)
    first = _circle_points(
        np.array([2.0, -3.0, 4.0]),
        np.array([0.0, 0.0, 1.0]),
        5.0,
        160,
    )
    second = _circle_points(
        np.array([-8.0, 6.0, 2.0]),
        np.array([1.0, 1.0, 2.0]),
        3.0,
        100,
    )
    first += rng.normal(0, 0.01, first.shape)
    second += rng.normal(0, 0.01, second.shape)
    outliers = rng.uniform(-20, 20, (80, 3))
    result = discover_circles(
        np.vstack((first, second, outliers)),
        distance_threshold=0.05,
        max_circles=3,
        min_points=60,
        min_inlier_fraction=0.15,
        iterations=500,
        min_radius=2.0,
        max_radius=6.0,
        random_seed=261010,
    )
    assert result["candidate_count"] == 2
    radii = sorted(candidate["circle"]["radius"] for candidate in result["candidates"])
    assert radii[0] == pytest.approx(3.0, abs=0.03)
    assert radii[1] == pytest.approx(5.0, abs=0.03)
    supports = sorted(
        (candidate["support_count"] for candidate in result["candidates"]),
        reverse=True,
    )
    assert supports[0] >= 145
    assert supports[1] >= 90


def _cylinder_points(
    center: np.ndarray,
    axis: np.ndarray,
    radius: float,
    axial_values: np.ndarray,
    theta_values: np.ndarray,
) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    seed = np.eye(3)[int(np.argmin(np.abs(axis)))]
    u = seed - axis * float(np.dot(seed, axis))
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    points = []
    for axial in axial_values:
        for theta in theta_values:
            points.append(
                center
                + axial * axis
                + radius * math.cos(theta) * u
                + radius * math.sin(theta) * v
            )
    return np.asarray(points)


def test_cylinder_discovery_finds_known_surface() -> None:
    rng = np.random.default_rng(261011)
    axis = np.array([0.3, -0.4, 0.8660254])
    axis /= np.linalg.norm(axis)
    center = np.array([4.0, -7.0, 3.0])
    surface = _cylinder_points(
        center,
        axis,
        4.5,
        np.linspace(-8.0, 8.0, 7),
        np.linspace(0, 2 * math.pi, 18, endpoint=False),
    )
    surface += rng.normal(0, 0.008, surface.shape)
    outliers = rng.uniform(-15, 15, (70, 3))
    result = discover_cylinders(
        np.vstack((surface, outliers)),
        distance_threshold=0.05,
        max_cylinders=2,
        min_points=80,
        min_inlier_fraction=0.4,
        iterations=40,
        candidate_sample_size=12,
        min_radius=3.0,
        max_radius=6.0,
        random_seed=261011,
    )
    assert result["candidate_count"] == 1
    fit = result["candidates"][0]["cylinder"]
    got_axis = np.asarray(fit["axis_direction"])
    assert abs(float(np.dot(got_axis, axis))) > 0.99999
    assert fit["radius"] == pytest.approx(4.5, abs=0.03)
    assert result["candidates"][0]["support_count"] >= 115


def test_circle_and_cylinder_discovery_are_deterministic() -> None:
    circle = _circle_points(
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        3.0,
        48,
    )
    circle_kwargs = dict(
        distance_threshold=0.01,
        max_circles=1,
        min_points=30,
        min_inlier_fraction=0.5,
        iterations=100,
        random_seed=77,
    )
    assert discover_circles(circle, **circle_kwargs) == discover_circles(
        circle, **circle_kwargs
    )

    cylinder = _cylinder_points(
        np.zeros(3),
        np.array([0.0, 0.0, 1.0]),
        3.0,
        np.linspace(-5, 5, 5),
        np.linspace(0, 2 * math.pi, 12, endpoint=False),
    )
    cylinder_kwargs = dict(
        distance_threshold=0.01,
        max_cylinders=1,
        min_points=40,
        min_inlier_fraction=0.5,
        iterations=20,
        candidate_sample_size=10,
        random_seed=78,
    )
    assert discover_cylinders(cylinder, **cylinder_kwargs) == discover_cylinders(
        cylinder, **cylinder_kwargs
    )


def test_circle_and_cylinder_discovery_validate_radius_limits() -> None:
    circle = _circle_points(
        np.zeros(3), np.array([0.0, 0.0, 1.0]), 3.0, 12
    )
    with pytest.raises(FeatureFitError, match="max_radius"):
        discover_circles(circle, min_radius=4, max_radius=2, min_points=4)
    cylinder = _cylinder_points(
        np.zeros(3),
        np.array([0.0, 0.0, 1.0]),
        3.0,
        np.array([-1.0, 1.0]),
        np.linspace(0, 2 * math.pi, 6, endpoint=False),
    )
    with pytest.raises(FeatureFitError, match="min_radius"):
        discover_cylinders(cylinder, min_radius=0, min_points=6)


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
