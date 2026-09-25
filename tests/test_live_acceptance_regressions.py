from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from cloudcompare_mcp import fusion_mesh


def _load_acceptance_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "live_fusion_acceptance.py"
    spec = importlib.util.spec_from_file_location("live_fusion_acceptance_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flatten_entities_handles_scene_envelope_and_nested_groups() -> None:
    module = _load_acceptance_module()
    scene = {
        "entities": [
            {
                "id": 260,
                "kind": "point_cloud",
                "children": [],
            },
            {
                "id": 300,
                "kind": "group",
                "children": [
                    {
                        "id": 264,
                        "kind": "point_cloud",
                        "children": [],
                    }
                ],
            },
        ],
        "selected_ids": [260, 264],
    }

    flattened = module.flatten_entities(scene)

    assert set(flattened) == {260, 264, 300}
    assert flattened[260]["kind"] == "point_cloud"
    assert flattened[264]["kind"] == "point_cloud"


def test_flatten_entities_handles_standalone_entity_and_list() -> None:
    module = _load_acceptance_module()
    entity = {"id": 7, "kind": "mesh", "children": []}

    assert set(module.flatten_entities(entity)) == {7}
    assert set(module.flatten_entities([entity])) == {7}


def test_pymeshlab_version_uses_distribution_metadata_without_importing_backend() -> None:
    sys.modules.pop("pymeshlab", None)
    with (
        patch.object(fusion_mesh, "pymeshlab_available", return_value=True),
        patch("cloudcompare_mcp.fusion_mesh.importlib.metadata.version", return_value="2025.7.post1") as version,
    ):
        assert fusion_mesh.pymeshlab_version() == "2025.7.post1"

    version.assert_called_once_with("pymeshlab")
    assert "pymeshlab" not in sys.modules
