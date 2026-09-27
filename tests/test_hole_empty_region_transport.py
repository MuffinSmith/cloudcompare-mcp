"""Real Python/MCP/TCP boundary regressions for the accepted native error contract.

The TCP peer replays native wire envelopes, not a CloudCompare host or geometry
implementation. Live Windows acceptance remains necessary. No live_request mock
is used, unlike the original successful-empty-response unit test.
"""
from contextlib import contextmanager
from copy import deepcopy
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import threading
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import pytest

from cloudcompare_mcp import server
from test_hole_tools import LIVE, body, native

NO_MATCH = "cloud.region_query selected no points"
NEAREST_NO_MATCH = "No point was found within nearest.max_distance"
EMPTY_REGIONS = [
    {"type": "box", "min": [100, 100, 100], "max": [101, 101, 101]},
    {"type": "sphere", "center": [100, 100, 100], "radius": 0.1},
    {"type": "slab", "origin": [0, 0, 100], "normal": [0, 0, 1], "half_thickness": 0.1},
    {"type": "nearest", "center": [100, 100, 100], "max_distance": 0.1},
]


@contextmanager
def wire_peer(monkeypatch, response):
    """Return one exact wire envelope; record requests and forbid hidden retries."""
    requests, errors = [], []
    stop = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(0.1)
        monkeypatch.setenv("CLOUDCOMPARE_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("CLOUDCOMPARE_MCP_PORT", str(listener.getsockname()[1]))
        monkeypatch.setenv("CLOUDCOMPARE_MCP_TIMEOUT", "2")
        monkeypatch.delenv("CLOUDCOMPARE_MCP_TOKEN", raising=False)

        def serve():
            while not stop.is_set():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                try:
                    with conn:
                        conn.settimeout(3)
                        with conn.makefile("rb") as stream:
                            requests.append(json.loads(stream.readline(65536)))
                        wire = response if isinstance(response, bytes) else (
                            json.dumps(response, allow_nan=False) + "\n").encode()
                        conn.sendall(wire)
                except Exception as exc:
                    errors.append(exc)
                    break

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            yield requests
        finally:
            stop.set()
            thread.join(timeout=5)
            assert not thread.is_alive()
            assert not errors


def error_envelope(message):
    return {"id": 1, "ok": False, "error": message}


def assert_empty(result, args, message):
    assert result["candidate_count"] == result["input_candidate_count"] == 0
    for key in ("candidates", "duplicates", "rejected", "diameter_groups",
                "center_spacings", "concentric_candidates"):
        assert result[key] == []
    assert result["source_cloud_id"] == args["cloud_id"]
    assert result["coordinate_space"] == "global" and result["units"] == "native"
    assert result["confirmed_holes"] is False
    assert result["scene_mutations_requested"] is False
    assert result["live_query_completed"] is True
    assert result["live_sample_acquired"] is False
    assert result["scene_freshness_guaranteed"] is False
    assert result["input_mode"] == "fresh_live_empty_region"
    provenance = result["input_provenance"]
    assert provenance["region"] == args["region"]
    assert provenance["region_match_count"] == provenance["region_sample_count"] == 0
    assert provenance["sample_count"] == 0
    assert provenance["region_sample_truncated"] is False
    assert provenance["region_sample_strategy"] is None
    assert provenance["empty_region_evidence"] == {
        "basis": "native_no_match_response", "native_error": message,
        "counts_derived_from_no_match_response": True,
        "source_frame_metadata_returned": False,
    }
    assert '"points"' not in json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("region", EMPTY_REGIONS, ids=["box", "sphere", "slab", "nearest"])
def test_native_no_match_wire_returns_empty_success(monkeypatch, region):
    args = {**LIVE, "region": region}
    before = deepcopy(args)
    message = NEAREST_NO_MATCH if region["type"] == "nearest" else NO_MATCH
    with wire_peer(monkeypatch, error_envelope(message)) as requests:
        with patch("cloudcompare_mcp.hole_tools.discover_circles") as fitting:
            result = body(server.handle_discover_live_hole_candidates(args))
    fitting.assert_not_called()
    assert_empty(result, args, message)
    assert args == before
    assert requests == [{"id": 1, "method": "cloud.region_query", "params": {
        "cloud_id": 42, "region": region, "coordinate_space": "global", "max_points": 1000,
    }}]


@pytest.mark.parametrize("message,region", [
    ("Entity not found: 42", EMPTY_REGIONS[0]),
    ("cloud.region_query requires a non-empty point cloud", EMPTY_REGIONS[0]),
    ("cloud.region_query requires a region object", EMPTY_REGIONS[0]),
    ("Unauthorized", EMPTY_REGIONS[0]),
    ("cloud.region_query could not inspect any source point", EMPTY_REGIONS[3]),
    ("cloud.region_grid selected no points", EMPTY_REGIONS[0]),
    (NO_MATCH + " (unknown condition)", EMPTY_REGIONS[0]),
    (NEAREST_NO_MATCH, EMPTY_REGIONS[0]),
    (NO_MATCH, EMPTY_REGIONS[3]),
    (NEAREST_NO_MATCH, {"type": "nearest", "center": [100, 100, 100]}),
])
def test_other_native_errors_are_not_hidden(monkeypatch, message, region):
    with wire_peer(monkeypatch, error_envelope(message)) as requests:
        result = server.handle_discover_live_hole_candidates({**LIVE, "region": region})
    assert isinstance(result, types.CallToolResult) and result.isError
    assert json.loads(result.content[0].text)["error"] == message
    assert len(requests) == 1


def test_malformed_wire_is_not_empty_success(monkeypatch):
    with wire_peer(monkeypatch, b'not JSON\n') as requests:
        result = server.handle_discover_live_hole_candidates(LIVE)
    assert isinstance(result, types.CallToolResult) and result.isError
    assert "invalid JSON" in result.content[0].text
    assert len(requests) == 1


def test_disconnected_bridge_is_not_empty_success(monkeypatch):
    # A bound, non-listening socket reserves the port without accepting connections.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        monkeypatch.setenv("CLOUDCOMPARE_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("CLOUDCOMPARE_MCP_PORT", str(reserved.getsockname()[1]))
        result = server.handle_discover_live_hole_candidates(LIVE)
    assert isinstance(result, types.CallToolResult) and result.isError
    assert "Could not connect" in result.content[0].text


def test_invalid_request_still_never_queries_native(monkeypatch):
    with wire_peer(monkeypatch, error_envelope(NO_MATCH)) as requests:
        result = server.handle_discover_live_hole_candidates({**LIVE, "face_normal": [0, 0, 0]})
    assert isinstance(result, types.CallToolResult) and result.isError
    assert requests == []


def test_general_region_tool_still_reports_native_error(monkeypatch):
    with wire_peer(monkeypatch, error_envelope(NO_MATCH)) as requests:
        result = server.handle_query_live_region({
            "cloud_id": 42, "region": EMPTY_REGIONS[0], "max_points": 1000})
    assert isinstance(result, types.CallToolResult) and result.isError
    assert NO_MATCH in result.content[0].text and len(requests) == 1


@pytest.mark.parametrize("count", [0, 1])
def test_successful_small_native_sample_still_works(monkeypatch, count):
    response = native([[0, 0, 0]] * count)
    with wire_peer(monkeypatch, {"id": 1, "ok": True, "result": response}) as requests:
        result = body(server.handle_discover_live_hole_candidates(LIVE))
    assert result["candidate_count"] == 0
    assert result["input_provenance"]["region_match_count"] == count
    assert "empty_region_evidence" not in result["input_provenance"]
    assert len(requests) == 1


def test_nonempty_numerical_path_unchanged_over_wire(monkeypatch):
    fixture = native()
    with patch.object(server, "live_request", return_value=fixture):
        expected = body(server.handle_discover_live_hole_candidates(LIVE))
    with wire_peer(monkeypatch, {"id": 1, "ok": True, "result": fixture}) as requests:
        result = body(server.handle_discover_live_hole_candidates(LIVE))
    assert result == expected and result["candidate_count"] == 4
    assert len(requests) == 1


@pytest.mark.parametrize("message", [NO_MATCH, "Entity not found: 42"])
def test_real_mcp_stdio_envelope(monkeypatch, message):
    async def invoke():
        env = dict(os.environ)
        root = Path(__file__).resolve().parents[1]
        env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), env.get("PYTHONPATH", "")])
        params = StdioServerParameters(command=sys.executable,
                                       args=["-m", "cloudcompare_mcp.server"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("discover_live_hole_candidates", LIVE)
                if message == NO_MATCH:
                    assert not result.isError
                    assert_empty(json.loads(result.content[0].text), LIVE, message)
                else:
                    assert result.isError
                    assert message in result.content[0].text
    with wire_peer(monkeypatch, error_envelope(message)) as requests:
        asyncio.run(asyncio.wait_for(invoke(), timeout=20))
    assert len(requests) == 1
