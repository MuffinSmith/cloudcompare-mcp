from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from cloudcompare_mcp import server


def _body(result) -> dict:
    return json.loads(result[0].text)


def _region(points: list[list[float]], *, matched_count: int | None = None) -> dict:
    records = [
        {
            "point_index": index,
            "position_native_local": point,
            "position_global": point,
        }
        for index, point in enumerate(points)
    ]
    count = len(records) if matched_count is None else matched_count
    return {
        "cloud_id": 42,
        "cloud_name": "fixture",
        "region_type": "box",
        "coordinate_space": "global",
        "matched_count": count,
        "returned_count": len(records),
        "truncated": count > len(records),
        "sample_strategy": (
            "all_matches" if count == len(records) else "deterministic_reservoir"
        ),
        "bounds_query_space": {
            "min": [-10, -10, -10],
            "max": [10, 10, 10],
            "extent": [20, 20, 20],
        },
        "centroid_query_space": [0, 0, 0],
        "points": records,
        "source_geometry_preserved": True,
        "source_global_shift": [0, 0, 0],
        "source_global_scale": 1.0,
    }


class LiveFeatureCandidateContractTests(unittest.TestCase):
    def test_circle_discovery_handler_adds_region_provenance(self) -> None:
        native = _region(
            [[1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]],
            matched_count=1000,
        )
        discovered = {
            "type": "circle_discovery",
            "sample_count": 4,
            "candidate_count": 1,
            "candidates": [
                {
                    "candidate_index": 0,
                    "support_count": 4,
                    "support_fraction_of_sample": 1.0,
                    "circle": {
                        "center": [0, 0, 0],
                        "normal": [0, 0, 1],
                        "radius": 1.0,
                        "diameter": 2.0,
                    },
                }
            ],
        }
        with (
            patch.object(server, "live_request", return_value=native) as request,
            patch(
                "cloudcompare_mcp.feature_discovery.discover_circles",
                return_value=discovered,
            ) as discover,
        ):
            result = server.handle_discover_live_circles(
                {
                    "cloud_id": 42,
                    "region": {
                        "type": "box",
                        "min": [-2, -2, -1],
                        "max": [2, 2, 1],
                    },
                    "sample_limit": 4,
                    "distance_threshold": 0.1,
                    "min_radius": 0.5,
                    "max_radius": 2.0,
                }
            )

        request.assert_called_once()
        discover.assert_called_once()
        body = _body(result)
        self.assertEqual(body["type"], "circle_discovery")
        self.assertEqual(body["source_cloud_id"], 42)
        self.assertEqual(body["region_match_count"], 1000)
        self.assertEqual(body["region_sample_count"], 4)
        self.assertTrue(body["region_sample_truncated"])
        self.assertIn("sampling_warning", body)
        self.assertFalse(body["image_required"])
        self.assertFalse(body["manual_picking_required"])
        self.assertNotIn("points", body)

    def test_cylinder_discovery_handler_adds_region_provenance(self) -> None:
        native = _region(
            [
                [1, 0, -1],
                [0, 1, -1],
                [-1, 0, -1],
                [1, 0, 1],
                [0, 1, 1],
                [-1, 0, 1],
            ]
        )
        discovered = {
            "type": "cylinder_discovery",
            "sample_count": 6,
            "candidate_count": 1,
            "candidates": [
                {
                    "candidate_index": 0,
                    "support_count": 6,
                    "support_fraction_of_sample": 1.0,
                    "cylinder": {
                        "axis_point": [0, 0, 0],
                        "axis_direction": [0, 0, 1],
                        "radius": 1.0,
                        "diameter": 2.0,
                        "span_endpoints": [[0, 0, -1], [0, 0, 1]],
                    },
                }
            ],
        }
        with (
            patch.object(server, "live_request", return_value=native),
            patch(
                "cloudcompare_mcp.feature_discovery.discover_cylinders",
                return_value=discovered,
            ) as discover,
        ):
            result = server.handle_discover_live_cylinders(
                {
                    "cloud_id": 42,
                    "region": {
                        "type": "box",
                        "min": [-2, -2, -2],
                        "max": [2, 2, 2],
                    },
                    "sample_limit": 6,
                    "restarts": 3,
                    "subset_size": 6,
                }
            )

        discover.assert_called_once()
        body = _body(result)
        self.assertEqual(body["type"], "cylinder_discovery")
        self.assertEqual(body["source_cloud_id"], 42)
        self.assertFalse(body["image_required"])
        self.assertFalse(body["manual_picking_required"])

    def test_plane_overlay_forwards_global_geometry(self) -> None:
        native = {
            "created": True,
            "temporary": True,
            "kind": "plane",
            "overlay_group_id": 900,
            "created_entities": [{"id": 901, "name": "Face"}],
            "source_geometry_preserved": True,
        }
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_show_live_plane_overlay(
                {
                    "source_cloud_id": 42,
                    "center": [1, 2, 3],
                    "normal": [0, 0, 1],
                    "width": 10,
                    "height": 20,
                    "name": "Face",
                }
            )

        request.assert_called_once_with(
            "fit.overlay.create",
            {
                "kind": "plane",
                "source_cloud_id": 42,
                "center": [1, 2, 3],
                "normal": [0, 0, 1],
                "width": 10,
                "height": 20,
                "name": "Face",
            },
            timeout=30.0,
        )
        self.assertTrue(_body(result)["created"])

    def test_circle_cylinder_and_axis_overlay_forwarding(self) -> None:
        native = {"created": True, "temporary": True, "created_entities": []}
        with patch.object(server, "live_request", return_value=native) as request:
            server.handle_show_live_circle_overlay(
                {
                    "source_cloud_id": 42,
                    "center": [1, 2, 3],
                    "normal": [0, 1, 0],
                    "radius": 4,
                }
            )
            server.handle_show_live_cylinder_overlay(
                {
                    "source_cloud_id": 42,
                    "endpoint_a": [0, 0, -5],
                    "endpoint_b": [0, 0, 5],
                    "radius": 2,
                    "show_axis": False,
                }
            )
            server.handle_show_live_axis_overlay(
                {
                    "source_cloud_id": 42,
                    "endpoint_a": [0, 0, 0],
                    "endpoint_b": [1, 2, 3],
                }
            )

        calls = request.call_args_list
        self.assertEqual(calls[0].args[0], "fit.overlay.create")
        self.assertEqual(calls[0].args[1]["kind"], "circle")
        self.assertEqual(calls[1].args[1]["kind"], "cylinder")
        self.assertFalse(calls[1].args[1]["show_axis"])
        self.assertEqual(calls[2].args[1]["kind"], "axis")

    def test_overlay_status_and_clear_use_native_lifecycle(self) -> None:
        with patch.object(
            server,
            "live_request",
            side_effect=[
                {"active": True, "group_id": 900, "overlay_entity_count": 3},
                {"cleared": True, "removed_entity_count": 3},
            ],
        ) as request:
            status = server.handle_get_live_fit_overlays({})
            clear = server.handle_clear_live_fit_overlays({})

        self.assertTrue(_body(status)["active"])
        self.assertTrue(_body(clear)["cleared"])
        self.assertEqual(
            [call.args[0] for call in request.call_args_list],
            ["fit.overlay.status", "fit.overlay.clear"],
        )

    def test_candidate_and_overlay_capabilities_are_composed(self) -> None:
        native = {
            "plugin_version": "0.12.0",
            "workflow_revision": 8,
            "region_query": {
                "available": True,
                "region_types": ["sphere", "box", "slab", "nearest"],
            },
            "fit_overlays": {
                "available": True,
                "kinds": ["plane", "circle", "cylinder", "axis"],
            },
        }
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_get_live_workflow_capabilities({})

        body = _body(result)
        self.assertEqual(body["plugin_version"], "0.12.0")
        self.assertEqual(body["workflow_revision"], 8)
        self.assertTrue(body["live_feature_candidates"]["circle_discovery"])
        self.assertTrue(body["live_feature_candidates"]["cylinder_discovery"])
        self.assertTrue(body["live_feature_candidates"]["visible_overlays"])
        self.assertTrue(body["python_feature_discovery"]["visible_overlays"])

    def test_new_tools_are_discoverable(self) -> None:
        names = {tool.name for tool in server.TOOLS}
        for name in (
            "discover_live_circles",
            "discover_live_cylinders",
            "show_live_plane_overlay",
            "show_live_circle_overlay",
            "show_live_cylinder_overlay",
            "show_live_axis_overlay",
            "get_live_fit_overlays",
            "clear_live_fit_overlays",
        ):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
