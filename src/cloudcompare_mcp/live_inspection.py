"""Bounded live inspection and process-local semantic evidence, never CAD authority."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import uuid
from typing import Any

from . import feature_discovery, feature_fit, live
from .inspection_camera import (
    InspectionError, Request, camera_difference, capture, digest, encoded, fingerprint, guard,
    integer, navigate, number, only, text, vector,
)

VERSION = "0.16.3"
VIEWS = {
    "top": ([0, 0, -1], [0, 1, 0]), "bottom": ([0, 0, 1], [0, 1, 0]),
    "front": ([0, 1, 0], [0, 0, 1]), "back": ([0, -1, 0], [0, 0, 1]),
    "left": ([1, 0, 0], [0, 0, 1]), "right": ([-1, 0, 0], [0, 0, 1]),
    "isometric": ([-1, -1, -1], [0, 0, 1]),
}
ROLES = {
    "possible_mounting_face": "a mounting face", "possible_hub": "a hub",
    "possible_round_feature": "a hole, recess, or other round feature",
    "possible_bolt_pattern": "one bolt pattern", "possible_through_feature": "a through feature",
    "possible_scan_clutter": "scan clutter rather than part geometry",
    "possible_manufactured_feature": "one manufactured feature", "unknown_feature": "an intended part feature",
}
LIMITS = {"camera_moves": 6, "captures": 4, "geometric_queries": 2,
          "discovery_calls": 3, "initial_proposals": 6, "proposals_per_inspection": 12,
          "cached_inspections": 16, "metadata_bytes": 128*1024,
          "png_total_bytes": 16*1024*1024, "source_points": 5_000_000}
LIMITATIONS = [
    "Geometry is dimensional evidence in global native units; units are not confirmed.",
    "Images and semantic answers never authorize reconstruction or override numerical refusals.",
    "Freshness covers scene/overlay metadata and the exact deterministic sample plus full query summary, not unobserved whole-cloud geometry or attribute equality.",
    "Read brackets are not atomic; keep the host quiescent. Unobserved change-and-change-back remains indistinguishable.",
    "Native session is a process-local nonce, not authenticated host identity; endpoint is configuration, not authentication.",
    "No automatic visual interpretation runs inside this tool. The calling agent must inspect returned images and issue a reviewed proposal before recording an explicit human answer.",
]


def endpoint() -> dict:
    host, port, _, _ = live._config()
    return {"host": host, "port": port}


class BoundRequest:
    """Reject endpoint changes before and after each call, including restoration."""
    def __init__(self, request: Request, expected: dict):
        self.request, self.endpoint = request, expected
        self.calls: list[str] = []

    def __call__(self, method: str, args: dict, **kwargs: Any) -> Any:
        if endpoint() != self.endpoint:
            raise InspectionError("Configured live endpoint changed")
        self.calls.append(method)
        result = self.request(method, args, **kwargs)
        if endpoint() != self.endpoint:
            raise InspectionError("Configured live endpoint changed during request")
        return result


def scene_sources(scene: Any, excluded_ids: set[int] | None = None) -> list[dict]:
    if not isinstance(scene, dict) or not isinstance(scene.get("entities"), list):
        raise InspectionError("Malformed scene inventory")
    encoded(scene, 1024*1024)
    sources, seen = [], set()

    def walk(items: list, enabled: bool, parent_mesh: bool, depth: int) -> None:
        if depth > 64:
            raise InspectionError("Scene depth exceeds inspection budget")
        for item in items:
            if not isinstance(item, dict):
                raise InspectionError("Malformed scene entity")
            entity_id = integer(item.get("id"), "scene entity ID", 1, 2**32-1)
            if entity_id in seen or len(seen) >= 2048:
                raise InspectionError("Duplicate scene ID or entity budget exceeded")
            seen.add(entity_id)
            if entity_id in (excluded_ids or set()):
                continue
            effective_enabled = enabled and item.get("enabled") is True
            if (item.get("kind") == "point_cloud" and effective_enabled and not parent_mesh
                    and item.get("visible") is True):
                sources.append(item)
            children = item.get("children", [])
            if not isinstance(children, list):
                raise InspectionError("Malformed scene children")
            walk(children, effective_enabled, parent_mesh or item.get("kind") == "mesh", depth+1)
    walk(scene["entities"], True, False, 0)
    return sources


def source_query(source: dict, sample_limit: int) -> dict:
    integer(source.get("point_count"), "source point count", 24, LIMITS["source_points"])
    if source.get("pending_transform_in_hierarchy") is not False:
        raise InspectionError("Source has pending/unknown display transformations; do not bake or clear them automatically")
    vector(source.get("global_shift"), "source shift", 1e15)
    number(source.get("global_scale"), "source scale", 1e-12, 1e12)
    bounds = source.get("bounds_global_native")
    if not isinstance(bounds, dict):
        raise InspectionError("Source has no global bounds")
    lo, hi = vector(bounds.get("min"), "source minimum", 1e15), vector(bounds.get("max"), "source maximum", 1e15)
    if any(a > b for a, b in zip(lo, hi)) or lo == hi:
        raise InspectionError("Source bounds are reversed or degenerate")
    return {"cloud_id": source["id"], "coordinate_space": "global", "max_points": sample_limit,
            "region": {"type": "box", "min": lo, "max": hi}}


def read_sample(request: Request, query: dict, source: dict) -> tuple[dict, list]:
    native = request("cloud.region_query", query, timeout=60.0)
    if not isinstance(native, dict):
        raise InspectionError("Malformed region response")
    encoded(native, 2*1024*1024)
    points = native.get("points")
    if not isinstance(points, list) or not 24 <= len(points) <= query["max_points"]:
        raise InspectionError("Source returned too few points or exceeded the declared sample budget")
    matched = integer(native.get("matched_count"), "matched_count", 24, source["point_count"])
    if (integer(native.get("cloud_id"), "native cloud ID", 1, 2**32-1) != source["id"]
            or matched < len(points) or len(points) != min(matched, query["max_points"])
            or native.get("coordinate_space") != "global"
            or native.get("region_type") != "box" or native.get("source_geometry_preserved") is not True
            or type(native.get("returned_count")) is not int or native["returned_count"] != len(points)
            or type(native.get("truncated")) is not bool or native["truncated"] != (matched > len(points))
            or native.get("sample_strategy") != ("deterministic_reservoir" if matched > len(points) else "all_matches")):
        raise InspectionError("Region identity/count/sampling contract mismatch")
    vector(native.get("source_global_shift"), "native source shift", 1e15)
    number(native.get("source_global_scale"), "native source scale", 1e-12, 1e12)
    if native.get("source_global_shift") != source["global_shift"] or native.get("source_global_scale") != source["global_scale"]:
        raise InspectionError("Source shift/scale changed during acquisition")
    ids, positions = [], []
    for point in points:
        if not isinstance(point, dict):
            raise InspectionError("Malformed sampled point")
        ids.append(integer(point.get("point_index"), "point_index", 0, source["point_count"]-1))
        positions.append(vector(point.get("position_global"), "position_global", 1e15))
        local_position = vector(point.get("position_native_local"), "position_native_local", 1e12)
        for component, local_value, shift in zip(positions[-1], local_position, source["global_shift"]):
            expected = local_value / source["global_scale"] - shift
            tolerance = max(32*math.ulp(expected), 32*math.ulp(component), 1e-12/source["global_scale"])
            if abs(component - expected) > tolerance:
                raise InspectionError("Sample global/local coordinates disagree with the source frame")
    if ids != sorted(set(ids)):
        raise InspectionError("Sample indexes are not distinct and ordered")
    return native, positions


def context_hash(scene: dict, overlays: dict, native: dict, query: dict, camera: dict, configured: dict) -> str:
    return fingerprint("live-inspection-context-v1", {
        "scene_sha256": fingerprint("scene-metadata-v1", scene, 1024*1024),
        "overlays_sha256": fingerprint("overlay-metadata-v1", overlays),
        "acquisition_sha256": fingerprint("region-acquisition-v1", native, 2*1024*1024),
        "query": query, "native_session": camera["native_session"],
        "window_id": camera["window_id"], "endpoint": configured,
    })


def discover(positions: list, threshold: float, kinds: list[str]) -> tuple[list, list]:
    """One fixed invocation per kind, no retry, padding search, or fit-quality tuning."""
    candidates, diagnostics = [], []
    common = {"distance_threshold": threshold, "min_points": 24,
              "min_inlier_fraction": .05, "random_seed": 0}
    options = {"plane": {"max_planes": 2, "iterations": 96},
               "circle": {"max_circles": 2, "iterations": 128},
               "cylinder": {"max_cylinders": 2, "restarts": 8}}
    functions = {"plane": feature_discovery.discover_planes,
                 "circle": feature_discovery.discover_circles,
                 "cylinder": feature_discovery.discover_cylinders}
    for kind in kinds:
        params = common | options[kind]
        try:
            result = functions[kind](positions, **params)
        except feature_fit.FeatureFitError as exc:
            diagnostics.append({"kind": kind, "status": "refused", "reason": str(exc), "parameters": params})
            continue
        diagnostics.append({"kind": kind, "status": "completed", "candidate_count": len(result["candidates"]), "parameters": params})
        for item in result["candidates"]:
            candidates.append({"kind": kind, "numerical_evidence": item, "parameters": params})
    return candidates, diagnostics


class InspectionStore:
    """Bounded, explicitly released in-memory evidence. Restart invalidates all IDs."""
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def inspect(self, args: dict, request: Request) -> tuple[dict, list[str]]:
        only(args, {"cloud_id", "distance_threshold", "sample_limit", "views", "kinds", "restore_camera"}, {"distance_threshold"})
        threshold = number(args["distance_threshold"], "distance_threshold", 1e-12, 1e12)
        limit = integer(args.get("sample_limit", 1024), "sample_limit", 24, 2048)
        if "cloud_id" in args:
            integer(args["cloud_id"], "cloud_id", 1, 2**32-1)
        views, kinds = args.get("views", ["top", "front", "isometric"]), args.get("kinds", ["plane", "cylinder"])
        for values, choices, maximum, name in [(views, VIEWS, 4, "views"), (kinds, {"plane", "circle", "cylinder"}, 3, "kinds")]:
            if (not isinstance(values, list) or not 1 <= len(values) <= maximum
                    or any(not isinstance(v, str) or v not in choices for v in values) or len(set(values)) != len(values)):
                raise InspectionError(f"{name} must be a distinct bounded list of supported names")
        restore = args.get("restore_camera", True)
        if type(restore) is not bool:
            raise InspectionError("restore_camera must be a boolean")
        if len(self.records) >= LIMITS["cached_inspections"]:
            raise InspectionError("Inspection cache full; explicitly release a previous inspection")
        configured = endpoint()
        req = BoundRequest(request, configured)
        initial_camera = navigate(req, {"action": "get"})
        if initial_camera["navigation_supported"] is not True:
            raise InspectionError("Current camera mode cannot be inspected recoverably")
        scene = req("scene.list", {"recursive": True})
        overlays = req("fit.overlay.status", {})
        if not isinstance(overlays, dict) or not isinstance(overlays.get("entities"), list):
            raise InspectionError("Malformed overlay inventory")
        eligible = scene_sources(scene, {overlays.get("group_id")})
        selected = [s for s in eligible if s["id"] == args["cloud_id"]] if "cloud_id" in args else eligible
        if len(selected) != 1:
            raise InspectionError("Choose one explicit visible point-cloud ID; no camera was moved", {
                "source_candidates": [{"id": s["id"], "name": s.get("name"), "point_count": s.get("point_count")} for s in eligible[:12]]})
        source = selected[0]
        query = source_query(source, limit)
        native, positions = read_sample(req, query, source)
        context = context_hash(scene, overlays, native, query, initial_camera, configured)
        raw_candidates, diagnostics = discover(positions, threshold, kinds)
        # CloudCompare's default center-screen auto-pivot can move pivot + camera
        # after a redraw. Own a bounded suspension for the saved-camera token so
        # inspection movement remains deterministic without weakening pose guards.
        baseline = navigate(req, {"action": "save", "suspend_auto_pivot": True})
        last = baseline
        images, captures, total_png = [], [], 0
        failure: Exception | None = None
        recovery: dict = {"status": "not_restored", "baseline": baseline}
        try:
            if not camera_difference(initial_camera, baseline)["guard_equal"]:
                raise InspectionError("Camera changed while geometry was being discovered; no inspection move made",
                    {"stage": "inspection.before_move", "camera_difference": camera_difference(initial_camera, baseline),
                     "expected": initial_camera, "current": baseline})
            last = navigate(req, {"action": "focus", "entity_id": source["id"], **guard(last)})
            for name in views:
                direction, up = VIEWS[name]
                last = navigate(req, {"action": "look", "direction": direction, "up": up, **guard(last)})
                evidence, image, size = capture(req, last)
                total_png += size
                if total_png > LIMITS["png_total_bytes"]:
                    raise InspectionError("Inspection exceeded the total PNG byte budget")
                evidence.update({"sequence": len(captures), "declared_view": name, "context_fingerprint": context,
                                 "scene_fingerprint": fingerprint("scene-metadata-v1", scene, 1024*1024),
                                 "overlay_fingerprint": fingerprint("overlay-metadata-v1", overlays),
                                 "overlay_ids": [e.get("id") for e in overlays.get("entities", [])]})
                evidence["capture_fingerprint"] = fingerprint("inspection-capture-v1", evidence)
                captures.append(evidence)
                images.append(image)
            after_native, _ = read_sample(req, query, source)
            after_scene, after_overlays = req("scene.list", {"recursive": True}), req("fit.overlay.status", {})
            if context_hash(after_scene, after_overlays, after_native, query, last, configured) != context:
                raise InspectionError("Observed source/scene/selection/overlay context changed during inspection")
        except Exception as exc:
            failure = exc
        finally:
            # Restore only when the live pose is still our last known pose. Never
            # overwrite a concurrent human move or a transport-ambiguous mutation.
            try:
                current = navigate(req, {"action": "get"})
                recovery["last_owned"] = last
                recovery["current"] = current
                recovery["camera_difference"] = camera_difference(last, current)
                if not recovery["camera_difference"]["guard_equal"]:
                    raise InspectionError("Camera ownership conflict; automatic restoration refused")
                if restore or failure is not None:
                    restored = navigate(req, {"action": "restore", "restore_token": baseline["restore_token"], **guard(current)})
                    if not camera_difference(baseline, restored)["guard_equal"]:
                        raise InspectionError("Native camera restoration did not compare equal")
                    released = navigate(req, {"action": "release", "restore_token": baseline["restore_token"], "native_session": baseline["native_session"]})
                    # Release is irreversible even if restoring the host auto-pivot mode
                    # subsequently moves the camera. Preserve that fact in recovery.
                    recovery["token_released"] = True
                    recovery["release"] = released
                    final_camera = released.get("camera_state")
                    if final_camera is None:
                        raise InspectionError("Camera token release did not report the post-auto-pivot camera state", {"release": released})
                    if (released.get("auto_pivot_restored_to_original") is not True
                            and released.get("auto_pivot_external_override_preserved") is not True):
                        raise InspectionError("CloudCompare automatic pivot mode was neither restored nor externally superseded",
                            {"stage": "inspection.release_auto_pivot_control", "release": released,
                             "expected": baseline, "current": final_camera})
                    final_difference = camera_difference(baseline, final_camera)
                    # Safety ownership ends at successful exact restore. Release then
                    # returns CloudCompare's original host control (notably automatic
                    # center pivot), which may immediately move the camera. Never
                    # overwrite or tolerance-filter that post-release motion; retain it
                    # as evidence while keeping the exact owned restore as the gate.
                    recovery = {"status": "restored", "camera_fingerprint": restored["camera_fingerprint"],
                                "restored_guard_equal": restored.get("restored_guard_equal", restored.get("restored_equal")),
                                "restored_full_equal": restored.get("restored_equal"),
                                "restored_while_owned": True,
                                "camera_difference": camera_difference(baseline, restored), "token_released": True,
                                "release": released,
                                "release_camera_difference": final_difference,
                                "post_release_navigation_changed": not final_difference["guard_equal"],
                                "post_release_change_scope": "host_or_human_after_release" if not final_difference["guard_equal"] else "unchanged",
                                "auto_pivot_restored_to_original": released.get("auto_pivot_restored_to_original"),
                                "auto_pivot_external_override_preserved": released.get("auto_pivot_external_override_preserved"),
                                "final_camera_fingerprint": final_camera["camera_fingerprint"]}
                else:
                    recovery = {"status": "retained_by_request", "baseline": baseline, "current": current}
            except Exception as exc:
                recovery["error"] = str(exc)
                failure = failure or exc
        if failure is not None:
            if isinstance(failure, InspectionError) and failure.recovery is not None:
                recovery["failure_diagnostics"] = failure.recovery
            raise InspectionError(str(failure), recovery) from failure
        try:
            inspection_id = "inspection-" + uuid.uuid4().hex
            solver_hashes = {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                             for m in (feature_discovery, feature_fit)}
            candidates = []
            for index, item in enumerate(raw_candidates[:6]):
                item = deepcopy(item)
                item.update({"label": chr(65+index), "source_id": source["id"], "context_fingerprint": context, "solver_code_sha256": solver_hashes})
                item["candidate_fingerprint"] = fingerprint("inspection-geometric-candidate-v1", item)
                item["candidate_id"] = "candidate-" + item["candidate_fingerprint"]
                candidates.append(item)
            packet = {"version": VERSION, "contract": "live-inspection-v1", "inspection_id": inspection_id,
                      "context_fingerprint": context, "source": {k: v for k, v in source.items() if k != "children"},
                      "endpoint": configured, "native_session": baseline["native_session"], "window_id": baseline["window_id"],
                      "query": query, "sample_summary": {k: v for k, v in native.items() if k != "points"},
                      "candidates": candidates, "captures": captures, "discovery": diagnostics,
                      "camera_recovery": recovery, "limits": LIMITS, "limitations": LIMITATIONS,
                      "authorizes_reconstruction": False, "native_calls_requested": len(req.calls), "proposals": []}
            record = {"packet": packet, "source": deepcopy(source), "context": context, "query": query,
                      "proposals": {}, "confirmations": {}, "invalidated": None}
            for c in candidates:
                role = {"plane": "possible_mounting_face", "circle": "possible_round_feature", "cylinder": "possible_hub"}[c["kind"]]
                proposal = self._proposal(record, [c["candidate_id"]], role,
                                          f"Could feature {c['label']} be {ROLES[role]}?", [], [], False)
                packet["proposals"].append(proposal)
            packet["inspection_fingerprint"] = fingerprint("inspection-packet-v1", packet)
            encoded(packet)
            self.records[inspection_id] = deepcopy(record)
            return deepcopy(packet), images
        except Exception as exc:
            raise InspectionError(str(exc), recovery) from exc

    def _record(self, inspection_id: str) -> dict:
        text(inspection_id, "inspection_id")
        if inspection_id not in self.records:
            raise InspectionError("Unknown/expired inspection; restart or explicit release invalidates its evidence IDs")
        return self.records[inspection_id]

    def _fresh(self, record: dict, request: Request) -> None:
        if record["invalidated"]:
            raise InspectionError("Inspection permanently stale: " + record["invalidated"])
        packet = record["packet"]
        req = BoundRequest(request, packet["endpoint"])
        try:
            camera = navigate(req, {"action": "get"})
            scene, overlays = req("scene.list", {"recursive": True}), req("fit.overlay.status", {})
            candidates = scene_sources(scene, {overlays.get("group_id")})
            current = next((s for s in candidates if s["id"] == record["source"]["id"]), None)
            if current is None or source_query(current, record["query"]["max_points"]) != record["query"]:
                raise InspectionError("Source/query changed or disappeared")
            native, _ = read_sample(req, record["query"], current)
            end_scene, end_overlays = req("scene.list", {"recursive": True}), req("fit.overlay.status", {})
            end_camera = navigate(req, {"action": "get"})
            for s, o, c in [(scene, overlays, camera), (end_scene, end_overlays, end_camera)]:
                if context_hash(s, o, native, record["query"], c, packet["endpoint"]) != record["context"]:
                    raise InspectionError("Observed evidence/context no longer matches the issued inspection")
        except Exception as exc:
            record["invalidated"] = str(exc)
            raise InspectionError("Cannot bind or reuse semantic intent: " + str(exc)) from exc

    def _proposal(self, record: dict, candidate_ids: list, role: str, question: str,
                  observations: list, capture_indexes: list, reviewed: bool) -> dict:
        packet = record["packet"]
        selected = [next(c for c in packet["candidates"] if c["candidate_id"] == cid) for cid in candidate_ids]
        proposal = {"proposal_id": "proposal-" + uuid.uuid4().hex, "inspection_id": packet["inspection_id"],
                    "semantic_role": role, "question": question, "context_fingerprint": record["context"],
                    "candidate_ids": candidate_ids, "candidate_fingerprints": [c["candidate_fingerprint"] for c in selected],
                    "candidate_labels": [c["label"] for c in selected],
                    "capture_fingerprints": [packet["captures"][i]["capture_fingerprint"] for i in capture_indexes],
                    "visual_observations": observations, "visual_observations_provenance": "caller_asserted" if reviewed else "not_yet_supplied",
                    "requires_agent_review": not reviewed, "requires_human_confirmation": True,
                    "support": "See bound numerical candidates; geometric support does not prove manufacturing role.",
                    "ambiguity": "semantic_role_unconfirmed", "authorizes_reconstruction": False}
        proposal["proposal_fingerprint"] = fingerprint("semantic-proposal-v1", proposal)
        record["proposals"][proposal["proposal_id"]] = deepcopy(proposal)
        return proposal

    def propose(self, args: dict, request: Request) -> dict:
        only(args, {"inspection_id", "candidate_ids", "semantic_role", "question", "visual_observations", "capture_indexes"},
             {"inspection_id", "candidate_ids", "semantic_role", "question", "visual_observations", "capture_indexes"})
        record = self._record(args["inspection_id"])
        if len(record["proposals"]) >= LIMITS["proposals_per_inspection"]:
            raise InspectionError("Proposal budget reached; no hidden extra inspection")
        ids, indexes, observations = args["candidate_ids"], args["capture_indexes"], args["visual_observations"]
        valid_ids = {c["candidate_id"] for c in record["packet"]["candidates"]}
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 6 or any(not isinstance(c, str) or c not in valid_ids for c in ids)
                or len(set(ids)) != len(ids)):
            raise InspectionError("Use distinct geometric candidate IDs from this inspection")
        if not isinstance(indexes, list) or not 1 <= len(indexes) <= 4:
            raise InspectionError("Bind one to four actual captured views")
        for i in indexes:
            integer(i, "capture index", 0, len(record["packet"]["captures"])-1)
        if len(set(indexes)) != len(indexes):
            raise InspectionError("Capture indexes must be distinct")
        if not isinstance(observations, list) or not 1 <= len(observations) <= 3:
            raise InspectionError("Supply one to three explicit visual observations")
        for observation in observations:
            text(observation, "visual observation", 512)
        if not isinstance(args["semantic_role"], str) or args["semantic_role"] not in ROLES:
            raise InspectionError("Unknown semantic role")
        text(args["question"], "question", 512)
        self._fresh(record, request)
        return self._proposal(record, ids, args["semantic_role"], args["question"], observations, indexes, True)

    def confirm(self, args: dict, request: Request) -> dict:
        only(args, {"inspection_id", "proposal_id", "expected_proposal_fingerprint", "answer", "answer_text"},
             {"inspection_id", "proposal_id", "expected_proposal_fingerprint", "answer", "answer_text"})
        record = self._record(args["inspection_id"])
        proposal = record["proposals"].get(text(args["proposal_id"], "proposal_id"))
        if proposal is None or digest(args["expected_proposal_fingerprint"]) != proposal["proposal_fingerprint"]:
            raise InspectionError("Unknown or changed semantic proposal")
        if proposal["requires_agent_review"]:
            raise InspectionError("Review captured images and issue a provenance-bound proposal before asking the human")
        if args["answer"] not in ("yes", "no", "unsure"):
            raise InspectionError("Answer must explicitly be yes, no, or unsure; never infer it from context")
        text(args["answer_text"], "exact human answer text", 2048)
        self._fresh(record, request)
        answer = {"confirmation_id": "answer-" + uuid.uuid4().hex,
                  "inspection_id": args["inspection_id"], "proposal_id": proposal["proposal_id"],
                  "proposal_fingerprint": proposal["proposal_fingerprint"], "context_fingerprint": record["context"],
                  "answer": args["answer"], "answer_text": args["answer_text"],
                  "answer_provenance": "caller_reports_explicit_human_answer_not_authenticated_identity",
                  "confirmed_semantic_role": proposal["semantic_role"] if args["answer"] == "yes" else None,
                  "status": {"yes": "confirmed", "no": "rejected", "unsure": "uncertain"}[args["answer"]],
                  "authorizes_reconstruction": False}
        answer["confirmation_fingerprint"] = fingerprint("semantic-answer-v1", answer)
        record["confirmations"][proposal["proposal_id"]] = deepcopy(answer)
        return self._semantic_state(record, answer)

    def _semantic_state(self, record: dict, answer: dict) -> dict:
        proposal = record["proposals"][answer["proposal_id"]]
        conflicts = []
        if answer["answer"] == "yes":
            for pid, other in record["confirmations"].items():
                other_proposal = record["proposals"][pid]
                if (pid != answer["proposal_id"] and other["answer"] == "yes"
                        and other_proposal["semantic_role"] != proposal["semantic_role"]
                        and set(other_proposal["candidate_ids"]) & set(proposal["candidate_ids"])):
                    conflicts.append(pid)
        return deepcopy(answer) | {"overlapping_role_confirmations": sorted(conflicts),
            "semantic_review_required": bool(conflicts),
            "semantic_intent_usable": answer["answer"] == "yes" and not conflicts,
            "authorizes_reconstruction": False}

    def validate(self, args: dict, request: Request) -> dict:
        only(args, {"inspection_id", "proposal_id", "confirmation_fingerprint"},
             {"inspection_id", "proposal_id", "confirmation_fingerprint"})
        record = self._record(args["inspection_id"])
        text(args["proposal_id"], "proposal_id")
        digest(args["confirmation_fingerprint"])
        answer = record["confirmations"].get(args["proposal_id"])
        if answer is None or answer["confirmation_fingerprint"] != args["confirmation_fingerprint"]:
            return {"status": "unknown_or_superseded", "fresh": False, "authorizes_reconstruction": False}
        try:
            self._fresh(record, request)
        except InspectionError as exc:
            return {"status": "stale", "fresh": False, "reason": str(exc), "authorizes_reconstruction": False}
        return self._semantic_state(record, answer) | {"fresh": True}

    def release(self, args: dict) -> dict:
        only(args, {"inspection_id", "inspection_fingerprint"}, {"inspection_id", "inspection_fingerprint"})
        record = self._record(args["inspection_id"])
        if digest(args["inspection_fingerprint"]) != record["packet"]["inspection_fingerprint"]:
            raise InspectionError("Inspection fingerprint mismatch")
        recovery = deepcopy(record["packet"]["camera_recovery"])
        del self.records[args["inspection_id"]]
        return {"released": True, "inspection_id": args["inspection_id"], "camera_recovery": recovery,
                "note": "Only this process-local evidence was released. Retained native camera tokens require explicit camera restore/release."}
