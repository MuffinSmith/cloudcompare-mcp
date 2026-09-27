"""MCP surface for filled-section occupancy boundary evidence and reconstruction."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .profile_tools import NAME, SECTION, VEC3
from .profile_topology import MAX_TOPOLOGY_LOOPS, MAX_TOPOLOGY_POINTS
from .section_boundary import (
    MAX_FILLED_SECTION_POINTS,
    MAX_OCCUPIED_CELLS,
    SectionBoundaryError,
    extract_section_boundary_evidence_2d,
    reconstruct_filled_section_profile_2d,
)


def capabilities() -> dict[str, Any]:
    return {
        "filled_section_boundary_version": "0.15.2",
        "snapshot_boundary_evidence": True,
        "snapshot_filled_section_reconstruction": True,
        "live_filled_section_reconstruction": True,
        "explicit_cell_size": True,
        "morphological_repair": False,
        "filled_section_boundary_inference": True,
        "requires_complete_live_acquisition": True,
        "max_filled_section_points": MAX_FILLED_SECTION_POINTS,
        "max_occupied_cells": MAX_OCCUPIED_CELLS,
        "native_rebuild_required": False,
    }


def _filled_section_schema() -> dict[str, Any]:
    section = deepcopy(SECTION)
    section["properties"]["points_uv"]["minItems"] = 8
    section["properties"]["points_uv"]["maxItems"] = MAX_FILLED_SECTION_POINTS
    section["properties"]["points_uv"]["description"] = (
        "Unordered projected section samples that may include material-interior points. "
        "Boundary evidence is inferred from explicit occupancy-grid parameters."
    )
    return section


def _extraction_properties() -> dict[str, Any]:
    return {
        "cell_size": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": (
                "Explicit native-unit occupancy grid cell size. The result reports "
                "grid-origin sensitivity rather than hiding this resolution assumption."
            ),
        },
        "min_cell_support": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1_000_000,
            "default": 1,
        },
        "min_component_cells": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_OCCUPIED_CELLS,
            "default": 2,
            "description": (
                "Minimum supported occupied cells per disconnected material component. "
                "Smaller components cause an error; they are never silently discarded."
            ),
        },
        "max_cells": {
            "type": "integer",
            "minimum": 4,
            "maximum": MAX_OCCUPIED_CELLS,
            "default": MAX_OCCUPIED_CELLS,
        },
        "max_boundary_points": {
            "type": "integer",
            "minimum": 6,
            "maximum": MAX_TOPOLOGY_POINTS,
            "default": MAX_TOPOLOGY_POINTS,
            "description": (
                "Maximum associated original source samples allowed as boundary evidence. "
                "Evidence exceeding the limit is rejected rather than silently thinned."
            ),
        },
    }


def _topology_properties() -> dict[str, Any]:
    return {
        "max_edge_length": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": (
                "Caller-selected native-unit locality threshold passed unchanged to the "
                "accepted 0.15.1 boundary topology solver."
            ),
        },
        "fit_tolerance": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Native-unit primitive fit threshold.",
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
        "require_grid_stability": {
            "type": "boolean",
            "default": True,
            "description": (
                "When true, composite reconstruction refuses a cell size whose contour "
                "or material-component count changes under half-cell grid-origin shifts."
            ),
        },
    }


def tools() -> list[Tool]:
    extraction = _extraction_properties()
    topology = _topology_properties()
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    return [
        Tool(
            name="extract_section_boundary_evidence",
            description=(
                "Derive compact 2D boundary evidence from unordered filled/interior section "
                "samples using an explicit native-unit occupancy grid. Exposed grid edges "
                "are traced into closed contour candidates and associated back to original "
                "source samples. Ambiguous diagonal connectivity and tiny disconnected "
                "components are rejected; raw point arrays are not returned."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": _filled_section_schema(),
                    **deepcopy(extraction),
                    "check_grid_origin_sensitivity": {
                        "type": "boolean",
                        "default": True,
                    },
                },
                "required": ["section", "cell_size"],
            },
            annotations=annotations,
        ),
        Tool(
            name="reconstruct_filled_section_profile",
            description=(
                "Reconstruct a filled/interior 2D section by deriving occupancy boundary "
                "evidence, feeding associated source boundary samples into the accepted "
                "0.15.1 multi-loop topology solver, then using the accepted primitive "
                "fitter. All output remains inferred candidate geometry."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": _filled_section_schema(),
                    **deepcopy(extraction),
                    **deepcopy(topology),
                },
                "required": [
                    "section",
                    "cell_size",
                    "max_edge_length",
                    "fit_tolerance",
                ],
            },
            annotations=annotations,
        ),
        Tool(
            name="reconstruct_live_filled_section_profile",
            description=(
                "Acquire a complete bounded live CloudCompare slab, project it to section "
                "U/V, derive occupancy boundary evidence from ordinary filled/interior "
                "samples, and run the accepted topology/primitive pipeline. Truncated "
                "native acquisition is rejected; raw samples stay server-side."
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
                        "minimum": 8,
                        "maximum": MAX_FILLED_SECTION_POINTS,
                        "default": MAX_FILLED_SECTION_POINTS,
                    },
                    **deepcopy(extraction),
                    **deepcopy(topology),
                },
                "required": [
                    "cloud_id",
                    "origin",
                    "normal",
                    "half_thickness",
                    "cell_size",
                    "max_edge_length",
                    "fit_tolerance",
                ],
            },
            annotations=annotations,
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
        raise SectionBoundaryError(f"{label} must be finite JSON") from exc
    if len(encoded) > limit:
        raise SectionBoundaryError(f"{label} exceeds {limit} bytes")


def _validate_section(section: Any) -> dict[str, Any]:
    if not isinstance(section, dict):
        raise SectionBoundaryError("section must be an object")
    _finite_json_size(section, limit=2_000_000, label="section")
    if section.get("coordinate_space") != "section_uv":
        raise SectionBoundaryError("section.coordinate_space must be 'section_uv'")
    if section.get("units") != "native":
        raise SectionBoundaryError("section.units must be 'native'")
    if "points" in section or "points_global" in section:
        raise SectionBoundaryError(
            "section must use points_uv; raw 3D point arrays are not accepted"
        )
    provenance = section.get("provenance")
    if provenance is not None:
        _finite_json_size(provenance, limit=4096, label="section.provenance")
    if "global_scale" in section:
        value = section["global_scale"]
        if isinstance(value, bool):
            raise SectionBoundaryError(
                "section.global_scale must be finite and positive"
            )
        try:
            scale = float(value)
        except (TypeError, ValueError) as exc:
            raise SectionBoundaryError(
                "section.global_scale must be finite and positive"
            ) from exc
        if not math.isfinite(scale) or scale <= 0:
            raise SectionBoundaryError(
                "section.global_scale must be finite and positive"
            )
    return section


def _section_frame(section: dict[str, Any]) -> dict[str, Any]:
    return {
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


def extract_section_boundary_evidence_snapshot(
    *,
    section: dict[str, Any],
    cell_size: float,
    min_cell_support: int = 1,
    min_component_cells: int = 2,
    max_cells: int = MAX_OCCUPIED_CELLS,
    max_boundary_points: int = MAX_TOPOLOGY_POINTS,
    check_grid_origin_sensitivity: bool = True,
) -> dict[str, Any]:
    section = _validate_section(section)
    evidence = extract_section_boundary_evidence_2d(
        section.get("points_uv", []),
        cell_size=cell_size,
        min_cell_support=min_cell_support,
        min_component_cells=min_component_cells,
        max_cells=max_cells,
        max_boundary_points=max_boundary_points,
        check_grid_origin_sensitivity=check_grid_origin_sensitivity,
    )
    result = deepcopy(evidence.public)
    result["section_frame"] = _section_frame(section)
    result["live_connection_used"] = False
    result["scene_mutations_requested"] = False
    return result


def reconstruct_filled_section_profile_snapshot(
    *,
    section: dict[str, Any],
    cell_size: float,
    max_edge_length: float,
    fit_tolerance: float,
    min_cell_support: int = 1,
    min_component_cells: int = 2,
    max_cells: int = MAX_OCCUPIED_CELLS,
    max_boundary_points: int = MAX_TOPOLOGY_POINTS,
    angular_tolerance_degrees: float = 1.0,
    minimum_loop_points: int = 6,
    max_loops: int = 16,
    minimum_arc_angle_degrees: float = 12.0,
    max_segments_per_loop: int = 64,
    require_grid_stability: bool = True,
) -> dict[str, Any]:
    section = _validate_section(section)
    result = reconstruct_filled_section_profile_2d(
        section.get("points_uv", []),
        cell_size=cell_size,
        max_edge_length=max_edge_length,
        fit_tolerance=fit_tolerance,
        min_cell_support=min_cell_support,
        min_component_cells=min_component_cells,
        max_cells=max_cells,
        max_boundary_points=max_boundary_points,
        angular_tolerance_degrees=angular_tolerance_degrees,
        minimum_loop_points=minimum_loop_points,
        max_loops=max_loops,
        minimum_arc_angle_degrees=minimum_arc_angle_degrees,
        max_segments_per_loop=max_segments_per_loop,
        require_grid_stability=require_grid_stability,
    )
    result["section_frame"] = _section_frame(section)
    result["live_connection_used"] = False
    result["scene_mutations_requested"] = False
    return result


def _handle(function, arguments: Any):
    try:
        if not isinstance(arguments, dict):
            raise SectionBoundaryError("Tool arguments must be an object")
        result = function(**arguments)
        return [
            TextContent(
                type="text",
                text=json.dumps(result, allow_nan=False, separators=(",", ":")),
            )
        ]
    except (SectionBoundaryError, TypeError, KeyError, ArithmeticError) as exc:
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(exc)}),
                )
            ],
        )


def handle_extract_section_boundary_evidence(arguments: Any):
    return _handle(extract_section_boundary_evidence_snapshot, arguments)


def handle_reconstruct_filled_section_profile(arguments: Any):
    return _handle(reconstruct_filled_section_profile_snapshot, arguments)
