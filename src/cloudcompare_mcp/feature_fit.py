"""Geometry fitting helpers for CloudCompare MCP metrology workflows.

All functions are unit-neutral and operate on Cartesian coordinates supplied by the
caller. They do not depend on CloudCompare or a GUI, which keeps the numerical
core directly testable on every supported platform.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np


class FeatureFitError(ValueError):
    """Raised when input geometry cannot support the requested fit."""


def _points_array(
    points: Iterable[Sequence[float]],
    *,
    minimum: int,
    label: str,
) -> np.ndarray:
    try:
        array = np.asarray(list(points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise FeatureFitError(f"{label} must be an array of 3D numeric points") from exc

    if array.ndim != 2 or array.shape[1:] != (3,):
        raise FeatureFitError(f"{label} must be an array of [x, y, z] points")
    if array.shape[0] < minimum:
        raise FeatureFitError(f"{label} requires at least {minimum} points")
    if not np.isfinite(array).all():
        raise FeatureFitError(f"{label} coordinates must all be finite")
    return array


def _vector3(value: np.ndarray) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


def _orient_vector(vector: np.ndarray) -> np.ndarray:
    """Choose a deterministic sign for an axis whose mathematical sign is ambiguous."""
    vector = np.asarray(vector, dtype=np.float64)
    index = int(np.argmax(np.abs(vector)))
    if vector[index] < 0:
        vector = -vector
    return vector


def _residual_stats(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise FeatureFitError("Residual statistics require finite values")
    absolute = np.abs(values)
    return {
        "count": int(values.size),
        "rms": float(np.sqrt(np.mean(np.square(values)))),
        "mean_abs": float(np.mean(absolute)),
        "median_abs": float(np.median(absolute)),
        "p95_abs": float(np.percentile(absolute, 95)),
        "max_abs": float(np.max(absolute)),
        "signed_mean": float(np.mean(values)),
        "signed_min": float(np.min(values)),
        "signed_max": float(np.max(values)),
    }


def _orthonormal_plane_basis(
    normal: np.ndarray,
    principal: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    normal = np.asarray(normal, dtype=np.float64)
    principal = np.asarray(principal, dtype=np.float64)
    principal = principal - normal * float(np.dot(principal, normal))
    norm = float(np.linalg.norm(principal))
    if norm <= np.finfo(np.float64).eps:
        seed = np.eye(3, dtype=np.float64)[int(np.argmin(np.abs(normal)))]
        principal = seed - normal * float(np.dot(seed, normal))
        norm = float(np.linalg.norm(principal))

    u = _orient_vector(principal / norm)
    v = np.cross(normal, u)
    v /= np.linalg.norm(v)
    u = np.cross(v, normal)
    u /= np.linalg.norm(u)
    u = _orient_vector(u)
    v = np.cross(normal, u)
    v /= np.linalg.norm(v)
    return u, v


def fit_plane(points: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Fit an orthogonal least-squares plane to 3D points."""
    xyz = _points_array(points, minimum=3, label="Plane fitting")
    centroid = np.mean(xyz, axis=0)
    centered = xyz - centroid

    try:
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise FeatureFitError("Plane fitting SVD did not converge") from exc

    if singular_values.size < 3:
        raise FeatureFitError("Plane fitting requires three-dimensional input")

    scale = float(singular_values[0])
    if not math.isfinite(scale) or scale <= np.finfo(np.float64).tiny:
        raise FeatureFitError(
            "Plane fitting points are coincident or numerically unresolved"
        )
    tolerance = np.finfo(np.float64).eps * max(xyz.shape) * scale * 32.0
    if float(singular_values[1]) <= tolerance:
        raise FeatureFitError("Plane fitting points are coincident or collinear")

    normal = _orient_vector(vh[-1] / np.linalg.norm(vh[-1]))
    u, v = _orthonormal_plane_basis(normal, vh[0])

    signed = centered @ normal
    projected_u = centered @ u
    projected_v = centered @ v
    constant = float(np.dot(normal, centroid))
    eigenvalues = np.square(singular_values) / float(xyz.shape[0])
    lambda1, lambda2, lambda3 = [float(x) for x in eigenvalues]

    linearity = (lambda1 - lambda2) / lambda1
    planarity = (lambda2 - lambda3) / lambda1
    scattering = lambda3 / lambda1

    residuals = _residual_stats(signed)
    extent_u = float(np.ptp(projected_u))
    extent_v = float(np.ptp(projected_v))
    characteristic_extent = max(extent_u, extent_v)
    normalized_rms = (
        float(residuals["rms"]) / characteristic_extent
        if characteristic_extent > 0
        else math.inf
    )

    return {
        "type": "plane",
        "sample_count": int(xyz.shape[0]),
        "centroid": _vector3(centroid),
        "normal": _vector3(normal),
        "normal_orientation_policy": "largest_absolute_component_positive",
        "basis_u": _vector3(u),
        "basis_v": _vector3(v),
        "equation": {
            "form": "n_dot_x_equals_constant",
            "normal": _vector3(normal),
            "constant": constant,
            "homogeneous": [
                float(normal[0]),
                float(normal[1]),
                float(normal[2]),
                -constant,
            ],
        },
        "residuals": residuals,
        "normalized_rms_to_extent": normalized_rms,
        "principal_variances": [lambda1, lambda2, lambda3],
        "shape_metrics": {
            "linearity": float(linearity),
            "planarity": float(planarity),
            "scattering": float(scattering),
        },
        "projected_bounds": {
            "u": [float(np.min(projected_u)), float(np.max(projected_u))],
            "v": [float(np.min(projected_v)), float(np.max(projected_v))],
            "extent_u": extent_u,
            "extent_v": extent_v,
        },
    }


