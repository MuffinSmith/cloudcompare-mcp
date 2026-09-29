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
PYTHON_CLIENT_VERSION = "0.17.0"
MIN_WORKFLOW_REVISION = 10

# Operations that pre-date the capability handshake. They remain usable for
# recovery against a legacy bridge, but anything outside this set is refused
# before the workflow begins so a stale native DLL cannot masquerade as a
# complete current runtime.
LEGACY_BASELINE_OPERATIONS = frozenset({
    "ping",
    "scene.list",
    "selection.get",
    "selection.set",
    "file.load",
    "entity.rename",
    "entity.set_state",
    "entity.delete",
    "entity.transform",
    "view",
    "view.capture",
})



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


def _raw_request(
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


def _legacy_runtime_info(ping: Any, handshake_error: str) -> dict[str, Any]:
    ping_info = ping if isinstance(ping, dict) else {}
    return {
        "handshake_contract": "cc-runtime-handshake-v1",
        "python_client_version": PYTHON_CLIENT_VERSION,
        "compatible": False,
        "compatibility_status": "legacy_bridge",
        "compatibility_message": (
            "The loaded qMCPBridge DLL predates the runtime capability handshake. "
            "Only the documented legacy baseline operations are considered available; "
            "current workflow tools are blocked before execution."
        ),
        "legacy_bridge": True,
        "handshake_error": handshake_error,
        "protocol_version": ping_info.get("protocol_version"),
        "plugin": ping_info.get("plugin", "qMCPBridge"),
        "plugin_version": ping_info.get("plugin_version"),
        "workflow_revision": None,
        "application_version": ping_info.get("application_version"),
        "application_version_source": ping_info.get("application_version_source", "legacy_ping"),
        "process_id": ping_info.get("process_id"),
        "session_id": None,
        "port": ping_info.get("port"),
        "loaded_module_path": None,
        "loaded_module_sha256": None,
        "supported_operations": sorted(LEGACY_BASELINE_OPERATIONS),
        "operation_availability_source": "legacy_baseline_contract",
        "recovery": {
            "requires_cloudcompare_restart": True,
            "automatic_restart_allowed": False,
            "automatic_loaded_dll_replacement_allowed": False,
            "preserve_open_scene_first": True,
            "steps": [
                "Preserve the open scene with currently supported operations or the CloudCompare UI.",
                "Close CloudCompare only after unsaved work is checkpointed.",
                "Replace/install the accepted qMCPBridge DLL while CloudCompare is closed.",
                "Reopen CloudCompare and call get_live_cloudcompare_info before resuming the workflow.",
            ],
        },
    }


def runtime_handshake(*, timeout: float | None = None) -> dict[str, Any]:
    """Return a compatibility-aware description of the loaded native bridge.

    New bridges expose runtime.handshake. Legacy bridges are diagnosed without
    attempting current operations: a successful ping is converted into a
    conservative baseline capability set plus an explicit restart plan.
    """
    try:
        result = _raw_request("runtime.handshake", {}, timeout=timeout)
    except LiveBridgeError as exc:
        message = str(exc)
        if "Unknown bridge method: runtime.handshake" not in message:
            raise
        ping = _raw_request("ping", {}, timeout=timeout)
        return _legacy_runtime_info(ping, message)

    if not isinstance(result, dict):
        raise LiveBridgeError("CloudCompare runtime handshake returned an unexpected response")

    operations = result.get("supported_operations")
    if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
        raise LiveBridgeError("CloudCompare runtime handshake omitted supported_operations")

    protocol_version = result.get("protocol_version")
    workflow_revision = result.get("workflow_revision")
    compatible = (
        protocol_version == 1
        and isinstance(workflow_revision, int)
        and workflow_revision >= MIN_WORKFLOW_REVISION
    )

    normalized = dict(result)
    normalized["python_client_version"] = PYTHON_CLIENT_VERSION
    normalized["compatible"] = compatible
    normalized["legacy_bridge"] = False
    normalized["operation_availability_source"] = "native_runtime_handshake"
    if compatible:
        normalized["compatibility_status"] = "compatible"
        normalized["compatibility_message"] = (
            f"Native bridge workflow revision {workflow_revision} satisfies "
            f"the Python client's minimum revision {MIN_WORKFLOW_REVISION}."
        )
    else:
        normalized["compatibility_status"] = "native_revision_mismatch"
        normalized["compatibility_message"] = (
            f"Loaded native bridge protocol/workflow revision is incompatible with "
            f"cloudcompare-mcp {PYTHON_CLIENT_VERSION}: protocol={protocol_version!r}, "
            f"workflow_revision={workflow_revision!r}, required protocol=1 and "
            f"workflow_revision>={MIN_WORKFLOW_REVISION}."
        )
        normalized.setdefault(
            "recovery",
            {
                "requires_cloudcompare_restart": True,
                "automatic_restart_allowed": False,
                "automatic_loaded_dll_replacement_allowed": False,
                "preserve_open_scene_first": True,
            },
        )
    return normalized


def request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
) -> Any:
    """Send a compatibility-preflighted request to the open CloudCompare instance."""
    if method == "runtime.handshake":
        return runtime_handshake(timeout=timeout)
    if method == "ping":
        return _raw_request(method, params, timeout=timeout)

    runtime = runtime_handshake(timeout=timeout)
    operations = set(runtime.get("supported_operations") or ())
    if method not in operations:
        status = runtime.get("compatibility_status", "unknown")
        plugin_version = runtime.get("plugin_version")
        workflow_revision = runtime.get("workflow_revision")
        raise LiveBridgeError(
            f"Live operation {method!r} is unavailable in the loaded qMCPBridge runtime "
            f"(status={status}, plugin_version={plugin_version!r}, "
            f"workflow_revision={workflow_revision!r}). "
            "Checkpoint unsaved work before replacing the DLL; CloudCompare must be "
            "restarted to load a different native plugin."
        )
    if not runtime.get("compatible") and method not in LEGACY_BASELINE_OPERATIONS:
        raise LiveBridgeError(
            f"Live operation {method!r} is blocked because the loaded qMCPBridge DLL "
            "does not satisfy the current runtime compatibility contract."
        )

    return _raw_request(method, params, timeout=timeout)
