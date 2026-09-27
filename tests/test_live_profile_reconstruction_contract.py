from __future__ import annotations

import json
import math
from unittest.mock import patch

import numpy as np
import pytest
from mcp.types import CallToolResult

from cloudcompare_mcp import server


def slot_uv(centerline=20.0, radius=5.0, line_count=21, arc_count=31):
    h = centerline / 2
    p=[]
    p.extend([[x,radius] for x in np.linspace(h,-h,line_count)])
    p.extend([[-h+radius*math.cos(a),radius*math.sin(a)] for a in np.linspace(math.pi/2,3*math.pi/2,arc_count)[1:]])
    p.extend([[x,-radius] for x in np.linspace(-h,h,line_count)[1:]])
    p.extend([[h+radius*math.cos(a),radius*math.sin(a)] for a in np.linspace(3*math.pi/2,5*math.pi/2,arc_count)[1:-1]])
    return np.asarray(p)


def region_response(points, *, truncated=False):
    rng=np.random.default_rng(15003)
    order=rng.permutation(len(points))
    sample=[]
    for i in order:
        row=np.asarray(points[i],dtype=float)
        xyz=[float(row[0]),float(row[1]),float(row[2]) if row.shape[0] >= 3 else 0.0]
        sample.append({"point_index":int(i), "position_global":xyz})
    return {
        "cloud_name": "profile-fixture",
        "coordinate_space": "global",
        "source_global_shift": [1234.5, -6789.25, 100000.125],
        "source_global_scale": 2.5,
        "matched_count": len(points),
        "returned_count": len(points),
        "truncated": truncated,
        "sample_strategy": "deterministic_stride",
        "points": sample,
    }


def body(result): return json.loads(result[0].text)


def test_live_profile_keeps_raw_points_server_side_and_finds_slot():
    points=slot_uv()
    with patch.object(server,"live_request",return_value=region_response(points)) as native:
        result=server.handle_reconstruct_live_section_profile({
            "cloud_id":77,"origin":[0,0,0],"normal":[0,0,1],"half_thickness":0.01,
            "closed":True,"fit_tolerance":1e-8,"angular_tolerance_degrees":0.1,
            "ordering_method":"polar_closed_loop","sample_limit":512,
        })
    parsed=body(result)
    assert parsed["type"]=="live_cad_section_profile"
    candidate,=[c for c in parsed["profile_candidates"] if c["type"]=="slot_candidate"]
    assert candidate["radius"]==5.0
    assert candidate["centerline_length"]==20.0
    assert parsed["source_geometry_preserved"] and parsed["live_connection_used"]
    assert parsed["scene_mutations_requested"] is False
    assert parsed["source_cloud_name"] == "profile-fixture"
    assert parsed["source_coordinate_bookkeeping"] == {
        "query_coordinate_space": "global",
        "global_shift": [1234.5, -6789.25, 100000.125],
        "global_scale": 2.5,
    }
    assert parsed["acquisition"]["raw_points_returned"] is False
    dumped=json.dumps(parsed)
    assert 'position_global' not in dumped and 'points_uv' not in dumped
    native.assert_called_once()
    method,params=native.call_args.args[:2]
    assert method=="cloud.region_query"
    assert params["cloud_id"]==77 and params["max_points"]==512
    assert params["region"]["type"]=="slab"


def test_live_profile_default_ordering_matches_closed_mode():
    points=slot_uv()
    with patch.object(server,"live_request",return_value=region_response(points)):
        parsed=body(server.handle_reconstruct_live_section_profile({
            "cloud_id":77,"origin":[0,0,0],"normal":[0,0,1],"half_thickness":0.01,
            "closed":True,"fit_tolerance":1e-8,
        }))
    assert parsed["ordering"]["method"]=="polar_closed_loop"


