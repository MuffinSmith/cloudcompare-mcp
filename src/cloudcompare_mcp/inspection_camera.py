"""Strict Python boundary for native camera navigation and captured evidence.

Camera parameters live in CloudCompare's host-render frame, not CAD/global space.
Native fingerprints use Qt JSON; Python evidence fingerprints have their own domain.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import struct
import zlib
from typing import Any, Callable

from .live import LiveBridgeError

Request = Callable[..., Any]
MAX_JSON = 128 * 1024
MAX_PNG = 8 * 1024 * 1024


class InspectionError(ValueError):
    def __init__(self, message: str, recovery: dict | None = None):
        super().__init__(message)
        self.recovery = recovery


def encoded(value: Any, limit: int = MAX_JSON) -> bytes:
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise InspectionError("Evidence must be finite, bounded JSON") from exc
    if len(data) > limit:
        raise InspectionError("Evidence exceeds the declared JSON byte budget")
    return data


def fingerprint(domain: str, value: Any, limit: int = MAX_JSON) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\0" + encoded(value, limit)).hexdigest()


def number(value: Any, name: str, lo: float, hi: float) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and lo <= value <= hi
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise InspectionError(f"{name} must be a finite number in [{lo}, {hi}], not a boolean")
    return float(value)


def integer(value: Any, name: str, lo: int, hi: int) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise InspectionError(f"{name} must be an integer in [{lo}, {hi}]")
    return value


def text(value: Any, name: str, limit: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InspectionError(f"{name} must be nonempty text of at most {limit} characters")
    return value


def digest(value: Any, name: str = "fingerprint") -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise InspectionError(f"{name} must be a lowercase SHA256 fingerprint")
    return value


def vector(value: Any, name: str, limit: float = 1e12) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise InspectionError(f"{name} must contain exactly three numbers")
    return [number(v, name, -limit, limit) for v in value]


def unit(value: Any, name: str) -> list[float]:
    v = vector(value, name)
    n = math.hypot(*v)
    number(n, f"{name} length", 1e-12, 1e12)
    return [x / n for x in v]


def only(args: Any, allowed: set[str], required: set[str]) -> None:
    if not isinstance(args, dict) or not required <= args.keys() or args.keys() - allowed:
        raise InspectionError("Missing or unexpected arguments")
    encoded(args, 16 * 1024)


def camera_state(result: Any) -> dict:
    if not isinstance(result, dict) or result.get("contract") != "cc-camera-v1":
        raise InspectionError("Recoverable camera requires qMCPBridge 0.13.0 / revision 9")
    encoded(result, 16 * 1024)
    text(result.get("native_session"), "native_session")
    integer(result.get("window_id"), "window_id", 0, 2**31-1)
    integer(result.get("viewport_width"), "viewport_width", 1, 16384)
    integer(result.get("viewport_height"), "viewport_height", 1, 16384)
    digest(result.get("camera_fingerprint"), "camera_fingerprint")
    if "camera_guard_contract" in result or "camera_guard_fingerprint" in result:
        if result.get("camera_guard_contract") != "cc-camera-guard-v1":
            raise InspectionError("Unsupported or incomplete navigation guard contract")
        digest(result.get("camera_guard_fingerprint"), "camera_guard_fingerprint")
    if type(result.get("navigation_supported")) is not bool or not isinstance(result.get("parameters"), dict):
        raise InspectionError("Malformed native camera state")
    if result["navigation_supported"]:
        p = result["parameters"]
        for field in ("perspective", "object_centered", "bubble_view", "stereo", "clipping_enabled"):
            if type(p.get(field)) is not bool:
                raise InspectionError("Malformed camera mode flags")
        if not p["object_centered"] or p["bubble_view"] or p["stereo"] or p.get("display_scale") != [1, 1]:
            raise InspectionError("Inconsistent supported camera mode")
        for field in ("pivot_host", "camera_center_host", "view_direction_host", "up_direction_host"):
            vector(p.get(field), field)
        number(p.get("focal_distance"), "focal distance", 1e-9, 1e12)
        number(p.get("fov_degrees"), "fov degrees", 1, 170)
        number(p.get("camera_aspect_ratio"), "camera aspect", .01, 100)
        m = p.get("view_rotation_column_major")
        if not isinstance(m, list) or len(m) != 16:
            raise InspectionError("Camera rotation must be a complete column-major matrix")
        m = [number(v, "rotation element", -1.000001, 1.000001) for v in m]
        if any(m[i] != 0 for i in (3, 7, 11, 12, 13, 14)) or m[15] != 1:
            raise InspectionError("Camera rotation contains non-rotation components")
        for a in range(3):
            for b in range(3):
                if abs(sum(m[4*a+k]*m[4*b+k] for k in range(3)) - int(a == b)) > 1e-6:
                    raise InspectionError("Camera rotation is not orthonormal")
        det = m[0]*(m[5]*m[10]-m[9]*m[6])-m[4]*(m[1]*m[10]-m[9]*m[2])+m[8]*(m[1]*m[6]-m[5]*m[2])
        if abs(det-1) > 1e-6:
            raise InspectionError("Camera rotation is a reflection")
    return result


def guard(state: dict) -> dict:
    camera_state(state)
    key = "camera_guard_fingerprint" if "camera_guard_contract" in state else "camera_fingerprint"
    return {"native_session": state["native_session"], "window_id": state["window_id"],
            "expected_" + key: state[key]}


def camera_difference(before: dict, after: dict) -> dict:
    """Exact field comparison; native hashes remain in their own serialization domain."""
    camera_state(before)
    camera_state(after)
    a, b = before["parameters"], after["parameters"]
    fields = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
    identity = [k for k in ("native_session", "window_id", "viewport_width", "viewport_height")
                if before.get(k) != after.get(k)]
    excluded = {"point_size", "line_width", "view_direction_host", "up_direction_host"}
    modern = "camera_guard_contract" in before and "camera_guard_contract" in after
    equal = guard(before) == guard(after)
    if modern:
        equal = equal and not identity and not (set(fields) - excluded)
    return {"identity_fields": identity, "parameter_fields": fields,
            "guard_equal": equal, "full_equal": before["camera_fingerprint"] == after["camera_fingerprint"]}


def camera_request(request: Request, method: str, args: dict) -> Any:
    try:
        return request(method, args, timeout=15.0)
    except LiveBridgeError as exc:
        recovery = {"camera_diagnostics": exc.details} if exc.details is not None else None
        raise InspectionError(exc.args[0], recovery) from exc


def navigate(request: Request, args: dict) -> dict:
    action = args.get("action") if isinstance(args, dict) else None
    fields = {
        "get": set(), "save": set(), "release": {"native_session", "restore_token"},
        "look": {"direction", "up"}, "orbit": {"axis_camera", "degrees"},
        "pan": {"right_fraction", "up_fraction"}, "zoom": {"factor"},
        "focus": {"entity_id", "center_global", "width_global", "min_global", "max_global"},
        "restore": {"restore_token"},
    }
    if action not in fields:
        raise InspectionError("Unknown camera action")
    common = set()
    if action not in ("get", "save", "release"):
        keys = set(args) & {"expected_camera_fingerprint", "expected_camera_guard_fingerprint"}
        if len(keys) != 1:
            raise InspectionError("Provide exactly one full or navigation camera guard")
        common = {"native_session", "window_id"} | keys
    required = fields[action] if action != "focus" else {"entity_id"}
    only(args, {"action"} | common | fields[action], {"action"} | common | required)
    if "native_session" in args:
        text(args["native_session"], "native_session")
    if common:
        integer(args["window_id"], "window_id", 0, 2**31-1)
        digest(args[next(k for k in common if k.startswith("expected_"))])
    if "restore_token" in args:
        text(args["restore_token"], "restore_token")
    if action == "look":
        f, u = unit(args["direction"], "direction"), unit(args["up"], "up")
        cross = [f[1]*u[2]-f[2]*u[1], f[2]*u[0]-f[0]*u[2], f[0]*u[1]-f[1]*u[0]]
        if math.hypot(*cross) < 1e-6:
            raise InspectionError("View direction and up are nearly parallel")
    elif action == "orbit":
        unit(args["axis_camera"], "axis_camera")
        number(args["degrees"], "degrees", -180, 180)
    elif action == "pan":
        number(args["right_fraction"], "right_fraction", -1, 1)
        number(args["up_fraction"], "up_fraction", -1, 1)
    elif action == "zoom":
        number(args["factor"], "factor", .1, 10)
    elif action == "focus":
        integer(args["entity_id"], "entity_id", 1, 2**32-1)
        shape = set(args) & {"center_global", "width_global", "min_global", "max_global"}
        if shape == {"center_global", "width_global"}:
            vector(args["center_global"], "center_global", 1e15)
            number(args["width_global"], "width_global", 1e-12, 1e15)
        elif shape == {"min_global", "max_global"}:
            lo = vector(args["min_global"], "min_global", 1e15)
            hi = vector(args["max_global"], "max_global", 1e15)
            if any(a > b for a, b in zip(lo, hi)) or lo == hi:
                raise InspectionError("Focus bounds must have ordered, nonzero extent")
        elif shape:
            raise InspectionError("Choose entity, center plus width, or complete region; not mixed focus inputs")
    result = camera_request(request, "view.camera", args)
    if action == "release":
        if not isinstance(result, dict) or result.get("released") is not True:
            raise InspectionError("Native camera token release was not confirmed")
        return result
    result = camera_state(result)
    if common and (result["native_session"] != args["native_session"] or result["window_id"] != args["window_id"]):
        raise InspectionError("Camera response changed session or active window")
    if action == "save":
        text(result.get("restore_token"), "restore_token")
    if "expected_camera_guard_fingerprint" in args and "camera_guard_contract" not in result:
        raise InspectionError("Navigation guard response was downgraded", {"current": result})
    equality = "restored_guard_equal" if "expected_camera_guard_fingerprint" in args else "restored_equal"
    if action == "restore" and result.get(equality) is not True:
        raise InspectionError("Native camera restoration did not compare equal", {"restore_token": args["restore_token"], "current": result})
    return result


def capture(request: Request, state: dict) -> tuple[dict, str, int]:
    """Read a real native PNG; verify its bytes and bind the reported camera state."""
    camera_state(state)
    # Native 0.13.0 accepts only the legacy digest on view.capture.
    capture_guard = guard(state) if "camera_guard_contract" in state else {
        "expected_camera_fingerprint": state["camera_fingerprint"]}
    result = camera_request(request, "view.capture", capture_guard)
    if not isinstance(result, dict) or result.get("capture_contract") != "cc-viewport-capture-v1":
        raise InspectionError("Viewport capture has no recoverable camera provenance")
    observed = camera_state(result.get("camera_state"))
    transition = camera_difference(state, observed)
    if not transition["guard_equal"]:
        raise InspectionError("Camera changed during viewport capture", {"camera_difference": transition, "expected": state, "current": observed})
    b64 = result.get("png_base64")
    if not isinstance(b64, str) or len(b64) > (MAX_PNG + 2) // 3 * 4:
        raise InspectionError("PNG exceeds the per-capture byte budget")
    try:
        png = base64.b64decode(b64, validate=True)
    except ValueError as exc:
        raise InspectionError("Invalid base64 viewport PNG") from exc
    if len(png) < 33 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
        raise InspectionError("Native capture is not a PNG with an IHDR header")
    width, height = struct.unpack(">II", png[16:24])
    integer(width, "PNG width", 1, 16384)
    integer(height, "PNG height", 1, 16384)
    if width * height > 16 * 1024 * 1024:
        raise InspectionError("Viewport PNG exceeds the pixel budget")
    if (integer(result.get("width"), "capture width", 1, 16384) != width
            or integer(result.get("height"), "capture height", 1, 16384) != height):
        raise InspectionError("PNG and declared capture dimensions disagree")
    pos, chunks, found_idat, ended = 8, 0, False, False
    while pos < len(png) and chunks < 8192:
        if pos + 12 > len(png):
            raise InspectionError("Truncated PNG chunk")
        size = struct.unpack(">I", png[pos:pos+4])[0]
        end = pos + 12 + size
        if end > len(png):
            raise InspectionError("Truncated PNG payload")
        kind = png[pos+4:pos+8]
        crc = struct.unpack(">I", png[end-4:end])[0]
        if zlib.crc32(png[pos+4:end-4]) != crc:
            raise InspectionError("PNG chunk checksum mismatch")
        if chunks == 0 and (kind != b"IHDR" or size != 13):
            raise InspectionError("Malformed PNG header")
        found_idat |= kind == b"IDAT"
        chunks += 1
        pos = end
        if kind == b"IEND":
            ended = size == 0 and end == len(png)
            break
    if not ended or not found_idat:
        raise InspectionError("Incomplete PNG or excessive chunk count")
    sha = hashlib.sha256(png).hexdigest()
    if digest(result.get("png_sha256"), "png_sha256") != sha:
        raise InspectionError("Viewport PNG checksum mismatch")
    evidence = {"contract": "viewport-evidence-v1", "width": width, "height": height,
                "png_sha256": sha, "camera": observed, "image_interpretation": "agent_pending",
                "dimensional_authority": False, "requested_camera_fingerprint": state["camera_fingerprint"],
                "camera_difference": transition}
    for key in ("camera_before_redraw", "redraw_difference"):
        if key in result:
            encoded(result[key], 16 * 1024)
            evidence[key] = result[key]
    return evidence, b64, len(png)
