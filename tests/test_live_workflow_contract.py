from __future__ import annotations

import unittest
from unittest.mock import patch

from cloudcompare_mcp import server


class LiveWorkflowContractTests(unittest.TestCase):
    def test_multi_selection_forwards_all_ids(self) -> None:
        ids = list(range(101, 110))
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_set_live_selection({"ids": ids, "clear": True})
        call.assert_called_once_with("selection.set", {"ids": ids, "clear": True})

    def test_clone_is_explicit_and_long_running(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_clone_live_entities(
                {"ids": [10, 11], "name_suffix": ".working", "destination_group_id": 3}
            )
        call.assert_called_once_with(
            "entity.clone",
            {"ids": [10, 11], "name_suffix": ".working", "destination_group_id": 3},
            timeout=300.0,
        )

    def test_merge_defaults_to_strict_coordinate_frames(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_merge_live_clouds({"ids": [1, 2, 3]})
        call.assert_called_once_with(
            "cloud.merge",
            {"ids": [1, 2, 3], "coordinate_frame_policy": "strict"},
            timeout=600.0,
        )

    def test_reconstruction_requires_explicit_method_and_ack(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_reconstruct_live_mesh(
                {
                    "cloud_id": 7,
                    "method": "delaunay_2_5d_best_fit_plane",
                    "acknowledge_2_5d_limitations": True,
                    "max_edge_length": 2.5,
                }
            )
        call.assert_called_once_with(
            "mesh.reconstruct",
            {
                "cloud_id": 7,
                "method": "delaunay_2_5d_best_fit_plane",
                "acknowledge_2_5d_limitations": True,
                "max_edge_length": 2.5,
            },
            timeout=600.0,
        )

    def test_export_refuses_to_invent_units(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_export_live_entity(
                {"entity_id": 9, "path": r"C:\scan\fan_reference.obj"}
            )
        call.assert_called_once_with(
            "entity.export",
            {
                "entity_id": 9,
                "path": r"C:\scan\fan_reference.obj",
                "overwrite": False,
            },
            timeout=600.0,
        )

    def test_export_can_record_caller_supplied_obj_units(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_export_live_entity(
                {
                    "entity_id": 9,
                    "path": r"C:\scan\fan_reference.obj",
                    "intended_import_units": "millimeters",
                }
            )
        params = call.call_args.args[1]
        self.assertEqual(params["intended_import_units"], "millimeters")


if __name__ == "__main__":
    unittest.main()
