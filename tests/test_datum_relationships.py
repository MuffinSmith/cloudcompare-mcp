"""Exact product numerical tests; no MCP or native host required."""
from copy import deepcopy
import json
import math

import numpy as np
import pytest

from cloudcompare_mcp.datum_relationships import (
    DatumError, analyze_feature_relationships as analyze, build_live_datum_frame as build,
)
from cloudcompare_mcp.feature_fit import fit_plane, fit_line_3d, fit_circle_3d


def feature(fid, kind, point=(0, 0, 0), direction=(0, 0, 1), radius=2):
    o = dict(type=kind, coordinate_space="global", units="native", source_cloud_id=42,
             global_shift=[-1000, 2000, -3000], global_scale=0.25)
    keys = {"plane": ("centroid", "normal"), "line": ("centroid", "direction"),
            "circle": ("center", "normal"), "cylinder": ("axis_point", "axis_direction"),
            "point": ("position_global", None)}
    p, d = keys[kind]; o[p] = list(point)
    if d: o[d] = list(direction)
    if kind in ("circle", "cylinder"): o["radius"] = radius
    return dict(id=fid, observation=o, provenance={"dataset": "synthetic", "global_scale": 0.25})


def analysis(features, **kwargs):
    return analyze(features=features, frame_id="fixture-global", distance_tolerance=kwargs.pop("distance_tolerance", .01),
                   angular_tolerance_degrees=kwargs.pop("angular_tolerance_degrees", .5), **kwargs)


def datum(features=None, **kwargs):
    if features is None:
        features = [feature("base", "plane"), feature("edge", "line", direction=(1, 0, 0))]
    return build(features=features, frame_id="fixture-global", primary_plane_id="base", secondary_feature_id="edge",
                 distance_tolerance=kwargs.pop("distance_tolerance", .01), **kwargs)


def pair(features, **kwargs):
    return analysis(features, **kwargs)["relationships"][0]


def rotation(seed=123):
    q, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    if np.linalg.det(q) < 0: q[:, 0] *= -1
    return q


def transform(features, r, t):
    out = deepcopy(features)
    for f in out:
        for key in ("centroid", "center", "axis_point", "position_global"):
            if key in f["observation"]: f["observation"][key] = (r @ f["observation"][key] + t).tolist()
        for key in ("normal", "direction", "axis_direction"):
            if key in f["observation"]: f["observation"][key] = (r @ f["observation"][key]).tolist()
    return out


def test_parallel_planes_signed_spacing_and_unconfirmed_thickness():
    f = [feature("a", "plane"), feature("b", "plane", (12, 15, 2), (0, 0, -7))]
    r = pair(f)["plane_plane"]
    assert r["parallel_spacing"] == 2
    assert r["signed_reference_normal_offset"] == 2
    assert r["thickness_candidate"] and not r["opposing_material_sides_verified"]
    assert not r["bounded_face_overlap_verified"]


def test_almost_parallel_planes_have_no_constant_spacing():
    a = math.radians(.1)
    r = pair([feature("a", "plane"), feature("b", "plane", (0, 0, 2), (0, math.sin(a), math.cos(a)))])["plane_plane"]
    assert r["parallel_candidate"] and r["parallel_spacing"] is None
    assert r["reference_normal_spacing"] == 2 and not r["constant_spacing_defined"]


@pytest.mark.parametrize("sign_a,sign_b", [(1, 1), (1, -1), (-1, 1), (-1, -1)])
def test_plane_normal_sign_invariant_metrics(sign_a, sign_b):
    r = pair([feature("a", "plane", direction=(0, 0, sign_a)),
              feature("b", "plane", (3, 2, 4), (0, 0, sign_b))])["plane_plane"]
    assert r["parallel_spacing"] == 4 and r["signed_reference_normal_offset"] == 4


def test_perpendicular_planes():
    r = pair([feature("a", "plane"), feature("b", "plane", direction=(1, 0, 0))])["plane_plane"]
    assert r["angle_degrees"] == 90 and r["perpendicular_candidate"]
    assert not r["parallel_candidate"] and r["parallel_spacing"] is None


