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
        listener.listen(1)
        listener.settimeout(5)
        monkeypatch.setenv("CLOUDCOMPARE_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("CLOUDCOMPARE_MCP_PORT", str(listener.getsockname()[1]))
        monkeypatch.setenv("CLOUDCOMPARE_MCP_TIMEOUT", "2")
        monkeypatch.delenv("CLOUDCOMPARE_MCP_TOKEN", raising=False)
        def serve():
            try:
                with listener.accept()[0] as conn:
                    conn.settimeout(5)
                    with conn.makefile("rb") as stream:
                        received.append(json.loads(stream.readline()))
                    conn.sendall(b'{"id":1,"ok":true,"result":{"active":false}}\n')
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
    assert received == [{"id": 1, "method": "fit.overlay.status", "params": {}}]
