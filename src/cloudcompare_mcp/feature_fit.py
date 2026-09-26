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
        parameter_scale = max(
            float(np.linalg.norm(parameters)),
            abs(float(parameters[2])),
            np.finfo(np.float64).tiny,
        )
        if float(np.linalg.norm(step)) <= 1.0e-12 * parameter_scale:
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
    if np.unique(xyz, axis=0).shape[0] < 4:
        raise FeatureFitError("Circle fitting requires at least 4 distinct points")
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


def _stable_basis_from_axis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    axis = np.asarray(axis, dtype=np.float64)
    norm = float(np.linalg.norm(axis))
    if not math.isfinite(norm) or norm <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Axis direction has zero length")
    axis = axis / norm
    seed = np.eye(3, dtype=np.float64)[int(np.argmin(np.abs(axis)))]
    u = seed - axis * float(np.dot(seed, axis))
    u_norm = float(np.linalg.norm(u))
    if u_norm <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Could not construct an axis basis")
    u = _orient_vector(u / u_norm)
    v = np.cross(axis, u)
    v /= np.linalg.norm(v)
    u = np.cross(v, axis)
    u /= np.linalg.norm(u)
    u = _orient_vector(u)
    v = np.cross(axis, u)
    v /= np.linalg.norm(v)
    return u, v


def _fit_circle_2d_seed(xy: np.ndarray) -> tuple[np.ndarray, float]:
    """Fast normalized algebraic circle seed used inside iterative axis search."""
    xy = np.asarray(xy, dtype=np.float64)
    if xy.ndim != 2 or xy.shape[1:] != (2,) or xy.shape[0] < 3:
        raise FeatureFitError("Projected circle fitting requires at least three 2D points")
    if not np.isfinite(xy).all():
        raise FeatureFitError("Projected circle fitting requires finite coordinates")

    coordinate_scale = float(np.max(np.linalg.norm(xy, axis=1)))
    if (
        not math.isfinite(coordinate_scale)
        or coordinate_scale <= np.finfo(np.float64).tiny
    ):
        raise FeatureFitError("Circle fitting points have no resolvable radial extent")

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

    center_seed = solution[:2]
    radius_squared_seed = float(
        solution[2] + np.dot(center_seed, center_seed)
    )
    if not math.isfinite(radius_squared_seed) or radius_squared_seed <= 0:
        raise FeatureFitError("Circle fitting produced an invalid algebraic radius")

    center = center_seed * coordinate_scale
    radius = math.sqrt(radius_squared_seed) * coordinate_scale
    return center, radius


def _fit_circle_2d_geometric(
    xy: np.ndarray,
) -> tuple[np.ndarray, float, int, np.ndarray]:
    center, radius_seed = _fit_circle_2d_seed(xy)
    center, radius, iterations = _refine_circle_2d(
        np.asarray(xy, dtype=np.float64),
        center,
        radius_seed,
    )
    radial_distance = np.hypot(
        xy[:, 0] - center[0],
        xy[:, 1] - center[1],
    )
    return center, radius, iterations, radial_distance - radius


