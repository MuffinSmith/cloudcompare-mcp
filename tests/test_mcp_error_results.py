from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from mcp import types as mcp_types
from mcp.types import CallToolResult

from cloudcompare_mcp import server
from cloudcompare_mcp.live import LiveBridgeError


def _error_message(result: CallToolResult) -> str:
    assert len(result.content) == 1
    block = result.content[0]
    payload = json.loads(block.text)
    return payload["error"]


def test_err_marks_mcp_tool_result_as_error() -> None:
    result = server._err("native validation failed")

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert _error_message(result) == "native validation failed"


def test_live_bridge_validation_failure_is_mcp_error() -> None:
    with patch.object(
        server,
        "live_request",
        side_effect=LiveBridgeError("cloud.register_icp requires different data and model entities"),
    ):
        result = server.handle_register_live_icp({"data_id": 520, "model_id": 520})

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert _error_message(result) == "cloud.register_icp requires different data and model entities"


def test_call_tool_preserves_failed_result() -> None:
    failed = server._err("Destination group 999 was not found")

    with patch.object(server, "handle_register_live_icp", return_value=failed):
        result = asyncio.run(
            server.call_tool(
                "register_live_icp",
                {"data_id": 10, "model_id": 20},
            )
        )

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert _error_message(result) == "Destination group 999 was not found"


def test_unknown_tool_is_reported_as_mcp_tool_error() -> None:
    result = asyncio.run(server.call_tool("definitely_not_a_tool", {}))

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert _error_message(result) == "Unknown tool: definitely_not_a_tool"


def test_low_level_server_wrapper_preserves_is_error() -> None:
    failed = server._err("cloud.register_icp requires different data and model entities")
    request = mcp_types.CallToolRequest(
        params=mcp_types.CallToolRequestParams(
            name="register_live_icp",
            arguments={"data_id": 520, "model_id": 520},
        )
    )
    handler = server.server.request_handlers[mcp_types.CallToolRequest]

    with patch.object(server, "handle_register_live_icp", return_value=failed):
        wrapped = asyncio.run(handler(request))

    result = wrapped.root
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert _error_message(result) == "cloud.register_icp requires different data and model entities"
