"""Read-only relationships between circular candidates, never hole certification.

All lengths use one global native coordinate frame. Clustering is deterministic
and bounded; no CAD snapping, raw-point retention, or scene mutations occur here.
"""
from __future__ import annotations

import math
from itertools import combinations
from numbers import Real
from typing import Any

import numpy as np

from .feature_fit import FeatureFitError

MAX_CANDIDATES = 32


def number(value: Any, name: str, *, minimum: float = 0, positive: bool = False,
           maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise FeatureFitError(f"{name} must be a finite number")
    result = float(value)
    if (not math.isfinite(result) or result < minimum or (positive and result <= 0)
            or (maximum is not None and result > maximum)):
        raise FeatureFitError(f"{name} is outside its finite allowed range")
    return result


def integer(value: Any, name: str, low: int, high: int) -> int:
    result = number(value, name, minimum=low, maximum=high)
    if not result.is_integer():
        raise FeatureFitError(f"{name} must be an integer")
    return int(result)


def vector(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise FeatureFitError(f"{name} must contain three finite numbers")
    return np.array([number(x, name, minimum=-math.inf) for x in value])


def unit(value: Any, name: str) -> np.ndarray:
    out = vector(value, name)
    scale = float(np.max(np.abs(out)))
    if scale == 0:
        raise FeatureFitError(f"{name} must be nonzero")
    out /= scale
    out /= np.linalg.norm(out)
    # Unoriented fitted normals: n and -n give the same deterministic frame.
    if out[int(np.argmax(np.abs(out)))] < 0:
        out = -out
    return out


def settings(args: dict) -> dict:
    """Validate analysis settings before requesting anything from the live host."""
    origin = vector(args["face_origin"], "face_origin")
    normal = unit(args["face_normal"], "face_normal")
    seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = seed - normal * np.dot(seed, normal)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    out = {key: number(args[key], key, positive=True) for key in (
        "plane_tolerance", "diameter_tolerance", "center_tolerance", "spacing_tolerance"
    )}
    out.update(
        normal_tolerance_degrees=number(args.get("normal_tolerance_degrees", 10),
                                        "normal_tolerance_degrees", maximum=90),
        min_support_count=integer(args.get("min_support_count", 12), "min_support_count", 4, 20000),
        min_support_fraction=number(args.get("min_support_fraction", 0.02),
                                    "min_support_fraction", maximum=1),
        min_coverage_degrees=number(args.get("min_coverage_degrees", 270),
                                    "min_coverage_degrees", maximum=360),
        max_fit_rms=(None if args.get("max_fit_rms") is None else
                     number(args["max_fit_rms"], "max_fit_rms", positive=True)),
        origin=origin, normal=normal, u=u, v=v,
    )
    return out


def _normal_angle(a: np.ndarray, b: np.ndarray) -> float:
    return math.degrees(math.atan2(math.hypot(*np.cross(a, b)), abs(float(np.dot(a, b)))))


def _layouts(group: list[dict], cfg: dict) -> list[dict]:
    """Check only the full diameter group, not combinatorial subsets or missing holes."""
    if len(group) < 3:
        return []
    xy = np.array([c["center_uv"] for c in group])
    # Center and scale first to keep SVD and circle equations well-conditioned.
    anchor = xy[0].copy()
    local = xy - anchor
    scale = float(np.max(np.abs(local)))
    if scale <= cfg["center_tolerance"]:
        return []
    q = local / scale
    mean = q.mean(axis=0)
    q -= mean
    _, singular, vt = np.linalg.svd(q, full_matrices=False)
    axis = vt[0]
    if axis[int(np.argmax(np.abs(axis)))] < 0:
        axis = -axis
    along = q @ axis * scale
    off = q @ np.array([-axis[1], axis[0]]) * scale
    order = sorted(range(len(group)), key=lambda i: (float(along[i]), group[i]["candidate_index"]))
    gaps = np.diff(along[order])
    tolerance = cfg["spacing_tolerance"]
    layouts = []
    # Distinct centers are required: coincident concentric circles aren't a row.
    if float(np.min(gaps)) > cfg["center_tolerance"]:
        pitch = float(np.mean(gaps))
        deviation = float(np.max(np.abs(gaps - pitch)))
        line_error = float(np.max(np.abs(off)))
        if line_error <= tolerance and deviation <= tolerance:
            layouts.append({
                "type": "equally_spaced_row_candidate",
                "candidate_indices": [group[i]["candidate_index"] for i in order],
                "pitch": pitch, "adjacent_spacings": gaps.tolist(),
                "max_spacing_deviation": deviation, "max_line_offset": line_error,
                "direction_global": (cfg["u"] * axis[0] + cfg["v"] * axis[1]).tolist(),
                "confirmed_holes": False,
            })
    # Three centers always define a circle; do not call that pattern evidence.
    if len(group) < 4 or singular[-1] <= singular[0] * 1e-8:
        return layouts
    design = np.column_stack([2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))])
    solution, _, rank, _ = np.linalg.lstsq(design, np.sum(q * q, axis=1), rcond=1e-10)
    if rank != 3:
        return layouts
    radial = q - solution[:2]
    distances = np.linalg.norm(radial, axis=1) * scale
    radius = float(np.mean(distances))
    if radius <= cfg["center_tolerance"]:
        return layouts
    residual = float(np.max(np.abs(distances - radius)))
    angles = np.mod(np.arctan2(radial[:, 1], radial[:, 0]), 2 * math.pi)
    angle_order = sorted(range(len(group)), key=lambda i: (float(angles[i]), group[i]["candidate_index"]))
    angular_gaps = np.diff(np.r_[angles[angle_order], angles[angle_order[0]] + 2 * math.pi])
    arc_errors = np.abs(angular_gaps - 2 * math.pi / len(group)) * radius
    if (residual <= tolerance and float(np.max(arc_errors)) <= tolerance
            and float(np.min(angular_gaps)) * radius > cfg["center_tolerance"]):
        center_uv = anchor + (mean + solution[:2]) * scale
        center = cfg["origin"] + cfg["u"] * center_uv[0] + cfg["v"] * center_uv[1]
        layouts.append({
            "type": "equally_spaced_bolt_circle_candidate",
            "candidate_indices": [group[i]["candidate_index"] for i in angle_order],
            "center_global": center.tolist(), "normal": cfg["normal"].tolist(),
            "pitch_circle_radius": radius, "pitch_circle_diameter": 2 * radius,
            "angular_gaps_degrees": np.degrees(angular_gaps).tolist(),
            "nominal_angular_spacing_degrees": 360 / len(group),
            "max_radial_error": residual, "max_arc_spacing_deviation": float(np.max(arc_errors)),
            "confirmed_holes": False,
        })
    return layouts


