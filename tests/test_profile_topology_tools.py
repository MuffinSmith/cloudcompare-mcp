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
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import numpy as np

from cloudcompare_mcp import server
from cloudcompare_mcp.profile_topology_tools import (
    reconstruct_section_topology_snapshot,
)


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


def section_fixture():
    points = np.vstack((rectangle(), circle(2.5, 48)))
    points = points[np.random.default_rng(15200).permutation(len(points))]
    return {
        "coordinate_space": "section_uv",
        "units": "native",
        "frame_id": "topology-fixture",
        "origin_global": [100.0, -200.0, 300.0],
        "basis_u": [1.0, 0.0, 0.0],
        "basis_v": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "source_cloud_id": 55,
        "global_shift": [1000.0, -2000.0, 3000.0],
        "global_scale": 2.5,
        "provenance": {"source": "synthetic-topology"},
        "points_uv": points.tolist(),
    }


def body(result):
    return json.loads(result[0].text)


def test_snapshot_schema_dispatch_no_io_and_compact_output():
    args = {
        "section": section_fixture(),
        "boundary_samples_only": True,
        "max_edge_length": 0.9,
        "fit_tolerance": 1e-7,
        "angular_tolerance_degrees": 0.2,
    }
    before = deepcopy(args)
    tools = asyncio.run(server.list_tools())
    tool, = [item for item in tools if item.name == "reconstruct_section_topology"]
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint

    with patch.object(
        server, "live_request", side_effect=AssertionError("unexpected native I/O")
    ) as native:
        with patch.object(
            socket, "create_connection", side_effect=AssertionError("unexpected socket")
        ):
            parsed = body(
                asyncio.run(
                    server.call_tool(
                        "reconstruct_section_topology",
                        deepcopy(args),
                    )
                )
            )
    native.assert_not_called()
    assert args == before
    assert parsed["live_connection_used"] is False
    assert parsed["scene_mutations_requested"] is False
    assert parsed["source_geometry_preserved"] is True
    assert parsed["loop_count"] == 2
    assert [loop["role_candidate"] for loop in parsed["loops"]] == ["outer", "hole"]
    assert parsed["section_frame"]["global_scale"] == 2.5
    assert parsed["section_frame"]["global_shift"] == [1000.0, -2000.0, 3000.0]
    dumped = json.dumps(parsed)
    assert "points_uv" not in dumped
    assert parsed["raw_points_returned"] is False


def test_boundary_assertion_is_required_before_io():
    args = {
        "section": section_fixture(),
        "boundary_samples_only": False,
        "max_edge_length": 0.9,
        "fit_tolerance": 1e-7,
    }
    with patch.object(server, "live_request") as native:
        result = asyncio.run(server.call_tool("reconstruct_section_topology", args))
    native.assert_not_called()
    assert isinstance(result, types.CallToolResult) and result.isError
    assert "boundary_samples_only=true" in result.content[0].text


def test_snapshot_preserves_candidate_not_accepted_semantics():
    parsed = reconstruct_section_topology_snapshot(
        section=section_fixture(),
        boundary_samples_only=True,
        max_edge_length=0.9,
        fit_tolerance=1e-7,
    )
    assert parsed["state"] == "inferred_candidate"
    assert parsed["topology_confirmed"] is False
    assert parsed["manufacturing_intent_confirmed"] is False
    assert parsed["user_accepted"] is False
    assert all(loop["state"] == "inferred_candidate" for loop in parsed["loops"])


def test_real_stdio_snapshot_roundtrip_without_bridge():
    args = {
        "section": section_fixture(),
        "boundary_samples_only": True,
        "max_edge_length": 0.9,
        "fit_tolerance": 1e-7,
    }
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "CLOUDCOMPARE_MCP_PORT": "invalid-profile-topology-no-host",
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
                assert "reconstruct_section_topology" in names
                assert "reconstruct_live_section_topology" in names
                result = await session.call_tool("reconstruct_section_topology", args)
                assert not result.isError
                parsed = json.loads(result.content[0].text)
                assert parsed["loop_count"] == 2
                bad = deepcopy(args)
                bad["boundary_samples_only"] = False
                result = await session.call_tool("reconstruct_section_topology", bad)
                assert result.isError

    asyncio.run(asyncio.wait_for(run(), timeout=60))
