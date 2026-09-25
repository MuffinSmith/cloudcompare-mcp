"""Optional local mesh reconstruction/simplification backends for live CloudCompare workflows.

The functions in this module operate only on temporary copies exported from the live
CloudCompare scene. They never modify source entities or project files.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import math
import tempfile
from pathlib import Path
from typing import Any

from .live import request as live_request


class FusionMeshBackendError(RuntimeError):
    """Raised when an optional reverse-engineering backend cannot safely complete."""


def pymeshlab_available() -> bool:
    return importlib.util.find_spec("pymeshlab") is not None


def pymeshlab_version() -> str | None:
    """Return the installed distribution version without importing native modules."""
    if not pymeshlab_available():
        return None
    try:
        return importlib.metadata.version("pymeshlab")
    except importlib.metadata.PackageNotFoundError:
        return None


def _json_value(value: Any) -> Any:
    """Convert PyMeshLab/numpy result values to JSON-safe values without guessing units."""
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass

    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _bounds(mesh: Any) -> dict[str, list[float]]:
    vertices = mesh.vertex_matrix()
    if vertices.size == 0:
        return {}
    minimum = vertices.min(axis=0)
    maximum = vertices.max(axis=0)
    return {
        "min": [float(x) for x in minimum],
        "max": [float(x) for x in maximum],
        "extent": [float(x) for x in (maximum - minimum)],
    }


def _topology(ms: Any) -> dict[str, Any]:
    try:
        values = ms.get_topological_measures()
        return _json_value(values)
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def backend_capabilities() -> dict[str, Any]:
    available = pymeshlab_available()
    return {
        "pymeshlab": {
            "available": available,
            "version": pymeshlab_version() if available else None,
            "install": "pip install 'cloudcompare-mcp[fusion]'",
            "reconstruction": {
                "ball_pivoting": {
                    "available": available,
                    "full_3d": True,
                    "watertight_by_design": False,
                    "hole_preservation_guaranteed": False,
                    "requires_normals": True,
                    "parameters": [
                        "ball_radius_percent",
                        "clustering_percent",
                        "crease_threshold_degrees",
                    ],
                    "result_options": ["name", "destination_group_id"],
                }
            },
            "simplification": {
                "quadric_edge_collapse": {
                    "available": available,
                    "preserve_boundary_control": True,
                    "preserve_normal_control": True,
                    "preserve_topology_control": True,
                    "geometric_deviation": "bidirectional sampled Hausdorff distance",
                }
            },
        }
    }


def _walk_live_entities(value: Any):
    if isinstance(value, dict):
        if isinstance(value.get("id"), int):
            yield value
        children = value.get("children")
        if isinstance(children, list):
            for child in children:
                yield from _walk_live_entities(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_live_entities(item)


def _delete_loaded_root(loaded: Any) -> None:
    if not isinstance(loaded, dict) or not isinstance(loaded.get("id"), int):
        return
    try:
        live_request("entity.delete", {"ids": [int(loaded["id"])]}, timeout=60.0)
    except Exception:
        # Preserve the original option-validation error. The caller still gets a
        # clear failure even if cleanup itself cannot be completed.
        pass


def _load_generated_geometry(
    path: Path,
    *,
    name: str | None = None,
    destination_group_id: int | None = None,
) -> dict[str, Any]:
    """Load generated geometry and verify optional live result placement/name."""
    params: dict[str, Any] = {"path": str(path.resolve())}
    if name is not None:
        params["name"] = name
    if destination_group_id is not None:
        params["destination_group_id"] = int(destination_group_id)

    loaded = live_request("file.load", params, timeout=600.0)

    if destination_group_id is not None:
        parent = loaded.get("parent") if isinstance(loaded, dict) else None
        actual_parent = parent.get("id") if isinstance(parent, dict) else None
        if actual_parent != int(destination_group_id):
            _delete_loaded_root(loaded)
            raise FusionMeshBackendError(
                "CloudCompare loaded the reconstructed mesh, but did not place it in the "
                f"requested destination group {destination_group_id}. The loaded result was removed."
            )

    if name is not None:
        geometry = next(
            (
                entity
                for entity in _walk_live_entities(loaded)
                if entity.get("kind") in {"mesh", "point_cloud"}
            ),
            None,
        )
        actual_name = geometry.get("name") if geometry else None
        if actual_name != name:
            _delete_loaded_root(loaded)
            raise FusionMeshBackendError(
                "CloudCompare loaded the reconstructed mesh, but did not apply the requested "
                f"name {name!r}. The loaded result was removed."
            )

    return loaded


def reconstruct_ball_pivoting(
    *,
    cloud_id: int,
    ball_radius_percent: float | None = None,
    clustering_percent: float = 20.0,
    crease_threshold_degrees: float = 90.0,
    name: str | None = None,
    destination_group_id: int | None = None,
) -> dict[str, Any]:
    if not pymeshlab_available():
        raise FusionMeshBackendError(
            "Ball-pivoting reconstruction requires the optional PyMeshLab backend. "
            "Install it with: pip install 'cloudcompare-mcp[fusion]'"
        )

    if ball_radius_percent is not None and ball_radius_percent < 0:
        raise FusionMeshBackendError("ball_radius_percent must be non-negative")
    if clustering_percent < 0:
        raise FusionMeshBackendError("clustering_percent must be non-negative")
    if not (0 <= crease_threshold_degrees <= 180):
        raise FusionMeshBackendError("crease_threshold_degrees must be between 0 and 180")

    import pymeshlab  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory(prefix="cloudcompare-mcp-bpa-") as tmp:
        tmpdir = Path(tmp)
        source_path = tmpdir / "live_source.ply"
        output_path = tmpdir / "reconstructed.obj"

        export_report = live_request(
            "entity.export",
            {
                "entity_id": int(cloud_id),
                "path": str(source_path.resolve()),
                "overwrite": False,
            },
            timeout=600.0,
        )

        if not export_report.get("has_normals", False):
            raise FusionMeshBackendError(
                "Ball pivoting requires oriented point normals. The live source reports no normals. "
                "Compute/review normals on a working copy first; the backend will not invent them automatically."
            )

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(source_path))

        kwargs: dict[str, Any] = {
            "clustering": float(clustering_percent),
            "creasethr": float(crease_threshold_degrees),
        }
        if ball_radius_percent is not None:
            kwargs["ballradius"] = pymeshlab.PercentageValue(float(ball_radius_percent))

        before = {
            "point_count": int(ms.current_mesh().vertex_number()),
            "triangle_count": int(ms.current_mesh().face_number()),
            "bounds_native": _bounds(ms.current_mesh()),
        }

        try:
            ms.generate_surface_reconstruction_ball_pivoting(**kwargs)
        except Exception as exc:
            raise FusionMeshBackendError(f"PyMeshLab ball-pivoting reconstruction failed: {exc}") from exc

        mesh = ms.current_mesh()
        triangles = int(mesh.face_number())
        if triangles <= 0:
            raise FusionMeshBackendError("Ball-pivoting reconstruction produced no triangle faces")

        after = {
            "point_count": int(mesh.vertex_number()),
            "triangle_count": triangles,
            "bounds_native": _bounds(mesh),
            "topology": _topology(ms),
        }

        ms.save_current_mesh(str(output_path))
        loaded = _load_generated_geometry(
            output_path,
            name=name,
            destination_group_id=destination_group_id,
        )

        # file.load may return a wrapper group depending on the importer; preserve the
        # full returned hierarchy instead of guessing a child ID here.
        return {
            "backend": "pymeshlab",
            "method": "ball_pivoting",
            "source_id": int(cloud_id),
            "source_preserved": True,
            "settings": {
                "ball_radius_percent": ball_radius_percent,
                "clustering_percent": float(clustering_percent),
                "crease_threshold_degrees": float(crease_threshold_degrees),
            },
            "before": before,
            "after": after,
            "hole_preservation_guaranteed": False,
            "warning": (
                "Ball pivoting is local/non-watertight in character, but no reconstruction method "
                "can guarantee that every physical slot or opening survived. Review the result visually."
            ),
            "live_loaded_entity": loaded,
            "requested_name": name,
            "requested_destination_group_id": destination_group_id,
        }


def simplify_quadric(
    *,
    mesh_id: int,
    target_triangles: int,
    preserve_boundaries: bool = True,
    preserve_sharp_features: bool = True,
    preserve_topology: bool = True,
    deviation_samples: int = 100_000,
) -> dict[str, Any]:
    if not pymeshlab_available():
        raise FusionMeshBackendError(
            "Reference-mesh simplification requires the optional PyMeshLab backend. "
            "Install it with: pip install 'cloudcompare-mcp[fusion]'"
        )
    if target_triangles <= 0:
        raise FusionMeshBackendError("target_triangles must be greater than zero")
    if deviation_samples <= 0:
        raise FusionMeshBackendError("deviation_samples must be greater than zero")

    import pymeshlab  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory(prefix="cloudcompare-mcp-qem-") as tmp:
        tmpdir = Path(tmp)
        source_path = tmpdir / "live_mesh.obj"
        output_path = tmpdir / "simplified.obj"

        export_report = live_request(
            "entity.export",
            {
                "entity_id": int(mesh_id),
                "path": str(source_path.resolve()),
                "overwrite": False,
            },
            timeout=600.0,
        )

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(source_path))
        original_id = int(ms.current_mesh_id())
        original_mesh = ms.current_mesh()
        original_triangles = int(original_mesh.face_number())
        if original_triangles <= 0:
            raise FusionMeshBackendError("The selected source contains no triangle faces")

        before = {
            "point_count": int(original_mesh.vertex_number()),
            "triangle_count": original_triangles,
            "bounds_native": _bounds(original_mesh),
            "topology": _topology(ms),
        }

        if target_triangles >= original_triangles:
            raise FusionMeshBackendError(
                f"Target {target_triangles} is not below the source triangle count {original_triangles}; "
                "no simplification was performed."
            )

        ms.generate_copy_of_current_mesh()
        simplified_id = int(ms.current_mesh_id())

        kwargs = {
            "targetfacenum": int(target_triangles),
            "preserveboundary": bool(preserve_boundaries),
            "boundaryweight": 1.0,
            "preservenormal": bool(preserve_sharp_features),
            "preservetopology": bool(preserve_topology),
            "optimalplacement": True,
            "planarquadric": True,
            "autoclean": True,
        }

        try:
            ms.meshing_decimation_quadric_edge_collapse(**kwargs)
        except Exception as exc:
            raise FusionMeshBackendError(f"PyMeshLab quadric simplification failed: {exc}") from exc

        simplified = ms.current_mesh()
        achieved = int(simplified.face_number())
        after = {
            "point_count": int(simplified.vertex_number()),
            "triangle_count": achieved,
            "bounds_native": _bounds(simplified),
            "topology": _topology(ms),
        }

        # Numerical evidence in both directions: simplified -> original and
        # original -> simplified. The result dictionaries include mean/max/RMS
        # style statistics as provided by MeshLab.
        sample_count = int(min(max(deviation_samples, 1_000), 1_000_000))
        deviation: dict[str, Any] = {}
        try:
            deviation["simplified_to_original"] = _json_value(
                ms.get_hausdorff_distance(
                    targetmesh=original_id,
                    sampledmesh=simplified_id,
                    samplenum=sample_count,
                )
            )
            deviation["original_to_simplified"] = _json_value(
                ms.get_hausdorff_distance(
                    targetmesh=simplified_id,
                    sampledmesh=original_id,
                    samplenum=sample_count,
                )
            )
        except Exception as exc:
            deviation = {"available": False, "error": str(exc), "samples_requested": sample_count}

        ms.set_current_mesh(simplified_id)
        ms.save_current_mesh(str(output_path))
        loaded = live_request("file.load", {"path": str(output_path.resolve())}, timeout=600.0)

        target_met = achieved <= target_triangles
        return {
            "backend": "pymeshlab",
            "method": "quadric_edge_collapse",
            "source_id": int(mesh_id),
            "source_preserved": True,
            "unsimplified_mesh_remains_live": True,
            "settings": {
                "target_triangles": int(target_triangles),
                "preserve_boundaries": bool(preserve_boundaries),
                "preserve_sharp_features": bool(preserve_sharp_features),
                "preserve_topology": bool(preserve_topology),
                "deviation_samples": sample_count,
            },
            "before": before,
            "after": after,
            "geometric_deviation": deviation,
            "target_met": target_met,
            "target_note": (
                None
                if target_met
                else "The requested target could not be reached with the requested preservation constraints."
            ),
            "boundary_preservation_verified": False,
            "feature_preservation_note": (
                "Topology/boundary metrics and sampled geometric deviation are evidence, not proof that every "
                "physical vent slot, mounting hole, bracket edge, or curved feature survived. Visual review is still required."
            ),
            "live_loaded_entity": loaded,
            "source_export_report": export_report,
        }