def test_live_profile_truncation_is_explicit():
    points=slot_uv()
    response=region_response(points,truncated=True); response["matched_count"]=10000
    with patch.object(server,"live_request",return_value=response):
        parsed=body(server.handle_reconstruct_live_section_profile({
            "cloud_id":77,"origin":[0,0,0],"normal":[0,0,1],"half_thickness":0.01,
            "closed":True,"fit_tolerance":1e-8,
        }))
    assert parsed["acquisition"]["sample_truncated"] is True
    assert any("bounded sample" in w for w in parsed["quality_warnings"])


def test_live_profile_sparse_region_is_mcp_error():
    response={"matched_count":1,"returned_count":1,"truncated":False,"sample_strategy":"all",
              "points":[{"point_index":0,"position_global":[0,0,0]}]}
    with patch.object(server,"live_request",return_value=response):
        result=server.handle_reconstruct_live_section_profile({
            "cloud_id":77,"origin":[0,0,0],"normal":[0,0,1],"half_thickness":0.01,
            "closed":True,"fit_tolerance":0.1,
        })
    assert isinstance(result,CallToolResult) and result.isError
    assert "at least 3" in result.content[0].text

def test_live_profile_arbitrary_plane_and_large_translation():
    uv = slot_uv()
    normal = np.array([0.31, -0.57, 0.76], dtype=float)
    normal /= np.linalg.norm(normal)
    seed = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(seed, normal))) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])
    u = seed - normal * float(np.dot(seed, normal)); u /= np.linalg.norm(u)
    v = np.cross(normal, u); v /= np.linalg.norm(v)
    origin = np.array([1.0e8, -2.0e8, 3.0e8])
    xyz = origin + uv[:,0,None]*u + uv[:,1,None]*v
    with patch.object(server, "live_request", return_value=region_response(xyz)):
        parsed = body(server.handle_reconstruct_live_section_profile({
            "cloud_id": 88, "origin": origin.tolist(), "normal": normal.tolist(),
            "half_thickness": 0.01, "closed": True, "fit_tolerance": 1e-4,
            "ordering_method": "polar_closed_loop", "angular_tolerance_degrees": 0.2,
        }))
    candidate, = [c for c in parsed["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidate["radius"] == pytest.approx(5.0, abs=2e-6)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=2e-6)
    assert parsed["section_frame"]["origin_global"] == origin.tolist()


def test_live_invalid_profile_options_fail_before_native_io():
    bad_cases = [
        {"fit_tolerance": 0.0},
        {"fit_tolerance": float("nan")},
        {"ordering_method": "principal_open"},
        {"sample_limit": 2},
        {"normal": [0,0,0]},
        {"half_thickness": -1},
    ]
    base = {"cloud_id":77,"origin":[0,0,0],"normal":[0,0,1],"half_thickness":0.01,
            "closed":True,"fit_tolerance":0.1}
    for change in bad_cases:
        args = dict(base); args.update(change)
        with patch.object(server, "live_request") as native:
            result = server.handle_reconstruct_live_section_profile(args)
        native.assert_not_called()
        assert isinstance(result, CallToolResult) and result.isError


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("coordinate_space", "native_local", "expected global"),
        ("source_global_shift", [0, float("nan"), 0], "non-finite"),
        ("source_global_shift", [0, 0], "malformed"),
        ("source_global_scale", 0, "finite and positive"),
        ("source_global_scale", float("inf"), "finite and positive"),
    ],
)
def test_live_profile_rejects_malformed_native_coordinate_bookkeeping(field, value, match):
    response = region_response(slot_uv())
    response[field] = value
    with patch.object(server, "live_request", return_value=response):
        result = server.handle_reconstruct_live_section_profile({
            "cloud_id": 77,
            "origin": [0, 0, 0],
            "normal": [0, 0, 1],
            "half_thickness": 0.01,
            "closed": True,
            "fit_tolerance": 1e-8,
        })
    assert isinstance(result, CallToolResult) and result.isError
    assert match in result.content[0].text
