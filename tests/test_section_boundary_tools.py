from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import numpy as np

from cloudcompare_mcp import server


def filled_points(spacing: float = 0.2) -> np.ndarray:
    xs = np.arange(-10.0, 10.0 + spacing * 0.25, spacing)
    ys = np.arange(-8.0, 8.0 + spacing * 0.25, spacing)
    output = []
    for y in ys:
        for x in xs:
            in_outer = (
                -10 <= x <= 10
                and -8 <= y <= 8
                and not (-4 < x < 4 and 2 < y <= 8)
            )
            if not in_outer:
                continue
            r = math.hypot(float(x), float(y) + 2.0)
            if r < 2.5 and r > 0.8:
                continue
            output.append((float(x), float(y)))
    return np.asarray(output, dtype=np.float64)


def section_fixture():
    points = filled_points()
    points = points[np.random.default_rng(15601).permutation(len(points))]
    return {
        "coordinate_space": "section_uv",
        "units": "native",
        "frame_id": "filled-section-fixture",
        "origin_global": [100.0, -200.0, 300.0],
        "basis_u": [1.0, 0.0, 0.0],
        "basis_v": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "source_cloud_id": 77,
        "global_shift": [1000.0, -2000.0, 3000.0],
        "global_scale": 2.5,
        "provenance": {"source": "synthetic-filled-section"},
        "points_uv": points.tolist(),
    }


def body(result):
    return json.loads(result[0].text)


def extract_args():
    return {
        "section": section_fixture(),
        "cell_size": 0.5,
        "min_cell_support": 1,
        "min_component_cells": 2,
        "max_cells": 20000,
        "max_boundary_points": 2048,
        "check_grid_origin_sensitivity": True,
    }


def reconstruct_args():
    args = extract_args()
    args.pop("check_grid_origin_sensitivity")
    args.update(
        {
            "max_edge_length": 0.95,
            "fit_tolerance": 0.35,
            "angular_tolerance_degrees": 2.0,
            "max_loops": 8,
            "require_grid_stability": True,
        }
    )
    return args


def test_new_tool_schemas_and_capabilities_are_registered():
    tools = asyncio.run(server.list_tools())
    by_name = {item.name: item for item in tools}
    for name in (
        "extract_section_boundary_evidence",
        "reconstruct_filled_section_profile",
        "reconstruct_live_filled_section_profile",
    ):
        assert name in by_name
        jsonschema.Draft202012Validator.check_schema(by_name[name].inputSchema)
        assert by_name[name].annotations.readOnlyHint
        assert by_name[name].annotations.idempotentHint

    with patch.object(
        server,
        "live_request",
        return_value={
            "region_query": {"available": True},
            "fit_overlays": {"available": False},
        },
    ):
        caps = body(server.handle_get_live_workflow_capabilities({}))
    profile = caps["python_cad_profiles"]
    assert profile["version"] == "0.15.2"
    assert profile["filled_section_boundary_version"] == "0.15.2"
    assert profile["filled_section_boundary_inference"] is True
    assert profile["native_rebuild_required"] is False


def test_snapshot_boundary_evidence_uses_no_live_io_and_is_compact():
    args = extract_args()
    before = deepcopy(args)
    with patch.object(
        server, "live_request", side_effect=AssertionError("unexpected native I/O")
    ) as native:
        with patch.object(
            socket, "create_connection", side_effect=AssertionError("unexpected socket")
        ):
            parsed = body(
                asyncio.run(
                    server.call_tool(
                        "extract_section_boundary_evidence",
                        deepcopy(args),
                    )
                )
            )
    native.assert_not_called()
    assert args == before
    assert parsed["connected_contour_count"] == 3
    assert parsed["section_frame"]["global_scale"] == 2.5
    assert parsed["live_connection_used"] is False
    assert parsed["scene_mutations_requested"] is False
    assert parsed["source_geometry_preserved"] is True
    assert "points_uv" not in json.dumps(parsed)


def test_snapshot_composite_returns_outer_hole_island_candidates():
    parsed = body(
        asyncio.run(
            server.call_tool(
                "reconstruct_filled_section_profile",
                reconstruct_args(),
            )
        )
    )
    assert parsed["topology"]["loop_count"] == 3
    assert [loop["role_candidate"] for loop in parsed["topology"]["loops"]] == [
        "outer",
        "hole",
        "island",
    ]
    assert parsed["state"] == "inferred_candidate"
    assert parsed["manufacturing_intent_confirmed"] is False
    assert parsed["section_frame"]["global_shift"] == [1000.0, -2000.0, 3000.0]
    assert "points_uv" not in json.dumps(parsed)


def test_snapshot_rejects_nonfinite_and_too_large_cell_size():
    args = extract_args()
    args["section"]["points_uv"][0][0] = float("nan")
    result = asyncio.run(server.call_tool("extract_section_boundary_evidence", args))
    assert result.isError

    args = extract_args()
    args["cell_size"] = 1000.0
    result = asyncio.run(server.call_tool("extract_section_boundary_evidence", args))
    assert result.isError
    assert "Too few supported occupied cells" in result.content[0].text


def test_real_stdio_snapshot_roundtrip_without_bridge():
    args = extract_args()
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "CLOUDCOMPARE_MCP_PORT": "invalid-filled-section-no-host",
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cloudcompare_mcp.server"],
        env=env,
    )

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                names = {tool.name for tool in listing.tools}
                assert "extract_section_boundary_evidence" in names
                assert "reconstruct_filled_section_profile" in names
                assert "reconstruct_live_filled_section_profile" in names
                result = await session.call_tool(
                    "extract_section_boundary_evidence",
                    args,
                )
                assert not result.isError
                parsed = json.loads(result.content[0].text)
                assert parsed["connected_contour_count"] == 3

    asyncio.run(asyncio.wait_for(run(), timeout=60))
