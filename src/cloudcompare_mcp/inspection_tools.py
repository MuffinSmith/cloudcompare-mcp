"""MCP schemas and dispatch for the bounded camera/semantic workflow."""
from __future__ import annotations

import copy
import json
import jsonschema
from mcp.types import CallToolResult, ImageContent, TextContent, Tool, ToolAnnotations

from .inspection_camera import InspectionError, encoded, navigate
from .live_inspection import InspectionStore, LIMITS, ROLES, VERSION, VIEWS

STORE = InspectionStore()


def obj(properties: dict, required: list[str] = ()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def bounded_number(lo: float, hi: float) -> dict:
    return {"type": "number", "minimum": lo, "maximum": hi}


def bounded_int(lo: int, hi: int) -> dict:
    return {"type": "integer", "minimum": lo, "maximum": hi}


def string(limit: int = 128) -> dict:
    return {"type": "string", "minLength": 1, "maxLength": limit}


def array(items: dict, lo: int, hi: int, unique: bool = False) -> dict:
    return {"type": "array", "items": items, "minItems": lo, "maxItems": hi, "uniqueItems": unique}


def vector(limit: float = 1e12) -> dict:
    return array(bounded_number(-limit, limit), 3, 3)


DIGEST = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
GUARD = {"native_session": string(), "window_id": bounded_int(0, 2**31-1), "expected_camera_fingerprint": DIGEST}
IDENTITY = {"inspection_id": string(), "proposal_id": string()}
MOVES = {
    "look": {"direction": vector(), "up": vector()},
    "orbit": {"axis_camera": vector(), "degrees": bounded_number(-180, 180)},
    "pan": {"right_fraction": bounded_number(-1, 1), "up_fraction": bounded_number(-1, 1)},
    "zoom": {"factor": bounded_number(.1, 10)},
    "restore": {"restore_token": string()},
}
CAMERA_CHOICES = [obj({"action": {"const": action}} | GUARD | fields,
                      ["action", *GUARD, *fields]) for action, fields in MOVES.items()]
for fields in ({}, {"center_global": vector(1e15), "width_global": bounded_number(1e-12, 1e15)},
               {"min_global": vector(1e15), "max_global": vector(1e15)}):
    CAMERA_CHOICES.append(obj({"action": {"const": "focus"}, "entity_id": bounded_int(1, 2**32-1)} | GUARD | fields,
                              ["action", "entity_id", *GUARD, *fields]))
for legacy_choice in list(CAMERA_CHOICES):
    choice = copy.deepcopy(legacy_choice)
    choice["properties"]["expected_camera_guard_fingerprint"] = choice["properties"].pop("expected_camera_fingerprint")
    choice["required"][choice["required"].index("expected_camera_fingerprint")] = "expected_camera_guard_fingerprint"
    CAMERA_CHOICES.append(choice)
CAMERA_CHOICES.append(obj({"action": {"const": "release"}, "native_session": string(), "restore_token": string()},
                          ["action", "native_session", "restore_token"]))
SCHEMAS = {
    "get_live_camera": obj({"save": {"type": "boolean", "default": False},
                            "suspend_auto_pivot": {"type": "boolean", "default": False}}),
    "set_live_camera": {"type": "object", "oneOf": CAMERA_CHOICES},
    "inspect_live_part": obj({
        "cloud_id": bounded_int(1, 2**32-1), "distance_threshold": bounded_number(1e-12, 1e12),
        "sample_limit": bounded_int(24, 2048), "views": array({"enum": list(VIEWS)}, 1, 4, True),
        "kinds": array({"enum": ["plane", "circle", "cylinder"]}, 1, 3, True),
        "restore_camera": {"type": "boolean", "default": True}}, ["distance_threshold"]),
    "propose_live_semantic_feature": obj({"inspection_id": string(),
        "candidate_ids": array({"type": "string", "pattern": "^candidate-[0-9a-f]{64}$"}, 1, 6, True),
        "semantic_role": {"enum": list(ROLES)}, "question": string(512),
        "visual_observations": array(string(512), 1, 3),
        "capture_indexes": array(bounded_int(0, 3), 1, 4, True)},
        ["inspection_id", "candidate_ids", "semantic_role", "question", "visual_observations", "capture_indexes"]),
    "confirm_live_semantic_feature": obj(IDENTITY | {"expected_proposal_fingerprint": DIGEST,
        "answer": {"enum": ["yes", "no", "unsure"]}, "answer_text": string(2048)},
        [*IDENTITY, "expected_proposal_fingerprint", "answer", "answer_text"]),
    "validate_live_semantic_confirmation": obj(IDENTITY | {"confirmation_fingerprint": DIGEST},
        [*IDENTITY, "confirmation_fingerprint"]),
    "release_live_inspection": obj({"inspection_id": string(), "inspection_fingerprint": DIGEST},
        ["inspection_id", "inspection_fingerprint"]),
}
DESCRIPTIONS = {
    "get_live_camera": "Get native CloudCompare camera state; save=true creates a same-session/window restoration token (max eight, explicit release). With save=true, suspend_auto_pivot=true owns a temporary suspension of CloudCompare's center-screen automatic pivot until that token is released. qMCPBridge 0.13.2/revision 9 provides camera guards, diagnostics and cc-camera-auto-pivot-v1. Host-render camera center is not a global world-eye coordinate.",
    "set_live_camera": "Deterministic source-safe camera look/orbit/pan/zoom/focus/restore/release. Moves require current native session/window and exactly one expected_camera_guard_fingerprint (navigation) or expected_camera_fingerprint (legacy strict full state). Orbit uses camera-space axes, pan uses view-span fractions, zoom>1 zooms in. Focus requires a visible source cloud frame for global coordinates. No GUI mouse simulation.",
    "inspect_live_part": "Bounded agent inspection: explicit dimensional threshold, deterministic geometry sample, up to four declared views with real PNGs, geometric candidates and draft semantic questions. Restores camera by default. Does not interpret images or confirm semantics; next inspect the returned PNGs and propose a reviewed feature. No source/selection/overlay editing or reconstruction.",
    "propose_live_semantic_feature": "Bind the calling agent's explicit visual observations and concise semantic question to issued geometric candidate IDs and captured-view indexes. Rechecks observed source freshness. This is a hypothesis, not human confirmation or dimensional authority.",
    "confirm_live_semantic_feature": "Record an explicit human yes/no/unsure answer and its exact text for a reviewed proposal fingerprint, after freshness checks. Never infer yes from conversation context. Caller-reported intent, not authenticated identity; cannot override numerical refusal or authorize CAD reconstruction.",
    "validate_live_semantic_confirmation": "Revalidate latest answer against the same observed source/scene/sample and native session. Old answers become stale/superseded, overlapping different roles require review. Sampled freshness is not whole-cloud equality; camera motion alone does not stale frozen capture evidence.",
    "release_live_inspection": "Explicitly discard one process-local inspection and its semantic proposals/answers. Does not modify sources or release unrelated camera tokens/overlays. Retained camera tokens still require explicit camera restore/release.",
}


def tools() -> list[Tool]:
    return [Tool(name=name, description=DESCRIPTIONS[name], inputSchema=schema,
                 annotations=ToolAnnotations(readOnlyHint=name == "validate_live_semantic_confirmation",
                     destructiveHint=False, idempotentHint=False, openWorldHint=True))
            for name, schema in SCHEMAS.items()]


def capabilities(available: bool) -> dict:
    return {"version": VERSION, "native_camera_required": "0.13.2 / workflow revision 9 for bounded auto-pivot ownership; legacy guards remain supported outside inspection",
            "available": available, "bounded": True, "limits": LIMITS,
            "automatic_image_interpretation": False, "precise_human_picking_required": False,
            "semantic_fingerprint_authorizes_reconstruction": False,
            "inspection_overlays_created": False, "freshness_scope": "observed_sample_and_scene_metadata"}


def handlers(request, store: InspectionStore | None = None) -> dict:
    active_store = STORE if store is None else store

    def execute(name: str, args: dict):
        try:
            encoded(args, 16*1024)
            jsonschema.Draft202012Validator(SCHEMAS[name]).validate(args)
            images = []
            if name == "get_live_camera":
                if args.get("suspend_auto_pivot", False) and not args.get("save", False):
                    raise InspectionError("suspend_auto_pivot requires save=true")
                camera_args = {"action": "save" if args.get("save", False) else "get"}
                if args.get("save", False) and args.get("suspend_auto_pivot", False):
                    camera_args["suspend_auto_pivot"] = True
                result = navigate(request, camera_args)
            elif name == "set_live_camera":
                result = navigate(request, args)
            elif name == "inspect_live_part":
                result, images = active_store.inspect(args, request)
            elif name == "propose_live_semantic_feature":
                result = active_store.propose(args, request)
            elif name == "confirm_live_semantic_feature":
                result = active_store.confirm(args, request)
            elif name == "validate_live_semantic_confirmation":
                result = active_store.validate(args, request)
            else:
                result = active_store.release(args)
            body = encoded(result).decode("ascii")
            return [TextContent(type="text", text=body),
                    *[ImageContent(type="image", mimeType="image/png", data=image) for image in images]]
        except Exception as exc:
            error = {"status": "blocked", "reason": str(exc)[:4096], "authorizes_reconstruction": False}
            if isinstance(exc, InspectionError) and exc.recovery is not None:
                error["recovery"] = exc.recovery
            return CallToolResult(isError=True, content=[TextContent(type="text", text=json.dumps(error, allow_nan=False))])

    return {name: (lambda args, name=name: execute(name, args)) for name in SCHEMAS}