@pytest.mark.parametrize("angle,expected", [(0.499, True), (.5, True), (.501, False)])
def test_angular_boundary(angle, expected):
    a = math.radians(angle)
    r = pair([feature("a", "plane"), feature("b", "plane", direction=(math.sin(a), 0, math.cos(a)))])["plane_plane"]
    assert r["parallel_candidate"] is expected


@pytest.mark.parametrize("offset,expected", [(0.0099, True), (.01, True), (.0101, False)])
def test_coaxial_distance_boundary(offset, expected):
    r = pair([feature("a", "line"), feature("b", "cylinder", (offset, 0, 8))])["axis_axis"]
    assert r["coaxial_candidate"] is expected
    assert r["shortest_distance"] == pytest.approx(offset)
    assert r["intersection_point_global"] is None


def test_close_skew_axes_not_silently_intersected():
    r = pair([feature("a", "line", direction=(1, 0, 0)),
              feature("b", "line", (0, 0, .005), (0, 1, 0))])["axis_axis"]
    assert r["shortest_distance"] == .005 and r["intersection_candidate"]
    assert r["intersection_status"] == "skew_within_tolerance"
    assert r["intersection_point_global"] is None
    assert r["closest_approach_midpoint_global"] == [0, 0, .0025]


def test_axis_intersection_and_distant_crossing_not_coaxial():
    r = pair([feature("a", "line", direction=(1, 0, 0)),
              feature("b", "line", (5, -3, 0), (0, 1, 0))])["axis_axis"]
    assert r["intersection_point_global"] == pytest.approx([5, 0, 0])
    a = math.radians(.1)
    r = pair([feature("a", "line", direction=(1, 0, 0)),
              feature("b", "line", (0, 10, 0), (math.cos(a), math.sin(a), 0))])["axis_axis"]
    assert r["parallel_candidate"] and r["shortest_distance"] == 0
    assert not r["coaxial_candidate"]


def test_near_parallel_intersection_withheld():
    r = pair([feature("a", "line", direction=(1, 0, 0)),
              feature("b", "line", (0, 1, 0), (1, 1e-10, 0))])["axis_axis"]
    assert r["intersection_status"] == "ill_conditioned_point_construction_withheld"
    assert r["closest_points_global"] is None
    r = pair([feature("a", "plane"), feature("b", "line", (0, 0, 1), (1, 0, 1e-10))])["axis_plane"]
    assert r["intersection_point_global"] is None


@pytest.mark.parametrize("direction,point,status", [
    ((0, 0, 1), (2, 3, 5), "unique_ideal_axis_plane_intersection"),
    ((1, 0, 0), (2, 3, 5), "parallel_no_unique_intersection"),
    ((1, 0, 0), (2, 3, 0), "parallel_no_unique_intersection"),
])
def test_axis_plane(direction, point, status):
    r = pair([feature("a", "plane"), feature("b", "cylinder", point, direction)])["axis_plane"]
    assert r["intersection_status"] == status
    assert r["signed_anchor_offset"] == point[2]
    if direction == (0, 0, 1):
        assert r["perpendicular_candidate"] and r["intersection_point_global"] == [2, 3, 0]
    else:
        assert r["parallel_candidate"] and r["axis_in_plane_candidate"] == (point[2] == 0)


def test_circle_concentric_and_shared_axis_not_same_plane():
    a = feature("a", "circle")
    r = pair([a, feature("b", "circle", radius=3)])
    assert r["concentric_candidate"] and r["diameter_difference"] == 2
    r = pair([a, feature("b", "circle", (0, 0, 5), radius=3)])
    assert r["axis_axis"]["coaxial_candidate"] and not r["concentric_candidate"]
    assert r["center_distance"] == 5


def test_point_plane_and_centroid_semantics():
    r = pair([feature("a", "plane"), feature("b", "point", (3, 4, -5))])
    assert r["point_plane"]["signed_distance"] == -5 and "center_distance" not in r
    assert r["reference_point_distance"] == pytest.approx(math.sqrt(50))


