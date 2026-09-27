"""Real MCP schemas, dispatch, stdio; native geometry is not exercised here."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import jsonschema
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import pytest

from cloudcompare_mcp import server
from test_datum_relationships import feature

FEATURES = [feature("base", "plane"), feature("edge", "line", direction=(1, 0, 0)),
            feature("bore", "cylinder", (3, 4, 5))]
ANALYSIS = dict(features=FEATURES, frame_id="fixture-global", distance_tolerance=.01, angular_tolerance_degrees=.5)
DATUM = dict(features=FEATURES, frame_id="fixture-global", distance_tolerance=.01,
             primary_plane_id="base", secondary_feature_id="edge", origin_feature_id="bore")
TOOLS = [("analyze_feature_relationships", ANALYSIS), ("build_live_datum_frame", DATUM)]


def body(result):
    return json.loads(result[0].text)


@pytest.mark.parametrize("name,args", TOOLS)
def test_schema_registration_dispatch_and_no_io(name, args):
    before = deepcopy(args)
    tools = asyncio.run(server.list_tools())
    assert len({t.name for t in tools}) == len(tools)
    tool, = [t for t in tools if t.name == name]
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    assert not tool.annotations.destructiveHint and not tool.annotations.openWorldHint
    with patch.object(server, "live_request", side_effect=AssertionError("Unexpected native request")) as request:
        with patch.object(socket, "create_connection", side_effect=AssertionError("Unexpected socket")):
            result = body(asyncio.run(server.call_tool(name, deepcopy(args))))
    request.assert_not_called()
    assert args == before
    assert not result["live_connection_used"] and not result["scene_mutations_requested"]
    assert not result["manufacturing_intent_confirmed"] and not result["user_accepted"]


@pytest.mark.parametrize("name,args", TOOLS)
@pytest.mark.parametrize("change", ["unknown_argument", "bad_space", "bad_units", "missing", "nan", "duplicate", "bool"])
def test_invalid_requests_are_mcp_errors_before_io(name, args, change):
    args = deepcopy(args)
    if change == "unknown_argument": args["surprise"] = 1
    if change == "bad_space": args["features"][0]["observation"]["coordinate_space"] = "native_local"
    if change == "bad_units": args["features"][0]["observation"]["units"] = "mm"
    if change == "missing": args.pop("frame_id")
    if change == "nan": args["distance_tolerance"] = float("nan")
    if change == "bool": args["distance_tolerance"] = True
    if change == "duplicate": args["features"][1]["id"] = "base"
    with patch.object(server, "live_request") as request:
        result = asyncio.run(server.call_tool(name, args))
    request.assert_not_called()
    assert isinstance(result, types.CallToolResult) and result.isError
    assert json.loads(result.content[0].text)["error"]


@pytest.mark.parametrize("name,args", TOOLS)
def test_low_level_mcp_wrapper(name, args):
    request = types.CallToolRequest(params=types.CallToolRequestParams(name=name, arguments=args))
    handler = server.server.request_handlers[types.CallToolRequest]
    with patch.object(server, "live_request") as native:
        wrapped = asyncio.run(handler(request))
    native.assert_not_called()
    assert not wrapped.root.isError
    assert json.loads(wrapped.root.content[0].text)["units"] == "native"


def test_capabilities_describe_python_only_surface_without_breaking_existing():
    with patch.object(server, "live_request", return_value={"plugin_version": "0.12.0", "workflow_revision": 8}):
        result = body(server.handle_get_live_workflow_capabilities({}))
    assert result["python_cad_datums"]["version"] == "0.14.0"
    assert not result["python_cad_datums"]["native_rebuild_required"]
    assert result["python_hole_patterns"]["version"] == "0.13.0"
    assert result["plugin_version"] == "0.12.0" and result["workflow_revision"] == 8


def test_real_stdio_roundtrip_without_any_bridge_configuration():
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
           "CLOUDCOMPARE_MCP_PORT": "intentionally-invalid-no-native-io-allowed"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "cloudcompare_mcp.server"], env=env)
    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert {name for name, _ in TOOLS} <= {t.name for t in listing.tools}
                for name, args in TOOLS:
                    result = await session.call_tool(name, args)
                    assert not result.isError
                    assert not json.loads(result.content[0].text)["live_connection_used"]
                bad = deepcopy(DATUM)
                bad["features"][1]["observation"]["direction"] = [0, 0, 1]
                result = await session.call_tool("build_live_datum_frame", bad)
                assert result.isError
                assert "degenerate" in result.content[0].text
    asyncio.run(asyncio.wait_for(run(), timeout=60))
