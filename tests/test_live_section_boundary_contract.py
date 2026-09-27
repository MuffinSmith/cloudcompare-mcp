from __future__ import annotations

import json
import math
from unittest.mock import patch

from mcp.types import CallToolResult
import numpy as np

from cloudcompare_mcp import server


def filled_uv(spacing: float = 0.2) -> np.ndarray:
    xs = np.arange(-10.0, 10.0 + spacing * 0.25, spacing)
    ys = np.arange(-8.0, 8.0 + spacing * 0.25, spacing)
    output = []
    for y in ys:
        for x in xs:
            if not (
                -10 <= x <= 10
                and -8 <= y <= 8
                and not (-4 < x < 4 and 2 < y <= 8)
            ):
                continue
            r = math.hypot(float(x), float(y) + 2.0)
            if r < 2.5 and r > 0.8:
                continue
            output.append((float(x), float(y)))
    result = np.asarray(output, dtype=np.float64)
    return result[np.random.default_rng(15701).permutation(len(result))]


def region_response(*, truncated: bool = False, layered: bool = False):
    uv = filled_uv()
    z = np.zeros(len(uv), dtype=np.float64)
    if layered:
        z[::2] = -0.45
        z[1::2] = 0.45
    xyz = np.column_stack((uv, z))
    sample = [
        {
            "point_index": int(index),
            "position_global": row.astype(float).tolist(),
        }
        for index, row in enumerate(xyz)
    ]
    matched = len(sample) + (10 if truncated else 0)
    return {
        "cloud_id": 101,
        "cloud_name": "filled-section",
        "coordinate_space": "global",
        "matched_count": matched,
        "returned_count": len(sample),
        "truncated": truncated,
        "sample_strategy": (
            "all_matches" if not truncated else "deterministic_reservoir"
        ),
        "source_global_shift": [1234.5, -6789.25, 100000.125],
        "source_global_scale": 2.5,
        "points": sample,
    }


def body(result):
    return json.loads(result[0].text)


def args():
    return {
        "cloud_id": 101,
        "origin": [0.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "half_thickness": 0.5,
        "sample_limit": 20000,
        "cell_size": 0.5,
        "min_cell_support": 1,
        "min_component_cells": 2,
        "max_cells": 20000,
        "max_boundary_points": 2048,
        "max_edge_length": 0.95,
        "fit_tolerance": 0.35,
        "angular_tolerance_degrees": 2.0,
        "max_loops": 8,
        "require_grid_stability": True,
    }


def test_live_filled_section_uses_complete_region_and_preserves_bookkeeping():
    response = region_response()
    with patch.object(server, "live_request", return_value=response) as native:
        parsed = body(server.handle_reconstruct_live_filled_section_profile(args()))

    assert parsed["type"] == "live_cad_filled_section_profile"
    assert parsed["topology"]["loop_count"] == 3
    assert [loop["role_candidate"] for loop in parsed["topology"]["loops"]] == [
        "outer",
        "hole",
        "island",
    ]
    assert parsed["live_connection_used"] is True
    assert parsed["scene_mutations_requested"] is False
    assert parsed["source_geometry_preserved"] is True
    assert parsed["source_cloud_id"] == 101
    assert parsed["source_cloud_name"] == "filled-section"
    assert parsed["source_coordinate_bookkeeping"] == {
        "query_coordinate_space": "global",
        "global_shift": [1234.5, -6789.25, 100000.125],
        "global_scale": 2.5,
    }
    assert parsed["acquisition"]["matched_count"] == len(response["points"])
    assert parsed["acquisition"]["sampled_count"] == len(response["points"])
    assert parsed["acquisition"]["sample_truncated"] is False
    assert parsed["projection_depth_diagnostic"][
        "possible_multiple_projected_surfaces"
    ] is False
    dumped = json.dumps(parsed)
    assert "position_global" not in dumped
    assert "points_uv" not in dumped
    assert "signed_offsets" not in dumped

    native.assert_called_once()
    method, params = native.call_args.args[:2]
    assert method == "cloud.region_query"
    assert params["cloud_id"] == 101
    assert params["coordinate_space"] == "global"
    assert params["region"]["type"] == "slab"
    assert params["max_points"] == 20000


def test_live_filled_section_rejects_truncated_acquisition():
    with patch.object(
        server,
        "live_request",
        return_value=region_response(truncated=True),
    ):
        result = server.handle_reconstruct_live_filled_section_profile(args())
    assert isinstance(result, CallToolResult) and result.isError
    assert "complete slab acquisition" in result.content[0].text


def test_live_filled_section_rejects_layered_projection():
    with patch.object(
        server,
        "live_request",
        return_value=region_response(layered=True),
    ):
        result = server.handle_reconstruct_live_filled_section_profile(args())
    assert isinstance(result, CallToolResult) and result.isError
    assert "multiple or thick projected surfaces" in result.content[0].text


def test_live_filled_section_invalid_threshold_fails_before_io():
    bad = args()
    bad["cell_size"] = 0.0
    with patch.object(server, "live_request") as native:
        result = server.handle_reconstruct_live_filled_section_profile(bad)
    native.assert_not_called()
    assert isinstance(result, CallToolResult) and result.isError
    assert "cell_size" in result.content[0].text


def test_live_filled_section_rejects_non_global_response():
    response = region_response()
    response["coordinate_space"] = "native_local"
    with patch.object(server, "live_request", return_value=response):
        result = server.handle_reconstruct_live_filled_section_profile(args())
    assert isinstance(result, CallToolResult) and result.isError
    assert "expected global" in result.content[0].text


def test_live_filled_section_rejects_malformed_shift_scale():
    cases = [
        ("source_global_shift", [0.0, 0.0], "malformed"),
        ("source_global_shift", [0.0, float("nan"), 0.0], "non-finite"),
        ("source_global_scale", 0.0, "finite and positive"),
    ]
    for field, value, match in cases:
        response = region_response()
        response[field] = value
        with patch.object(server, "live_request", return_value=response):
            result = server.handle_reconstruct_live_filled_section_profile(args())
        assert isinstance(result, CallToolResult) and result.isError
        assert match in result.content[0].text