@pytest.mark.parametrize("seed", range(8))
def test_rotated_large_translation_relationships(seed):
    f = [feature("a", "line", direction=(1, 0, 0)), feature("b", "line", (5, -3, 2), (0, 1, 0))]
    r = rotation(seed); t = np.array([1e9, -2e9, 3e9])
    result = pair(transform(f, r, t))["axis_axis"]
    assert result["angle_degrees"] == pytest.approx(90, abs=1e-10)
    assert result["shortest_distance"] == pytest.approx(2, abs=1e-6)
    pa, pb = np.array(result["closest_points_global"])
    np.testing.assert_allclose(r.T @ (pa-t), [5, 0, 0], atol=2e-6)
    np.testing.assert_allclose(r.T @ (pb-t), [5, 0, 2], atol=2e-6)


@pytest.mark.parametrize("seed", range(8))
def test_rotated_translated_right_handed_datum(seed):
    f = [feature("base", "plane", (0, 0, 2)), feature("edge", "line", direction=(3, 0, 0)),
         feature("origin", "cylinder", (5, -3, 8))]
    r = rotation(seed); t = np.array([1e9, -2e9, 3e9])
    result = datum(transform(f, r, t), origin_feature_id="origin", z_direction_hint=r[:, 2].tolist(), x_direction_hint=r[:, 0].tolist())
    axes = np.array([result[k] for k in ("x_axis", "y_axis", "z_axis")])
    np.testing.assert_allclose(axes, r.T, atol=1e-14)
    np.testing.assert_allclose(axes @ axes.T, np.eye(3), atol=1e-14)
    assert result["determinant"] == pytest.approx(1, abs=1e-14)
    np.testing.assert_allclose(r.T @ (np.array(result["origin_global"])-t), [5, -3, 2], atol=2e-6)
    assert result["handedness"] == "right" and not result["ambiguities"]


def test_frame_from_secondary_plane():
    r = datum([feature("base", "plane"), feature("edge", "plane", direction=(0, 1, 0))])
    assert r["x_axis"] == [1, 0, 0] and r["y_axis"] == [0, 1, 0]
    assert r["x_axis_construction"] == "intersection_direction_of_primary_and_secondary_planes"
    assert len(r["ambiguities"]) == 3


@pytest.mark.parametrize("kind", ["circle", "point"])
@pytest.mark.parametrize("offset", [0, .01, -.01])
def test_origin_projection_explicit_and_bounded(kind, offset):
    f = [feature("base", "plane"), feature("edge", "line", direction=(1, 0, 0)), feature("origin", kind, (2, 3, offset))]
    r = datum(f, origin_feature_id="origin")
    assert r["origin_global"] == [2, 3, 0]
    assert r["origin_evidence"]["signed_projection_distance"] == offset


@pytest.mark.parametrize("kind", ["line", "plane", "cylinder", "circle"])
def test_degenerate_secondary_rejected(kind):
    direction = (0, 0, 1)
    with pytest.raises(DatumError, match="degenerate"):
        datum([feature("base", "plane"), feature("edge", kind, direction=direction)])


@pytest.mark.parametrize("value", [True, None, "1", 0, -1, float("nan"), float("inf"), 1e-9, 46])
def test_bad_datum_threshold(value):
    with pytest.raises(DatumError): datum(minimum_datum_angle_degrees=value)


def test_hints_reverse_axes_preserve_right_handedness():
    r = datum(z_direction_hint=[0, 0, -1], x_direction_hint=[-1, 0, 0])
    assert r["z_axis"] == [0, 0, -1] and r["x_axis"] == [-1, 0, 0]
    assert r["y_axis"] == [0, 1, 0] and r["determinant"] == 1
    with pytest.raises(DatumError, match="ambiguous"): datum(z_direction_hint=[1, 0, 0])
    with pytest.raises(DatumError, match="ambiguous"): datum(x_direction_hint=[0, 1, 0])


def test_sign_invariant_frame_without_hints():
    f = [feature("base", "plane", direction=(0, 0, -5)), feature("edge", "line", direction=(-8, 0, 0))]
    r = datum(f)
    assert r["x_axis"] == [1, 0, 0] and r["z_axis"] == [0, 0, 1]


def test_projection_residual_is_reported_not_assumed_perpendicular():
    r = datum([feature("base", "plane"), feature("edge", "line", direction=(1, 0, 1))])
    assert r["secondary_angular_residual_degrees"] == pytest.approx(45)


