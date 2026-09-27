#!/usr/bin/env python3
"""Exercise overlay safety on an already-open disposable CloudCompare instance.

No screenshots or raw points are captured. Existing overlays cause a safe refusal.
The specified source is only a frame reference; it is never edited or deleted.
Scene metadata equality is checked, not a full point/attribute checksum.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from cloudcompare_mcp.live import LiveBridgeError, request


def entities_by_id(scene: dict[str, Any]) -> dict[int, dict[str, Any]]:
    found = {}
    pending = list(scene.get("entities", []))
    while pending:
        node = pending.pop()
        found[int(node["id"])] = node
        pending.extend(node.get("children", []))
    return found


def overlay_specs(source: dict[str, Any]) -> list[dict[str, Any]]:
    bounds = source["bounds_global_native"]
    low, high = bounds["min"], bounds["max"]
    center = [a / 2 + b / 2 for a, b in zip(low, high)]
    span = max(b - a for a, b in zip(low, high))
    if len(center) != 3 or not all(map(math.isfinite, [*center, span])) or span <= 0:
        raise ValueError("Source must have finite, nonzero global bounds")
    radius = span * 0.03
    a, b = center.copy(), center.copy()
    a[2] -= radius
    b[2] += radius
    return [
        dict(kind="plane", center=center, normal=[0, 0, 1], width=radius * 4, height=radius * 3),
        dict(kind="circle", center=center, normal=[0, 0, 1], radius=radius),
        dict(kind="cylinder", endpoint_a=a, endpoint_b=b, radius=radius, show_axis=True),
        dict(kind="axis", endpoint_a=a, endpoint_b=b),
    ]


def run_checks(source_id: int, report: dict[str, Any]) -> None:
    def scene():
        return request("scene.list", {"recursive": True})

    def status():
        return request("fit.overlay.status", {})

    def create(spec):
        return request("fit.overlay.create", {"source_cloud_id": source_id, **spec}, timeout=30)

    def passed(name):
        report["checks"].append(name)

    def rejected_without_mutation(method, params):
        before = scene()["entities"]
        try:
            request(method, params, timeout=30)
        except LiveBridgeError:
            pass
        else:
            raise AssertionError(f"{method} unexpectedly succeeded")
        assert scene()["entities"] == before, f"Rejected {method} changed scene metadata"

    report["ping"] = request("ping", {})
    report["capabilities"] = request("capabilities.get", {})
    if status().get("active"):
        raise RuntimeError("Existing overlays are not owned by this run. Clear them explicitly or restart the disposable test instance first.")
    baseline = scene()["entities"]
    source = entities_by_id({"entities": baseline})[source_id]
    if source.get("kind") != "point_cloud":
        raise ValueError("source-cloud-id must identify a standalone point cloud")
    specs = overlay_specs(source)
    report["source_before"] = {key: value for key, value in source.items() if key != "children"}
    invalid = [
        {**specs[0], "normal": [0, 0, 0]},
        {**specs[1], "radius": -1},
        {**specs[1], "radius": 1e300},
        {**specs[1], "center": [1e300, 0, 0]},
        {**specs[3], "endpoint_b": specs[3]["endpoint_a"]},
    ]
    for index, spec in enumerate(invalid):
        rejected_without_mutation("fit.overlay.create", {"source_cloud_id": source_id, **spec})
        assert not status()["active"]
        passed(f"invalid_without_group_{index}")

    # This same-name group is deliberately not an overlay, and is ours to remove.
    same_name_id = int(request("group.create", {"name": "MCP Fit Overlays"})["id"])
    assert not status()["active"], "Display name incorrectly granted ownership"
    for spec in specs:
        create(spec)
        passed(f"create_{spec['kind']}")
    managed = status()
    assert managed["clear_safe"] and managed["overlay_entity_count"] == 5
    assert managed["group_id"] != same_name_id
    for index, spec in enumerate(invalid):
        rejected_without_mutation("fit.overlay.create", {"source_cloud_id": source_id, **spec})
        passed(f"invalid_with_group_{index}")

    # All foreign nodes below are newly created by this run, never user data.
    foreign = int(request("group.create", {
        "name": "acceptance_foreign_parent", "destination_group_id": managed["group_id"],
    })["id"])
    request("group.create", {"name": "acceptance_foreign_nested", "destination_group_id": foreign})
    assert status()["clear_safe"] is False
    rejected_without_mutation("fit.overlay.clear", {})
    rejected_without_mutation("fit.overlay.create", {"source_cloud_id": source_id, **specs[1]})
    passed("foreign_descendants_block_clear_and_create")
    request("entity.delete", {"ids": [foreign]})
    assert status()["clear_safe"]
    request("fit.overlay.clear", {})
    assert not status()["active"]
    assert same_name_id in entities_by_id(scene())
    passed("same_name_user_group_survives_clear")
    request("fit.overlay.clear", {})
    passed("idempotent_clear")
    request("entity.delete", {"ids": [same_name_id]})
    assert scene()["entities"] == baseline
    passed("scene_metadata_restored")

    create(specs[1])
    group_id = status()["group_id"]
    request("entity.delete", {"ids": [group_id]})
    assert not status()["active"]
    create(specs[1])
    assert status()["clear_safe"]
    request("fit.overlay.clear", {})
    assert scene()["entities"] == baseline
    passed("manual_group_delete_recreate_clear")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cloud-id", type=int, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.outdir.resolve()
    repo = Path(__file__).resolve().parents[1]
    if outdir == repo or repo in outdir.parents:
        parser.error("Acceptance evidence must be outside the repository")
    outdir.mkdir(parents=True, exist_ok=True)
    report = {"source_cloud_id": args.source_cloud_id, "checks": [], "status": "RUNNING",
              "boundary": "Real bridge lifecycle and scene-metadata equality; not a full geometry checksum or visual acceptance"}
    try:
        run_checks(args.source_cloud_id, report)
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["recovery"] = "Preserve evidence. This is a disposable test instance: close without saving, then reopen the test copy. No automatic cleanup after a failure."
    path = outdir / "overlay_acceptance.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks_passed": len(report["checks"]), "report": str(path)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
