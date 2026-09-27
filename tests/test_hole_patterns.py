"""Exact production numerical implementation; no CloudCompare host needed."""
from copy import deepcopy
import json
import math

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import FeatureFitError
from cloudcompare_mcp.hole_patterns import analyze_hole_candidates

CONFIG = dict(face_origin=[0, 0, 0], face_normal=[0, 0, 1], plane_tolerance=.2,
              diameter_tolerance=.1, center_tolerance=.05, spacing_tolerance=.1)


def candidate(i, x=0, y=0, z=0, radius=2, **changes):
    out = dict(candidate_index=i, support_count=100, support_fraction_of_sample=.2,
               support_angular_coverage_degrees=359, orthogonal_residuals={"rms": .01},
               circle=dict(center=[x, y, z], normal=[0, 0, 1], radius=radius))
    out.update(changes)
    return out


def analyze(cs, **changes):
    return analyze_hole_candidates(cs, **{**CONFIG, **changes})


def layouts(result):
    return [p for g in result["diameter_groups"] for p in g["layout_candidates"]]


def test_empty_is_honest_and_finite():
    r = analyze([])
    assert r["candidates"] == r["center_spacings"] == r["diameter_groups"] == []
    assert not r["confirmed_holes"] and r["read_only"]
    json.dumps(r, allow_nan=False)


def test_row_recovers_pitch_and_never_confirms_holes():
    r = analyze([candidate(7, 0), candidate(3, 10), candidate(12, 20)])
    p, = layouts(r)
    assert p["type"] == "equally_spaced_row_candidate"
    assert p["candidate_indices"] == [7, 3, 12]
    assert p["pitch"] == pytest.approx(10)
    assert p["max_line_offset"] == pytest.approx(0)
    assert not p["confirmed_holes"]
    assert [s["center_distance_3d"] for s in r["center_spacings"]] == [10, 10, 20]


def test_square_is_bolt_circle_and_diagonals_are_measured():
    r = analyze([candidate(i, x, y) for i, (x, y) in enumerate([(-10,-10), (10,-10), (10,10), (-10,10)])])
    p, = layouts(r)
    assert p["type"] == "equally_spaced_bolt_circle_candidate"
    assert p["pitch_circle_diameter"] == pytest.approx(20 * math.sqrt(2))
    assert p["angular_gaps_degrees"] == pytest.approx([90] * 4)
    assert p["center_global"] == pytest.approx([0,0,0])
    assert len(r["center_spacings"]) == 6


