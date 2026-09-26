from __future__ import annotations

import math

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import (
    FeatureFitError,
    fit_circle_3d,
    fit_plane,
    plane_relationship,
    point_to_plane,
)


def _basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = normal / np.linalg.norm(normal)
    seed = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(seed, normal))) > 0.8:
        seed = np.array([0.0, 1.0, 0.0])
    u = seed - normal * np.dot(seed, normal)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return u, v


def test_exact_tilted_plane() -> None:
    normal = np.array([1.0, 2.0, 3.0])
    normal /= np.linalg.norm(normal)
    u, v = _basis(normal)
    center = np.array([9.0, -7.0, 5.0])
    uu, vv = np.meshgrid(np.linspace(-4, 4, 17), np.linspace(-3, 3, 13))
    points = center + uu.reshape(-1, 1) * u + vv.reshape(-1, 1) * v

    fit = fit_plane(points)
    got = np.asarray(fit["normal"])
    assert abs(float(np.dot(got, normal))) > 1 - 1e-13
    assert fit["residuals"]["rms"] < 1e-12
    assert np.allclose(fit["centroid"], center, atol=1e-12)


def test_noisy_plane_recovers_known_surface() -> None:
    rng = np.random.default_rng(260926)
    normal = np.array([0.31, 0.57, 0.76])
    normal /= np.linalg.norm(normal)
    u, v = _basis(normal)
    center = np.array([20.0, -3.0, 8.0])
    a = rng.uniform(-15, 15, 4000)
    b = rng.uniform(-8, 8, 4000)
    noise = rng.normal(0, 0.025, 4000)
    points = (
        center
        + a[:, None] * u
        + b[:, None] * v
        + noise[:, None] * normal
    )

    fit = fit_plane(points)
    got = np.asarray(fit["normal"])
    angle = math.degrees(
        math.acos(np.clip(abs(np.dot(got, normal)), -1, 1))
    )
    assert angle < 0.02
    assert abs(fit["residuals"]["rms"] - 0.025) < 0.001
    assert fit["shape_metrics"]["planarity"] > 0.08
    assert fit["shape_metrics"]["scattering"] < 1e-4


def test_plane_rejects_collinear_and_nonfinite() -> None:
    with pytest.raises(FeatureFitError, match="collinear"):
        fit_plane([[0, 0, 0], [1, 1, 1], [2, 2, 2], [3, 3, 3]])
    with pytest.raises(FeatureFitError, match="finite"):
        fit_plane([[0, 0, 0], [1, 0, 0], [0, math.nan, 0]])


def test_exact_3d_circle() -> None:
    normal = np.array([1.0, -2.0, 4.0])
    normal /= np.linalg.norm(normal)
    u, v = _basis(normal)
    center = np.array([12.0, -7.0, 3.0])
    radius = 6.25
    theta = np.linspace(0, 2 * math.pi, 180, endpoint=False)
    points = (
        center
        + radius * np.cos(theta)[:, None] * u
        + radius * np.sin(theta)[:, None] * v
    )

    fit = fit_circle_3d(points)
    assert np.allclose(fit["center"], center, atol=1e-10)
    assert abs(fit["radius"] - radius) < 1e-10
    assert fit["radial_residuals"]["rms"] < 1e-10
    assert fit["plane_residuals"]["rms"] < 1e-10
    assert fit["arc_coverage_degrees"] > 350


def test_noisy_partial_circle_and_coverage() -> None:
    rng = np.random.default_rng(260927)
    normal = np.array([0.2, 0.4, 0.89442719])
    normal /= np.linalg.norm(normal)
    u, v = _basis(normal)
    center = np.array([2.0, 4.0, -1.0])
    radius = 10.0
    theta = np.linspace(math.radians(15), math.radians(245), 600)
    radial = rng.normal(0, 0.03, theta.size)
    axial = rng.normal(0, 0.02, theta.size)
    points = (
        center
        + (radius + radial)[:, None] * np.cos(theta)[:, None] * u
        + (radius + radial)[:, None] * np.sin(theta)[:, None] * v
        + axial[:, None] * normal
    )

    fit = fit_circle_3d(points)
    assert np.linalg.norm(np.asarray(fit["center"]) - center) < 0.01
    assert abs(fit["radius"] - radius) < 0.01
    assert 225 < fit["arc_coverage_degrees"] < 235
    assert 0.02 < fit["radial_residuals"]["rms"] < 0.04
    assert 0.01 < fit["plane_residuals"]["rms"] < 0.03


