from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from cloudcompare_mcp import server


def _body(result) -> dict:
    return json.loads(result[0].text)


def _region(points: list[list[float]], matched_count: int | None = None) -> dict:
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
        "cloud_id": 21,
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
            "min": [-20, -20, -20],
            "max": [20, 20, 20],
            "extent": [40, 40, 40],
        },
        "centroid_query_space": [0, 0, 0],
        "points": records,
        "source_geometry_preserved": True,
        "source_global_shift": [0, 0, 0],
        "source_global_scale": 1.0,
    }


def _circle_points(center: tuple[float, float, float], radius: float, count: int) -> list[list[float]]:
    return [
        [
            center[0] + radius * math.cos(i * 2 * math.pi / count),
            center[1] + radius * math.sin(i * 2 * math.pi / count),
            center[2],
        ]
        for i in range(count)
    ]


def _cylinder_points(radius: float = 4.0) -> list[list[float]]:
    points: list[list[float]] = []
    for z in (-5.0, 0.0, 5.0):
        for i in range(12):
            theta = i * 2 * math.pi / 12
            points.append([radius * math.cos(theta), radius * math.sin(theta), z])
    return points


class AutoFeatureOverlayContractTests(unittest.TestCase):
    def test_discover_live_circles_returns_compact_candidates(self) -> None:
        points = _circle_points((2.0, -3.0, 4.0), 5.0, 48)
        with patch.object(server, "live_request", return_value=_region(points)):
            result = server.handle_discover_live_circles(
                {
                    "cloud_id": 21,
                    "region": {
                        "type": "box",
                        "min": [-5, -10, 3],
                        "max": [10, 5, 5],
                    },
                    "distance_threshold": 0.01,
                    "max_circles": 1,
                    "min_points": 30,
                    "iterations": 100,
                }
            )

        body = _body(result)
        self.assertEqual(body["candidate_count"], 1)
        self.assertAlmostEqual(body["candidates"][0]["circle"]["radius"], 5.0, places=8)
        self.assertFalse(body["image_required"])
        self.assertNotIn("points", body)

    def test_discover_live_cylinders_returns_axis_and_support(self) -> None:
        points = _cylinder_points()
        with patch.object(server, "live_request", return_value=_region(points)):
            result = server.handle_discover_live_cylinders(
                {
                    "cloud_id": 21,
                    "region": {
                        "type": "box",
                        "min": [-5, -5, -6],
                        "max": [5, 5, 6],
                    },
                    "distance_threshold": 0.01,
                    "max_cylinders": 1,
                    "min_points": 24,
                    "iterations": 10,
                    "candidate_sample_size": 8,
                }
            )

        body = _body(result)
        self.assertEqual(body["candidate_count"], 1)
        cylinder = body["candidates"][0]["cylinder"]
        self.assertAlmostEqual(cylinder["radius"], 4.0, places=7)
        self.assertAlmostEqual(abs(cylinder["axis_direction"][2]), 1.0, places=7)
        self.assertGreaterEqual(body["candidates"][0]["support_count"], 30)

    def test_plane_overlay_converts_fit_to_native_request(self) -> None:
        fit = {
            "centroid": [1.0, 2.0, 3.0],
            "normal": [0.0, 0.0, 1.0],
            "basis_u": [1.0, 0.0, 0.0],
            "basis_v": [0.0, 1.0, 0.0],
            "projected_bounds": {
                "extent_u": 10.0,
                "extent_v": 5.0,
            },
        }
        native = {
            "kind": "plane",
            "overlay_root_id": 100,
            "fit_group_id": 101,
            "entity_ids": [102, 103],
            "source_geometry_preserved": True,
        }
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_show_live_fit_overlay(
                {
                    "source_cloud_id": 21,
                    "fit_type": "plane",
                    "fit": fit,
                    "padding": 1.1,
                    "name": "candidate plane",
                }
            )

        params = request.call_args.args[1]
        self.assertEqual(request.call_args.args[0], "overlay.create")
        self.assertEqual(params["kind"], "plane")
        self.assertEqual(params["geometry"]["center"], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(params["geometry"]["width"], 11.0)
        self.assertAlmostEqual(params["geometry"]["height"], 5.5)
        self.assertEqual(params["name"], "candidate plane")
        self.assertEqual(_body(result)["fit_group_id"], 101)

    def test_cylinder_overlay_centers_sampled_axial_span(self) -> None:
        fit = {
            "axis_point": [10.0, 20.0, 30.0],
            "axis_direction": [0.0, 0.0, 2.0],
            "radius": 5.0,
            "axial_range": [-4.0, 6.0],
        }
        with patch.object(
            server,
            "live_request",
            return_value={"kind": "cylinder", "fit_group_id": 5},
        ) as request:
            server.handle_show_live_fit_overlay(
                {
                    "source_cloud_id": 21,
                    "fit_type": "cylinder",
                    "fit": fit,
                    "padding": 1.2,
                }
            )

        geometry = request.call_args.args[1]["geometry"]
        self.assertEqual(geometry["center"], [10.0, 20.0, 31.0])
        self.assertEqual(geometry["direction"], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(geometry["radius"], 5.0)
        self.assertAlmostEqual(geometry["height"], 12.0)

    def test_circle_and_line_overlay_requests(self) -> None:
        with patch.object(server, "live_request", return_value={"ok": True}) as request:
            server.handle_show_live_fit_overlay(
                {
                    "source_cloud_id": 21,
                    "fit_type": "circle",
                    "fit": {
                        "center": [1, 2, 3],
                        "normal": [0, 0, 1],
                        "radius": 4,
                    },
                    "padding": 1.25,
                }
            )
        params = request.call_args.args[1]
        self.assertEqual(params["kind"], "circle")
        self.assertAlmostEqual(params["geometry"]["radius"], 4.0)

        with patch.object(server, "live_request", return_value={"ok": True}) as request2:
            server.handle_show_live_fit_overlay(
                {
                    "source_cloud_id": 21,
                    "fit_type": "line",
                    "fit": {
                        "centroid": [1, 2, 3],
                        "direction": [1, 0, 0],
                        "axial_span": 8,
                    },
                }
            )
        params2 = request2.call_args.args[1]
        self.assertEqual(params2["kind"], "axis")
        self.assertAlmostEqual(params2["geometry"]["length"], 8.4)

    def test_batch_discovery_overlays_use_distinct_colors_and_names(self) -> None:
        discovery = {
            "candidates": [
                {
                    "candidate_index": 0,
                    "support_count": 100,
                    "support_fraction_of_sample": 0.5,
                    "circle": {
                        "center": [0, 0, 0],
                        "normal": [0, 0, 1],
                        "radius": 5,
                    },
                },
                {
                    "candidate_index": 1,
                    "support_count": 60,
                    "support_fraction_of_sample": 0.3,
                    "circle": {
                        "center": [10, 0, 0],
                        "normal": [0, 0, 1],
                        "radius": 3,
                    },
                },
            ]
        }

        calls: list[tuple[str, dict]] = []

        def fake_request(method, params, timeout=None):
            calls.append((method, params))
            if method == "overlay.clear":
                return {"cleared": True}
            ordinal = len([item for item in calls if item[0] == "overlay.create"])
            return {
                "fit_group_id": 100 + ordinal,
                "entity_ids": [200 + ordinal],
            }

        with patch.object(server, "live_request", side_effect=fake_request):
            result = server.handle_show_live_discovery_overlays(
                {
                    "source_cloud_id": 21,
                    "feature_type": "circle",
                    "discovery_result": discovery,
                }
            )

        self.assertEqual(calls[0][0], "overlay.clear")
        creates = [params for method, params in calls if method == "overlay.create"]
        self.assertEqual(len(creates), 2)
        self.assertNotEqual(creates[0]["color"], creates[1]["color"])
        self.assertIn("candidate 1", creates[0]["name"])
        self.assertIn("50.0% support", creates[0]["name"])
        body = _body(result)
        self.assertEqual(body["created_candidate_count"], 2)
        self.assertFalse(body["image_required"])

    def test_overlay_status_calls_native_structured_query(self) -> None:
        native = {
            "active": True,
            "overlay_root_id": 100,
            "fit_count": 2,
            "fits": [
                {"id": 101, "overlay_kind": "circle", "source_cloud_id": 21},
                {"id": 102, "overlay_kind": "cylinder", "source_cloud_id": 21},
            ],
        }
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_get_live_fit_overlays({})

        request.assert_called_once_with("overlay.status", {}, timeout=300.0)
        body = _body(result)
        self.assertTrue(body["active"])
        self.assertEqual(body["fit_count"], 2)
        self.assertEqual(body["fits"][0]["overlay_kind"], "circle")

    def test_clear_overlay_calls_native_safe_clear(self) -> None:
        with patch.object(
            server,
            "live_request",
            return_value={"cleared": True, "deleted_group_id": 100},
        ) as request:
            result = server.handle_clear_live_fit_overlays({})

        request.assert_called_once_with("overlay.clear", {}, timeout=300.0)
        self.assertTrue(_body(result)["cleared"])

    def test_auto_feature_tools_are_discoverable(self) -> None:
        names = {tool.name for tool in server.TOOLS}
        for name in (
            "discover_live_circles",
            "discover_live_cylinders",
            "show_live_fit_overlay",
            "show_live_discovery_overlays",
            "get_live_fit_overlays",
            "clear_live_fit_overlays",
        ):
            self.assertIn(name, names)

    def test_overlay_capabilities_become_visible(self) -> None:
        native = {
            "plugin_version": "0.12.0",
            "workflow_revision": 8,
            "region_query": {
                "available": True,
                "region_types": ["sphere", "box", "slab", "nearest"],
            },
            "region_grid": {"available": True},
            "fit_overlays": {
                "available": True,
                "wireframe": True,
                "safe_clear": True,
            },
        }
        with patch.object(server, "live_request", return_value=native):
            body = _body(server.handle_get_live_workflow_capabilities({}))

        self.assertTrue(body["python_feature_fitting"]["visible_fit_overlays"])
        self.assertTrue(body["python_feature_discovery"]["visible_overlays"])
        self.assertTrue(body["fit_overlays"]["wireframe"])


if __name__ == "__main__":
    unittest.main()