@pytest.mark.parametrize("n", [4, 5, 6, 8, 12])
def test_full_ring(n):
    cs = [candidate(i, 30 * math.cos(2 * math.pi * i / n), 30 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    p, = layouts(analyze(cs))
    assert p["pitch_circle_radius"] == pytest.approx(30)
    assert p["angular_gaps_degrees"] == pytest.approx([360 / n] * n)


def test_noisy_ring_in_tolerance():
    rng = np.random.default_rng(13)
    cs = [candidate(i, 20 * math.cos(i * math.pi / 3) + rng.normal(0,.005),
                    20 * math.sin(i * math.pi / 3) + rng.normal(0,.005)) for i in range(6)]
    p, = layouts(analyze(cs))
    assert p["pitch_circle_radius"] == pytest.approx(20, abs=.01)


@pytest.mark.parametrize("points", [
    [(0,0),(10,0),(23,0)],                  # uneven row
    [(0,0),(10,0),(11,8),(0,10)],           # irregular quadrilateral
    [(10,0),(0,10),(-10,0)],               # three centers are not bolt pattern evidence
    [(10,0),(0,10),(-10,0),(7,-7)],         # near-circle, uneven angles
    [(0,0),(10,0)],                        # two centers are insufficient
])
def test_irregular_or_insufficient_sets_have_no_layout(points):
    assert not layouts(analyze([candidate(i,x,y) for i,(x,y) in enumerate(points)]))


def test_weak_off_face_and_tilted_candidates_explained():
    cs = [candidate(0), candidate(1,z=1), candidate(2, support_count=4),
          candidate(3,support_fraction_of_sample=.001),
          candidate(4,support_angular_coverage_degrees=30),
          candidate(5,orthogonal_residuals={"rms":.3}), candidate(6)]
    cs[-1]["circle"]["normal"] = [0,1,0]
    r = analyze(cs, max_fit_rms=.1)
    assert [c["candidate_index"] for c in r["candidates"]] == [0]
    reasons = {x["candidate_index"]:x["reasons"] for x in r["rejected"]}
    assert "outside_face_slab" in reasons[1]
    assert "insufficient_support_count" in reasons[2]
    assert "insufficient_support_fraction" in reasons[3]
    assert "insufficient_angular_coverage" in reasons[4]
    assert "excessive_fit_residual" in reasons[5]
    assert "normal_mismatch" in reasons[6]


def test_entire_circle_must_fit_face_slab():
    c = candidate(0, radius=100)
    c["circle"]["normal"] = [0,math.sin(.02),math.cos(.02)]
    assert analyze([c])["rejected"][0]["reasons"] == ["outside_face_slab"]


def test_duplicate_representative_is_deterministic_no_double_count():
    cs = [candidate(9,0),candidate(3,.01),candidate(1,10),candidate(5,20)]
    original = deepcopy(cs)
    r = analyze(cs)
    assert r["duplicates"] == [{"candidate_index":9,"representative_index":3}]
    assert r["candidate_count"] == 3
    assert cs == original
    assert r == analyze(list(reversed(cs)))
    assert len(layouts(r)) == 1


def test_duplicate_chain_does_not_swallow_distinct_centers():
    r = analyze([candidate(0,0),candidate(1,.04),candidate(2,.08)])
    assert r["candidate_count"] == 2
    assert len(r["duplicates"]) == 1


def test_diameter_chain_is_bounded_by_entire_group_range():
    r = analyze([candidate(0,0,radius=2),candidate(1,10,radius=2.04),candidate(2,20,radius=2.08)])
    assert [g["count"] for g in r["diameter_groups"]] == [2,1]
    assert all(g["diameter_max"] - g["diameter_min"] <= .1 for g in r["diameter_groups"])


def test_concentric_different_sizes_retained_not_duplicates():
    r = analyze([candidate(0,radius=2),candidate(1,radius=3)])
    assert not r["duplicates"]
    assert len(r["concentric_candidates"]) == 1
    assert len(r["diameter_groups"]) == 2


def test_3d_distance_and_projected_spacing_are_separate():
    r = analyze([candidate(0,0,z=-.1),candidate(1,3,4,.1)])
    p, = r["center_spacings"]
    assert p["center_distance_in_face"] == 5
    assert p["center_distance_3d"] == pytest.approx(math.sqrt(25.04))
    assert p["signed_face_offset_difference"] == pytest.approx(.2)


def test_transform_large_translation_and_normal_sign_invariance():
    axis = np.array([1.,2.,3.]); axis /= np.linalg.norm(axis)
    u = np.cross(axis,[1,0,0]); u /= np.linalg.norm(u); v = np.cross(axis,u)
    origin = np.array([300000.,-200000.,100000.])
    cs = []
    for i in range(6):
        c = candidate(i)
        c["circle"]["center"] = (origin + 20 * (u * math.cos(i*math.pi/3) + v*math.sin(i*math.pi/3))).tolist()
        c["circle"]["normal"] = axis.tolist()
        cs.append(c)
    r = analyze(cs,face_origin=origin.tolist(),face_normal=axis.tolist())
    p, = layouts(r)
    assert p["pitch_circle_radius"] == pytest.approx(20, abs=1e-7)
    assert p["center_global"] == pytest.approx(origin, abs=1e-7)
    for c in cs: c["circle"]["normal"] = (-axis).tolist()
    assert r == analyze(cs,face_origin=origin.tolist(),face_normal=(-axis).tolist())


@pytest.mark.parametrize("key,value", [
    ("plane_tolerance",0),("diameter_tolerance",-1),("spacing_tolerance",float("nan")),
    ("center_tolerance",float("inf")),("face_normal",[0,0,0]),("face_origin",[1,2]),
    ("min_support_count",True),("min_support_fraction",1.1),("min_coverage_degrees",361),
    ("normal_tolerance_degrees",91),("max_fit_rms",-1),
])
def test_invalid_analysis_parameters_rejected(key,value):
    with pytest.raises((FeatureFitError,KeyError)):
        analyze([], **{key:value})


@pytest.mark.parametrize("change", [
    {"candidate_index":True}, {"support_count":1}, {"support_fraction_of_sample":float("nan")},
    {"orthogonal_residuals":{"rms":float("inf")}}, {"support_angular_coverage_degrees":-1},
    {"circle":{"center":[0,0,0],"normal":[0,0,1],"radius":0}},
    {"circle":{"center":[float("inf"),0,0],"normal":[0,0,1],"radius":2}},
])
def test_invalid_candidate_rejected_not_silently_dropped(change):
    with pytest.raises(FeatureFitError): analyze([candidate(0, **change)])


def test_duplicate_ids_and_bound_enforced():
    with pytest.raises(FeatureFitError,match="unique"): analyze([candidate(0),candidate(0,10)])
    with pytest.raises(FeatureFitError,match="at most"): analyze([candidate(i,i) for i in range(33)])


def test_no_raw_payload_or_inherited_confirmation():
    c = candidate(0); c.update(points=[[1,2,3]], confirmed_hole=True, pixels="private")
    c["circle"]["point_indices"] = [1,2,3]
    r = analyze([c]); text = json.dumps(r)
    assert "pixels" not in text and "point_indices" not in text and '"points"' not in text
    assert r["candidates"][0]["confirmed_hole"] is False
