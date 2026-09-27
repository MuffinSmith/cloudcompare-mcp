"""MCP surface for Python-only section-profile reconstruction."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .profile_reconstruction import (
    MAX_PROFILE_POINTS,
    MAX_PROFILE_SEGMENTS,
    ProfileError,
    reconstruct_profile_2d,
)

VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
VEC2 = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
NAME = {"type": "string", "minLength": 1, "maxLength": 128}
SECTION = {
    "type": "object",
    "additionalProperties": True,
    "required": ["coordinate_space", "units", "points_uv"],
    "properties": {
        "coordinate_space": {"const": "section_uv"},
        "units": {"const": "native"},
        "frame_id": NAME,
        "points_uv": {
            "type": "array",
            "items": VEC2,
            "minItems": 2,
            "maxItems": MAX_PROFILE_POINTS,
            "description": "Ordered or explicitly orderable section coordinates. Raw 3D point arrays are not accepted here.",
        },
        "origin_global": VEC3,
        "basis_u": VEC3,
        "basis_v": VEC3,
        "normal": VEC3,
        "source_cloud_id": {"type": "integer"},
        "global_shift": VEC3,
        "global_scale": {"type": "number", "exclusiveMinimum": 0},
        "provenance": {"type": "object"},
    },
}


def capabilities() -> dict[str, Any]:
    return {
        "version": "0.15.1",
        "snapshot_profile_reconstruction": True,
        "live_section_profile_reconstruction": True,
        "native_rebuild_required": False,
        "supported_primitives": ["line", "arc", "circle"],
        "profile_candidates": ["circle", "rectangle", "slot"],
        "ordering_methods": ["input", "polar_closed_loop", "principal_open"],
        "max_points": MAX_PROFILE_POINTS,
        "max_segments": MAX_PROFILE_SEGMENTS,
        "spline_fallback": False,
        "persistent_acceptance": False,
        "manufacturing_intent_confirmed": False,
    }


def tools() -> list[Tool]:
    return [
        Tool(
            name="reconstruct_section_profile",
            description=(
                "Reconstruct a compact candidate CAD profile from a supplied 2D section snapshot without contacting CloudCompare. "
                "Fits deterministic line/arc/circle primitives, adjacency/tangency candidates, and bounded circle/rectangle/slot candidates. "
                "No raw point array is echoed. Ordering assumptions are explicit and results are geometric candidates, not accepted manufacturing intent."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": deepcopy(SECTION),
                    "closed": {"type": "boolean"},
                    "fit_tolerance": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Native-unit numerical fit threshold, not calibrated measurement uncertainty.",
                    },
                    "angular_tolerance_degrees": {"type": "number", "minimum": 0, "maximum": 45, "default": 1},
                    "ordering_method": {
                        "type": "string",
                        "enum": ["input", "polar_closed_loop", "principal_open"],
                        "default": "input",
                    },
                    "minimum_arc_angle_degrees": {"type": "number", "minimum": 1, "maximum": 180, "default": 12},
                    "max_segments": {"type": "integer", "minimum": 1, "maximum": MAX_PROFILE_SEGMENTS, "default": 64},
                },
                "required": ["section", "closed", "fit_tolerance"],
            },
            annotations=ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
    ]


def _finite_json_size(value: Any, *, limit: int, label: str) -> int:
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"{label} must be finite JSON") from exc
    if len(encoded) > limit:
        raise ProfileError(f"{label} exceeds {limit} bytes")
    return len(encoded)


def reconstruct_section_profile_snapshot(
    *,
    section: dict[str, Any],
    closed: bool,
    fit_tolerance: float,
    angular_tolerance_degrees: float = 1.0,
    ordering_method: str = "input",
    minimum_arc_angle_degrees: float = 12.0,
    max_segments: int = 64,
) -> dict[str, Any]:
    if not isinstance(section, dict):
        raise ProfileError("section must be an object")
    _finite_json_size(section, limit=131072, label="section")
    if section.get("coordinate_space") != "section_uv":
        raise ProfileError("section.coordinate_space must be 'section_uv'")
    if section.get("units") != "native":
        raise ProfileError("section.units must be 'native'")
    if "points" in section or "points_global" in section:
        raise ProfileError("section must use points_uv; raw 3D point arrays are not accepted")
    provenance = section.get("provenance")
    if provenance is not None:
        _finite_json_size(provenance, limit=4096, label="section.provenance")
    if "global_scale" in section:
        value = section["global_scale"]
        if isinstance(value, bool):
            raise ProfileError("section.global_scale must be finite and positive")
        try:
            scale = float(value)
        except (TypeError, ValueError) as exc:
            raise ProfileError("section.global_scale must be finite and positive") from exc
        if not math.isfinite(scale) or scale <= 0:
            raise ProfileError("section.global_scale must be finite and positive")

    result = reconstruct_profile_2d(
        section.get("points_uv", []),
        closed=closed,
        fit_tolerance=fit_tolerance,
        angular_tolerance_degrees=angular_tolerance_degrees,
        ordering_method=ordering_method,
        minimum_arc_angle_degrees=minimum_arc_angle_degrees,
        max_segments=max_segments,
    )
    frame = {
        key: deepcopy(section[key])
        for key in (
            "frame_id",
            "origin_global",
            "basis_u",
            "basis_v",
            "normal",
            "source_cloud_id",
            "global_shift",
            "global_scale",
            "provenance",
        )
        if key in section
    }
    result["section_frame"] = frame
    result["live_connection_used"] = False
    result["scene_mutations_requested"] = False
    result["source_geometry_preserved"] = True
    return result


def handle_reconstruct_section_profile(arguments: Any):
    try:
        if not isinstance(arguments, dict):
            raise ProfileError("Tool arguments must be an object")
        result = reconstruct_section_profile_snapshot(**arguments)
        return [TextContent(type="text", text=json.dumps(result, allow_nan=False, separators=(",", ":")))]
    except (ProfileError, TypeError, KeyError, ArithmeticError) as exc:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=json.dumps({"error": str(exc)}))],
        )
