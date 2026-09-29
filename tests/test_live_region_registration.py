from __future__ import annotations

import json
from unittest.mock import patch

from mcp.types import CallToolResult

from cloudcompare_mcp import server


def _region(centroid, matched=25):
    return {
        "matched_count": matched,
        "returned_count": 0,
        "sample_strategy": "summary_only",
        "centroid_query_space": list(centroid),
        "points": [],
        "source_geometry_preserved": True,
    }


def _body(result):
    return json.loads(result[0].text)


def test_asymmetric_region_centroids_drive_proper_rigid_correspondences():
    data = [
        [0.0, 0.0, 0.0],
        [4.0, 0.0, 0.0],
        [0.0, 2.0, 1.0],
    ]
    # Proper +90 degree Z rotation followed by translation [10, 5, 3].
    model = [
        [10.0, 5.0, 3.0],
        [10.0, 9.0, 3.0],
        [8.0, 5.0, 4.0],
    ]
    region_results = []
    for a, b in zip(data, model):
        region_results.extend([_region(a), _region(b)])
    registration = {
        "transformation_available": True,
        "rotation_determinant": 1.0,
        "rotation_orthogonality_max_error": 1e-12,
        "scale": 1.0,
        "proper_rotation": True,
        "unit_scale": True,
        "rigid_transform_valid": True,
        "proposal_rejected": False,
        "pair_residuals_global_native": {"rms": 0.0},
    }

    calls = []

    def request(method, params, **kwargs):
        calls.append((method, params, kwargs))
        if method == "cloud.region_query":
            return region_results.pop(0)
        if method == "cloud.register_point_pairs":
            return registration
        raise AssertionError(method)

    pairs = [
        {
            "label": f"feature_{i + 1}",
            "data_region": {"type": "sphere", "center": a, "radius": 0.5},
            "model_region": {"type": "sphere", "center": b, "radius": 0.5},
        }
        for i, (a, b) in enumerate(zip(data, model))
    ]

    with patch.object(server, "live_request", side_effect=request):
        result = server.handle_register_live_regions(
            {
                "data_id": 11,
                "model_id": 22,
                "region_pairs": pairs,
                "preview_only": True,
            }
        )

    body = _body(result)
    assert body["constraint_mode"] == "paired_region_centroids"
    assert body["constraint_pair_count"] == 3
    assert body["whole_cloud_icp_used"] is False
    assert body["rotation_determinant"] == 1.0
    assert body["proposal_rejected"] is False

    registration_call = calls[-1]
    assert registration_call[0] == "cloud.register_point_pairs"
    assert registration_call[1]["data_points"] == data
    assert registration_call[1]["model_points"] == model
    assert registration_call[1]["coordinate_space"] == "global"
    assert registration_call[1]["preview_only"] is True
    assert registration_call[2]["timeout"] == 300.0

    region_calls = [call for call in calls if call[0] == "cloud.region_query"]
    assert len(region_calls) == 6
    assert all(call[1]["max_points"] == 0 for call in region_calls)


def test_region_registration_refuses_weak_feature_before_solver():
    weak = _region([0, 0, 0], matched=2)
    with patch.object(server, "live_request", return_value=weak) as request:
        result = server.handle_register_live_regions(
            {
                "data_id": 1,
                "model_id": 2,
                "region_pairs": [
                    {
                        "data_region": {"type": "sphere", "center": [0, 0, 0], "radius": 1},
                        "model_region": {"type": "sphere", "center": [1, 0, 0], "radius": 1},
                    }
                ] * 3,
                "minimum_points_per_region": 3,
            }
        )

    assert isinstance(result, CallToolResult)
    assert result.isError
    assert "matched only 2 points" in result.content[0].text
    assert all(call.args[0] == "cloud.region_query" for call in request.call_args_list)


def test_region_registration_tool_is_discoverable():
    names = {tool.name for tool in server.TOOLS}
    assert "register_live_regions" in names
