"""Deterministic boundary-loop extraction for section-profile reconstruction.

This module consumes unordered 2D *boundary samples*.  It does not infer a boundary
from a filled section, and it refuses ambiguous graphs rather than inventing topology.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Sequence

import numpy as np

from .profile_reconstruction import ProfileError, reconstruct_profile_2d


class ProfileTopologyError(ProfileError):
    """Raised when section boundary topology cannot be recovered safely."""


MAX_TOPOLOGY_POINTS = 2048
MAX_TOPOLOGY_LOOPS = 32


def _points2d(points: Iterable[Sequence[float]]) -> np.ndarray:
    try:
        array = np.asarray(list(points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ProfileTopologyError(
            "points_uv must be an array of 2D numeric boundary samples"
        ) from exc
    if array.ndim != 2 or array.shape[1:] != (2,):
        raise ProfileTopologyError("points_uv must be an array of [u, v] points")
    if array.shape[0] < 6:
        raise ProfileTopologyError("Boundary topology requires at least 6 points")
    if array.shape[0] > MAX_TOPOLOGY_POINTS:
        raise ProfileTopologyError(
            f"Boundary topology supports at most {MAX_TOPOLOGY_POINTS} points"
        )
    if not np.isfinite(array).all():
        raise ProfileTopologyError("points_uv coordinates must all be finite")
    if np.unique(array, axis=0).shape[0] != array.shape[0]:
        raise ProfileTopologyError(
            "Boundary topology requires unique points; duplicate coordinates are ambiguous"
        )
    return array


def _precision_floor(points: np.ndarray) -> float:
    spacing = np.abs(np.spacing(np.abs(points)))
    finite = spacing[np.isfinite(spacing)]
    floor = float(np.max(finite)) if finite.size else 0.0
    scale = max(
        float(np.max(np.abs(points))),
        float(np.ptp(points, axis=0).max()),
        1.0,
    )
    return 8.0 * max(floor, np.finfo(np.float64).eps * scale)


def _float64_sha256(points: np.ndarray) -> str:
    return hashlib.sha256(
        np.asarray(points, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _index_sha256(indices: Sequence[int]) -> str:
    return hashlib.sha256(
        np.asarray(indices, dtype="<i8").tobytes(order="C")
    ).hexdigest()


def _pairwise_distances(points: np.ndarray) -> np.ndarray:
    relative = points - points[0]
    if not np.isfinite(relative).all():
        raise ProfileTopologyError(
            "Boundary coordinate differences overflow float64; shift coordinates before analysis"
        )
    delta = relative[:, None, :] - relative[None, :, :]
    distances = np.hypot(delta[:, :, 0], delta[:, :, 1])
    if not np.isfinite(distances).all():
        raise ProfileTopologyError("Boundary pairwise distances overflow float64")
    np.fill_diagonal(distances, np.inf)
    return distances


def _components(neighbors: list[list[int]]) -> list[list[int]]:
    seen: set[int] = set()
    output: list[list[int]] = []
    for start in range(len(neighbors)):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in neighbors[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        output.append(sorted(component))
    return output


def _turn_score(
    points: np.ndarray,
    previous: int,
    current: int,
    candidate: int,
) -> float:
    incoming = points[current] - points[previous]
    outgoing = points[candidate] - points[current]
    ni = float(np.linalg.norm(incoming))
    no = float(np.linalg.norm(outgoing))
    if ni <= np.finfo(np.float64).tiny or no <= np.finfo(np.float64).tiny:
        raise ProfileTopologyError("Boundary trace encountered a zero-length edge")
    cosine = float(np.clip(np.dot(incoming, outgoing) / (ni * no), -1.0, 1.0))
    return float(math.acos(cosine))


def _trace_component(
    points: np.ndarray,
    component: list[int],
    neighbors: list[list[int]],
    distances: np.ndarray,
) -> list[int]:
    if len(component) < 3:
        raise ProfileTopologyError("Boundary component has too few points for a loop")

    for index in component:
        if len(neighbors[index]) < 2:
            raise ProfileTopologyError(
                "Boundary graph is open or undersampled: "
                f"point {index} has only {len(neighbors[index])} neighbors within max_edge_length"
            )

    start = min(
        component,
        key=lambda index: (
            float(points[index, 0]),
            float(points[index, 1]),
            index,
        ),
    )
    first = min(
        neighbors[start],
        key=lambda index: (
            float(distances[start, index]),
            float(points[index, 0]),
            float(points[index, 1]),
            index,
        ),
    )

    sequence = [start, first]
    visited = {start, first}
    component_set = set(component)

    while True:
        previous, current = sequence[-2], sequence[-1]
        candidates: list[tuple[float, float, float, float, int]] = []
        for candidate in neighbors[current]:
            if candidate not in component_set or candidate == previous:
                continue
            if candidate == start:
                if len(visited) != len(component):
                    continue
            elif candidate in visited:
                continue

            candidates.append(
                (
                    _turn_score(points, previous, current, candidate),
                    float(distances[current, candidate]),
                    float(points[candidate, 0]),
                    float(points[candidate, 1]),
                    candidate,
                )
            )

        if not candidates:
            raise ProfileTopologyError(
                "Boundary trace became ambiguous or dead-ended before closing; "
                "reduce max_edge_length, isolate loops, or provide denser boundary samples"
            )

        candidate = min(candidates)[-1]
        if candidate == start:
            if len(visited) != len(component):
                raise ProfileTopologyError(
                    "Boundary trace closed before visiting every component point"
                )
            return sequence

        sequence.append(candidate)
        visited.add(candidate)
        if len(sequence) > len(component):
            raise ProfileTopologyError("Boundary trace exceeded component size")


def _signed_area(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(
        np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))
    )


def _edge_lengths(points: np.ndarray) -> np.ndarray:
    return np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)


def _orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ab = b - a
    ac = c - a
    return float(ab[0] * ac[1] - ab[1] * ac[0])


def _point_on_segment(
    point: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    epsilon: float,
) -> bool:
    if abs(_orientation(a, b, point)) > epsilon:
        return False
    return bool(
        min(a[0], b[0]) - epsilon <= point[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= point[1] <= max(a[1], b[1]) + epsilon
    )


def _segments_intersect(
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
    d: np.ndarray,
    epsilon: float,
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if (
        ((o1 > epsilon and o2 < -epsilon) or (o1 < -epsilon and o2 > epsilon))
        and ((o3 > epsilon and o4 < -epsilon) or (o3 < -epsilon and o4 > epsilon))
    ):
        return True

    return (
        (abs(o1) <= epsilon and _point_on_segment(c, a, b, epsilon))
        or (abs(o2) <= epsilon and _point_on_segment(d, a, b, epsilon))
        or (abs(o3) <= epsilon and _point_on_segment(a, c, d, epsilon))
        or (abs(o4) <= epsilon and _point_on_segment(b, c, d, epsilon))
    )


def _validate_loop_self_intersection(points: np.ndarray, epsilon: float) -> None:
    count = points.shape[0]
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % count]
        for j in range(i + 1, count):
            if j == i or j == (i + 1) % count or (j + 1) % count == i:
                continue
            if i == 0 and j == count - 1:
                continue
            c = points[j]
            d = points[(j + 1) % count]
            if _segments_intersect(a, b, c, d, epsilon):
                raise ProfileTopologyError(
                    "Recovered boundary loop self-intersects or touches itself"
                )


def _validate_loop_pair_intersection(
    a: np.ndarray,
    b: np.ndarray,
    epsilon: float,
) -> None:
    for i in range(a.shape[0]):
        a0 = a[i]
        a1 = a[(i + 1) % a.shape[0]]
        for j in range(b.shape[0]):
            b0 = b[j]
            b1 = b[(j + 1) % b.shape[0]]
            if _segments_intersect(a0, a1, b0, b1, epsilon):
                raise ProfileTopologyError(
                    "Recovered boundary loops intersect or touch; nesting is ambiguous"
                )


def _point_in_polygon(
    point: np.ndarray,
    polygon: np.ndarray,
    epsilon: float,
) -> bool:
    inside = False
    x, y = float(point[0]), float(point[1])
    count = polygon.shape[0]
    for i in range(count):
        a = polygon[i]
        b = polygon[(i + 1) % count]
        if _point_on_segment(point, a, b, epsilon):
            raise ProfileTopologyError(
                "Recovered loop lies on another loop boundary; nesting is ambiguous"
            )
        ay, by = float(a[1]), float(b[1])
        if (ay > y) != (by > y):
            x_intersection = float(a[0] + (y - ay) * (b[0] - a[0]) / (by - ay))
            if x_intersection > x:
                inside = not inside
    return inside


def _rotate_to_canonical_start(
    points: np.ndarray,
    indices: list[int],
) -> tuple[np.ndarray, list[int]]:
    start = min(
        range(points.shape[0]),
        key=lambda offset: (
            float(points[offset, 0]),
            float(points[offset, 1]),
            int(indices[offset]),
        ),
    )
    if start == 0:
        return points, indices
    return (
        np.concatenate((points[start:], points[:start]), axis=0),
        indices[start:] + indices[:start],
    )


def _map_profile_source_indices(
    profile: dict[str, Any],
    ordered_input_indices: Sequence[int],
) -> None:
    for primitive in profile.get("primitives", []):
        endpoints = primitive.get("source_endpoint_input_indices")
        if not isinstance(endpoints, list) or len(endpoints) != 2:
            continue
        mapped: list[int] = []
        for endpoint in endpoints:
            if not isinstance(endpoint, int) or not 0 <= endpoint < len(ordered_input_indices):
                raise ProfileTopologyError(
                    "Profile primitive returned an invalid loop-local source index"
                )
            mapped.append(int(ordered_input_indices[endpoint]))
        primitive["source_endpoint_input_indices"] = mapped
        primitive["source_index_space"] = "section_input"


def reconstruct_profile_topology_2d(
    points_uv: Iterable[Sequence[float]],
    *,
    max_edge_length: float,
    fit_tolerance: float,
    angular_tolerance_degrees: float = 1.0,
    minimum_loop_points: int = 6,
    max_loops: int = 16,
    minimum_arc_angle_degrees: float = 12.0,
    max_segments_per_loop: int = 64,
) -> dict[str, Any]:
    """Recover explicit closed loops from unordered boundary samples and fit each loop.

    The caller must supply boundary samples, not a filled 2D section.  The graph uses
    a caller-selected maximum local edge length and deterministic local turning
    continuity.  Ambiguous, open, intersecting, touching, or truncated topology is
    rejected instead of guessed.
    """
    points = _points2d(points_uv)
    try:
        edge_limit = float(max_edge_length)
        fit_limit = float(fit_tolerance)
        angular = float(angular_tolerance_degrees)
        min_arc = float(minimum_arc_angle_degrees)
    except (TypeError, ValueError) as exc:
        raise ProfileTopologyError("Topology thresholds must be numeric") from exc

    if isinstance(max_edge_length, bool) or not math.isfinite(edge_limit) or edge_limit <= 0:
        raise ProfileTopologyError("max_edge_length must be finite and positive")
    if isinstance(fit_tolerance, bool) or not math.isfinite(fit_limit) or fit_limit <= 0:
        raise ProfileTopologyError("fit_tolerance must be finite and positive")
    if not math.isfinite(angular) or not 0 <= angular <= 45:
        raise ProfileTopologyError(
            "angular_tolerance_degrees must be finite and between 0 and 45"
        )
    if not math.isfinite(min_arc) or not 1 <= min_arc <= 180:
        raise ProfileTopologyError(
            "minimum_arc_angle_degrees must be between 1 and 180"
        )
    if (
        isinstance(minimum_loop_points, bool)
        or not isinstance(minimum_loop_points, int)
        or not 3 <= minimum_loop_points <= MAX_TOPOLOGY_POINTS
    ):
        raise ProfileTopologyError(
            f"minimum_loop_points must be an integer between 3 and {MAX_TOPOLOGY_POINTS}"
        )
    if (
        isinstance(max_loops, bool)
        or not isinstance(max_loops, int)
        or not 1 <= max_loops <= MAX_TOPOLOGY_LOOPS
    ):
        raise ProfileTopologyError(
            f"max_loops must be an integer between 1 and {MAX_TOPOLOGY_LOOPS}"
        )
    if (
        isinstance(max_segments_per_loop, bool)
        or not isinstance(max_segments_per_loop, int)
        or not 1 <= max_segments_per_loop <= 128
    ):
        raise ProfileTopologyError(
            "max_segments_per_loop must be an integer between 1 and 128"
        )

    precision_floor = _precision_floor(points)
    if edge_limit < precision_floor:
        raise ProfileTopologyError(
            f"max_edge_length {edge_limit:.17g} is below the representable "
            f"coordinate precision floor {precision_floor:.17g}"
        )
    if fit_limit < precision_floor:
        raise ProfileTopologyError(
            f"fit_tolerance {fit_limit:.17g} is below the representable "
            f"coordinate precision floor {precision_floor:.17g}"
        )

    distances = _pairwise_distances(points)
    neighbors = [
        np.where(distances[index] <= edge_limit)[0].astype(int).tolist()
        for index in range(points.shape[0])
    ]
    sparse = [
        (index, len(row))
        for index, row in enumerate(neighbors)
        if len(row) < 2
    ]
    if sparse:
        preview = ", ".join(f"{index}:{count}" for index, count in sparse[:8])
        raise ProfileTopologyError(
            "Boundary graph is open or undersampled; points with fewer than two "
            f"neighbors within max_edge_length include {preview}"
        )

    components = _components(neighbors)
    if len(components) > max_loops:
        raise ProfileTopologyError(
            f"Boundary graph contains {len(components)} components, exceeding max_loops={max_loops}"
        )

    epsilon = max(
        precision_floor,
        edge_limit * 1.0e-12,
        np.finfo(np.float64).eps,
    )
    raw_loops: list[dict[str, Any]] = []
    for component_index, component in enumerate(components):
        if len(component) < minimum_loop_points:
            raise ProfileTopologyError(
                f"Boundary component {component_index} has {len(component)} points, "
                f"below minimum_loop_points={minimum_loop_points}"
            )
        sequence = _trace_component(points, component, neighbors, distances)
        loop_points = points[sequence]
        _validate_loop_self_intersection(loop_points, epsilon)

        area = _signed_area(loop_points)
        edges = _edge_lengths(loop_points)
        perimeter = float(np.sum(edges))
        if not math.isfinite(area) or not math.isfinite(perimeter) or perimeter <= 0:
            raise ProfileTopologyError("Boundary loop produced invalid area/perimeter")
        area_floor = max(precision_floor * perimeter, epsilon * epsilon)
        if abs(area) <= area_floor:
            raise ProfileTopologyError("Boundary loop area is numerically degenerate")

        raw_loops.append(
            {
                "component_index": component_index,
                "indices": list(map(int, sequence)),
                "points": loop_points,
                "signed_area": area,
                "perimeter": perimeter,
                "edge_min": float(np.min(edges)),
                "edge_max": float(np.max(edges)),
                "edge_mean": float(np.mean(edges)),
            }
        )

    for i in range(len(raw_loops)):
        for j in range(i + 1, len(raw_loops)):
            _validate_loop_pair_intersection(
                raw_loops[i]["points"],
                raw_loops[j]["points"],
                epsilon,
            )

    # Determine containment using one boundary sample from each disjoint loop.
    containing: list[list[int]] = [[] for _ in raw_loops]
    for child_index, child in enumerate(raw_loops):
        probe = child["points"][0]
        for parent_index, parent in enumerate(raw_loops):
            if child_index == parent_index:
                continue
            if abs(float(parent["signed_area"])) <= abs(float(child["signed_area"])):
                continue
            if _point_in_polygon(probe, parent["points"], epsilon):
                containing[child_index].append(parent_index)

    parent_index: list[int | None] = [None] * len(raw_loops)
    depth: list[int] = [0] * len(raw_loops)
    for child_index, parents in enumerate(containing):
        depth[child_index] = len(parents)
        if parents:
            parent_index[child_index] = min(
                parents,
                key=lambda index: abs(float(raw_loops[index]["signed_area"])),
            )

    # Orient material boundaries CCW and holes CW, then canonicalize the start.
    for index, loop in enumerate(raw_loops):
        desired_positive = depth[index] % 2 == 0
        loop_points = loop["points"]
        loop_indices = loop["indices"]
        if (float(loop["signed_area"]) > 0) != desired_positive:
            loop_points = loop_points[::-1].copy()
            loop_indices = list(reversed(loop_indices))
        loop_points, loop_indices = _rotate_to_canonical_start(
            loop_points,
            loop_indices,
        )
        loop["points"] = loop_points
        loop["indices"] = loop_indices
        loop["signed_area"] = _signed_area(loop_points)

    order = sorted(
        range(len(raw_loops)),
        key=lambda index: (
            depth[index],
            -abs(float(raw_loops[index]["signed_area"])),
            float(raw_loops[index]["points"][0, 0]),
            float(raw_loops[index]["points"][0, 1]),
        ),
    )
    new_position = {old: new for new, old in enumerate(order)}

    loops: list[dict[str, Any]] = []
    for new_index, old_index in enumerate(order):
        loop = raw_loops[old_index]
        loop_points = loop["points"]
        loop_indices = loop["indices"]
        profile = reconstruct_profile_2d(
            loop_points,
            closed=True,
            fit_tolerance=fit_limit,
            angular_tolerance_degrees=angular,
            ordering_method="input",
            minimum_arc_angle_degrees=min_arc,
            max_segments=max_segments_per_loop,
        )
        _map_profile_source_indices(profile, loop_indices)

        nesting_depth = depth[old_index]
        role = (
            "outer"
            if nesting_depth == 0
            else ("hole" if nesting_depth % 2 else "island")
        )
        old_parent = parent_index[old_index]
        preview = (
            loop_indices[:8]
            if len(loop_indices) <= 16
            else loop_indices[:8] + loop_indices[-8:]
        )
        loops.append(
            {
                "loop_id": f"loop-{new_index}",
                "state": "inferred_candidate",
                "role_candidate": role,
                "nesting_depth": nesting_depth,
                "parent_loop_id": (
                    None
                    if old_parent is None
                    else f"loop-{new_position[old_parent]}"
                ),
                "source_point_count": len(loop_indices),
                "source_index_order_sha256_int64_le": _index_sha256(loop_indices),
                "source_index_preview": list(map(int, preview)),
                "signed_area": float(loop["signed_area"]),
                "area_abs": abs(float(loop["signed_area"])),
                "sampled_perimeter": float(loop["perimeter"]),
                "sample_edge_length": {
                    "min": float(loop["edge_min"]),
                    "mean": float(loop["edge_mean"]),
                    "max": float(loop["edge_max"]),
                },
                "profile": profile,
            }
        )

    neighbor_counts = np.asarray([len(row) for row in neighbors], dtype=np.int64)
    return {
        "type": "cad_section_profile_topology",
        "version": "0.15.1",
        "coordinate_space": "section_uv",
        "units": "native",
        "state": "inferred_candidate",
        "topology_confirmed": False,
        "manufacturing_intent_confirmed": False,
        "user_accepted": False,
        "boundary_samples_asserted": True,
        "input_point_count": int(points.shape[0]),
        "input_points_sha256_float64_le": _float64_sha256(points),
        "raw_points_returned": False,
        "max_edge_length": edge_limit,
        "fit_tolerance": fit_limit,
        "coordinate_precision_floor": precision_floor,
        "loop_count": len(loops),
        "loops": loops,
        "graph_diagnostics": {
            "component_count": len(components),
            "minimum_loop_points": minimum_loop_points,
            "max_loops": max_loops,
            "radius_neighbor_count": {
                "min": int(np.min(neighbor_counts)),
                "median": float(np.median(neighbor_counts)),
                "max": int(np.max(neighbor_counts)),
            },
            "trace_policy": "nearest-start then minimum-turn local continuation",
        },
        "assumptions": [
            "input points sample one or more closed boundary curves rather than a filled section",
            "max_edge_length is small enough not to connect nonadjacent branches or separate loops",
            "each loop is sampled densely enough that local turning continuity follows its boundary",
            "intersecting, touching, open, truncated, or ambiguous topology is rejected rather than repaired",
        ],
    }
