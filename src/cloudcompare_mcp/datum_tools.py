"""MCP surface for snapshot-only CAD datum and relationship analysis."""
from __future__ import annotations

from copy import deepcopy
import json

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .datum_relationships import (
    DatumError, MAX_FEATURES, analyze_feature_relationships, build_live_datum_frame,
)

VECTOR = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
NAME = {"type": "string", "minLength": 1, "maxLength": 128}
OBSERVATION = {
    "type": "object",
    "description": "Complete global/native fit snapshot. Keep upstream evidence; no point arrays. A point uses position_global.",
    "required": ["type", "coordinate_space", "units"],
    "properties": {
        "type": {"enum": ["plane", "line", "circle", "cylinder", "point"]},
        "coordinate_space": {"const": "global"}, "units": {"const": "native"},
        **{key: VECTOR for key in ("centroid", "normal", "direction", "center", "axis_point", "axis_direction", "position_global")},
        "radius": {"type": "number", "exclusiveMinimum": 0},
    },
    "oneOf": [
        {"properties": {"type": {"const": kind}}, "required": keys}
        for kind, keys in (
            ("plane", ["centroid", "normal"]), ("line", ["centroid", "direction"]),
            ("circle", ["center", "normal", "radius"]),
            ("cylinder", ["axis_point", "axis_direction", "radius"]), ("point", ["position_global"]),
        )
    ],
}
FEATURE = {
    "type": "object", "additionalProperties": False, "required": ["id", "observation"],
    "properties": {"id": NAME, "observation": OBSERVATION,
                   "provenance": {"type": "object", "description": "Optional compact source evidence (max 4096 bytes), copied unchanged; include known global shift/scale here."}},
}
COMMON = {
    "features": {"type": "array", "items": FEATURE, "minItems": 2, "maxItems": MAX_FEATURES},
    "frame_id": {**NAME, "description": "Caller assertion that all snapshots share this global reference frame; not a live registration/freshness check."},
    "distance_tolerance": {"type": "number", "exclusiveMinimum": 0,
                           "description": "Explicit native-unit tolerance, not measurement uncertainty. Must resolve the supplied global coordinates."},
}


def capabilities() -> dict:
    return {"version": "0.14.0", "snapshot_relationships": True, "snapshot_datum_frames": True,
            "live_connection_required": False, "native_rebuild_required": False,
            "max_features": MAX_FEATURES, "max_pairs": MAX_FEATURES * (MAX_FEATURES - 1) // 2,
            "supported_observations": ["plane", "line", "circle", "cylinder", "point"],
            "persistent_acceptance": False, "manufacturing_intent_confirmed": False}


def tools() -> list[Tool]:
    definitions = [
        ("analyze_feature_relationships",
         "Analyze supplied global/native measured fit snapshots without contacting CloudCompare. "
         "Return bounded plane/axis relationships, signed reference offsets, ideal intersections, "
         "diameter and center distances as candidates, never confirmed CAD intent. "
         "Use complete fit_live_* results in features[].observation with stable caller IDs; "
         "discovery candidates need an explicit global fit envelope and provenance.",
         {"angular_tolerance_degrees": {"type": "number", "minimum": 0, "maximum": 45}},
         ["angular_tolerance_degrees"]),
        ("build_live_datum_frame",
         "Construct a right-handed CAD frame from supplied global/native fit snapshots; NO live I/O despite the name. "
         "Primary plane sets Z; a secondary plane intersection or projected line/circle/cylinder axis sets X. "
         "Optional point/circle origin must be within distance_tolerance and is explicitly projected; "
         "line/cylinder origin uses an axis-plane intersection. Default origin is the primary centroid. "
         "Hints resolve axis signs only; canonical signs otherwise remain physically ambiguous.",
         {"primary_plane_id": NAME, "secondary_feature_id": NAME, "origin_feature_id": NAME,
          "z_direction_hint": VECTOR, "x_direction_hint": VECTOR,
          "minimum_datum_angle_degrees": {"type": "number", "minimum": 0.0001, "maximum": 45, "default": 1}},
         ["primary_plane_id", "secondary_feature_id"]),
    ]
    return [Tool(name=name, description=description,
                 inputSchema={"type": "object", "additionalProperties": False,
                              "properties": deepcopy({**COMMON, **extra}),
                              "required": ["features", "frame_id", "distance_tolerance", *required]},
                 annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                             idempotentHint=True, openWorldHint=False))
            for name, description, extra, required in definitions]


def _handle(function, arguments):
    try:
        if not isinstance(arguments, dict):
            raise DatumError("Tool arguments must be an object")
        result = function(**arguments)
        return [TextContent(type="text", text=json.dumps(result, allow_nan=False, indent=2))]
    except (DatumError, TypeError, KeyError, ArithmeticError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=json.dumps({"error": str(exc)}))])


def handle_analyze_feature_relationships(arguments):
    return _handle(analyze_feature_relationships, arguments)


def handle_build_live_datum_frame(arguments):
    return _handle(build_live_datum_frame, arguments)
