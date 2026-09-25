from __future__ import annotations

from unittest.mock import patch

from cloudcompare_mcp import fusion_mesh


def test_generated_geometry_load_applies_name_and_destination(tmp_path) -> None:
    output_path = tmp_path / "reconstructed.obj"
    output_path.write_text("v 0 0 0\n", encoding="utf-8")

    with patch.object(
        fusion_mesh,
        "live_request",
        return_value={"id": 100, "children": []},
    ) as request:
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
