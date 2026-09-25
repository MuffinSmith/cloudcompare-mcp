#!/usr/bin/env python3
"""End-to-end live acceptance harness for the safe Fusion 360 reference workflow.

Run this only against an already-open CloudCompare instance containing the intended
aligned source clouds. The script never renames, hides, transforms, deletes, or
overwrites the supplied source IDs.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from cloudcompare_mcp.fusion_mesh import (
    pymeshlab_available,
    reconstruct_ball_pivoting,
    simplify_quadric,
)
from cloudcompare_mcp.live import LiveBridgeError, request


def flatten_entities(result: Any) -> dict[int, dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("id"), int):
                found[int(value["id"])] = value
            for child in value.get("children", []):
                visit(child)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    return found


def first_kind_id(value: Any, kind: str) -> int | None:
    entities = flatten_entities(value)
    for entity_id, entity in entities.items():
        if entity.get("kind") == kind:
            return entity_id
    return None


def integrity_snapshot(entity: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "name",
        "kind",
        "visible",
        "enabled",
        "point_count",
        "triangle_count",
        "bounds_native",
        "bounds_global_native",
        "has_normals",
        "has_colors",
        "scalar_fields",
        "global_shift",
        "global_scale",
    )
    return {key: entity.get(key) for key in keys}


def capture(path: Path) -> dict[str, Any]:
    shot = request("view.capture", {})
    path.write_bytes(base64.b64decode(shot["png_base64"]))
    return {"path": str(path.resolve()), "width": shot["width"], "height": shot["height"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud-id", type=int, action="append", required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--units", default="unknown", help="Caller-confirmed intended Fusion import units")
    parser.add_argument("--target-triangles", type=int, default=350_000)
    parser.add_argument("--ball-radius-percent", type=float)
    parser.add_argument("--exercise-errors", action="store_true")
    args = parser.parse_args()

    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    report_path = outdir / "fan_export_report.json"
    master_path = outdir / "fan_master.ply"
    reference_path = outdir / "fan_reference.obj"

    report: dict[str, Any] = {
        "requested_source_ids": args.cloud_id,
        "outputs": {},
        "checks": {},
        "warnings": [],
    }

    ping = request("ping", {})
    capabilities = request("capabilities.get", {})
    report["ping"] = ping
    report["capabilities"] = capabilities

    scene_before = request("scene.list", {"recursive": True})
    entities_before = flatten_entities(scene_before)
    missing = [entity_id for entity_id in args.cloud_id if entity_id not in entities_before]
    if missing:
        raise RuntimeError(f"Source IDs are not present in the live scene: {missing}")

    wrong_type = [
        entity_id
        for entity_id in args.cloud_id
        if entities_before[entity_id].get("kind") != "point_cloud"
    ]
    if wrong_type:
        raise RuntimeError(f"Source IDs are not standalone point clouds: {wrong_type}")

    originals_before = {
        entity_id: integrity_snapshot(entities_before[entity_id])
        for entity_id in args.cloud_id
    }
    report["originals_before"] = originals_before
    report["visual_before"] = capture(outdir / "fan_before.png")

    selection = request(
        "selection.set",
        {"ids": args.cloud_id, "clear": True},
    )
    report["checks"]["multi_selection"] = selection
    if set(selection.get("selected_ids", [])) != set(args.cloud_id):
        raise RuntimeError(f"Nine/multi-cloud selection verification failed: {selection}")

    clones = request(
        "entity.clone",
        {"ids": args.cloud_id, "name_suffix": ".fusion_working"},
        timeout=600.0,
    )
    clone_ids = [int(item["clone_id"]) for item in clones["mappings"]]
    report["clones"] = clones

    merged = request(
        "cloud.merge",
        {
            "ids": clone_ids,
            "name": "fan_fusion_working_merged",
            "coordinate_frame_policy": "strict",
        },
        timeout=900.0,
    )
    merged_id = int(merged["id"])
    report["merged"] = merged
    if not merged.get("point_count_verified"):
        raise RuntimeError("Merged point count was not verified")

    master_export = request(
        "entity.export",
        {
            "entity_id": merged_id,
            "path": str(master_path),
            "overwrite": False,
            "intended_import_units": args.units,
        },
        timeout=900.0,
    )
    report["outputs"]["fan_master"] = master_export

    if not pymeshlab_available():
        report["warnings"].append(
            "PyMeshLab is not installed, so the full-3D ball-pivoting and QEM stages were not run. "
            "Install cloudcompare-mcp[fusion] and rerun this acceptance harness."
        )
        report["visual_after"] = capture(outdir / "fan_after.png")
    else:
        reconstruction = reconstruct_ball_pivoting(
            cloud_id=merged_id,
            ball_radius_percent=args.ball_radius_percent,
        )
        report["reconstruction"] = reconstruction
        mesh_id = first_kind_id(reconstruction.get("live_loaded_entity"), "mesh")
        if mesh_id is None:
            raise RuntimeError("Could not identify the live triangle mesh loaded after reconstruction")

        mesh_triangles = int(reconstruction["after"]["triangle_count"])
        final_mesh_id = mesh_id
        if mesh_triangles > 500_000:
            simplification = simplify_quadric(
                mesh_id=mesh_id,
                target_triangles=args.target_triangles,
                preserve_boundaries=True,
                preserve_sharp_features=True,
                preserve_topology=True,
            )
            report["simplification"] = simplification
            simplified_id = first_kind_id(simplification.get("live_loaded_entity"), "mesh")
            if simplified_id is None:
                raise RuntimeError("Could not identify the simplified live mesh")
            final_mesh_id = simplified_id
        else:
            report["simplification"] = {
                "skipped": True,
                "reason": f"Reconstructed mesh already has {mesh_triangles} triangles (<= 500000).",
            }

        reference_export = request(
            "entity.export",
            {
                "entity_id": final_mesh_id,
                "path": str(reference_path),
                "overwrite": False,
                "intended_import_units": args.units,
            },
            timeout=900.0,
        )
        if int(reference_export.get("triangle_count", 0)) <= 0:
            raise RuntimeError("fan_reference.obj did not validate as a real triangle mesh")
        report["outputs"]["fan_reference"] = reference_export
        report["visual_after"] = capture(outdir / "fan_after.png")

        if args.exercise_errors:
            error_checks: dict[str, Any] = {}
            try:
                request("entity.export", {
                    "entity_id": final_mesh_id,
                    "path": str(reference_path),
                    "overwrite": False,
                })
                error_checks["existing_output_refused"] = False
            except LiveBridgeError:
                error_checks["existing_output_refused"] = True

            try:
                request("cloud.merge", {"ids": [final_mesh_id], "coordinate_frame_policy": "strict"})
                error_checks["invalid_merge_type_refused"] = False
            except LiveBridgeError:
                error_checks["invalid_merge_type_refused"] = True

            selection_probe = request(
                "selection.set",
                {"ids": args.cloud_id + [4_294_967_000], "clear": True},
            )
            error_checks["missing_id_reported"] = 4_294_967_000 in selection_probe.get("missing_ids", [])
            report["checks"]["error_cases"] = error_checks

    scene_after = request("scene.list", {"recursive": True})
    entities_after = flatten_entities(scene_after)
    originals_after = {
        entity_id: integrity_snapshot(entities_after[entity_id])
        for entity_id in args.cloud_id
    }
    report["originals_after"] = originals_after
    unchanged = originals_before == originals_after
    report["checks"]["original_sources_unchanged"] = unchanged
    if not unchanged:
        raise RuntimeError("Original source integrity snapshot changed during the acceptance workflow")

    report["coordinate_unit_assumption"] = {
        "native_units": "unknown unless caller-confirmed",
        "intended_import_units": args.units,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
