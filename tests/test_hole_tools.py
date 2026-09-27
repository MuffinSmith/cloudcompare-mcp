"""MCP/region-boundary integration. Native CloudCompare is a test double here."""
import asyncio
from copy import deepcopy
import json
from unittest.mock import patch

import numpy as np
import pytest
from mcp import types

from cloudcompare_mcp import server
from cloudcompare_mcp.hole_tools import analyze_snapshot
from cloudcompare_mcp.feature_fit import FeatureFitError

CONFIG = dict(face_origin=[0,0,0], face_normal=[0,0,1], plane_tolerance=.2,
              diameter_tolerance=.1, center_tolerance=.05, spacing_tolerance=.1)
LIVE = dict(**CONFIG, cloud_id=42, region={"type":"box","min":[-15,-15,-1],"max":[15,15,1]},
            min_radius=1.5, max_radius=2.5, distance_threshold=.03, min_support_count=40,
            iterations=200, max_circles=4, sample_limit=1000)


def circles_snapshot():
    candidates = [dict(candidate_index=i, support_count=100,support_fraction_of_sample=.25,
                       support_angular_coverage_degrees=359,orthogonal_residuals={"rms":.01},
                       circle=dict(center=[x,y,0],normal=[0,0,1],radius=2))
                  for i,(x,y) in enumerate([(-10,-10),(10,-10),(10,10),(-10,10)])]
    return dict(type="circle_discovery",coordinate_space="global",units="native",source_cloud_id=42,
                sample_count=400,candidate_count=4,candidates=candidates,
                region_sample_truncated=True,region_match_count=4000,region_sample_count=400,
                sampling_warning="bounded sample")


def native(points=None):
    if points is None:
        points = [[x + 2*np.cos(t),y+2*np.sin(t),0] for x,y in [(-10,-10),(10,-10),(10,10),(-10,10)]
                  for t in np.linspace(0,2*np.pi,120,endpoint=False)]
    records = [dict(point_index=i,position_global=p,position_native_local=p) for i,p in enumerate(points)]
    return dict(cloud_id=42,coordinate_space="global",returned_count=len(records),matched_count=len(records),
                truncated=False,sample_strategy="all_matches",points=records)


def body(result):
    assert isinstance(result,list),result
    return json.loads(result[0].text)


def is_error(result):
    assert isinstance(result,types.CallToolResult)
    assert result.isError is True


def test_offline_no_connection_preserves_input_and_provenance():
    snapshot = circles_snapshot(); before = deepcopy(snapshot)
    with patch.object(server,"live_request") as request:
        r = body(server.handle_analyze_hole_candidates(dict(**CONFIG,circle_discovery=snapshot)))
    request.assert_not_called()
    assert snapshot == before
    assert not r["live_sample_acquired"] and not r["scene_freshness_guaranteed"]
    assert r["input_provenance"]["sampling_warning"] == "bounded sample"
    assert r["input_provenance"]["region_match_count"] == 4000
    assert r["candidate_count"] == 4


def test_actual_discovery_math_via_native_boundary():
    fixture = native(); before = deepcopy(fixture)
    with patch.object(server,"live_request",return_value=fixture) as request:
        r = body(server.handle_discover_live_hole_candidates(LIVE))
    request.assert_called_once_with("cloud.region_query",{
        "cloud_id":42,"region":LIVE["region"],"coordinate_space":"global","max_points":1000,
    },timeout=300.0)
    assert fixture == before
    assert r["candidate_count"] == 4
    p, = r["diameter_groups"][0]["layout_candidates"]
    assert p["pitch_circle_diameter"] == pytest.approx(20*np.sqrt(2),abs=1e-5)
    assert r["live_sample_acquired"] and r["scene_mutations_requested"] is False
    assert '"points"' not in json.dumps(r)
    with patch.object(server,"live_request",return_value=fixture):
        assert r == body(server.handle_discover_live_hole_candidates(LIVE))


