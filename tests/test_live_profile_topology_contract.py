from __future__ import annotations

import json
import math
from unittest.mock import patch

from mcp.types import CallToolResult
import numpy as np

from cloudcompare_mcp import server


def circle(radius, count):
    theta = np.linspace(0, 2 * math.pi, count, endpoint=False)
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))


def rectangle(width=20.0, height=14.0, spacing=0.5):
    vertices = np.asarray(
        [
            [-width / 2, -height / 2],
            [width / 2, -height / 2],
            [width / 2, height / 2],
            [-width / 2, height / 2],
        ],
        dtype=float,
    )
    output = []
    for index in range(4):
        a = vertices[index]
        b = vertices[(index + 1) % 4]
        count = int(math.ceil(np.linalg.norm(b - a) / spacing))
        for t in np.linspace(0, 1, count, endpoint=False):
            output.append(a * (1 - t) + b * t)
    return np.asarray(output)


def boundary_xyz():
    uv = np.vstack((rectangle(), circle(2.5, 48)))
    rng = np.random.default_rng(15300)
    uv = uv[rng.permutation(len(uv))]
    return np.column_stack((uv, np.zeros(len(uv))))


def region_response(*, truncated=False):
    points = boundary_xyz()
    sample = [
        {"point_index": int(index), "position_global": row.astype(float).tolist()}
        for index, row in enumerate(points)
    ]
    matched = len(sample) + (5 if truncated else 0)
    return {
        "cloud_id": 91,
        "cloud_name": "boundary-outline",
        "coordinate_space": "global",
        "matched_count": matched,
        "returned_count": len(sample),
        "truncated": truncated,
        "sample_strategy": "all_matches" if not truncated else "deterministic_reservoir",
        "source_global_shift": [1234.5, -6789.25, 100000.125],
        "source_global_scale": 2.5,
        "points": sample,
    }


def body(result):
    return json.loads(result[0].text)


def base_args():
    return {
        "cloud_id": 91,
        "origin": [0.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "half_thickness": 0.001,
        "boundary_samples_only": True,
        "max_edge_length": 0.9,
        "fit_tolerance": 1e-7,
        "angular_tolerance_degrees": 0.2,
        "sample_limit": 2048,
    }


def test_live_topology_uses_region_query_and_preserves_bookkeeping():
    with patch.object(server, "live_request", return_value=region_response()) as native:
        parsed = body(server.handle_reconstruct_live_section_topology(base_args()))

    assert parsed["type"] == "live_cad_section_profile_topology"
    assert parsed["loop_count"] == 2
    assert [loop["role_candidate"] for loop in parsed["loops"]] == ["outer", "hole"]
    assert parsed["live_connection_used"] is True
    assert parsed["scene_mutations_requested"] is False
    assert parsed["source_geometry_preserved"] is True
    assert parsed["source_cloud_id"] == 91
    assert parsed["source_cloud_name"] == "boundary-outline"
    assert parsed["source_coordinate_bookkeeping"] == {
        "query_coordinate_space": "global",
        "global_shift": [1234.5, -6789.25, 100000.125],
        "global_scale": 2.5,
    }
    assert parsed["acquisition"]["boundary_samples_asserted_by_caller"] is True
    assert parsed["acquisition"]["sample_truncated"] is False
    assert parsed["acquisition"]["raw_points_returned"] is False
    dumped = json.dumps(parsed)
    assert "position_global" not in dumped
    assert "points_uv" not in dumped

    native.assert_called_once()
    method, params = native.call_args.args[:2]
    assert method == "cloud.region_query"
    assert params["cloud_id"] == 91
    assert params["coordinate_space"] == "global"
    assert params["region"]["type"] == "slab"
    assert params["max_points"] == 2048


def test_live_topology_rejects_boundary_assumption_false_before_io():
    args = base_args()
    args["boundary_samples_only"] = False
    with patch.object(server, "live_request") as native:
        result = server.handle_reconstruct_live_section_topology(args)
    native.assert_not_called()
    assert isinstance(result, CallToolResult) and result.isError
    assert "boundary_samples_only=true" in result.content[0].text


def test_live_topology_rejects_truncated_acquisition():
    with patch.object(server, "live_request", return_value=region_response(truncated=True)):
        result = server.handle_reconstruct_live_section_topology(base_args())
    assert isinstance(result, CallToolResult) and result.isError
    assert "complete slab sample" in result.content[0].text


def test_live_topology_invalid_threshold_fails_before_io():
    args = base_args()
    args["max_edge_length"] = 0.0
    with patch.object(server, "live_request") as native:
        result = server.handle_reconstruct_live_section_topology(args)
    native.assert_not_called()
    assert isinstance(result, CallToolResult) and result.isError
    assert "max_edge_length" in result.content[0].text


def test_live_topology_rejects_non_global_native_response():
    response = region_response()
    response["coordinate_space"] = "native_local"
    with patch.object(server, "live_request", return_value=response):
        result = server.handle_reconstruct_live_section_topology(base_args())
    assert isinstance(result, CallToolResult) and result.isError
    assert "expected global" in result.content[0].text


def test_live_topology_rejects_malformed_shift_scale():
    cases = [
        ("source_global_shift", [0.0, 0.0], "malformed"),
        ("source_global_shift", [0.0, float("nan"), 0.0], "non-finite"),
        ("source_global_scale", 0.0, "finite and positive"),
    ]
    for field, value, match in cases:
        response = region_response()
        response[field] = value
        with patch.object(server, "live_request", return_value=response):
            result = server.handle_reconstruct_live_section_topology(base_args())
        assert isinstance(result, CallToolResult) and result.isError
        assert match in result.content[0].text