def _refine_circle_2d(
    xy: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> tuple[np.ndarray, float, int]:
    """Geometric least-squares refinement of a 2D circle by Gauss-Newton."""
    parameters = np.array([center[0], center[1], radius], dtype=np.float64)
    iterations = 0
    for iterations in range(1, 51):
        dx = xy[:, 0] - parameters[0]
        dy = xy[:, 1] - parameters[1]
        distances = np.hypot(dx, dy)
        if np.any(distances <= np.finfo(np.float64).eps):
            break

        residual = distances - parameters[2]
        jacobian = np.column_stack(
            (-dx / distances, -dy / distances, -np.ones_like(distances))
        )
        try:
            step, *_ = np.linalg.lstsq(jacobian, -residual, rcond=None)
        except np.linalg.LinAlgError as exc:
            raise FeatureFitError(
                "Circle refinement failed to solve its least-squares step"
            ) from exc

        parameters += step
        if float(np.linalg.norm(step)) <= 1.0e-12 * max(
            1.0, abs(float(parameters[2]))
        ):
            break

    if not np.isfinite(parameters).all() or parameters[2] <= 0:
        raise FeatureFitError("Circle fitting produced an invalid radius")
    return parameters[:2], float(parameters[2]), iterations


def _arc_coverage_degrees(xy: np.ndarray, center: np.ndarray) -> float:
    angles = np.mod(
        np.arctan2(xy[:, 1] - center[1], xy[:, 0] - center[0]),
        2.0 * math.pi,
    )
    angles.sort()
    wrapped = np.concatenate((angles, [angles[0] + 2.0 * math.pi]))
    largest_gap = float(np.max(np.diff(wrapped)))
    coverage = 2.0 * math.pi - largest_gap
    return float(math.degrees(max(0.0, min(2.0 * math.pi, coverage))))


def fit_circle_3d(points: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Fit a circle to 3D points by plane projection + geometric 2D refinement."""
    xyz = _points_array(points, minimum=4, label="Circle fitting")
    plane = fit_plane(xyz)
    centroid = np.asarray(plane["centroid"], dtype=np.float64)
    normal = np.asarray(plane["normal"], dtype=np.float64)
    u = np.asarray(plane["basis_u"], dtype=np.float64)
    v = np.asarray(plane["basis_v"], dtype=np.float64)

    centered = xyz - centroid
    xy = np.column_stack((centered @ u, centered @ v))

    # Normalize the algebraic seed so the unit-neutral fitter behaves the same
    # for tiny and huge native-coordinate scales. Without this, the constant
    # design column can dominate the X/Y columns and make a valid small circle
    # appear rank deficient.
    coordinate_scale = float(np.max(np.linalg.norm(xy, axis=1)))
    if (
        not math.isfinite(coordinate_scale)
        or coordinate_scale <= np.finfo(np.float64).tiny
    ):
        raise FeatureFitError(
            "Circle fitting points have no resolvable radial extent"
        )
    xy_seed = xy / coordinate_scale

    design = np.column_stack(
        (
            2.0 * xy_seed[:, 0],
            2.0 * xy_seed[:, 1],
            np.ones(xy_seed.shape[0]),
        )
    )
    rhs = np.sum(np.square(xy_seed), axis=1)
    try:
        solution, _, rank, _ = np.linalg.lstsq(design, rhs, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise FeatureFitError(
            "Circle fitting least-squares solve did not converge"
        ) from exc
    if rank < 3:
        raise FeatureFitError(
            "Circle fitting points are degenerate after plane projection"
        )

    center2d_seed = solution[:2]
    radius_squared_seed = float(
        solution[2] + np.dot(center2d_seed, center2d_seed)
    )
    if not math.isfinite(radius_squared_seed) or radius_squared_seed <= 0:
        raise FeatureFitError("Circle fitting produced an invalid algebraic radius")

    center2d = center2d_seed * coordinate_scale
    radius_seed = math.sqrt(radius_squared_seed) * coordinate_scale
    center2d, radius, iterations = _refine_circle_2d(
        xy,
        center2d,
        radius_seed,
    )
    radial_distance = np.hypot(
        xy[:, 0] - center2d[0],
        xy[:, 1] - center2d[1],
    )
    radial_residual = radial_distance - radius

    center3d = centroid + center2d[0] * u + center2d[1] * v
    plane_signed = (xyz - centroid) @ normal
    combined_distance = np.sqrt(
        np.square(radial_residual) + np.square(plane_signed)
    )

    radial_stats = _residual_stats(radial_residual)
    plane_stats = plane["residuals"]
    arc_coverage = _arc_coverage_degrees(xy, center2d)
    warnings: list[str] = []
    if arc_coverage < 120.0:
        warnings.append(
            "Sampled arc coverage is below 120 degrees; center and diameter can be weakly constrained."
        )

    return {
        "type": "circle",
        "sample_count": int(xyz.shape[0]),
        "center": _vector3(center3d),
        "normal": _vector3(normal),
        "normal_orientation_policy": "largest_absolute_component_positive",
        "radius": float(radius),
        "diameter": float(2.0 * radius),
        "basis_u": _vector3(u),
        "basis_v": _vector3(v),
        "arc_coverage_degrees": arc_coverage,
        "radial_residuals": radial_stats,
        "plane_residuals": plane_stats,
        "orthogonal_circle_residuals": _residual_stats(combined_distance),
        "normalized_radial_rms_to_radius": (
            float(radial_stats["rms"]) / radius
        ),
        "normalized_plane_rms_to_radius": (
            float(plane_stats["rms"]) / radius
        ),
        "plane": plane,
        "refinement_iterations": int(iterations),
        "quality_warnings": warnings,
    }


def point_to_plane(
    point: Sequence[float],
    plane: dict[str, Any],
) -> dict[str, Any]:
    """Measure signed/absolute distance and projection from a point to a fitted plane."""
    p = _points_array(
        [point],
        minimum=1,
        label="Point-to-plane measurement",
    )[0]
    try:
        normal = np.asarray(plane["normal"], dtype=np.float64)
        centroid = np.asarray(plane["centroid"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureFitError("plane must be a plane-fit result") from exc

    if (
        normal.shape != (3,)
        or centroid.shape != (3,)
        or not np.isfinite(normal).all()
        or not np.isfinite(centroid).all()
    ):
        raise FeatureFitError("plane contains invalid coordinates")

    norm = float(np.linalg.norm(normal))
    if norm <= np.finfo(np.float64).eps:
        raise FeatureFitError("plane normal has zero length")
    normal = normal / norm

    signed = float(np.dot(p - centroid, normal))
    projected = p - signed * normal
    return {
        "signed_distance": signed,
        "absolute_distance": abs(signed),
        "projected_point": _vector3(projected),
    }


def plane_relationship(
    plane_a: dict[str, Any],
    plane_b: dict[str, Any],
) -> dict[str, Any]:
    """Return acute plane angle and centroid offsets between two plane fits."""
    try:
        n1 = np.asarray(plane_a["normal"], dtype=np.float64)
        n2 = np.asarray(plane_b["normal"], dtype=np.float64)
        c1 = np.asarray(plane_a["centroid"], dtype=np.float64)
        c2 = np.asarray(plane_b["centroid"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureFitError("Both inputs must be plane-fit results") from exc

    if (
        n1.shape != (3,)
        or n2.shape != (3,)
        or c1.shape != (3,)
        or c2.shape != (3,)
        or not np.isfinite(n1).all()
        or not np.isfinite(n2).all()
        or not np.isfinite(c1).all()
        or not np.isfinite(c2).all()
    ):
        raise FeatureFitError("Plane relationship inputs contain invalid coordinates")

    n1_norm = float(np.linalg.norm(n1))
    n2_norm = float(np.linalg.norm(n2))
    if n1_norm <= np.finfo(np.float64).eps or n2_norm <= np.finfo(np.float64).eps:
        raise FeatureFitError("Plane relationship requires non-zero normals")

    n1 /= n1_norm
    n2 /= n2_norm
    cosine = float(np.clip(abs(np.dot(n1, n2)), 0.0, 1.0))
    angle = math.degrees(math.acos(cosine))
    delta = c2 - c1

    return {
        "acute_angle_degrees": float(angle),
        "centroid_delta": _vector3(delta),
        "centroid_distance": float(np.linalg.norm(delta)),
        "normal_offset_from_a": abs(float(np.dot(delta, n1))),
        "normal_offset_from_b": abs(float(np.dot(delta, n2))),
        "parallel_within_1_degree": bool(angle <= 1.0),
    }


def feature_fit_capabilities() -> dict[str, Any]:
    return {
        "built_in": True,
        "coordinate_policy": "fit inputs are CloudCompare global coordinates",
        "units_policy": "unit-neutral native coordinates",
        "normal_orientation_policy": "largest absolute normal component is forced positive",
        "plane": {
            "available": True,
            "method": "orthogonal least squares / PCA",
            "minimum_points": 3,
            "diagnostics": [
                "RMS",
                "mean absolute",
                "median absolute",
                "P95 absolute",
                "max absolute",
                "principal variances",
                "planarity",
                "projected extents",
            ],
        },
        "circle": {
            "available": True,
            "method": "best-fit plane + geometric 2D least-squares circle",
            "minimum_points": 4,
            "diagnostics": [
                "radial residuals",
                "plane residuals",
                "orthogonal circle residuals",
                "arc coverage",
            ],
        },
        "relationships": {
            "point_to_plane": True,
            "plane_to_plane_angle_and_offset": True,
        },
        "visible_fit_overlays": False,
    }
