"""Bounded, read-only relationships and CAD datums from global fit snapshots.

No bridge, scene state, unit conversion, CAD kernel, or acceptance store lives here.
Distances use anchor differences, never subtract large plane-equation constants.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
import itertools
import json
import math
from typing import Any

import numpy as np

MAX_FEATURES = 16
PARALLEL_SINE = float(64 * np.finfo(float).eps)
INTERSECTION_SINE = 1e-8  # Refuse point constructions with amplification > 1e8.


class DatumError(ValueError):
    """Invalid, ambiguous, or numerically unresolved supplied geometry."""


def _numeric_guard(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                return function(*args, **kwargs)
        except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            raise DatumError("Geometry is numerically unresolved or arithmetic overflowed") from exc
    return guarded


def _check_constructed_point(point: np.ndarray, tolerance: float) -> None:
    if not np.all(np.isfinite(point)) or tolerance < 8 * max(math.ulp(float(x)) for x in point):
        raise DatumError("Constructed point cannot resolve distance_tolerance in global coordinates")


def _json(value: Any, label: str, limit: int) -> str:
    try:
        text = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise DatumError(f"{label} must be finite JSON") from exc
    if len(text.encode("utf-8")) > limit:
        raise DatumError(f"{label} exceeds {limit} bytes; supply bounded fit evidence, not point arrays")
    return text


def _number(value: Any, label: str, low: float, high: float, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DatumError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise DatumError(f"{label} must be a finite number") from exc
    if not math.isfinite(number) or not low <= number <= high or (positive and number <= 0):
        raise DatumError(f"{label} is outside its permitted range")
    return number


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise DatumError(f"{label} must be a nonempty string of at most 128 characters")
    return value


def _vector(value: Any, label: str) -> np.ndarray:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise DatumError(f"{label} must contain exactly three finite numbers")
    return np.array([_number(v, label, -float('inf'), float('inf')) for v in value])


def _norm(v: np.ndarray) -> float:
    return math.hypot(*v)


def _unit(v: np.ndarray, label: str) -> tuple[np.ndarray, float]:
    scale = float(np.max(np.abs(v)))
    if scale == 0:
        raise DatumError(f"{label} cannot be a zero vector")
    scaled = v / scale
    length = _norm(scaled)
    original_length = scale * length
    if not math.isfinite(original_length):
        raise DatumError(f"{label} magnitude overflows")
    return scaled / length, original_length


def _orient(v: np.ndarray, hint: np.ndarray | None = None) -> np.ndarray:
    if hint is None:
        sign = float(v[int(np.argmax(np.abs(v)))])
    else:
        sign = float(np.dot(v, hint))
        if abs(sign) <= INTERSECTION_SINE:
            raise DatumError("Direction hint is perpendicular to the constructed axis; sign is ambiguous")
    return v if sign >= 0 else -v


def _within(value: float, tolerance: float) -> bool:
    # Inclusive comparison with only eight representable boundary steps, not a
    # hidden physical tolerance or a blanket epsilon in native units.
    boundary = tolerance
    for _ in range(8):
        boundary = math.nextafter(boundary, math.inf)
    return value <= boundary


def _angles(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    sine = _norm(np.cross(a, b))
    cosine = abs(float(np.dot(a, b)))
    return math.degrees(math.atan2(sine, cosine)), math.degrees(math.atan2(cosine, sine)), sine


def _off_axis(delta: np.ndarray, direction: np.ndarray) -> float:
    return _norm(np.cross(delta, direction))


def _feature(record: dict, frame_id: str) -> dict:
    if not isinstance(record, dict) or set(record) - {"id", "observation", "provenance"}:
        raise DatumError("Each feature requires id, observation, and optional provenance only")
    fid = _name(record.get("id"), "feature id")
    observation = record.get("observation")
    if not isinstance(observation, dict):
        raise DatumError(f"{fid}: observation must be a fit snapshot object")
    encoded = _json(observation, f"{fid} observation", 65536)
    if observation.get("coordinate_space") != "global" or observation.get("units") != "native":
        raise DatumError(f"{fid}: observation must explicitly use global coordinates and native units")
    if "frame_id" in observation and observation["frame_id"] != frame_id:
        raise DatumError(f"{fid}: observation frame_id differs from the asserted common frame")
    if "points" in observation:
        raise DatumError(f"{fid}: supply fitted geometry, not point arrays")
    provenance = record.get("provenance", {})
    if not isinstance(provenance, dict):
        raise DatumError(f"{fid}: provenance must be an object")
    _json(provenance, f"{fid} provenance", 4096)
    cloud = observation.get("source_cloud_id")
    if cloud is not None and (isinstance(cloud, bool) or not isinstance(cloud, int) or cloud <= 0):
        raise DatumError(f"{fid}: source_cloud_id must be a positive integer")
    picks = observation.get("source_picks", [])
    if not isinstance(picks, list) or any(not isinstance(p, dict) for p in picks):
        raise DatumError(f"{fid}: source_picks must be a list of records")
    for pick in picks:
        value = pick.get("entity_id")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DatumError(f"{fid}: every source pick requires a positive integer entity_id")
    for data in (observation, provenance):
        if "global_shift" in data:
            _vector(data["global_shift"], f"{fid}.global_shift")
        if "global_scale" in data:
            _number(data["global_scale"], f"{fid}.global_scale", 0, np.finfo(float).max, positive=True)
    if cloud is None and not picks and not provenance:
        raise DatumError(f"{fid}: provide source_cloud_id, source_picks, or explicit provenance")
    kind = observation.get("type")
    keys = {"plane": ("centroid", "normal"), "line": ("centroid", "direction"),
            "circle": ("center", "normal"), "cylinder": ("axis_point", "axis_direction"),
            "point": ("position_global", None)}
    if not isinstance(kind, str) or kind not in keys:
        raise DatumError(f"{fid}: supported types are plane, line, circle, cylinder, point")
    point_key, direction_key = keys[kind]
    point = _vector(observation.get(point_key), f"{fid}.{point_key}")
    direction, magnitude = None, None
    if direction_key:
        direction, magnitude = _unit(_vector(observation.get(direction_key), f"{fid}.{direction_key}"), fid)
        direction = _orient(direction)
    radius = None
    if kind in ("circle", "cylinder"):
        radius = _number(observation.get("radius"), f"{fid}.radius", 0, np.finfo(float).max / 2, positive=True)
        if "diameter" in observation:
            diameter = _number(observation["diameter"], f"{fid}.diameter", 0, np.finfo(float).max, positive=True)
            if not math.isclose(diameter, radius * 2, rel_tol=1e-12, abs_tol=0):
                raise DatumError(f"{fid}: diameter and radius disagree")
    metadata_keys = ("source_cloud_id", "sample_count", "region", "region_coordinate_space",
                     "region_match_count", "region_sample_count", "region_sample_truncated",
                     "region_sample_strategy", "sampling_warning", "global_shift", "global_scale")
    metadata = {k: deepcopy(observation[k]) for k in metadata_keys if k in observation}
    _json(metadata, f"{fid} source metadata", 8192)
    quality = {k: deepcopy(observation[k]) for k in ("residuals", "radial_residuals", "quality_warnings",
               "arc_coverage_degrees", "angular_coverage_degrees") if k in observation}
    _json(quality, f"{fid} fit quality", 8192)
    # Pick positions remain in the upstream snapshot; retain an exact fingerprint
    # and bounded source identities instead of echoing point arrays to the model.
    source_ids = sorted({p["entity_id"] for p in picks})
    if len(source_ids) > 64:
        raise DatumError(f"{fid}: too many distinct pick entities")
    evidence = {"id": fid, "type": kind, "evidence_state": "supplied_geometry",
                "supplied_interpretation_state": deepcopy(observation.get("state", "unspecified")),
                "measurement_independently_verified": False,
                "reference_point_global": point.tolist(), "reference_point_semantics": point_key,
                "direction": None if direction is None else direction.tolist(),
                "direction_input_magnitude": magnitude, "radius": radius,
                "snapshot_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                "source_metadata": metadata, "source_pick_count": len(picks),
                "source_pick_entity_ids": source_ids, "provenance": deepcopy(provenance),
                "fit_quality_supplied": quality}
    return dict(id=fid, kind=kind, point=point, direction=direction, radius=radius, evidence=evidence)


def _prepare(features, frame_id, distance_tolerance) -> tuple[list[dict], dict]:
    frame_id = _name(frame_id, "frame_id")
    tolerance = _number(distance_tolerance, "distance_tolerance", 0, np.finfo(float).max, positive=True)
    if not isinstance(features, list) or not 1 <= len(features) <= MAX_FEATURES:
        raise DatumError(f"features must contain 1 to {MAX_FEATURES} observations")
    parsed = [_feature(record, frame_id) for record in features]
    if len({p["id"] for p in parsed}) != len(parsed):
        raise DatumError("Duplicate feature IDs are not allowed")
    parsed.sort(key=lambda p: p["id"])
    resolution = max(math.ulp(float(v)) for p in parsed for v in p["point"])
    if tolerance < 8 * resolution:
        raise DatumError("distance_tolerance is below eight ULPs of the supplied global coordinates")
    common = {"schema_version": "0.14.0", "coordinate_space": "global", "units": "native",
              "units_confirmed": False, "frame_id": frame_id,
              "common_frame_asserted_by_caller": True, "frame_alignment_verified": False,
              "coordinate_resolution_estimate": resolution, "distance_tolerance": tolerance,
              "live_connection_used": False, "scene_freshness_guaranteed": False,
              "scene_mutations_requested": False, "source_geometry_preserved": True,
              "manufacturing_intent_confirmed": False, "user_accepted": False,
              "observations": [p["evidence"] for p in parsed]}
    return parsed, common


def _finish(result: dict) -> dict:
    _json(result, "computed result", 1048576)  # Reject arithmetic overflow too.
    return result


def _axis_pair(a, b, tolerance, angle_tolerance):
    u, v = a["direction"], b["direction"]
    delta = b["point"] - a["point"]
    angle, perpendicular, sine = _angles(u, v)
    offset_a = _off_axis(delta, v)
    offset_b = _off_axis(delta, u)
    parallel = _within(angle, angle_tolerance)
    out = {"angle_degrees": angle, "perpendicular_deviation_degrees": perpendicular,
           "parallel_candidate": parallel, "perpendicular_candidate": _within(perpendicular, angle_tolerance),
           "anchor_a_to_axis_b": offset_a, "anchor_b_to_axis_a": offset_b,
           "coaxial_candidate": parallel and _within(max(offset_a, offset_b), tolerance),
           "intersection_point_global": None, "closest_points_global": None}
    if sine <= PARALLEL_SINE:
        out.update(shortest_distance=offset_b, intersection_status="parallel_no_unique_intersection",
                   intersection_candidate=False)
    else:
        cross_unit = np.cross(u, v) / sine
        gap = abs(float(np.dot(delta, cross_unit)))
        out.update(shortest_distance=gap, intersection_candidate=_within(gap, tolerance))
        if sine < INTERSECTION_SINE:
            out["intersection_status"] = "ill_conditioned_point_construction_withheld"
        else:
            ta = float(np.dot(np.cross(delta, v), cross_unit)) / sine
            tb = float(np.dot(np.cross(delta, u), cross_unit)) / sine
            pa = a["point"] + ta * u
            pb = b["point"] + tb * v
            _check_constructed_point(pa, tolerance)
            _check_constructed_point(pb, tolerance)
            out["closest_points_global"] = [pa.tolist(), pb.tolist()]
            out["closest_approach_midpoint_global"] = (pa + (pb - pa) / 2).tolist()
            # A tolerance-close skew pair is not silently made into an intersection.
            roundoff = 64 * np.finfo(float).eps * max(_norm(delta), np.finfo(float).tiny)
            if gap <= roundoff:
                out["intersection_status"] = "numerically_intersecting_ideal_axes"
                out["intersection_point_global"] = out["closest_approach_midpoint_global"]
            else:
                out["intersection_status"] = "skew_within_tolerance" if out["intersection_candidate"] else "skew"
    return out


def _axis_plane(axis, plane, tolerance, angle_tolerance):
    u, n = axis["direction"], plane["direction"]
    normal_angle, plane_angle, _ = _angles(u, n)
    denominator = float(np.dot(u, n))
    signed = float(np.dot(axis["point"] - plane["point"], n))
    out = {"axis_id": axis["id"], "plane_id": plane["id"], "angle_to_plane_degrees": plane_angle,
           "parallel_candidate": _within(plane_angle, angle_tolerance),
           "perpendicular_candidate": _within(normal_angle, angle_tolerance),
           "signed_anchor_offset": signed, "signed_normal_global": n.tolist(),
           "intersection_point_global": None, "axis_in_plane_candidate": False}
    if abs(denominator) <= PARALLEL_SINE:
        out.update(intersection_status="parallel_no_unique_intersection",
                   axis_in_plane_candidate=_within(abs(signed), tolerance))
    elif abs(denominator) < INTERSECTION_SINE:
        out["intersection_status"] = "ill_conditioned_point_construction_withheld"
    else:
        intersection = axis["point"] - signed / denominator * u
        _check_constructed_point(intersection, tolerance)
        out["intersection_point_global"] = intersection.tolist()
        out["intersection_status"] = "unique_ideal_axis_plane_intersection"
    return out


@_numeric_guard
def analyze_feature_relationships(*, features, frame_id, distance_tolerance,
                                  angular_tolerance_degrees) -> dict:
    """Analyze all unordered pairs, capped at 16 observations / 120 pairs."""
    parsed, out = _prepare(features, frame_id, distance_tolerance)
    angle_tolerance = _number(angular_tolerance_degrees, "angular_tolerance_degrees", 0, 45)
    if len(parsed) < 2:
        raise DatumError("Relationship analysis requires at least two features")
    tolerance = out["distance_tolerance"]
    pairs = []
    for a, b in itertools.combinations(parsed, 2):
        delta = b["point"] - a["point"]
        pair = {"feature_ids": [a["id"], b["id"]], "state": "inferred_candidate",
                "reference_point_distance": _norm(delta)}
        if a["kind"] in ("point", "circle") and b["kind"] in ("point", "circle"):
            pair["center_distance"] = pair["reference_point_distance"]
        if a["kind"] == b["kind"] == "plane":
            angle, perpendicular, sine = _angles(a["direction"], b["direction"])
            signed = float(np.dot(delta, a["direction"]))
            parallel = _within(angle, angle_tolerance)
            pair["plane_plane"] = {
                "angle_degrees": angle, "parallel_candidate": parallel,
                "perpendicular_candidate": _within(perpendicular, angle_tolerance),
                "signed_reference_normal_offset": signed, "signed_normal_global": a["direction"].tolist(),
                "parallel_spacing": abs(signed) if sine <= PARALLEL_SINE else None,
                "reference_normal_spacing": abs(signed),
                "constant_spacing_defined": sine <= PARALLEL_SINE,
                "thickness_candidate": parallel and not _within(abs(signed), tolerance),
                "bounded_face_overlap_verified": False, "opposing_material_sides_verified": False,
            }
        elif a["direction"] is not None and b["direction"] is not None:
            if a["kind"] == "plane" or b["kind"] == "plane":
                axis, plane = (b, a) if a["kind"] == "plane" else (a, b)
                pair["axis_plane"] = _axis_plane(axis, plane, tolerance, angle_tolerance)
            else:
                pair["axis_axis"] = _axis_pair(a, b, tolerance, angle_tolerance)
        if {a["kind"], b["kind"]} == {"point", "plane"}:
            point, plane = (a, b) if a["kind"] == "point" else (b, a)
            signed = float(np.dot(point["point"] - plane["point"], plane["direction"]))
            pair["point_plane"] = {"point_id": point["id"], "plane_id": plane["id"],
                                   "signed_distance": signed, "within_tolerance": _within(abs(signed), tolerance)}
        if a["radius"] is not None and b["radius"] is not None:
            pair["diameter_difference"] = abs(2 * a["radius"] - 2 * b["radius"])
            pair["diameters_within_tolerance"] = _within(pair["diameter_difference"], tolerance)
            if a["kind"] == b["kind"] == "circle":
                pair["concentric_candidate"] = (_within(pair["center_distance"], tolerance)
                    and pair["axis_axis"]["parallel_candidate"])
        pairs.append(pair)
    out.update(type="feature_relationships", angular_tolerance_degrees=angle_tolerance,
               pair_count=len(pairs), relationships=pairs,
               interpretation_notes=[
                   "Tolerances are caller settings, not calibrated uncertainty or physical confirmation.",
                   "Signed offsets use the first feature's canonical normal, not an outward material normal.",
                   "Axis offsets are checked at both supplied anchors; infinite-line minimum distance alone does not establish coaxiality.",
                   "Reference-point distances between fitted centroids/axis points are not physical part-center distances.",
                   "Coincident observations remain separate; no independent-evidence or symmetry claim is made."])
    return _finish(out)


@_numeric_guard
def build_live_datum_frame(*, features, frame_id, primary_plane_id, secondary_feature_id,
                           distance_tolerance, origin_feature_id=None, z_direction_hint=None,
                           x_direction_hint=None, minimum_datum_angle_degrees=1.0) -> dict:
    """Construct a right-handed frame from snapshots; despite the name, no live I/O.

    Primary plane sets Z. Project a secondary axis onto it, or intersect a secondary
    plane with it, to set X. The default origin is the primary fitted centroid.
    """
    parsed, out = _prepare(features, frame_id, distance_tolerance)
    minimum = _number(minimum_datum_angle_degrees, "minimum_datum_angle_degrees", 0, 45, positive=True)
    if minimum < 1e-4:
        raise DatumError("minimum_datum_angle_degrees must be at least 0.0001")
    by_id = {f["id"]: f for f in parsed}
    def find(fid):
        fid = _name(fid, "datum feature id")
        if fid not in by_id:
            raise DatumError(f"Unknown datum feature id: {fid}")
        return by_id[fid]
    primary, secondary = find(primary_plane_id), find(secondary_feature_id)
    if primary["kind"] != "plane" or primary["id"] == secondary["id"]:
        raise DatumError("A distinct primary plane and secondary directional feature are required")
    if secondary["direction"] is None:
        raise DatumError("Secondary datum requires a plane, line, circle axis, or cylinder axis")
    hints = []
    for value, label in ((z_direction_hint, "z_direction_hint"), (x_direction_hint, "x_direction_hint")):
        hints.append(None if value is None else _unit(_vector(value, label), label)[0])
    z = _orient(primary["direction"], hints[0])
    secondary_direction = secondary["direction"]
    if secondary["kind"] == "plane":
        x_raw = np.cross(secondary_direction, z)
        construction = "intersection_direction_of_primary_and_secondary_planes"
    else:
        x_raw = secondary_direction - float(np.dot(secondary_direction, z)) * z
        construction = "secondary_axis_projected_onto_primary_plane"
    length = _norm(x_raw)
    if not _within(math.sin(math.radians(minimum)), length):
        raise DatumError("Secondary datum is degenerate or below minimum_datum_angle_degrees")
    x = _orient(_unit(x_raw, "projected secondary direction")[0], hints[1])
    y = _unit(np.cross(z, x), "y axis")[0]
    x = _unit(np.cross(y, z), "x axis")[0]
    origin = primary["point"].copy()
    origin_evidence = {"feature_id": primary["id"], "construction": "primary_fitted_centroid",
                       "signed_projection_distance": 0.0}
    if origin_feature_id is not None:
        f = find(origin_feature_id)
        if f["kind"] in ("line", "cylinder"):
            denominator = float(np.dot(f["direction"], z))
            if not _within(math.sin(math.radians(minimum)), abs(denominator)):
                raise DatumError("Origin axis has no well-conditioned unique intersection with the primary plane")
            signed = float(np.dot(f["point"] - primary["point"], z))
            origin = f["point"] - signed / denominator * f["direction"]
            origin_evidence = {"feature_id": f["id"], "construction": "axis_primary_plane_intersection",
                               "signed_anchor_offset": signed}
        elif f["kind"] in ("circle", "point"):
            signed = float(np.dot(f["point"] - primary["point"], z))
            if not _within(abs(signed), out["distance_tolerance"]):
                raise DatumError("Origin point/center lies outside distance_tolerance of the primary plane")
            origin = f["point"] - signed * z
            origin_evidence = {"feature_id": f["id"], "construction": "point_or_center_projected_to_primary_plane",
                               "input_point_global": f["point"].tolist(), "signed_projection_distance": signed}
        else:
            raise DatumError("Origin feature must be a point, circle, line, or cylinder")
    _check_constructed_point(origin, out["distance_tolerance"])
    rotation = np.array([x, y, z])
    determinant = float(np.linalg.det(rotation))
    orthogonality_error = float(np.max(np.abs(rotation @ rotation.T - np.eye(3))))
    if determinant <= 0 or abs(determinant - 1) > 1e-12 or orthogonality_error > 1e-12:
        raise DatumError("Could not construct a right-handed orthonormal frame")
    origin_residual = float(np.dot(origin - primary["point"], z))
    if not _within(abs(origin_residual), out["distance_tolerance"]):
        raise DatumError("Constructed origin is numerically unresolved at the requested distance_tolerance")
    ambiguities = []
    if hints[0] is None:
        ambiguities.append("Z sign uses largest absolute global component positive; physical outward direction is unknown.")
    if hints[1] is None:
        ambiguities.append("X sign uses largest absolute global component positive; physical forward direction is unknown.")
    if origin_feature_id is None:
        ambiguities.append("Origin is the primary fitted centroid, not an inferred manufacturing origin.")
    out.update(type="cad_datum_frame", state="constructed_candidate", origin_global=origin.tolist(),
               x_axis=x.tolist(), y_axis=y.tolist(), z_axis=z.tolist(), handedness="right",
               determinant=determinant, orthogonality_max_abs_error=orthogonality_error,
               global_to_datum_rotation_rows=rotation.tolist(),
               coordinate_mapping="datum = rotation_rows @ (global - origin_global)",
               primary_plane_id=primary["id"], secondary_feature_id=secondary["id"],
               origin_evidence=origin_evidence, x_axis_construction=construction,
               origin_primary_plane_signed_residual=origin_residual,
               secondary_projection_length=length,
               secondary_angular_residual_degrees=math.degrees(math.atan2(abs(float(np.dot(secondary_direction, z))), length)),
               minimum_datum_angle_degrees=minimum, ambiguities=ambiguities,
               sign_hints={"z": None if hints[0] is None else hints[0].tolist(),
                           "x": None if hints[1] is None else hints[1].tolist()},
               normalization="Normalize supplied directions; project/intersect secondary; Y=Z cross X; recompute X=Y cross Z.")
    return _finish(out)