def fit_line_3d(points: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Fit an orthogonal least-squares 3D line to sampled points."""
    xyz = _points_array(points, minimum=2, label="Line fitting")
    if np.unique(xyz, axis=0).shape[0] < 2:
        raise FeatureFitError("Line fitting requires at least 2 distinct points")

    centroid = np.mean(xyz, axis=0)
    centered = xyz - centroid
    try:
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise FeatureFitError("Line fitting SVD did not converge") from exc

    scale = float(singular_values[0]) if singular_values.size else 0.0
    if not math.isfinite(scale) or scale <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Line fitting points are coincident or numerically unresolved")

    direction = _orient_vector(vh[0] / np.linalg.norm(vh[0]))
    axial = centered @ direction
    perpendicular = centered - axial[:, None] * direction
    distances = np.linalg.norm(perpendicular, axis=1)

    axial_min = float(np.min(axial))
    axial_max = float(np.max(axial))
    variances = np.square(singular_values) / float(xyz.shape[0])
    padded = np.zeros(3, dtype=np.float64)
    padded[: min(3, variances.size)] = variances[:3]
    lambda1, lambda2, lambda3 = [float(v) for v in padded]
    linearity = (
        (lambda1 - lambda2) / lambda1
        if lambda1 > np.finfo(np.float64).tiny
        else 0.0
    )

    return {
        "type": "line",
        "sample_count": int(xyz.shape[0]),
        "centroid": _vector3(centroid),
        "direction": _vector3(direction),
        "direction_orientation_policy": "largest_absolute_component_positive",
        "residuals": _residual_stats(distances),
        "principal_variances": [lambda1, lambda2, lambda3],
        "linearity": float(linearity),
        "axial_range": [axial_min, axial_max],
        "axial_span": axial_max - axial_min,
        "span_endpoints": [
            _vector3(centroid + axial_min * direction),
            _vector3(centroid + axial_max * direction),
        ],
    }


def _rotate_vector(vector: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (
        vector * cosine
        + np.cross(axis, vector) * sine
        + axis * float(np.dot(axis, vector)) * (1.0 - cosine)
    )


def _cylinder_for_axis(
    xyz: np.ndarray,
    centroid: np.ndarray,
    direction: np.ndarray,
    *,
    refine_circle: bool = False,
) -> dict[str, Any]:
    direction = _orient_vector(
        np.asarray(direction, dtype=np.float64)
        / np.linalg.norm(direction)
    )
    u, v = _stable_basis_from_axis(direction)
    centered = xyz - centroid
    xy = np.column_stack((centered @ u, centered @ v))
    if refine_circle:
        center2d, radius, iterations, _ = _fit_circle_2d_geometric(xy)
    else:
        center2d, radius = _fit_circle_2d_seed(xy)
        iterations = 0

    axis_point = centroid + center2d[0] * u + center2d[1] * v
    relative = xyz - axis_point
    axial = relative @ direction
    perpendicular = relative - axial[:, None] * direction
    radial_distance = np.linalg.norm(perpendicular, axis=1)
    radial_residual = radial_distance - radius
    rms = float(np.sqrt(np.mean(np.square(radial_residual))))

    angular_xy = np.column_stack((relative @ u, relative @ v))
    angular_coverage = _arc_coverage_degrees(angular_xy, np.zeros(2))

    return {
        "axis_point": axis_point,
        "direction": direction,
        "basis_u": u,
        "basis_v": v,
        "radius": float(radius),
        "axial": axial,
        "radial_residual": radial_residual,
        "rms": rms,
        "arc_coverage_degrees": angular_coverage,
        "circle_refinement_iterations": iterations,
    }


def fit_cylinder_3d(points: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Fit an infinite circular-cylinder axis/radius to 3D surface samples."""
    xyz = _points_array(points, minimum=6, label="Cylinder fitting")
    if np.unique(xyz, axis=0).shape[0] < 6:
        raise FeatureFitError("Cylinder fitting requires at least 6 distinct points")

    centroid = np.mean(xyz, axis=0)
    centered = xyz - centroid
    try:
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise FeatureFitError("Cylinder fitting SVD did not converge") from exc

    if singular_values.size < 3 or float(singular_values[0]) <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Cylinder fitting points are numerically unresolved")

    # The true cylinder axis is commonly a covariance eigenvector. Partial arcs and
    # uneven sampling can tilt that eigenvector, so use deterministic multi-start
    # directions and then refine each candidate directly against radial RMS.
    basis = np.asarray(vh, dtype=np.float64)
    candidate_coefficients = [
        (1, 0, 0), (0, 1, 0), (0, 0, 1),
        (1, 1, 0), (1, -1, 0),
        (1, 0, 1), (1, 0, -1),
        (0, 1, 1), (0, 1, -1),
        (1, 1, 1), (1, 1, -1),
        (1, -1, 1), (-1, 1, 1),
    ]

    raw_candidates: list[np.ndarray] = []
    for coeffs in candidate_coefficients:
        direction = (
            coeffs[0] * basis[0]
            + coeffs[1] * basis[1]
            + coeffs[2] * basis[2]
        )
        norm = float(np.linalg.norm(direction))
        if norm > np.finfo(np.float64).tiny:
            raw_candidates.append(_orient_vector(direction / norm))

    candidates: list[dict[str, Any]] = []
    for direction in raw_candidates:
        try:
            candidates.append(_cylinder_for_axis(xyz, centroid, direction))
        except FeatureFitError:
            continue
    if not candidates:
        raise FeatureFitError("Cylinder fitting could not form a non-degenerate radial projection")

    current = min(candidates, key=lambda item: item["rms"])
    step = math.radians(20.0)
    iterations = 0
    while step > 1.0e-8 and iterations < 120:
        iterations += 1
        direction = np.asarray(current["direction"], dtype=np.float64)
        u, v = _stable_basis_from_axis(direction)
        tangent_axes = [
            u,
            v,
            (u + v) / math.sqrt(2.0),
            (u - v) / math.sqrt(2.0),
        ]

        improved = False
        best = current
        for tangent in tangent_axes:
            for signed_step in (step, -step):
                trial_direction = _rotate_vector(direction, tangent, signed_step)
                try:
                    trial = _cylinder_for_axis(xyz, centroid, trial_direction)
                except FeatureFitError:
                    continue
                tolerance = max(
                    np.finfo(np.float64).tiny,
                    current["rms"] * 1.0e-12,
                    abs(float(current["radius"]))
                    * np.finfo(np.float64).eps
                    * 64.0,
                )
                if trial["rms"] + tolerance < best["rms"]:
                    best = trial
                    improved = True

        if improved:
            current = best
        else:
            step *= 0.5

    # The search uses the fast normalized algebraic circle seed. Refine the
    # final cross-section geometrically once, after the axis direction is settled.
    current = _cylinder_for_axis(
        xyz,
        centroid,
        np.asarray(current["direction"], dtype=np.float64),
        refine_circle=True,
    )

    direction = np.asarray(current["direction"], dtype=np.float64)
    axis_point = np.asarray(current["axis_point"], dtype=np.float64)
    axial = np.asarray(current["axial"], dtype=np.float64)
    radius = float(current["radius"])
    radial_residual = np.asarray(current["radial_residual"], dtype=np.float64)

    axial_min = float(np.min(axial))
    axial_max = float(np.max(axial))
    span = axial_max - axial_min
    coverage = float(current["arc_coverage_degrees"])
    warnings: list[str] = []
    if coverage < 120.0:
        warnings.append(
            "Sampled cylinder circumference coverage is below 120 degrees; axis and diameter can be weakly constrained."
        )
    if span < 0.25 * max(2.0 * radius, np.finfo(np.float64).tiny):
        warnings.append(
            "Sampled axial span is short relative to diameter; cylinder-axis location along the sampled feature may be weakly constrained."
        )

    return {
        "type": "cylinder",
        "sample_count": int(xyz.shape[0]),
        "axis_point": _vector3(axis_point),
        "axis_direction": _vector3(direction),
        "direction_orientation_policy": "largest_absolute_component_positive",
        "basis_u": _vector3(np.asarray(current["basis_u"])),
        "basis_v": _vector3(np.asarray(current["basis_v"])),
        "radius": radius,
        "diameter": 2.0 * radius,
        "radial_residuals": _residual_stats(radial_residual),
        "normalized_radial_rms_to_radius": (
            float(np.sqrt(np.mean(np.square(radial_residual)))) / radius
        ),
        "angular_coverage_degrees": coverage,
        "axial_range": [axial_min, axial_max],
        "axial_span": span,
        "axial_span_to_diameter": span / (2.0 * radius),
        "span_endpoints": [
            _vector3(axis_point + axial_min * direction),
            _vector3(axis_point + axial_max * direction),
        ],
        "optimizer_iterations": iterations,
        "candidate_count": len(candidates),
        "quality_warnings": warnings,
    }


def line_relationship(
    line_a: dict[str, Any],
    line_b: dict[str, Any],
) -> dict[str, Any]:
    """Compare two fitted infinite lines/axes."""
    try:
        p1 = np.asarray(line_a.get("axis_point", line_a.get("centroid")), dtype=np.float64)
        p2 = np.asarray(line_b.get("axis_point", line_b.get("centroid")), dtype=np.float64)
        d1 = np.asarray(line_a.get("axis_direction", line_a.get("direction")), dtype=np.float64)
        d2 = np.asarray(line_b.get("axis_direction", line_b.get("direction")), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise FeatureFitError("Both inputs must be fitted lines or cylinder axes") from exc

    if any(value.shape != (3,) or not np.isfinite(value).all() for value in (p1, p2, d1, d2)):
        raise FeatureFitError("Line relationship inputs contain invalid coordinates")
    d1_norm = float(np.linalg.norm(d1))
    d2_norm = float(np.linalg.norm(d2))
    if d1_norm <= np.finfo(np.float64).tiny or d2_norm <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Line relationship requires non-zero directions")
    d1 /= d1_norm
    d2 /= d2_norm

    dot = float(np.clip(np.dot(d1, d2), -1.0, 1.0))
    acute_angle = math.degrees(math.acos(abs(dot)))
    cross = np.cross(d1, d2)
    cross_norm = float(np.linalg.norm(cross))

    parallel_threshold = math.sqrt(np.finfo(np.float64).eps)
    if cross_norm <= parallel_threshold:
        offset = p2 - p1
        perpendicular = offset - d1 * float(np.dot(offset, d1))
        distance = float(np.linalg.norm(perpendicular))
        closest_a = p1
        closest_b = p2 - d1 * float(np.dot(p2 - p1, d1))
        parallel = True
    else:
        w0 = p1 - p2
        denominator = 1.0 - dot * dot
        d = float(np.dot(d1, w0))
        e = float(np.dot(d2, w0))
        s = (dot * e - d) / denominator
        t = (e - dot * d) / denominator
        closest_a = p1 + s * d1
        closest_b = p2 + t * d2
        distance = float(np.linalg.norm(closest_b - closest_a))
        parallel = False

    return {
        "acute_angle_degrees": float(acute_angle),
        "shortest_distance": distance,
        "closest_point_a": _vector3(closest_a),
        "closest_point_b": _vector3(closest_b),
        "parallel": parallel,
        "parallel_within_1_degree": bool(acute_angle <= 1.0),
    }


def line_plane_relationship(
    line: dict[str, Any],
    plane: dict[str, Any],
) -> dict[str, Any]:
    """Compare a fitted line/axis with a fitted plane."""
    try:
        point = np.asarray(line.get("axis_point", line.get("centroid")), dtype=np.float64)
        direction = np.asarray(line.get("axis_direction", line.get("direction")), dtype=np.float64)
        normal = np.asarray(plane["normal"], dtype=np.float64)
        plane_point = np.asarray(plane["centroid"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureFitError("Inputs must be a fitted line/axis and fitted plane") from exc

    if any(value.shape != (3,) or not np.isfinite(value).all() for value in (point, direction, normal, plane_point)):
        raise FeatureFitError("Line-plane inputs contain invalid coordinates")

    direction_norm = float(np.linalg.norm(direction))
    normal_norm = float(np.linalg.norm(normal))
    if (
        direction_norm <= np.finfo(np.float64).tiny
        or normal_norm <= np.finfo(np.float64).tiny
    ):
        raise FeatureFitError("Line-plane relationship requires non-zero directions and normals")
    direction /= direction_norm
    normal /= normal_norm
    dot = float(np.clip(np.dot(direction, normal), -1.0, 1.0))
    angle_to_plane = math.degrees(math.asin(abs(dot)))
    signed_point_distance = float(np.dot(point - plane_point, normal))

    intersection = None
    parallel_threshold = math.sqrt(np.finfo(np.float64).eps)
    if abs(dot) > parallel_threshold:
        parameter = float(np.dot(plane_point - point, normal) / dot)
        intersection = _vector3(point + parameter * direction)

    return {
        "angle_to_plane_degrees": float(angle_to_plane),
        "axis_point_signed_distance": signed_point_distance,
        "axis_point_absolute_distance": abs(signed_point_distance),
        "parallel_to_plane": bool(abs(dot) <= parallel_threshold),
        "perpendicular_to_plane_within_1_degree": bool(angle_to_plane >= 89.0),
        "intersection_point": intersection,
    }


def project_points_to_section(
    points: Iterable[Sequence[float]],
    origin: Sequence[float],
    normal: Sequence[float],
    *,
    half_thickness: float | None = None,
) -> dict[str, Any]:
    """Project 3D samples into a stable 2D coordinate frame on a section plane."""
    xyz = _points_array(points, minimum=1, label="Cross-section projection")
    origin_array = _points_array([origin], minimum=1, label="Cross-section origin")[0]
    normal_array = _points_array([normal], minimum=1, label="Cross-section normal")[0]
    normal_norm = float(np.linalg.norm(normal_array))
    if normal_norm <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Cross-section normal has zero length")
    normal_array = _orient_vector(normal_array / normal_norm)

    if half_thickness is not None:
        half_thickness = float(half_thickness)
        if not math.isfinite(half_thickness) or half_thickness < 0:
            raise FeatureFitError("half_thickness must be finite and non-negative")

    u, v = _stable_basis_from_axis(normal_array)
    relative = xyz - origin_array
    signed = relative @ normal_array
    mask = np.ones(xyz.shape[0], dtype=bool)
    if half_thickness is not None:
        mask = np.abs(signed) <= half_thickness

    selected = xyz[mask]
    selected_signed = signed[mask]
    selected_relative = selected - origin_array
    uv = np.column_stack((selected_relative @ u, selected_relative @ v))
    projected = selected - selected_signed[:, None] * normal_array

    if selected.shape[0]:
        bounds = {
            "u": [float(np.min(uv[:, 0])), float(np.max(uv[:, 0]))],
            "v": [float(np.min(uv[:, 1])), float(np.max(uv[:, 1]))],
            "extent_u": float(np.ptp(uv[:, 0])),
            "extent_v": float(np.ptp(uv[:, 1])),
        }
        offset_stats = _residual_stats(selected_signed)
    else:
        bounds = {
            "u": [],
            "v": [],
            "extent_u": 0.0,
            "extent_v": 0.0,
        }
        offset_stats = None

    return {
        "type": "cross_section_projection",
        "input_count": int(xyz.shape[0]),
        "selected_count": int(selected.shape[0]),
        "origin": _vector3(origin_array),
        "normal": _vector3(normal_array),
        "normal_orientation_policy": "largest_absolute_component_positive",
        "basis_u": _vector3(u),
        "basis_v": _vector3(v),
        "half_thickness": half_thickness,
        "source_indices": np.flatnonzero(mask).astype(int).tolist(),
        "points_global": selected.tolist(),
        "projected_points_global": projected.tolist(),
        "uv": uv.tolist(),
        "signed_offsets": selected_signed.astype(float).tolist(),
        "signed_offset_stats": offset_stats,
        "projected_bounds": bounds,
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
        "line": {
            "available": True,
            "method": "orthogonal least squares / PCA",
            "minimum_points": 2,
        },
        "cylinder": {
            "available": True,
            "method": "deterministic multi-start axis search + geometric radial least squares",
            "minimum_points": 6,
            "diagnostics": [
                "radial residuals",
                "angular coverage",
                "axial span",
            ],
        },
        "cross_section_projection": {
            "available": True,
            "source": "captured picks / explicit point arrays",
            "full_cloud_slab_extraction": False,
        },
        "relationships": {
            "point_to_plane": True,
            "plane_to_plane_angle_and_offset": True,
            "line_to_line": True,
            "line_or_axis_to_plane": True,
        },
        "visible_fit_overlays": False,
    }