def test_invalid_origin_and_missing_ids():
    f = [feature("base", "plane"), feature("edge", "line", direction=(1, 0, 0)), feature("origin", "point", (0, 0, .02))]
    with pytest.raises(DatumError, match="outside"): datum(f, origin_feature_id="origin")
    with pytest.raises(DatumError, match="Unknown"): datum(origin_feature_id="absent")
    with pytest.raises(DatumError, match="well-conditioned"): datum(origin_feature_id="edge")
    with pytest.raises(DatumError, match="Origin feature"): datum(origin_feature_id="base")


@pytest.mark.parametrize("path,value", [
    ("coordinate_space", "native_local"), ("units", "mm"), ("type", []), ("type", "cone"),
    ("centroid", [1, 2]), ("centroid", [True, 1, 2]), ("centroid", [0, 0, float("nan")]),
    ("normal", [0, 0, 0]), ("normal", [0, 0, float("inf")]), ("source_cloud_id", True),
    ("frame_id", "another-frame"), ("points", [[1, 2, 3]]), ("source_picks", "no"),
])
def test_bad_observations(path, value):
    f = [feature("a", "plane"), feature("b", "plane")]; f[0]["observation"][path] = value
    with pytest.raises(DatumError): analysis(f)


@pytest.mark.parametrize("value", [None, True, "0.1", 0, -.1, float("nan"), float("inf")])
def test_bad_distance_tolerance(value):
    with pytest.raises(DatumError): analysis([feature("a", "plane"), feature("b", "plane")], distance_tolerance=value)


@pytest.mark.parametrize("value", [True, "0.1", -.1, 46, float("nan"), float("inf")])
def test_bad_angle_tolerance(value):
    with pytest.raises(DatumError): analysis([feature("a", "plane"), feature("b", "plane")], angular_tolerance_degrees=value)


def test_reject_unresolvable_global_precision():
    with pytest.raises(DatumError, match="ULPs"):
        analysis([feature("a", "plane", (1e16, 0, 0)), feature("b", "plane", (1e16, 0, 1))])


def test_duplicates_boundedness_and_determinism():
    f = [feature("a", "plane"), feature("b", "plane")]
    r = analysis(f)
    assert r == analysis(list(reversed(f)))
    assert r["pair_count"] == 1 and len(r["observations"]) == 2  # Do not merge coincident observations.
    with pytest.raises(DatumError, match="Duplicate"): analysis([f[0], f[0]])
    with pytest.raises(DatumError): analysis([])
    with pytest.raises(DatumError): analysis(f[:1])
    with pytest.raises(DatumError): analysis([feature(str(i), "plane") for i in range(17)])
    assert analysis([feature(str(i), "plane") for i in range(16)])["pair_count"] == 120


def test_no_input_mutation_compact_traceable_provenance():
    f = [feature("a", "plane"), feature("b", "line", direction=(1, 0, 0))]
    f[0]["observation"]["source_picks"] = [{"entity_id": 42, "position_global": [i, 0, 0]} for i in range(10)]
    before = deepcopy(f); r = analysis(f)
    assert f == before and "source_picks" not in json.dumps(r)
    o = r["observations"][0]
    assert o["source_metadata"]["global_shift"] == [-1000, 2000, -3000]
    assert o["source_metadata"]["global_scale"] == .25
    assert o["provenance"] == f[0]["provenance"] and len(o["snapshot_sha256"]) == 64
    assert o["source_pick_count"] == 10 and o["source_pick_entity_ids"] == [42]
    assert not r["live_connection_used"] and not r["user_accepted"]
    o["provenance"]["dataset"] = "changed"
    assert f == before


def test_metadata_is_bounded_finite_and_source_not_invented():
    f = [feature("a", "plane"), feature("b", "plane")]
    f[0]["provenance"] = {"bad": float("nan")}
    with pytest.raises(DatumError): analysis(f)
    f[0]["provenance"] = {"large": "a" * 5000}
    with pytest.raises(DatumError): analysis(f)
    f[0].pop("provenance"); f[0]["observation"].pop("source_cloud_id")
    with pytest.raises(DatumError, match="provide"): analysis(f)


