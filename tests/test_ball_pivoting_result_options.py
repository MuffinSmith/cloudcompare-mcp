from __future__ import annotations

from unittest.mock import call, patch

import pytest

from cloudcompare_mcp import fusion_mesh


def test_generated_geometry_load_applies_name_and_destination(tmp_path) -> None:
    output_path = tmp_path / "reconstructed.obj"
    output_path.write_text("v 0 0 0\n", encoding="utf-8")

    loaded = {
        "id": 100,
        "kind": "group",
        "parent": {"id": 42, "name": "MCP Working"},
        "children": [
            {"id": 101, "kind": "mesh", "name": "Requested BPA", "children": []}
        ],
    }

    with patch.object(fusion_mesh, "live_request", return_value=loaded) as request:
        result = fusion_mesh._load_generated_geometry(
            output_path,
            name="Requested BPA",
            destination_group_id=42,
        )

    assert result["id"] == 100
    request.assert_called_once_with(
        "file.load",
        {
            "path": str(output_path.resolve()),
            "name": "Requested BPA",
            "destination_group_id": 42,
        },
        timeout=600.0,
    )


def test_generated_geometry_load_omits_optional_result_settings(tmp_path) -> None:
    output_path = tmp_path / "reconstructed.obj"
    output_path.write_text("v 0 0 0\n", encoding="utf-8")

    with patch.object(
        fusion_mesh,
        "live_request",
        return_value={"id": 101, "children": []},
    ) as request:
        fusion_mesh._load_generated_geometry(output_path)

    request.assert_called_once_with(
        "file.load",
        {"path": str(output_path.resolve())},
        timeout=600.0,
    )


def test_generated_geometry_load_removes_result_if_destination_was_ignored(tmp_path) -> None:
    output_path = tmp_path / "reconstructed.obj"
    output_path.write_text("v 0 0 0\n", encoding="utf-8")
    loaded = {
        "id": 200,
        "kind": "group",
        "parent": {"id": 1, "name": "DB Tree"},
        "children": [{"id": 201, "kind": "mesh", "name": "Requested BPA"}],
    }

    with patch.object(
        fusion_mesh,
        "live_request",
        side_effect=[loaded, {"deleted_ids": [200]}],
    ) as request:
        with pytest.raises(fusion_mesh.FusionMeshBackendError, match="destination group"):
            fusion_mesh._load_generated_geometry(
                output_path,
                name="Requested BPA",
                destination_group_id=42,
            )

    assert request.call_args_list == [
        call(
            "file.load",
            {
                "path": str(output_path.resolve()),
                "name": "Requested BPA",
                "destination_group_id": 42,
            },
            timeout=600.0,
        ),
        call("entity.delete", {"ids": [200]}, timeout=60.0),
    ]


def test_generated_geometry_load_removes_result_if_name_was_ignored(tmp_path) -> None:
    output_path = tmp_path / "reconstructed.obj"
    output_path.write_text("v 0 0 0\n", encoding="utf-8")
    loaded = {
        "id": 300,
        "kind": "group",
        "children": [{"id": 301, "kind": "mesh", "name": "reconstructed"}],
    }

    with patch.object(
        fusion_mesh,
        "live_request",
        side_effect=[loaded, {"deleted_ids": [300]}],
    ) as request:
        with pytest.raises(fusion_mesh.FusionMeshBackendError, match="requested name"):
            fusion_mesh._load_generated_geometry(output_path, name="Requested BPA")

    assert request.call_args_list == [
        call(
            "file.load",
            {"path": str(output_path.resolve()), "name": "Requested BPA"},
            timeout=600.0,
        ),
        call("entity.delete", {"ids": [300]}, timeout=60.0),
    ]
