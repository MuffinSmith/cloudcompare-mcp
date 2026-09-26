"""Structured geometry discovery helpers for image-light CloudCompare workflows."""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np

from .feature_fit import FeatureFitError, fit_plane


def _points_array(points: Iterable[Sequence[float]], minimum: int, label: str) -> np.ndarray:
    try:
        array = np.asarray(list(points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise FeatureFitError(f"{label} must be numeric 3D points") from exc
    if array.ndim != 2 or array.shape[1:] != (3,):
        raise FeatureFitError(f"{label} must be an array of [x, y, z] points")
    if array.shape[0] < minimum:
        raise FeatureFitError(f"{label} requires at least {minimum} points")
    if not np.isfinite(array).all():
        raise FeatureFitError(f"{label} coordinates must all be finite")
    return array


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
    }


def enrich_region_grid(grid: dict[str, Any]) -> dict[str, Any]:
    """Add covariance-derived shape metrics to a native exact region grid."""
    if not isinstance(grid, dict) or not isinstance(grid.get("cells"), list):
        raise FeatureFitError("Region-grid response is malformed")

    out = {key: value for key, value in grid.items() if key != "cells"}
    enriched: list[dict[str, Any]] = []

    for cell_index, cell in enumerate(grid["cells"]):
        if not isinstance(cell, dict):
            raise FeatureFitError(f"Region-grid cell {cell_index} is malformed")
        covariance = np.asarray(cell.get("covariance"), dtype=np.float64)
        if covariance.shape != (3, 3) or not np.isfinite(covariance).all():
            raise FeatureFitError(
                f"Region-grid cell {cell_index} contains invalid covariance"
            )

        covariance = 0.5 * (covariance + covariance.T)
        try:
            eigenvalues = np.linalg.eigvalsh(covariance)
        except np.linalg.LinAlgError as exc:
            raise FeatureFitError(
                f"Region-grid cell {cell_index} covariance eigensolve failed"
            ) from exc
        eigenvalues = np.maximum(eigenvalues[::-1], 0.0)
        lambda1, lambda2, lambda3 = [float(value) for value in eigenvalues]

        if lambda1 > np.finfo(np.float64).tiny:
            linearity = (lambda1 - lambda2) / lambda1
            planarity = (lambda2 - lambda3) / lambda1
            scattering = lambda3 / lambda1
        else:
            linearity = 0.0
            planarity = 0.0
            scattering = 0.0

        item = {key: value for key, value in cell.items() if key != "covariance"}
        item["principal_variances"] = [lambda1, lambda2, lambda3]
        item["shape_metrics"] = {
            "linearity": float(linearity),
            "planarity": float(planarity),
            "scattering": float(scattering),
        }
        item["rms_thickness"] = float(math.sqrt(lambda3))
        enriched.append(item)

    out["cells"] = enriched
    out["shape_metrics_source"] = "exact native per-cell covariance"
    return out


def _candidate_plane_from_three(points: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    a, b, c = points
    normal = np.cross(b - a, c - a)
    norm = float(np.linalg.norm(normal))
    if not math.isfinite(norm) or norm <= np.finfo(np.float64).tiny:
        return None
    return a, normal / norm


def discover_planes(
    points: Iterable[Sequence[float]],
    *,
    distance_threshold: float | None = None,
    max_planes: int = 5,
    min_points: int = 30,
    min_inlier_fraction: float = 0.05,
    iterations: int = 400,
    random_seed: int = 0,
) -> dict[str, Any]:
    """Discover multiple dominant planes using deterministic RANSAC + OLS refinement."""
    xyz = _points_array(points, 3, "Plane discovery")

    if not isinstance(max_planes, int) or not 1 <= max_planes <= 16:
        raise FeatureFitError("max_planes must be an integer between 1 and 16")
    if not isinstance(min_points, int) or min_points < 3:
        raise FeatureFitError("min_points must be an integer >= 3")
    if min_points > xyz.shape[0]:
        raise FeatureFitError("min_points exceeds the available sample count")
    if (
        not math.isfinite(float(min_inlier_fraction))
        or min_inlier_fraction <= 0.0
        or min_inlier_fraction > 1.0
    ):
        raise FeatureFitError("min_inlier_fraction must be in (0, 1]")
    if not isinstance(iterations, int) or not 10 <= iterations <= 5000:
        raise FeatureFitError("iterations must be an integer between 10 and 5000")

    extent = np.ptp(xyz, axis=0)
    diagonal = float(np.linalg.norm(extent))
    if not math.isfinite(diagonal) or diagonal <= np.finfo(np.float64).tiny:
        raise FeatureFitError("Plane discovery sample has no resolvable extent")

    if distance_threshold is None:
        threshold = max(
            diagonal * 0.002,
            np.finfo(np.float64).eps * max(diagonal, 1.0) * 1024.0,
        )
        threshold_source = "0.2_percent_sample_diagonal"
    else:
        threshold = float(distance_threshold)
        if not math.isfinite(threshold) or threshold <= 0.0:
            raise FeatureFitError("distance_threshold must be finite and > 0")
        threshold_source = "caller"

    rng = np.random.default_rng(random_seed)
    remaining = np.arange(xyz.shape[0], dtype=np.int64)
    candidates: list[dict[str, Any]] = []

    for candidate_index in range(max_planes):
        if remaining.size < min_points:
            break

        subset = xyz[remaining]
        best_mask: np.ndarray | None = None
        best_count = -1
        best_rms = math.inf

        for _ in range(iterations):
            sample_indices = rng.choice(subset.shape[0], size=3, replace=False)
            candidate = _candidate_plane_from_three(subset[sample_indices])
            if candidate is None:
                continue
            point_on_plane, normal = candidate
            distances = np.abs((subset - point_on_plane) @ normal)
            mask = distances <= threshold
            count = int(np.count_nonzero(mask))
            if count < min_points:
                continue
            rms = float(np.sqrt(np.mean(np.square(distances[mask]))))
            if count > best_count or (count == best_count and rms < best_rms):
                best_mask = mask
                best_count = count
                best_rms = rms

        if best_mask is None:
            break

        mask = best_mask
        refined: dict[str, Any] | None = None
        for _ in range(3):
            if int(np.count_nonzero(mask)) < min_points:
                break
            refined = fit_plane(subset[mask])
            centroid = np.asarray(refined["centroid"], dtype=np.float64)
            normal = np.asarray(refined["normal"], dtype=np.float64)
            distances = np.abs((subset - centroid) @ normal)
            mask = distances <= threshold

        support_count = int(np.count_nonzero(mask))
        if support_count < min_points:
            break
        support_fraction = support_count / float(xyz.shape[0])
        if support_fraction < min_inlier_fraction:
            break

        refined = fit_plane(subset[mask])
        centroid = np.asarray(refined["centroid"], dtype=np.float64)
        normal = np.asarray(refined["normal"], dtype=np.float64)
        signed = (subset[mask] - centroid) @ normal
        inliers = subset[mask]
        bounds_min = np.min(inliers, axis=0)
        bounds_max = np.max(inliers, axis=0)

        candidates.append(
            {
                "candidate_index": candidate_index,
                "support_count": support_count,
                "support_fraction_of_sample": float(support_fraction),
                "distance_threshold": threshold,
                "residuals": _residual_stats(signed),
                "bounds_global": {
                    "min": bounds_min.astype(float).tolist(),
                    "max": bounds_max.astype(float).tolist(),
                    "extent": (bounds_max - bounds_min).astype(float).tolist(),
                },
                "plane": refined,
            }
        )

        remaining = remaining[~mask]

    return {
        "type": "plane_discovery",
        "sample_count": int(xyz.shape[0]),
        "distance_threshold": threshold,
        "distance_threshold_source": threshold_source,
        "max_planes": max_planes,
        "min_points": min_points,
        "min_inlier_fraction": float(min_inlier_fraction),
        "iterations_per_plane": iterations,
        "random_seed": random_seed,
        "candidate_count": len(candidates),
        "unassigned_sample_count": int(remaining.size),
        "candidates": candidates,
    }


def occupancy_grid_2d(
    uv_points: Iterable[Sequence[float]],
    *,
    divisions: Sequence[int] = (24, 24),
    min_count: int = 1,
    max_cells: int = 512,
) -> dict[str, Any]:
    """Build a compact sparse 2D occupancy map from projected section samples."""
    try:
        uv = np.asarray(list(uv_points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise FeatureFitError("Section occupancy requires numeric [u, v] points") from exc
    if uv.ndim != 2 or uv.shape[1:] != (2,) or uv.shape[0] == 0:
        raise FeatureFitError("Section occupancy requires at least one [u, v] point")
    if not np.isfinite(uv).all():
        raise FeatureFitError("Section occupancy coordinates must be finite")
    if len(divisions) != 2:
        raise FeatureFitError("Section occupancy divisions must contain two integers")

    du, dv = divisions
    if (
        isinstance(du, bool)
        or isinstance(dv, bool)
        or not isinstance(du, int)
        or not isinstance(dv, int)
        or not 1 <= du <= 128
        or not 1 <= dv <= 128
    ):
        raise FeatureFitError("Section occupancy divisions must be integers from 1 to 128")
    if not isinstance(min_count, int) or min_count < 1:
        raise FeatureFitError("min_count must be a positive integer")
    if not isinstance(max_cells, int) or not 0 <= max_cells <= 4096:
        raise FeatureFitError("max_cells must be an integer between 0 and 4096")

    minimum = np.min(uv, axis=0)
    maximum = np.max(uv, axis=0)
    span = maximum - minimum
    effective = [du if span[0] > 0 else 1, dv if span[1] > 0 else 1]

    indices = np.zeros((uv.shape[0], 2), dtype=np.int64)
    for axis, div in enumerate(effective):
        if div <= 1 or span[axis] == 0:
            continue
        normalized = (uv[:, axis] - minimum[axis]) / span[axis]
        indices[:, axis] = np.floor(normalized * div).astype(np.int64)
        indices[:, axis] = np.clip(indices[:, axis], 0, div - 1)

    counts: dict[tuple[int, int], int] = {}
    sums: dict[tuple[int, int], np.ndarray] = {}
    for point, index in zip(uv, indices):
        key = (int(index[0]), int(index[1]))
        counts[key] = counts.get(key, 0) + 1
        if key in sums:
            sums[key] += point
        else:
            sums[key] = point.copy()

    eligible = [
        (key, count)
        for key, count in counts.items()
        if count >= min_count
    ]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    returned = eligible[:max_cells]

    cells = [
        {
            "index": [key[0], key[1]],
            "count": count,
            "fraction_of_sample": count / float(uv.shape[0]),
            "centroid_uv": (sums[key] / count).astype(float).tolist(),
        }
        for key, count in returned
    ]

    return {
        "type": "section_occupancy_grid",
        "sample_count": int(uv.shape[0]),
        "bounds_uv": {
            "min": minimum.astype(float).tolist(),
            "max": maximum.astype(float).tolist(),
            "extent": span.astype(float).tolist(),
        },
        "requested_divisions": [du, dv],
        "effective_divisions": effective,
        "nonempty_cell_count": len(counts),
        "eligible_cell_count": len(eligible),
        "returned_cell_count": len(cells),
        "cells_truncated": len(cells) < len(eligible),
        "min_count": min_count,
        "max_cells": max_cells,
        "cells": cells,
    }


def discovery_capabilities() -> dict[str, Any]:
    return {
        "structured_region_grid": True,
        "plane_discovery": {
            "available": True,
            "method": "deterministic RANSAC plus orthogonal least-squares refinement",
            "returns_inlier_fraction": True,
            "image_required": False,
        },
        "section_occupancy_grid": {
            "available": True,
            "sparse_output": True,
            "image_required": False,
        },
        "visible_overlays": False,
    }