def test_empty_region_is_not_invented_feature():
    with patch.object(server,"live_request",return_value=native([])):
        r = body(server.handle_discover_live_hole_candidates(LIVE))
    assert r["candidate_count"] == 0 and r["input_candidate_count"] == 0
    assert r["input_provenance"]["region_sample_count"] == 0


@pytest.mark.parametrize("key,value", [
    ("coordinate_space","native_local"),("coordinate_space",None),("units","mm"),
    ("type","cylinder_discovery"),("candidate_count",3),("sample_count",399),
    ("source_cloud_id",True),
])
def test_offline_wrong_frame_counts_and_identity_rejected(key,value):
    d = circles_snapshot();d[key]=value
    with patch.object(server,"live_request") as request:
        is_error(server.handle_analyze_hole_candidates(dict(**CONFIG,circle_discovery=d)))
    request.assert_not_called()


@pytest.mark.parametrize("key,value", [
    ("min_radius",3),("distance_threshold",0),("cloud_id",True),("max_circles",17),
    ("iterations",2001),("iterations",5.5),("sample_limit",20001),
    ("face_normal",[0,0,0]),("spacing_tolerance",float("nan")),
    ("min_support_count",1001),("min_support_fraction",0),
    ("region",{"type":"box","min":[0,0,0],"max":[0,0,0]}),
    ("region",{"type":"slab","origin":[0,0,0],"normal":[0,0,0],"half_thickness":1}),
    ("region",{"type":"sphere","center":[0,0,0],"radius":float("inf")}),
])
def test_invalid_live_input_rejected_before_io(key,value):
    with patch.object(server,"live_request") as request:
        is_error(server.handle_discover_live_hole_candidates({**LIVE,key:value}))
    request.assert_not_called()


@pytest.mark.parametrize("key,value", [
    ("cloud_id",43),("coordinate_space","native_local"),("returned_count",200),
    ("matched_count",100),("truncated",True),("truncated","false"),("points",None),
])
def test_malformed_native_metadata_errors_no_mutation_requests(key,value):
    fixture = native();fixture[key]=value
    with patch.object(server,"live_request",return_value=fixture) as request:
        is_error(server.handle_discover_live_hole_candidates(LIVE))
    assert [c.args[0] for c in request.call_args_list] == ["cloud.region_query"]


def test_truncation_is_preserved():
    fixture = native([])
    fixture.update(matched_count=50,truncated=True)
    with patch.object(server,"live_request",return_value=fixture):
        r = body(server.handle_discover_live_hole_candidates(LIVE))
    assert r["input_provenance"]["region_sample_truncated"]
    assert "not exhaustive" in r["input_provenance"]["sampling_warning"]


def test_tools_registered_read_only_and_dispatchable():
    tools = {t.name:t for t in server.TOOLS}
    for name in ("analyze_hole_candidates","discover_live_hole_candidates"):
        assert tools[name].annotations.readOnlyHint
        assert not tools[name].annotations.destructiveHint
    result = asyncio.run(server.call_tool("analyze_hole_candidates",dict(**CONFIG,circle_discovery=circles_snapshot())))
    assert body(result)["candidate_count"] == 4


def test_sdk_wrapper_preserves_error_result():
    request = types.CallToolRequest(params=types.CallToolRequestParams(
        name="discover_live_hole_candidates", arguments={**LIVE,"spacing_tolerance":-1}))
    handler = server.server.request_handlers[types.CallToolRequest]
    with patch.object(server,"live_request") as native_request:
        result = asyncio.run(handler(request))
    is_error(result.root)
    native_request.assert_not_called()


def test_workflow_capability_distinguishes_native_and_python_versions():
    with patch.object(server,"live_request",return_value={
        "plugin_version":"0.12.0","workflow_revision":8,"region_query":{"available":True}}):
        r = body(server.handle_get_live_workflow_capabilities({}))
    assert r["plugin_version"] == "0.12.0"
    assert r["python_hole_patterns"]["version"] == "0.13.0"
    assert r["python_hole_patterns"]["native_rebuild_required"] is False
