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

    def test_create_group_forwards_optional_parent(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_create_live_group({"name": "MCP Working", "destination_group_id": 42})
        call.assert_called_once_with(
            "group.create",
            {"name": "MCP Working", "destination_group_id": 42},
        )

    def test_crop_preserves_explicit_coordinate_space(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_crop_live_cloud(
                {
                    "cloud_id": 7,
                    "min": [-10.0, -20.0, -30.0],
                    "max": [10.0, 20.0, 30.0],
                    "coordinate_space": "global",
                    "keep_inside": False,
                    "destination_group_id": 99,
                }
            )
        call.assert_called_once_with(
            "cloud.crop",
            {
                "cloud_id": 7,
                "min": [-10.0, -20.0, -30.0],
                "max": [10.0, 20.0, 30.0],
                "coordinate_space": "global",
                "keep_inside": False,
                "destination_group_id": 99,
            },
            timeout=300.0,
        )

    def test_subsample_forwards_method_specific_settings(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_subsample_live_cloud(
                {"cloud_id": 7, "method": "spatial", "min_spacing": 0.25}
            )
        call.assert_called_once_with(
            "cloud.subsample",
            {"cloud_id": 7, "method": "spatial", "min_spacing": 0.25},
            timeout=600.0,
        )

    def test_sor_defaults_are_explicit(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_filter_live_cloud_sor({"cloud_id": 7})
        call.assert_called_once_with(
            "cloud.filter_sor",
            {"cloud_id": 7, "knn": 6, "n_sigma": 1.0},
            timeout=600.0,
        )

    def test_compute_normals_defaults_do_not_orient(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_compute_live_normals({"cloud_id": 7, "radius": 1.5})
        call.assert_called_once_with(
            "cloud.compute_normals",
            {
                "cloud_id": 7,
                "radius": 1.5,
                "model": "LS",
                "orient_with_mst": False,
                "mst_neighbors": 6,
            },
            timeout=900.0,
        )

    def test_live_icp_defaults_to_preview_and_forwards_safety_settings(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_register_live_icp({"data_id": 10, "model_id": 20})
        call.assert_called_once_with(
            "cloud.register_icp",
            {
                "data_id": 10,
                "model_id": 20,
                "overlap_percent": 100.0,
                "max_iterations": 20,
                "random_sampling_limit": 50000,
                "filter_out_farthest_points": False,
                "preview_only": True,
            },
            timeout=900.0,
        )

    def test_live_icp_forwards_result_options(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_register_live_icp(
                {
                    "data_id": 10,
                    "model_id": 20,
                    "overlap_percent": 65,
                    "max_iterations": 40,
                    "random_sampling_limit": 25000,
                    "filter_out_farthest_points": True,
                    "preview_only": False,
                    "name": "aligned working copy",
                    "destination_group_id": 42,
                }
            )
        call.assert_called_once_with(
            "cloud.register_icp",
            {
                "data_id": 10,
                "model_id": 20,
                "overlap_percent": 65.0,
                "max_iterations": 40,
                "random_sampling_limit": 25000,
                "filter_out_farthest_points": True,
                "preview_only": False,
                "name": "aligned working copy",
                "destination_group_id": 42,
            },
            timeout=900.0,
        )

    def test_ball_pivoting_forwards_result_name_and_destination(self) -> None:
        with patch(
            "cloudcompare_mcp.fusion_mesh.reconstruct_ball_pivoting",
            return_value={"method": "ball_pivoting"},
        ) as reconstruct:
            server.handle_reconstruct_live_mesh(
                {
                    "cloud_id": 7,
                    "method": "ball_pivoting",
                    "name": "Requested BPA",
                    "destination_group_id": 42,
                    "ball_radius_percent": 1.5,
                }
            )

        reconstruct.assert_called_once_with(
            cloud_id=7,
            ball_radius_percent=1.5,
            clustering_percent=20.0,
            crease_threshold_degrees=90.0,
            name="Requested BPA",
            destination_group_id=42,
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
