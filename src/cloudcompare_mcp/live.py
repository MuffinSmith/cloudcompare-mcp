"""Client for the qMCPBridge plugin running inside an open CloudCompare instance."""

from __future__ import annotations

import json
import os
import socket
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 5.0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class LiveBridgeError(RuntimeError):
    """Raised when the live CloudCompare bridge cannot be reached or returns an error."""


def _config() -> tuple[str, int, float, str | None]:
    host = os.environ.get("CLOUDCOMPARE_MCP_HOST", DEFAULT_HOST)
    try:
        port = int(os.environ.get("CLOUDCOMPARE_MCP_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise LiveBridgeError("CLOUDCOMPARE_MCP_PORT must be an integer") from exc
    if not (1 <= port <= 65535):
        raise LiveBridgeError("CLOUDCOMPARE_MCP_PORT must be between 1 and 65535")

    try:
        timeout = float(os.environ.get("CLOUDCOMPARE_MCP_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError as exc:
        raise LiveBridgeError("CLOUDCOMPARE_MCP_TIMEOUT must be numeric") from exc
    if timeout <= 0:
        raise LiveBridgeError("CLOUDCOMPARE_MCP_TIMEOUT must be greater than zero")

    token = os.environ.get("CLOUDCOMPARE_MCP_TOKEN") or None
    return host, port, timeout, token


def request(method: str, params: dict[str, Any] | None = None) -> Any:
    """Send one newline-delimited JSON request to the open CloudCompare instance."""
    host, port, timeout, token = _config()
    payload: dict[str, Any] = {
        "id": 1,
        "method": method,
        "params": params or {},
    }
    if token:
        payload["token"] = token

    wire = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(wire)
            with sock.makefile("rb") as stream:
                response_bytes = stream.readline(MAX_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise LiveBridgeError(
            f"Could not connect to the CloudCompare live bridge at {host}:{port}: {exc}. "
            "Make sure CloudCompare is open and the qMCPBridge plugin is running."
        ) from exc

    if not response_bytes:
        raise LiveBridgeError("CloudCompare live bridge closed the connection without a response")
    if len(response_bytes) > MAX_RESPONSE_BYTES:
        raise LiveBridgeError("CloudCompare live bridge response exceeded 64 MiB")

    try:
        response = json.loads(response_bytes)
    except json.JSONDecodeError as exc:
        raise LiveBridgeError("CloudCompare live bridge returned invalid JSON") from exc

    if not isinstance(response, dict):
        raise LiveBridgeError("CloudCompare live bridge returned an unexpected response")
    if not response.get("ok", False):
        raise LiveBridgeError(str(response.get("error", "Unknown live bridge error")))

    return response.get("result")