def test_low_arc_coverage_is_reported() -> None:
    theta = np.linspace(0, math.radians(60), 20)
    points = np.column_stack(
        (5 * np.cos(theta), 5 * np.sin(theta), np.zeros(theta.size))
    )
    fit = fit_circle_3d(points)
    assert fit["arc_coverage_degrees"] < 120
    assert fit["quality_warnings"]


def test_circle_requires_four_points_for_fit_quality() -> None:
    with pytest.raises(FeatureFitError, match="at least 4"):
        fit_circle_3d([[1, 0, 0], [0, 1, 0], [-1, 0, 0]])


def test_circle_rejects_degenerate_points() -> None:
    with pytest.raises(FeatureFitError):
        fit_circle_3d([[0, 0, 0], [1, 0, 0], [2, 0, 0]])


def test_point_to_plane_known_distance() -> None:
    fit = fit_plane([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]])
    result = point_to_plane([2, 3, 5], fit)
    assert result["absolute_distance"] == pytest.approx(5)
    assert np.allclose(result["projected_point"], [2, 3, 0])


def test_plane_relationship_parallel_and_orthogonal() -> None:
    a = fit_plane([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]])
    b = fit_plane([[0, 0, 5], [1, 0, 5], [0, 1, 5], [1, 1, 5]])
    rel = plane_relationship(a, b)
    assert rel["acute_angle_degrees"] == pytest.approx(0, abs=1e-12)
    assert rel["normal_offset_from_a"] == pytest.approx(5)
    assert rel["parallel_within_1_degree"]

    c = fit_plane([[0, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 1]])
    rel2 = plane_relationship(a, c)
    assert rel2["acute_angle_degrees"] == pytest.approx(90, abs=1e-12)


def test_large_shifted_coordinates_preserve_precision() -> None:
    rng = np.random.default_rng(260928)
    base = np.array([300000.0, -200000.0, 100000.0])
    normal = np.array([0.3, -0.7, 0.64])
    normal /= np.linalg.norm(normal)
    u, v = _basis(normal)
    a = rng.uniform(-20, 20, 1500)
    b = rng.uniform(-20, 20, 1500)
    points = (
        base
        + a[:, None] * u
        + b[:, None] * v
        + rng.normal(0, 0.001, 1500)[:, None] * normal
    )

    fit = fit_plane(points)
    assert fit["residuals"]["rms"] < 0.0011
    got = np.asarray(fit["normal"])
    angle = math.degrees(
        math.acos(np.clip(abs(np.dot(got, normal)), -1, 1))
    )
    assert angle < 0.001


@pytest.mark.parametrize("scale", [1e-20, 1e-14, 1.0, 1e14, 1e20])
def test_unit_neutral_scale_invariance(scale: float) -> None:
    plane_points = np.array(
        [
            [0.0, 0.0, 0.0],
            [scale, 0.0, 0.0],
            [0.0, scale, 0.0],
            [scale, scale, 0.0],
        ]
    )
    plane = fit_plane(plane_points)
    assert plane["residuals"]["rms"] == pytest.approx(0.0, abs=abs(scale) * 1e-14)

    theta = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    center = np.array([3.0, -2.0, 8.0]) * scale
    radius = 5.0 * scale
    circle_points = center + np.column_stack(
        (
            radius * np.cos(theta),
            radius * np.sin(theta),
            np.zeros_like(theta),
        )
    )
    circle = fit_circle_3d(circle_points)
    assert circle["radius"] == pytest.approx(radius, rel=1e-12)
    assert np.allclose(circle["center"], center, rtol=1e-12, atol=abs(scale) * 1e-12)


@pytest.mark.parametrize("seed", [260929, 260930, 260931])
def test_random_rotation_invariance(seed: int) -> None:
    rng = np.random.default_rng(seed)
    for _ in range(20):
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        if np.linalg.det(q) < 0:
            q[:, 0] *= -1
        center = rng.normal(size=3) * 10
        theta = np.linspace(0, 2 * math.pi, 72, endpoint=False)
        local = np.column_stack(
            (
                4 * np.cos(theta),
                4 * np.sin(theta),
                np.zeros_like(theta),
            )
        )
        points = center + local @ q.T
        fit = fit_circle_3d(points)
        assert np.linalg.norm(np.asarray(fit["center"]) - center) < 1e-10
        assert abs(fit["radius"] - 4) < 1e-10