def _analyze(candidates: list[dict], cfg: dict) -> dict:
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise FeatureFitError(f"candidates must be a list of at most {MAX_CANDIDATES} items")
    ids: set[int] = set()
    accepted, rejected = [], []
    for raw in candidates:
        if not isinstance(raw, dict) or not isinstance(raw.get("circle"), dict):
            raise FeatureFitError("Each candidate requires a circle and final support diagnostics")
        index = integer(raw["candidate_index"], "candidate_index", 0, 2**31 - 1)
        if index in ids:
            raise FeatureFitError("candidate_index values must be unique")
        ids.add(index)
        circle = raw["circle"]
        center = vector(circle["center"], "circle.center")
        normal = unit(circle["normal"], "circle.normal")
        radius = number(circle["radius"], "circle.radius", positive=True)
        count = integer(raw["support_count"], "support_count", 4, 20000)
        fraction = number(raw["support_fraction_of_sample"], "support_fraction_of_sample", maximum=1)
        coverage = number(raw["support_angular_coverage_degrees"], "support_angular_coverage_degrees", maximum=360)
        rms = number(raw["orthogonal_residuals"]["rms"], "orthogonal_residuals.rms")
        delta = center - cfg["origin"]
        offset = float(np.dot(delta, cfg["normal"]))
        angle = _normal_angle(normal, cfg["normal"])
        # The entire tilted circle, not only its center, must fit the face slab.
        departure = abs(offset) + radius * math.sin(math.radians(angle))
        reasons = []
        if angle > cfg["normal_tolerance_degrees"]:
            reasons.append("normal_mismatch")
        if departure > cfg["plane_tolerance"]:
            reasons.append("outside_face_slab")
        if count < cfg["min_support_count"]:
            reasons.append("insufficient_support_count")
        if fraction < cfg["min_support_fraction"]:
            reasons.append("insufficient_support_fraction")
        if coverage < cfg["min_coverage_degrees"]:
            reasons.append("insufficient_angular_coverage")
        if cfg["max_fit_rms"] is not None and rms > cfg["max_fit_rms"]:
            reasons.append("excessive_fit_residual")
        if reasons:
            rejected.append({"candidate_index": index, "reasons": reasons})
            continue
        accepted.append({
            "candidate_index": index, "circle": {"center": center.tolist(),
                "normal": normal.tolist(), "radius": radius, "diameter": 2 * radius},
            "center_uv": [float(np.dot(delta, cfg["u"])), float(np.dot(delta, cfg["v"]))],
            "signed_face_offset": offset, "normal_angle_degrees": angle,
            "max_face_departure": departure, "support_count": count,
            "support_fraction_of_sample": fraction, "support_angular_coverage_degrees": coverage,
            "orthogonal_rms": rms, "confirmed_hole": False,
        })
    # Quality is used only to select duplicate representatives, never a hole probability.
    accepted.sort(key=lambda c: (-c["support_count"], c["orthogonal_rms"], c["candidate_index"]))
    clusters: list[list[dict]] = []
    for item in accepted:
        for cluster in clusters:
            if all(
                math.dist(item["circle"]["center"], member["circle"]["center"]) <= cfg["center_tolerance"]
                and abs(item["circle"]["diameter"] - member["circle"]["diameter"]) <= cfg["diameter_tolerance"]
                and _normal_angle(np.array(item["circle"]["normal"]), np.array(member["circle"]["normal"])) <= cfg["normal_tolerance_degrees"]
                for member in cluster
            ):
                cluster.append(item)
                break
        else:
            clusters.append([item])
    representatives = sorted((c[0] for c in clusters), key=lambda c: c["candidate_index"])
    duplicates = sorted([
        {"candidate_index": member["candidate_index"], "representative_index": cluster[0]["candidate_index"]}
        for cluster in clusters for member in cluster[1:]
    ], key=lambda c: c["candidate_index"])
    # Sorted complete-diameter-range groups cannot grow via transitive chaining.
    grouped: list[list[dict]] = []
    for item in sorted(representatives, key=lambda c: (c["circle"]["diameter"], c["candidate_index"])):
        if grouped and item["circle"]["diameter"] - grouped[-1][0]["circle"]["diameter"] <= cfg["diameter_tolerance"]:
            grouped[-1].append(item)
        else:
            grouped.append([item])
    pairs, concentric = [], []
    for a, b in combinations(representatives, 2):
        separation = math.dist(a["center_uv"], b["center_uv"])
        entry = {
            "candidate_indices": [a["candidate_index"], b["candidate_index"]],
            "center_distance_in_face": separation,
            "center_distance_3d": math.dist(a["circle"]["center"], b["circle"]["center"]),
            "signed_face_offset_difference": b["signed_face_offset"] - a["signed_face_offset"],
            "diameter_difference": abs(a["circle"]["diameter"] - b["circle"]["diameter"]),
        }
        pairs.append(entry)
        if separation <= cfg["center_tolerance"]:
            concentric.append(entry)
    groups = []
    for index, members in enumerate(grouped):
        ds = [c["circle"]["diameter"] for c in members]
        has_coincident_centers = any(math.dist(a["center_uv"], b["center_uv"]) <= cfg["center_tolerance"]
                                     for a, b in combinations(members, 2))
        groups.append({
            "group_index": index, "candidate_indices": sorted(c["candidate_index"] for c in members),
            "count": len(members), "diameter_min": min(ds), "diameter_max": max(ds),
            "layout_candidates": [] if has_coincident_centers else _layouts(members, cfg),
            "coincident_centers_block_layout": has_coincident_centers,
        })
    return {
        "type": "hole_candidate_relationships", "schema_revision": 1,
        "coordinate_space": "global", "units": "native", "units_confirmed": False,
        "read_only": True, "confirmed_holes": False, "image_required": False,
        "input_candidate_count": len(candidates), "candidate_count": len(representatives),
        "face": {"origin": cfg["origin"].tolist(), "normal": cfg["normal"].tolist(),
                 "basis_u": cfg["u"].tolist(), "basis_v": cfg["v"].tolist()},
        "tolerances": {key: value for key, value in cfg.items() if not isinstance(value, np.ndarray)},
        "candidates": representatives, "duplicates": duplicates,
        "rejected": sorted(rejected, key=lambda c: c["candidate_index"]),
        "diameter_groups": groups, "center_spacings": pairs, "concentric_candidates": concentric,
        "limitations": [
            "Circular support does not establish a physical hole, bore, boss, or mounting function.",
            "Only full diameter groups are checked for rows (at least 3) or bolt circles (at least 4); no missing-hole or subset inference.",
            "Tolerances are user-selected native-unit limits, not measurement uncertainty or manufacturing tolerances.",
            "Results are a snapshot; rerun discovery after scene changes before using existing overlays or CAD references.",
        ],
    }


def analyze_hole_candidates(candidates: list[dict], **kwargs) -> dict:
    """Filter, deduplicate and measure provided final-fit candidates without mutation."""
    import json
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = _analyze(candidates, settings(kwargs))
        # A successful result must be interoperable JSON, including derived geometry.
        json.dumps(result, allow_nan=False)
        return result
    except (KeyError, TypeError, ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError) as exc:
        if isinstance(exc, FeatureFitError):
            raise
        raise FeatureFitError(f"Invalid or numerically unrepresentable hole candidates: {exc}") from exc
