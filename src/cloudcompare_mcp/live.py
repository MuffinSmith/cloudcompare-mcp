"""Client for the qMCPBridge plugin running inside an open CloudCompare instance."""

from __future__ import annotations

import json
import math
import os
import socket
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 5.0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class LiveBridgeError(RuntimeError):
    """Raised on transport/refusal; optional bounded native diagnostics are not authority."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = None
        try:
            if isinstance(details, dict) and details.get("contract") == "cc-camera-diagnostics-v1":
                wire = json.dumps(details, allow_nan=False)
                if len(wire.encode("utf-8")) <= 16 * 1024:
                    self.details = json.loads(wire)  # Freeze the bounded diagnostic evidence.
        except (ValueError, TypeError, RecursionError, OverflowError):
            pass

    def __str__(self) -> str:
        message = super().__str__()
        # Legacy public handlers stringify errors; do not drop the native evidence there.
        return message if self.details is None else message + "\nCamera diagnostics: " + json.dumps(self.details, allow_nan=False)


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
    if not math.isfinite(timeout) or timeout <= 0:
        raise LiveBridgeError("CLOUDCOMPARE_MCP_TIMEOUT must be finite and greater than zero")

    token = os.environ.get("CLOUDCOMPARE_MCP_TOKEN") or None
    return host, port, timeout, token


def request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
) -> Any:
    """Send one newline-delimited JSON request to the open CloudCompare instance.

    A longer timeout can be supplied for explicitly long-running geometry operations.
    """
    host, port, configured_timeout, token = _config()
    try:
        timeout = configured_timeout if timeout is None else float(timeout)
    except (TypeError, ValueError, OverflowError) as exc:
        raise LiveBridgeError("timeout must be numeric") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise LiveBridgeError("timeout must be finite and greater than zero")
    payload: dict[str, Any] = {
        "id": 1,
        "method": method,
        "params": params or {},
    }
    if token:
        payload["token"] = token

    try:
        wire = (json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise LiveBridgeError("Live bridge request must contain finite JSON values") from exc

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
        details = response.get("error_details")
        raise LiveBridgeError(str(response.get("error", "Unknown live bridge error")), details)

    return response.get("result")