def test_radius_validation():
    f = [feature("a", "circle"), feature("b", "cylinder")]
    f[0]["observation"]["diameter"] = 10
    with pytest.raises(DatumError, match="disagree"): analysis(f)
    f[0]["observation"].pop("diameter"); f[0]["observation"]["radius"] = -1
    with pytest.raises(DatumError): analysis(f)


def test_actual_fit_outputs_feed_datum_without_refitting():
    plane = fit_plane([[x, y, 2] for x in range(4) for y in range(4)])
    line = fit_line_3d([[x, 0, 2] for x in range(4)])
    circle = fit_circle_3d([[3+2*math.cos(t), 4+2*math.sin(t), 2] for t in np.linspace(0, 2*math.pi, 32, endpoint=False)])
    f = []
    for fid, o in (("base", plane), ("edge", line), ("origin", circle)):
        o.update(coordinate_space="global", units="native", source_cloud_id=42)
        f.append(dict(id=fid, observation=o))
    r = datum(f, origin_feature_id="origin", z_direction_hint=[0, 0, 1], x_direction_hint=[1, 0, 0])
    assert r["origin_global"] == pytest.approx([3, 4, 2])
    assert r["observations"][0]["fit_quality_supplied"]["residuals"]["rms"] < 1e-12


@pytest.mark.parametrize("angle,works", [(.9999, False), (1, True), (1.0001, True)])
def test_datum_minimum_angle_inclusive_boundary(angle, works):
    a = math.radians(angle)
    f = [feature("base", "plane"), feature("edge", "line", direction=(math.sin(a), 0, math.cos(a)))]
    if works: assert datum(f)["x_axis"] == pytest.approx([1, 0, 0])
    else:
        with pytest.raises(DatumError): datum(f)


@pytest.mark.parametrize("seed", range(6))
def test_rotated_plane_spacing_and_axis_plane_intersection(seed):
    r, t = rotation(seed), np.array([1e9, -2e9, 3e9])
    f = [feature("a", "plane"), feature("b", "plane", (0, 0, 2))]
    p = pair(transform(f, r, t))["plane_plane"]
    assert p["parallel_spacing"] == pytest.approx(2, abs=1e-6)
    f = [feature("a", "plane"), feature("b", "cylinder", (3, 4, 5))]
    p = pair(transform(f, r, t))["axis_plane"]
    np.testing.assert_allclose(r.T @ (np.array(p["intersection_point_global"])-t), [3, 4, 0], atol=1e-6)


@pytest.mark.parametrize("scale", [1e-300, 1e-10, 1, 1e100])
def test_direction_normalization_does_not_change_geometry(scale):
    r = datum([feature("base", "plane", direction=(0, 0, scale)),
               feature("edge", "line", direction=(scale, 0, 0))])
    assert r["x_axis"] == [1, 0, 0] and r["z_axis"] == [0, 0, 1]


@pytest.mark.parametrize("key,value", [("global_shift", [1, 2]), ("global_scale", 0),
                                       ("global_scale", -1), ("source_picks", [{}]),
                                       ("source_picks", [{"entity_id": True}])])
def test_invalid_coordinate_bookkeeping_and_pick_identity(key, value):
    f = [feature("a", "plane"), feature("b", "plane")]
    f[0]["observation"][key] = value
    with pytest.raises(DatumError): analysis(f)


def test_inferred_input_state_is_not_promoted_to_verified_measurement():
    f = [feature("a", "plane"), feature("b", "plane")]
    f[0]["observation"]["state"] = "inferred_candidate"
    o = analysis(f)["observations"][0]
    assert o["supplied_interpretation_state"] == "inferred_candidate"
    assert o["evidence_state"] == "supplied_geometry" and not o["measurement_independently_verified"]


def test_arithmetic_overflow_fails_as_domain_error():
    f = [feature("a", "point", (-1e308, 0, 0)), feature("b", "point", (1e308, 0, 0))]
    with pytest.raises(DatumError): analysis(f, distance_tolerance=1e295)


def test_far_intersection_precision_is_not_silently_overclaimed():
    f = [feature("a", "line", direction=(1, 0, 0)), feature("b", "line", (0, 1, 0), (1, 1e-7, 0))]
    with pytest.raises(DatumError, match="Constructed point"):
        analysis(f, distance_tolerance=1e-10)
