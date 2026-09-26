from __future__ import annotations

import math

import numpy as np
import pytest

from cloudcompare_mcp.feature_discovery import (
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


def test_plane_discovery_rejects_invalid_controls() -> None:
    points = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]]
    with pytest.raises(FeatureFitError, match="distance_threshold"):
        discover_planes(points, distance_threshold=0)
    with pytest.raises(FeatureFitError, match="min_points exceeds"):
        discover_planes(points, min_points=100)
    with pytest.raises(FeatureFitError, match="min_inlier_fraction"):
        discover_planes(points, min_inlier_fraction=0)


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
