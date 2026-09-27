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
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.profile_tools import reconstruct_section_profile_snapshot


def section_fixture():
    theta = np.linspace(0, 2 * math.pi, 48, endpoint=False)
    return {
        "coordinate_space": "section_uv",
        "units": "native",
        "frame_id": "fixture-section",
        "origin_global": [100, -200, 300],
        "basis_u": [1, 0, 0],
        "basis_v": [0, 1, 0],
        "normal": [0, 0, 1],
        "source_cloud_id": 42,
        "global_shift": [1000, -2000, 3000],
        "global_scale": 2.5,
        "provenance": {"source": "synthetic"},
        "points_uv": np.column_stack((5*np.cos(theta), 5*np.sin(theta))).tolist(),
    }


def body(result):
    return json.loads(result[0].text)


def test_snapshot_schema_registration_dispatch_and_no_io():
    args = {"section": section_fixture(), "closed": True, "fit_tolerance": 1e-8,
            "ordering_method": "polar_closed_loop"}
    before = deepcopy(args)
    tools = asyncio.run(server.list_tools())
    tool, = [t for t in tools if t.name == "reconstruct_section_profile"]
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    with patch.object(server, "live_request", side_effect=AssertionError("unexpected native I/O")) as native:
        with patch.object(socket, "create_connection", side_effect=AssertionError("unexpected socket")):
            result = body(asyncio.run(server.call_tool("reconstruct_section_profile", deepcopy(args))))
    native.assert_not_called()
    assert args == before
    assert result["live_connection_used"] is False
    assert result["scene_mutations_requested"] is False
    assert result["section_frame"]["global_scale"] == 2.5
    assert result["section_frame"]["global_shift"] == [1000, -2000, 3000]
    assert result["profile_candidates"][0]["type"] == "circle_profile_candidate"


def test_snapshot_never_echoes_raw_points():
    result = reconstruct_section_profile_snapshot(
        section=section_fixture(), closed=True, fit_tolerance=1e-8,
        ordering_method="polar_closed_loop",
    )
    dumped = json.dumps(result)
    assert "points_uv" not in dumped
    assert result["raw_points_returned"] is False
    assert result["input_point_count"] == 48


@pytest.mark.parametrize("mutation,match", [
    (lambda s: s.update(coordinate_space="global"), "section_uv"),
    (lambda s: s.update(units="mm"), "native"),
    (lambda s: s.update(points_global=[[0,0,0]]), "raw 3D"),
    (lambda s: s.update(global_scale=0), "global_scale"),
])
def test_snapshot_invalid_envelope_is_error_before_io(mutation, match):
    section = section_fixture(); mutation(section)
    args = {"section": section, "closed": True, "fit_tolerance": 0.1}
    with patch.object(server, "live_request") as native:
        result = asyncio.run(server.call_tool("reconstruct_section_profile", args))
    native.assert_not_called()
    assert isinstance(result, types.CallToolResult) and result.isError
    assert match in result.content[0].text


def test_capabilities_include_profiles_without_native_version_change():
    with patch.object(server, "live_request", return_value={
        "plugin_version": "0.12.0", "workflow_revision": 8,
        "region_query": {"available": True, "region_types": ["slab"]},
    }):
        result = body(server.handle_get_live_workflow_capabilities({}))
    caps = result["python_cad_profiles"]
    assert caps["version"] == "0.15.0"
    assert caps["snapshot_profile_reconstruction"]
    assert caps["live_section_profile_reconstruction"]
    assert not caps["native_rebuild_required"]
    assert result["plugin_version"] == "0.12.0" and result["workflow_revision"] == 8


def test_real_stdio_snapshot_roundtrip_without_bridge():
    args = {"section": section_fixture(), "closed": True, "fit_tolerance": 1e-8,
            "ordering_method": "polar_closed_loop"}
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
           "CLOUDCOMPARE_MCP_PORT": "intentionally-invalid-profile-no-native-io"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "cloudcompare_mcp.server"], env=env)
    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert "reconstruct_section_profile" in {t.name for t in listing.tools}
                result = await session.call_tool("reconstruct_section_profile", args)
                assert not result.isError
                parsed = json.loads(result.content[0].text)
                assert parsed["live_connection_used"] is False
                bad = deepcopy(args); bad["section"]["units"] = "mm"
                result = await session.call_tool("reconstruct_section_profile", bad)
                assert result.isError
    asyncio.run(asyncio.wait_for(run(), timeout=60))
