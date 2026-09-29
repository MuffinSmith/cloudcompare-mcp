"""Validation at the real JSON/TCP client boundary, without a CloudCompare host."""
import json
import socket
import threading
from unittest.mock import patch
import pytest
from cloudcompare_mcp import live

@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, "bad", object()])
def test_invalid_explicit_timeout_never_connects(value):
    with patch.object(live.socket, "create_connection") as connect:
        with pytest.raises(live.LiveBridgeError, match="timeout"):
            live.request("ping", timeout=value)
    connect.assert_not_called()

@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0"])
def test_invalid_environment_timeout_never_connects(monkeypatch, value):
    monkeypatch.setenv("CLOUDCOMPARE_MCP_TIMEOUT", value)
    with patch.object(live.socket, "create_connection") as connect:
        with pytest.raises(live.LiveBridgeError, match="TIMEOUT"):
            live.request("ping")
    connect.assert_not_called()

@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_nonfinite_or_unserializable_geometry_never_connects(value):
    with patch.object(live.socket, "create_connection") as connect:
        with pytest.raises(live.LiveBridgeError, match="finite JSON"):
            live.request("fit.overlay.create", {"center": [0, value, 0]})
    connect.assert_not_called()

def test_real_loopback_json_roundtrip(monkeypatch):
    received = []
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        listener.settimeout(5)
        monkeypatch.setenv("CLOUDCOMPARE_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("CLOUDCOMPARE_MCP_PORT", str(listener.getsockname()[1]))
        monkeypatch.setenv("CLOUDCOMPARE_MCP_TIMEOUT", "2")
        monkeypatch.delenv("CLOUDCOMPARE_MCP_TOKEN", raising=False)
        def serve():
            try:
                for _ in range(2):
                    with listener.accept()[0] as conn:
                        conn.settimeout(5)
                        with conn.makefile("rb") as stream:
                            request = json.loads(stream.readline())
                            received.append(request)
                        if request["method"] == "runtime.handshake":
                            response = {
                                "id": 1,
                                "ok": True,
                                "result": {
                                    "protocol_version": 1,
                                    "workflow_revision": 10,
                                    "plugin_version": "0.14.0",
                                    "supported_operations": [
                                        "runtime.handshake",
                                        "fit.overlay.status",
                                    ],
                                },
                            }
                        else:
                            response = {"id": 1, "ok": True, "result": {"active": False}}
                        conn.sendall((json.dumps(response) + "\n").encode())
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            assert live.request("fit.overlay.status", {}) == {"active": False}
        finally:
            thread.join(timeout=6)
        assert not thread.is_alive()
        assert not errors
    assert [item["method"] for item in received] == [
        "runtime.handshake",
        "fit.overlay.status",
    ]
