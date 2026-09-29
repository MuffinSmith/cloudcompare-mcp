from __future__ import annotations

from unittest.mock import patch

from cloudcompare_mcp import server


def test_import_processed_geometry_maps_explicit_provenance_contract():
    digest_a = "a" * 64
    digest_b = "b" * 64
    with patch.object(server, "_live_call", return_value=[]) as call:
        server.handle_import_live_processed_geometry(
            {
                "source_entity_id": 42,
                "path": r"C:\\work\\processed.ply",
                "source_export_sha256": digest_a,
                "processing_parameters": {
                    "tool": "fixture",
                    "voxel_size": 0.25,
                },
                "coordinate_contract": "preserve_exported_global_coordinates",
                "expected_result_sha256": digest_b,
                "result_group_name": "processed fixture",
                "destination_group_id": 77,
            }
        )

    call.assert_called_once_with(
        "geometry.import_processed",
        {
            "source_entity_id": 42,
            "path": r"C:\\work\\processed.ply",
            "source_export_sha256": digest_a,
            "processing_parameters": {
                "tool": "fixture",
                "voxel_size": 0.25,
            },
            "coordinate_contract": "preserve_exported_global_coordinates",
            "expected_result_sha256": digest_b,
            "result_group_name": "processed fixture",
            "destination_group_id": 77,
        },
        timeout=900.0,
    )


def test_external_roundtrip_tool_requires_provenance_fields():
    tool = next(
        item for item in server.TOOLS
        if item.name == "import_live_processed_geometry"
    )
    required = set(tool.inputSchema["required"])
    assert {
        "source_entity_id",
        "path",
        "source_export_sha256",
        "processing_parameters",
        "coordinate_contract",
    } <= required
    contract = tool.inputSchema["properties"]["coordinate_contract"]
    assert contract["enum"] == ["preserve_exported_global_coordinates"]
