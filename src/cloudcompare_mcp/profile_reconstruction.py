"""Deterministic 2D CAD-profile reconstruction from section samples.

This module is intentionally CloudCompare-independent.  It consumes 2D section
coordinates in caller-established native units and returns compact candidate CAD
primitives.  It never assigns manufacturing intent or edits source geometry.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Sequence

import numpy as np


class ProfileError(ValueError):
    """Raised when a section profile cannot be reconstructed safely."""


MAX_PROFILE_POINTS = 4096
MAX_PROFILE_SEGMENTS = 128


def _points2d(points: Iterable[Sequence[float]], *, minimum: int = 2) -> np.ndarray:
    try:
        array = np.asarray(list(points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ProfileError("points_uv must be an array of 2D numeric points") from exc
    if array.ndim != 2 or array.shape[1:] != (2,):
        raise ProfileError("points_uv must be an array of [u, v] points")
    if array.shape[0] < minimum:
        raise ProfileError(f"points_uv requires at least {minimum} points")
    if array.shape[0] > MAX_PROFILE_POINTS:
        raise ProfileError(f"points_uv supports at most {MAX_PROFILE_POINTS} points")
    if not np.isfinite(array).all():
        raise ProfileError("points_uv coordinates must all be finite")
    if np.unique(array, axis=0).shape[0] < minimum:
        raise ProfileError(f"points_uv requires at least {minimum} distinct points")
    return array


def _vec2(value: np.ndarray | Sequence[float]) -> list[float]:
    a = np.asarray(value, dtype=np.float64)
    return [float(a[0]), float(a[1])]


def _stats(values: np.ndarray) -> dict[str, float | int]:
    values = np.abs(np.asarray(values, dtype=np.float64))
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ProfileError("Residual statistics require finite values")
    return {
        "count": int(values.size),
        "rms": float(np.sqrt(np.mean(np.square(values)))),
        "mean_abs": float(np.mean(values)),
        "median_abs": float(np.median(values)),
        "p95_abs": float(np.percentile(values, 95)),
        "max_abs": float(np.max(values)),
    }


def _canonical_direction_2d(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= np.finfo(np.float64).tiny:
        raise ProfileError("Direction has zero length")
    vector = vector / norm
    index = int(np.argmax(np.abs(vector)))
    if vector[index] < 0:
        vector = -vector
    return vector


def _input_fingerprint(points: np.ndarray) -> str:
    little = np.asarray(points, dtype="<f8")
    return hashlib.sha256(little.tobytes(order="C")).hexdigest()


def _precision_floor(points: np.ndarray) -> float:
    absolute = np.abs(points)
    spacing = np.abs(np.spacing(absolute))
    finite = spacing[np.isfinite(spacing)]
    floor = float(np.max(finite)) if finite.size else 0.0
    scale = max(float(np.max(np.abs(points))), float(np.ptp(points, axis=0).max()), 1.0)
    floor = max(floor, np.finfo(np.float64).eps * scale)
    return 8.0 * floor


def _order_points(
    points: np.ndarray,
    *,
    method: str,
    closed: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    n = points.shape[0]
    input_indices = np.arange(n, dtype=int)
    if method == "input":
        ordered = points.copy()
        order = input_indices
        assumptions: list[str] = ["caller supplied boundary traversal order"]
    elif method == "polar_closed_loop":
        if not closed:
            raise ProfileError("polar_closed_loop ordering requires closed=true")
        center = np.mean(points, axis=0)
        delta = points - center
        radii = np.linalg.norm(delta, axis=1)
        if float(np.max(radii)) <= np.finfo(np.float64).tiny:
            raise ProfileError("polar_closed_loop cannot order coincident points")
        angles = np.arctan2(delta[:, 1], delta[:, 0])
        order = np.lexsort((radii, angles))
        ordered = points[order]
        assumptions = [
            "single closed loop",
            "loop is star-shaped enough around the sample centroid for polar ordering",
        ]
    elif method == "principal_open":
        if closed:
            raise ProfileError("principal_open ordering requires closed=false")
        center = np.mean(points, axis=0)
        centered = points - center
        try:
            _, singular, vh = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError as exc:
            raise ProfileError("principal_open ordering SVD did not converge") from exc
        if not singular.size or float(singular[0]) <= np.finfo(np.float64).tiny:
            raise ProfileError("principal_open cannot order coincident points")
        direction = _canonical_direction_2d(vh[0])
        projection = centered @ direction
        secondary = centered @ np.array([-direction[1], direction[0]])
        order = np.lexsort((secondary, projection))
        ordered = points[order]
        assumptions = ["profile is single-valued enough along its principal axis for projection ordering"]
    else:
        raise ProfileError(f"Unknown ordering_method: {method}")

    # Remove an explicitly repeated terminal point for closed loops.  Closure is
    # represented implicitly and re-added internally after ordering/rotation.
    removed_terminal_duplicate = False
    if closed and ordered.shape[0] >= 3:
        scale = max(float(np.max(np.abs(ordered))), float(np.ptp(ordered, axis=0).max()), 1.0)
        numeric = np.finfo(np.float64).eps * scale * 64.0
        if float(np.linalg.norm(ordered[-1] - ordered[0])) <= numeric:
            ordered = ordered[:-1]
            order = order[:-1]
            removed_terminal_duplicate = True

    minimum_ordered = 3 if closed else 2
    if ordered.shape[0] < minimum_ordered:
        raise ProfileError("Profile has too few distinct ordered points")

    diagnostics: dict[str, Any] = {
        "method": method,
        "input_order_changed": bool(not np.array_equal(order, np.arange(order.size))),
        "assumptions": assumptions,
        "removed_terminal_duplicate": removed_terminal_duplicate,
    }
    if method == "polar_closed_loop":
        center = np.mean(ordered, axis=0)
        radii = np.linalg.norm(ordered - center, axis=1)
        diagnostics["ordering_center_uv"] = _vec2(center)
        diagnostics["radial_range"] = [float(np.min(radii)), float(np.max(radii))]
    return ordered, order, diagnostics


def _fit_line(points: np.ndarray) -> dict[str, Any]:
    center = np.mean(points, axis=0)
    centered = points - center
    try:
        _, singular, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise ProfileError("Line fitting SVD did not converge") from exc
    if not singular.size or float(singular[0]) <= np.finfo(np.float64).tiny:
        raise ProfileError("Line fitting points are coincident")
    direction = np.asarray(vh[0], dtype=np.float64)
    endpoint_delta = points[-1] - points[0]
    if float(np.linalg.norm(endpoint_delta)) > np.finfo(np.float64).tiny:
        if float(np.dot(direction, endpoint_delta)) < 0:
            direction = -direction
    else:
        direction = _canonical_direction_2d(direction)
    direction /= np.linalg.norm(direction)
    normal = np.array([-direction[1], direction[0]])
    signed = centered @ normal
    along = centered @ direction
    first_t = float(np.dot(points[0] - center, direction))
    last_t = float(np.dot(points[-1] - center, direction))
    start = center + first_t * direction
    end = center + last_t * direction
    residual_abs = np.abs(signed)
    return {
        "kind": "line",
        "centroid": center,
        "direction": direction,
        "start": start,
        "end": end,
        "length": float(np.linalg.norm(end - start)),
        "residual": residual_abs,
        "max_index": int(np.argmax(residual_abs)),
        "stats": _stats(residual_abs),
        "span": [float(np.min(along)), float(np.max(along))],
    }


def _fit_circle_raw(points: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
    center0 = np.mean(points, axis=0)
    centered = points - center0
    scale = float(np.max(np.linalg.norm(centered, axis=1)))
    if not math.isfinite(scale) or scale <= np.finfo(np.float64).tiny:
        raise ProfileError("Circle fitting points have no radial extent")
    xy = centered / scale
    design = np.column_stack((2.0 * xy[:, 0], 2.0 * xy[:, 1], np.ones(xy.shape[0])))
    rhs = np.sum(np.square(xy), axis=1)
    try:
        solution, _, rank, _ = np.linalg.lstsq(design, rhs, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise ProfileError("Circle fitting least-squares solve did not converge") from exc
    if rank < 3:
        raise ProfileError("Circle fitting points are degenerate")
    local_center = solution[:2]
    radius2 = float(solution[2] + np.dot(local_center, local_center))
    if not math.isfinite(radius2) or radius2 <= 0:
        raise ProfileError("Circle fitting produced an invalid radius")
    center = center0 + local_center * scale
    radius = math.sqrt(radius2) * scale

    params = np.array([center[0], center[1], radius], dtype=np.float64)
    for _ in range(30):
        delta = points - params[:2]
        distances = np.linalg.norm(delta, axis=1)
        if np.any(distances <= np.finfo(np.float64).tiny):
            break
        residual = distances - params[2]
        jac = np.column_stack((-delta[:, 0] / distances, -delta[:, 1] / distances, -np.ones(points.shape[0])))
        try:
            step, *_ = np.linalg.lstsq(jac, -residual, rcond=None)
        except np.linalg.LinAlgError as exc:
            raise ProfileError("Circle refinement did not converge") from exc
        params += step
        if not np.isfinite(params).all() or params[2] <= 0:
            raise ProfileError("Circle refinement produced invalid parameters")
        if float(np.linalg.norm(step)) <= 1e-12 * max(float(np.linalg.norm(params)), 1.0):
            break
    center = params[:2]
    radius = float(params[2])
    radial = np.linalg.norm(points - center, axis=1) - radius
    return center, radius, radial


def _circle_coverage(points: np.ndarray, center: np.ndarray) -> float:
    angles = np.mod(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]), 2 * math.pi)
    angles.sort()
    wrapped = np.concatenate((angles, [angles[0] + 2 * math.pi]))
    gap = float(np.max(np.diff(wrapped)))
    return float(math.degrees(2 * math.pi - gap))


def _fit_arc(points: np.ndarray) -> dict[str, Any] | None:
    if points.shape[0] < 5:
        return None
    try:
        center, radius, residual = _fit_circle_raw(points)
    except ProfileError:
        return None
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    unwrapped = np.unwrap(angles)
    diffs = np.diff(unwrapped)
    if diffs.size == 0:
        return None
    sweep = float(unwrapped[-1] - unwrapped[0])
    travel = float(np.sum(np.abs(diffs)))
    consistency = abs(sweep) / travel if travel > np.finfo(np.float64).tiny else 0.0
    sign = 1.0 if sweep >= 0 else -1.0
    start_angle = float(unwrapped[0])
    end_angle = float(unwrapped[-1])
    start = center + radius * np.array([math.cos(start_angle), math.sin(start_angle)])
    end = center + radius * np.array([math.cos(end_angle), math.sin(end_angle)])
    radial_abs = np.abs(residual)
    return {
        "kind": "arc",
        "center": center,
        "radius": radius,
        "start": start,
        "end": end,
        "sweep_radians": sweep,
        "sweep_degrees": float(math.degrees(sweep)),
        "turn_sign": int(sign),
        "progress_consistency": float(consistency),
        "arc_length": abs(sweep) * radius,
        "residual": radial_abs,
        "max_index": int(np.argmax(radial_abs)),
        "stats": _stats(radial_abs),
    }


def _accepted_candidate(points: np.ndarray, *, tolerance: float, min_arc_degrees: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    line = _fit_line(points)
    arc = _fit_arc(points)
    line_ok = float(line["stats"]["max_abs"]) <= tolerance
    arc_ok = False
    if arc is not None:
        sweep = abs(float(arc["sweep_degrees"]))
        arc_ok = (
            float(arc["stats"]["max_abs"]) <= tolerance
            and min_arc_degrees <= sweep <= 355.0
            and float(arc["progress_consistency"]) >= 0.8
        )

    selected: dict[str, Any] | None = None
    if line_ok and arc_ok:
        sweep = abs(float(arc["sweep_degrees"])) if arc is not None else 0.0
        line_rms = float(line["stats"]["rms"])
        arc_rms = float(arc["stats"]["rms"])
        # Prefer a line for shallow curvature or when the extra arc parameter
        # does not materially improve the fit.
        if sweep < max(20.0, min_arc_degrees * 1.5) or line_rms <= max(arc_rms * 1.35, tolerance * 0.05):
            selected = line
        else:
            selected = arc
    elif line_ok:
        selected = line
    elif arc_ok:
        selected = arc

    # Split guidance when the span is not yet representable.  The lower score is
    # used only to select a residual peak; it never promotes an out-of-tolerance fit.
    choices: list[tuple[float, dict[str, Any]]] = []
    line_score = float(line["stats"]["max_abs"]) / tolerance
    choices.append((line_score, line))
    if arc is not None and float(arc["progress_consistency"]) >= 0.55:
        arc_score = float(arc["stats"]["max_abs"]) / tolerance + 0.12
        choices.append((arc_score, arc))
    preferred = min(choices, key=lambda pair: pair[0])[1]
    return selected, preferred


def _rotation_break(points: np.ndarray) -> int:
    n = points.shape[0]
    if n < 5:
        return 0
    turns = np.zeros(n, dtype=np.float64)
    for i in range(n):
        a = points[i] - points[(i - 1) % n]
        b = points[(i + 1) % n] - points[i]
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        if na <= np.finfo(np.float64).tiny or nb <= np.finfo(np.float64).tiny:
            continue
        cosine = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
        turns[i] = math.acos(cosine)
    change = np.abs(turns - np.roll(turns, 1))
    index = int(np.argmax(change))
    previous = (index - 1) % n
    # The larger-turn endpoint is the actual shared boundary sample.  At a
    # polygon corner it is the corner itself; at a tangent line/arc transition
    # it carries roughly half the neighboring arc turn while the first interior
    # line sample carries zero turn.  Cutting at the smaller-turn sample splits
    # one real primitive across the cyclic start/end and creates a tiny sliver.
    return index if turns[index] >= turns[previous] else previous


def _serialize_primitive(model: dict[str, Any], *, start_index: int, end_index: int, source_order: np.ndarray) -> dict[str, Any]:
    first_source = int(source_order[start_index % source_order.size])
    last_source = int(source_order[end_index % source_order.size])
    common = {
        "type": model["kind"],
        "state": "inferred_candidate",
        "ordered_index_range": [int(start_index), int(end_index)],
        "source_count": int(end_index - start_index + 1),
        "source_endpoint_input_indices": [first_source, last_source],
        "fit_residuals": model["stats"],
        "start_uv": _vec2(model["start"]),
        "end_uv": _vec2(model["end"]),
    }
    if model["kind"] == "line":
        common.update({
            "direction": _vec2(model["direction"]),
            "length": float(model["length"]),
        })
    else:
        common.update({
            "center_uv": _vec2(model["center"]),
            "radius": float(model["radius"]),
            "sweep_degrees": float(model["sweep_degrees"]),
            "turn_sign": int(model["turn_sign"]),
            "arc_length": float(model["arc_length"]),
            "progress_consistency": float(model["progress_consistency"]),
        })
    return common


def _segment(points: np.ndarray, source_order: np.ndarray, *, tolerance: float, min_arc_degrees: float, max_segments: int) -> list[dict[str, Any]]:
    primitives: list[dict[str, Any]] = []

    def recurse(start: int, end: int) -> None:
        if len(primitives) >= max_segments:
            raise ProfileError("Profile requires more than max_segments primitives at the requested tolerance")
        span = points[start : end + 1]
        accepted, split_model = _accepted_candidate(span, tolerance=tolerance, min_arc_degrees=min_arc_degrees)
        if accepted is not None:
            accepted = dict(accepted)
            accepted["_start"] = start
            accepted["_end"] = end
            primitives.append(accepted)
            return
        if end - start <= 1:
            # Two distinct points are always exactly representable by a line;
            # reaching this path would indicate numerical failure.
            raise ProfileError("Could not represent a two-point profile span as a line")
        local = int(split_model["max_index"])
        split = start + local
        if split <= start or split >= end:
            split = (start + end) // 2
        recurse(start, split)
        recurse(split, end)

    recurse(0, points.shape[0] - 1)

    # Deterministically merge adjacent primitives when the combined span remains
    # within tolerance.  This reduces recursive over-segmentation without hiding
    # residuals or using heuristic semantic templates.
    changed = True
    while changed:
        changed = False
        merged: list[dict[str, Any]] = []
        i = 0
        while i < len(primitives):
            if i + 1 < len(primitives):
                a, b = primitives[i], primitives[i + 1]
                same_kind = a["kind"] == b["kind"]
                a_count = int(a["_end"] - a["_start"] + 1)
                b_count = int(b["_end"] - b["_start"] + 1)
                tiny_boundary_fragment = min(a_count, b_count) <= 2
                if same_kind or tiny_boundary_fragment:
                    span = points[a["_start"] : b["_end"] + 1]
                    candidate, _ = _accepted_candidate(
                        span,
                        tolerance=tolerance,
                        min_arc_degrees=min_arc_degrees,
                    )
                    if candidate is not None and (
                        same_kind or candidate["kind"] in {a["kind"], b["kind"]}
                    ):
                        candidate = dict(candidate)
                        candidate["_start"] = a["_start"]
                        candidate["_end"] = b["_end"]
                        merged.append(candidate)
                        i += 2
                        changed = True
                        continue
            merged.append(primitives[i])
            i += 1
        primitives = merged
    if len(primitives) > max_segments:
        raise ProfileError("Profile requires more than max_segments primitives at the requested tolerance")
    return primitives


def _path_tangent(primitive: dict[str, Any], *, at_end: bool) -> np.ndarray:
    if primitive["type"] == "line":
        direction = np.asarray(primitive["end_uv"], dtype=np.float64) - np.asarray(primitive["start_uv"], dtype=np.float64)
        norm = float(np.linalg.norm(direction))
        if norm <= np.finfo(np.float64).tiny:
            return np.asarray(primitive["direction"], dtype=np.float64)
        return direction / norm
    center = np.asarray(primitive["center_uv"], dtype=np.float64)
    point = np.asarray(primitive["end_uv" if at_end else "start_uv"], dtype=np.float64)
    radial = point - center
    radial /= np.linalg.norm(radial)
    sign = 1.0 if float(primitive["sweep_degrees"]) >= 0 else -1.0
    tangent = sign * np.array([-radial[1], radial[0]])
    return tangent / np.linalg.norm(tangent)


def _relationships(primitives: list[dict[str, Any]], *, closed: bool, tolerance: float, angular_tolerance: float) -> list[dict[str, Any]]:
    if len(primitives) < 2:
        return []
    pairs = [(i, i + 1) for i in range(len(primitives) - 1)]
    if closed:
        pairs.append((len(primitives) - 1, 0))
    output: list[dict[str, Any]] = []
    for a_index, b_index in pairs:
        a, b = primitives[a_index], primitives[b_index]
        a_end = np.asarray(a["end_uv"], dtype=np.float64)
        b_start = np.asarray(b["start_uv"], dtype=np.float64)
        gap = float(np.linalg.norm(b_start - a_end))
        ta = _path_tangent(a, at_end=True)
        tb = _path_tangent(b, at_end=False)
        cosine = float(np.clip(np.dot(ta, tb), -1.0, 1.0))
        tangent_deviation = float(math.degrees(math.acos(cosine)))
        relation: dict[str, Any] = {
            "a": a_index,
            "b": b_index,
            "endpoint_gap": gap,
            "coincident_endpoint_candidate": bool(gap <= tolerance),
            "tangent_deviation_degrees": tangent_deviation,
            "tangent_candidate": bool(gap <= tolerance and tangent_deviation <= angular_tolerance),
            "state": "inferred_candidate",
        }
        if a["type"] == b["type"] == "line":
            da = np.asarray(a["direction"], dtype=np.float64)
            db = np.asarray(b["direction"], dtype=np.float64)
            acute = float(math.degrees(math.acos(float(np.clip(abs(np.dot(da, db)), 0.0, 1.0)))))
            relation["acute_line_angle_degrees"] = acute
            relation["parallel_candidate"] = bool(acute <= angular_tolerance)
            relation["perpendicular_candidate"] = bool(abs(90.0 - acute) <= angular_tolerance)
        output.append(relation)
    return output


def _angle_between_unsigned(a: Sequence[float], b: Sequence[float]) -> float:
    aa = np.asarray(a, dtype=np.float64); bb = np.asarray(b, dtype=np.float64)
    aa /= np.linalg.norm(aa); bb /= np.linalg.norm(bb)
    return float(math.degrees(math.acos(float(np.clip(abs(np.dot(aa, bb)), 0.0, 1.0)))))


def _classify_profile(primitives: list[dict[str, Any]], relationships: list[dict[str, Any]], *, closed: bool, tolerance: float, angular_tolerance: float) -> list[dict[str, Any]]:
    if not closed:
        return []
    if len(primitives) == 1 and primitives[0]["type"] == "circle":
        p = primitives[0]
        return [{
            "type": "circle_profile_candidate",
            "state": "inferred_candidate",
            "center_uv": p["center_uv"],
            "radius": p["radius"],
            "diameter": 2.0 * float(p["radius"]),
        }]
    if len(primitives) != 4:
        return []

    types = [p["type"] for p in primitives]
    candidates: list[dict[str, Any]] = []
    if all(t == "line" for t in types):
        dirs = [p["direction"] for p in primitives]
        opposite = [_angle_between_unsigned(dirs[0], dirs[2]), _angle_between_unsigned(dirs[1], dirs[3])]
        adjacent = [_angle_between_unsigned(dirs[i], dirs[(i + 1) % 4]) for i in range(4)]
        if max(opposite) <= angular_tolerance and max(abs(90.0 - a) for a in adjacent) <= angular_tolerance:
            pair_a = (float(primitives[0]["length"]) + float(primitives[2]["length"])) / 2.0
            pair_b = (float(primitives[1]["length"]) + float(primitives[3]["length"])) / 2.0
            corners = np.asarray([p["start_uv"] for p in primitives], dtype=np.float64)
            candidates.append({
                "type": "rectangle_candidate",
                "state": "inferred_candidate",
                "center_uv": _vec2(np.mean(corners, axis=0)),
                "side_pair_lengths": [pair_a, pair_b],
                "opposite_parallel_error_degrees": opposite,
                "adjacent_perpendicular_error_degrees": [abs(90.0 - a) for a in adjacent],
            })

    if types.count("line") == 2 and types.count("arc") == 2 and all(types[i] != types[(i + 1) % 4] for i in range(4)):
        line_ids = [i for i,t in enumerate(types) if t == "line"]
        arc_ids = [i for i,t in enumerate(types) if t == "arc"]
        lines = [primitives[i] for i in line_ids]
        arcs = [primitives[i] for i in arc_ids]
        line_angle = _angle_between_unsigned(lines[0]["direction"], lines[1]["direction"])
        avg_radius = (float(arcs[0]["radius"]) + float(arcs[1]["radius"])) / 2.0
        radius_delta = abs(float(arcs[0]["radius"]) - float(arcs[1]["radius"]))
        sweep_error = [abs(180.0 - abs(float(a["sweep_degrees"]))) for a in arcs]
        length_delta = abs(float(lines[0]["length"]) - float(lines[1]["length"]))
        centers = np.asarray([a["center_uv"] for a in arcs], dtype=np.float64)
        centerline = centers[1] - centers[0]
        centerline_length = float(np.linalg.norm(centerline))
        centerline_angle = 0.0 if centerline_length <= np.finfo(np.float64).tiny else _angle_between_unsigned(centerline, lines[0]["direction"])
        radius_limit = max(2.0 * tolerance, avg_radius * 0.002)
        length_limit = max(2.0 * tolerance, max(float(lines[0]["length"]), float(lines[1]["length"])) * 0.01)
        sweep_limit = max(5.0, angular_tolerance * 5.0)
        tangent_ok = all(bool(r.get("tangent_candidate")) for r in relationships)
        if (
            line_angle <= angular_tolerance
            and radius_delta <= radius_limit
            and max(sweep_error) <= sweep_limit
            and length_delta <= length_limit
            and centerline_angle <= angular_tolerance
            and tangent_ok
        ):
            candidates.append({
                "type": "slot_candidate",
                "state": "inferred_candidate",
                "center_uv": _vec2(np.mean(centers, axis=0)),
                "radius": avg_radius,
                "width": 2.0 * avg_radius,
                "centerline_length": centerline_length,
                "overall_length": centerline_length + 2.0 * avg_radius,
                "axis_direction": _vec2(_canonical_direction_2d(np.asarray(lines[0]["direction"], dtype=np.float64))),
                "line_parallel_error_degrees": line_angle,
                "arc_radius_difference": radius_delta,
                "arc_semicircle_error_degrees": sweep_error,
            })
    return candidates


def reconstruct_profile_2d(
    points_uv: Iterable[Sequence[float]],
    *,
    closed: bool,
    fit_tolerance: float,
    angular_tolerance_degrees: float = 1.0,
    ordering_method: str = "input",
    minimum_arc_angle_degrees: float = 12.0,
    max_segments: int = 64,
) -> dict[str, Any]:
    """Reconstruct an ordered 2D section as compact line/arc/circle candidates.

    ``fit_tolerance`` is a caller-selected native-unit numerical fit threshold, not
    calibrated measurement uncertainty.  ``ordering_method`` is explicit because
    profile topology cannot safely be inferred from arbitrary point order without
    assumptions.
    """
    if not isinstance(closed, bool):
        raise ProfileError("closed must be a boolean")
    try:
        tolerance = float(fit_tolerance)
        angular_tolerance = float(angular_tolerance_degrees)
        min_arc = float(minimum_arc_angle_degrees)
    except (TypeError, ValueError) as exc:
        raise ProfileError("Profile tolerances must be numeric") from exc
    if isinstance(fit_tolerance, bool) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ProfileError("fit_tolerance must be finite and positive")
    if not math.isfinite(angular_tolerance) or angular_tolerance < 0 or angular_tolerance > 45:
        raise ProfileError("angular_tolerance_degrees must be finite and between 0 and 45")
    if not math.isfinite(min_arc) or min_arc < 1 or min_arc > 180:
        raise ProfileError("minimum_arc_angle_degrees must be between 1 and 180")
    if isinstance(max_segments, bool) or not isinstance(max_segments, int) or not 1 <= max_segments <= MAX_PROFILE_SEGMENTS:
        raise ProfileError(f"max_segments must be an integer between 1 and {MAX_PROFILE_SEGMENTS}")

    raw = _points2d(points_uv, minimum=3 if closed else 2)
    precision_floor = _precision_floor(raw)
    if tolerance < precision_floor:
        raise ProfileError(
            f"fit_tolerance {tolerance:.17g} is below the representable coordinate precision floor {precision_floor:.17g}"
        )
    fingerprint = _input_fingerprint(raw)
    ordered, source_order, ordering = _order_points(raw, method=ordering_method, closed=closed)

    warnings: list[str] = []
    if ordering_method == "polar_closed_loop":
        warnings.append(
            "Polar ordering assumes one star-shaped closed boundary; inspect residuals/candidates before treating topology as accepted."
        )
    if ordering_method == "principal_open":
        warnings.append(
            "Principal-axis ordering assumes an open profile that is single-valued enough along its dominant direction."
        )

    serialized: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    if closed:
        # A complete circle is handled before selecting a cyclic break point.
        circle_center = None
        try:
            center, radius, radial = _fit_circle_raw(ordered)
            coverage = _circle_coverage(ordered, center)
            if float(np.max(np.abs(radial))) <= tolerance and coverage >= 300.0:
                circle_center = center
                serialized = [{
                    "type": "circle",
                    "state": "inferred_candidate",
                    "source_count": int(ordered.shape[0]),
                    "center_uv": _vec2(center),
                    "radius": float(radius),
                    "diameter": float(2.0 * radius),
                    "angular_coverage_degrees": coverage,
                    "fit_residuals": _stats(radial),
                }]
            else:
                circle_center = None
        except ProfileError:
            circle_center = None

        if circle_center is None:
            break_index = _rotation_break(ordered)
            ordered = np.concatenate((ordered[break_index:], ordered[:break_index]), axis=0)
            source_order = np.concatenate((source_order[break_index:], source_order[:break_index]), axis=0)
            ordering["cyclic_break_ordered_index"] = int(break_index)
            work = np.vstack((ordered, ordered[0]))
            work_sources = np.concatenate((source_order, source_order[:1]))
            models = _segment(
                work,
                work_sources,
                tolerance=tolerance,
                min_arc_degrees=min_arc,
                max_segments=max_segments,
            )
            serialized = [
                _serialize_primitive(
                    model,
                    start_index=int(model["_start"]),
                    end_index=int(model["_end"]),
                    source_order=work_sources,
                )
                for model in models
            ]
        relationships = _relationships(
            serialized,
            closed=True,
            tolerance=tolerance,
            angular_tolerance=angular_tolerance,
        )
    else:
        models = _segment(
            ordered,
            source_order,
            tolerance=tolerance,
            min_arc_degrees=min_arc,
            max_segments=max_segments,
        )
        serialized = [
            _serialize_primitive(
                model,
                start_index=int(model["_start"]),
                end_index=int(model["_end"]),
                source_order=source_order,
            )
            for model in models
        ]
        relationships = _relationships(
            serialized,
            closed=False,
            tolerance=tolerance,
            angular_tolerance=angular_tolerance,
        )

    max_residual = max(float(p["fit_residuals"]["max_abs"]) for p in serialized)
    primitive_length = 0.0
    for p in serialized:
        if p["type"] == "line":
            primitive_length += float(p["length"])
        elif p["type"] == "arc":
            primitive_length += float(p["arc_length"])
        elif p["type"] == "circle":
            primitive_length += 2.0 * math.pi * float(p["radius"])

    profile_candidates = _classify_profile(
        serialized,
        relationships,
        closed=closed,
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )
    if len(serialized) == max_segments:
        warnings.append("Primitive count reached max_segments; consider whether the requested fit tolerance is too tight.")

    return {
        "type": "cad_section_profile",
        "version": "0.15.0",
        "coordinate_space": "section_uv",
        "units": "native",
        "state": "inferred_candidate",
        "manufacturing_intent_confirmed": False,
        "user_accepted": False,
        "closed": closed,
        "input_point_count": int(raw.shape[0]),
        "input_points_sha256_float64_le": fingerprint,
        "raw_points_returned": False,
        "fit_tolerance": tolerance,
        "coordinate_precision_floor": precision_floor,
        "angular_tolerance_degrees": angular_tolerance,
        "minimum_arc_angle_degrees": min_arc,
        "ordering": ordering,
        "primitive_count": len(serialized),
        "primitives": serialized,
        "relationships": relationships,
        "profile_candidates": profile_candidates,
        "summary": {
            "max_primitive_fit_residual": max_residual,
            "estimated_perimeter_or_path_length": primitive_length,
            "all_primitives_within_fit_tolerance": bool(max_residual <= tolerance),
            "closed_loop_relationship_count": len(relationships) if closed else 0,
        },
        "quality_warnings": warnings,
    }
