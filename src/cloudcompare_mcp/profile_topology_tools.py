"""MCP surface for explicit section-boundary topology reconstruction."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .profile_tools import NAME, SECTION, VEC3
from .profile_topology import (
    MAX_TOPOLOGY_LOOPS,
    MAX_TOPOLOGY_POINTS,
    ProfileTopologyError,
    reconstruct_profile_topology_2d,
)


def capabilities() -> dict[str, Any]:
    return {
        "boundary_topology_version": "0.15.1",
        "snapshot_boundary_topology": True,
        "live_boundary_topology": True,
        "boundary_samples_required": True,
        "multiple_loops": True,
        "hole_island_nesting": True,
        "non_star_shaped_loops": True,
        "filled_section_boundary_inference": False,
        "self_intersection_repair": False,
        "max_topology_points": MAX_TOPOLOGY_POINTS,
        "max_topology_loops": MAX_TOPOLOGY_LOOPS,
    }


def _topology_section_schema() -> dict[str, Any]:
    section = deepcopy(SECTION)
    section["properties"]["points_uv"]["minItems"] = 6
    section["properties"]["points_uv"]["maxItems"] = MAX_TOPOLOGY_POINTS
    section["properties"]["points_uv"]["description"] = (
        "Unordered 2D samples that the caller explicitly asserts lie on one or more "
        "closed boundary curves. Filled sections are not supported by this tool."
    )
    return section


def _common_topology_properties() -> dict[str, Any]:
    return {
        "boundary_samples_only": {
            "const": True,
            "description": (
                "Required explicit caller assertion that every input/sample point belongs "
                "to a boundary curve rather than a filled section."
            ),
        },
        "max_edge_length": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": (
                "Caller-selected native-unit maximum local boundary connection length. "
                "It must be smaller than gaps to unrelated branches/loops."
            ),
        },
        "fit_tolerance": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Native-unit primitive fitting threshold for each recovered loop.",
        },
        "angular_tolerance_degrees": {
            "type": "number",
            "minimum": 0,
            "maximum": 45,
            "default": 1,
        },
        "minimum_loop_points": {
            "type": "integer",
            "minimum": 3,
            "maximum": MAX_TOPOLOGY_POINTS,
            "default": 6,
        },
        "max_loops": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_TOPOLOGY_LOOPS,
            "default": 16,
        },
        "minimum_arc_angle_degrees": {
            "type": "number",
            "minimum": 1,
            "maximum": 180,
            "default": 12,
        },
        "max_segments_per_loop": {
            "type": "integer",
            "minimum": 1,
            "maximum": 128,
            "default": 64,
        },
    }


def tools() -> list[Tool]:
    common = _common_topology_properties()
    return [
        Tool(
            name="reconstruct_section_topology",
            description=(
                "Recover one or more explicit closed loops from unordered 2D boundary "
                "samples, classify outer/hole/island nesting candidates, and run the "
                "accepted line/arc/circle profile fitter on each loop. The caller must "
                "explicitly assert boundary_samples_only=true and choose max_edge_length. "
                "Ambiguous/open/intersecting topology is rejected rather than repaired."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": _topology_section_schema(),
                    **deepcopy(common),
                },
                "required": [
                    "section",
                    "boundary_samples_only",
                    "max_edge_length",
                    "fit_tolerance",
                ],
            },
            annotations=ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        ),
        Tool(
            name="reconstruct_live_section_topology",
            description=(
                "Acquire a complete bounded live slab sample that the caller explicitly "
                "asserts contains boundary samples only, project it to section U/V, recover "
                "multiple closed loops with hole/island nesting, and fit each loop. This "
                "tool refuses truncated acquisition and does not infer a contour from a "
                "filled slab."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cloud_id": {"type": "integer"},
                    "origin": deepcopy(VEC3),
                    "normal": deepcopy(VEC3),
                    "half_thickness": {"type": "number", "minimum": 0},
                    "sample_limit": {
                        "type": "integer",
                        "minimum": 6,
                        "maximum": MAX_TOPOLOGY_POINTS,
                        "default": MAX_TOPOLOGY_POINTS,
                    },
                    **deepcopy(common),
                },
                "required": [
                    "cloud_id",
                    "origin",
                    "normal",
                    "half_thickness",
                    "boundary_samples_only",
                    "max_edge_length",
                    "fit_tolerance",
                ],
            },
            annotations=ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        ),
    ]


def _finite_json_size(value: Any, *, limit: int, label: str) -> None:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProfileTopologyError(f"{label} must be finite JSON") from exc
    if len(encoded) > limit:
        raise ProfileTopologyError(f"{label} exceeds {limit} bytes")


def reconstruct_section_topology_snapshot(
    *,
    section: dict[str, Any],
    boundary_samples_only: bool,
    max_edge_length: float,
    fit_tolerance: float,
    angular_tolerance_degrees: float = 1.0,
    minimum_loop_points: int = 6,
    max_loops: int = 16,
    minimum_arc_angle_degrees: float = 12.0,
    max_segments_per_loop: int = 64,
) -> dict[str, Any]:
    if boundary_samples_only is not True:
        raise ProfileTopologyError(
            "boundary_samples_only=true is required; filled-section boundary inference "
            "is not implemented"
        )
    if not isinstance(section, dict):
        raise ProfileTopologyError("section must be an object")
    _finite_json_size(section, limit=131072, label="section")
    if section.get("coordinate_space") != "section_uv":
        raise ProfileTopologyError("section.coordinate_space must be 'section_uv'")
    if section.get("units") != "native":
        raise ProfileTopologyError("section.units must be 'native'")
    if "points" in section or "points_global" in section:
        raise ProfileTopologyError(
            "section must use points_uv; raw 3D point arrays are not accepted"
        )
    provenance = section.get("provenance")
    if provenance is not None:
        _finite_json_size(provenance, limit=4096, label="section.provenance")
    if "global_scale" in section:
        value = section["global_scale"]
        if isinstance(value, bool):
            raise ProfileTopologyError(
                "section.global_scale must be finite and positive"
            )
        try:
            scale = float(value)
        except (TypeError, ValueError) as exc:
            raise ProfileTopologyError(
                "section.global_scale must be finite and positive"
            ) from exc
        if not math.isfinite(scale) or scale <= 0:
            raise ProfileTopologyError(
                "section.global_scale must be finite and positive"
            )

    result = reconstruct_profile_topology_2d(
        section.get("points_uv", []),
        max_edge_length=max_edge_length,
        fit_tolerance=fit_tolerance,
        angular_tolerance_degrees=angular_tolerance_degrees,
        minimum_loop_points=minimum_loop_points,
        max_loops=max_loops,
        minimum_arc_angle_degrees=minimum_arc_angle_degrees,
        max_segments_per_loop=max_segments_per_loop,
    )
    result["section_frame"] = {
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
    result["live_connection_used"] = False
    result["scene_mutations_requested"] = False
    result["source_geometry_preserved"] = True
    return result


def handle_reconstruct_section_topology(arguments: Any):
    try:
        if not isinstance(arguments, dict):
            raise ProfileTopologyError("Tool arguments must be an object")
        result = reconstruct_section_topology_snapshot(**arguments)
        return [
            TextContent(
                type="text",
                text=json.dumps(result, allow_nan=False, separators=(",", ":")),
            )
        ]
    except (ProfileTopologyError, TypeError, KeyError, ArithmeticError) as exc:
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(exc)}),
                )
            ],
        )
