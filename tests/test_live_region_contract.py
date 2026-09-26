from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from mcp.types import CallToolResult

from cloudcompare_mcp import server


def _native_region(points: list[list[float]], *, matched_count: int | None = None) -> dict:
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
        "cloud_id": 7,
        "cloud_name": "fixture",
        "region_type": "sphere",
        "coordinate_space": "global",
        "matched_count": count,
        "returned_count": len(records),
        "truncated": count > len(records),
        "max_points": len(records),
        "sample_strategy": "all_matches" if count == len(records) else "deterministic_reservoir",
        "centroid_query_space": [1.0, 2.0, 3.0],
        "bounds_query_space": {
            "min": [-1.0, -2.0, -3.0],
            "max": [3.0, 4.0, 5.0],
            "extent": [4.0, 6.0, 8.0],
        },
        "points": records,
        "source_geometry_preserved": True,
        "source_global_shift": [0.0, 0.0, 0.0],
        "source_global_scale": 1.0,
    }


def _body(result) -> dict:
    return json.loads(result[0].text)


class LiveRegionContractTests(unittest.TestCase):
    def test_query_live_region_returns_compact_preview(self) -> None:
        native = _native_region(
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            matched_count=1000,
        )
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_query_live_region(
                {
                    "cloud_id": 7,
                    "region": {"type": "sphere", "center": [0, 0, 0], "radius": 5},
                    "preview_points": 3,
                }
            )

        request.assert_called_once_with(
            "cloud.region_query",
            {
                "cloud_id": 7,
                "region": {"type": "sphere", "center": [0, 0, 0], "radius": 5},
                "coordinate_space": "global",
                "max_points": 3,
            },
            timeout=300.0,
        )
        body = _body(result)
        self.assertNotIn("points", body)
        self.assertEqual(len(body["preview_points"]), 3)
        self.assertEqual(body["matched_count"], 1000)
        self.assertTrue(body["truncated"])

    def test_query_live_region_can_be_summary_only(self) -> None:
        native = _native_region([], matched_count=123456)
        native["returned_count"] = 0
        native["truncated"] = True
        native["sample_strategy"] = "summary_only"
        native["points"] = []
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_query_live_region(
                {
                    "cloud_id": 7,
                    "region": {"type": "box", "min": [-10, -10, -10], "max": [10, 10, 10]},
                    "preview_points": 0,
                }
            )

        self.assertEqual(request.call_args.args[1]["max_points"], 0)
        body = _body(result)
        self.assertEqual(body["matched_count"], 123456)
        self.assertEqual(body["preview_points"], [])
        self.assertEqual(body["sample_strategy"], "summary_only")
        self.assertNotIn("points", body)

    def test_region_plane_fit_uses_internal_points_but_returns_only_fit(self) -> None:
        points = [[0, 0, 2], [4, 0, 2], [0, 3, 2], [4, 3, 2], [2, 1, 2]]
        native = _native_region(points, matched_count=500)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_fit_live_region_plane(
                {
                    "cloud_id": 7,
                    "region": {"type": "box", "min": [-1, -1, 1], "max": [5, 4, 3]},
                    "sample_limit": 5,
                }
            )

        body = _body(result)
        self.assertEqual(body["type"], "plane")
        self.assertEqual(body["region_match_count"], 500)
        self.assertEqual(body["region_sample_count"], 5)
        self.assertTrue(body["region_sample_truncated"])
        self.assertAlmostEqual(body["residuals"]["rms"], 0.0, places=12)
        self.assertNotIn("points", body)

    def test_region_circle_fit_known_diameter(self) -> None:
        points = [
            [3.0 + 5.0 * math.cos(i * 2.0 * math.pi / 16.0),
             -2.0 + 5.0 * math.sin(i * 2.0 * math.pi / 16.0),
             7.0]
            for i in range(16)
        ]
        native = _native_region(points)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_fit_live_region_circle(
                {
                    "cloud_id": 7,
                    "region": {"type": "slab", "origin": [0, 0, 7], "normal": [0, 0, 1], "half_thickness": 0.1},
                }
            )

        body = _body(result)
        self.assertAlmostEqual(body["diameter"], 10.0, places=10)
        self.assertAlmostEqual(body["center"][0], 3.0, places=10)
        self.assertAlmostEqual(body["center"][1], -2.0, places=10)

    def test_region_cylinder_fit_known_axis_and_diameter(self) -> None:
        points: list[list[float]] = []
        for z in (-4.0, 0.0, 4.0):
            for i in range(12):
                theta = i * 2.0 * math.pi / 12.0
                points.append(
                    [
                        3.0 + 5.0 * math.cos(theta),
                        -2.0 + 5.0 * math.sin(theta),
                        z,
                    ]
                )
        native = _native_region(points)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_fit_live_region_cylinder(
                {
                    "cloud_id": 7,
                    "region": {"type": "box", "min": [-3, -8, -5], "max": [9, 4, 5]},
                }
            )

        body = _body(result)
        self.assertAlmostEqual(body["diameter"], 10.0, places=8)
        self.assertAlmostEqual(body["axis_point"][0], 3.0, places=8)
        self.assertAlmostEqual(body["axis_point"][1], -2.0, places=8)
        self.assertAlmostEqual(abs(body["axis_direction"][2]), 1.0, places=8)

    def test_extract_live_section_compacts_profile_points(self) -> None:
        points = [
            [1, 2, 0],
            [3, 4, 0.1],
            [-2, 5, -0.2],
        ]
        native = _native_region(points, matched_count=3000)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_extract_live_section(
                {
                    "cloud_id": 7,
                    "origin": [0, 0, 0],
                    "normal": [0, 0, 1],
                    "half_thickness": 0.25,
                    "sample_limit": 3,
                    "preview_points": 2,
                }
            )

        body = _body(result)
        self.assertEqual(body["type"], "full_cloud_section_sample")
        self.assertEqual(body["matched_count"], 3000)
        self.assertEqual(body["sampled_count"], 3)
        self.assertTrue(body["sample_truncated"])
        self.assertEqual(len(body["profile_preview"]), 2)
        self.assertNotIn("uv", body)
        self.assertNotIn("points_global", body)
        self.assertAlmostEqual(body["signed_offset_stats"]["max_abs"], 0.2)

    def test_section_preview_uses_projection_source_mapping(self) -> None:
        native = _native_region(
            [
                [1, 2, 0.0],
                [9, 9, 2.0],
                [3, 4, 0.1],
                [-2, 5, -0.2],
            ],
            matched_count=4,
        )
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_extract_live_section(
                {
                    "cloud_id": 7,
                    "origin": [0, 0, 0],
                    "normal": [0, 0, 1],
                    "half_thickness": 0.25,
                    "sample_limit": 4,
                    "preview_points": 3,
                }
            )

        body = _body(result)
        self.assertEqual(body["projected_sample_count"], 3)
        self.assertEqual(
            [point["point_index"] for point in body["profile_preview"]],
            [0, 2, 3],
        )
        self.assertEqual(
            [point["signed_offset"] for point in body["profile_preview"]],
            [0.0, 0.1, -0.2],
        )

    def test_region_fit_rejects_malformed_or_insufficient_native_samples(self) -> None:
        malformed = _native_region([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        malformed["points"][1]["position_global"] = [math.nan, 0, 0]
        with patch.object(server, "live_request", return_value=malformed):
            result = server.handle_fit_live_region_plane(
                {"cloud_id": 7, "region": {"type": "sphere", "center": [0, 0, 0], "radius": 2}}
            )
        self.assertIsInstance(result, CallToolResult)
        self.assertTrue(result.isError)
        self.assertIn("non-finite", result.content[0].text)

        insufficient = _native_region([[0, 0, 0], [1, 0, 0]], matched_count=2)
        with patch.object(server, "live_request", return_value=insufficient):
            result2 = server.handle_fit_live_region_plane(
                {"cloud_id": 7, "region": {"type": "sphere", "center": [0, 0, 0], "radius": 2}}
            )
        self.assertIsInstance(result2, CallToolResult)
        self.assertTrue(result2.isError)
        self.assertIn("at least 3", result2.content[0].text)

    def test_region_tools_are_discoverable(self) -> None:
        names = {tool.name for tool in server.TOOLS}
        for name in (
            "query_live_region",
            "fit_live_region_plane",
            "fit_live_region_circle",
            "fit_live_region_cylinder",
            "extract_live_section",
        ):
            self.assertIn(name, names)

    def test_capabilities_preserve_native_region_query_advertisement(self) -> None:
        native = {
            "plugin_version": "0.10.0",
            "workflow_revision": 6,
            "region_query": {
                "available": True,
                "region_types": ["sphere", "box", "slab", "nearest"],
                "max_returned_points": 20000,
            },
        }
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_get_live_workflow_capabilities({})

        body = _body(result)
        self.assertEqual(body["plugin_version"], "0.10.0")
        self.assertEqual(body["workflow_revision"], 6)
        self.assertTrue(body["region_query"]["available"])
        self.assertEqual(
            body["region_query"]["region_types"],
            ["sphere", "box", "slab", "nearest"],
        )
        self.assertTrue(body["live_region_fitting"]["available"])
        self.assertFalse(body["live_region_fitting"]["image_required"])
        self.assertFalse(body["live_region_fitting"]["manual_picking_required"])
        self.assertTrue(
            body["python_feature_fitting"]["cross_section_projection"][
                "full_cloud_slab_extraction"
            ]
        )

    def test_truncated_region_fit_reports_sampling_warning(self) -> None:
        points = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]]
        native = _native_region(points, matched_count=100000)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_fit_live_region_plane(
                {
                    "cloud_id": 7,
                    "region": {"type": "box", "min": [-1, -1, -1], "max": [2, 2, 1]},
                    "sample_limit": 4,
                }
            )

        body = _body(result)
        self.assertTrue(body["region_sample_truncated"])
        self.assertIn("sampling_warning", body)
        self.assertEqual(body["region_sample_strategy"], "deterministic_reservoir")

    def test_nearest_region_forwards_native_local_coordinate_space(self) -> None:
        native = _native_region([[10, 20, 30]])
        native["region_type"] = "nearest"
        native["nearest_distance"] = 0.25
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_query_live_region(
                {
                    "cloud_id": 7,
                    "region": {"type": "nearest", "center": [10, 20, 29.75], "max_distance": 1},
                    "coordinate_space": "native_local",
                    "preview_points": 1,
                }
            )

        request.assert_called_once_with(
            "cloud.region_query",
            {
                "cloud_id": 7,
                "region": {"type": "nearest", "center": [10, 20, 29.75], "max_distance": 1},
                "coordinate_space": "native_local",
                "max_points": 1,
            },
            timeout=300.0,
        )
        body = _body(result)
        self.assertEqual(body["nearest_distance"], 0.25)


if __name__ == "__main__":
    unittest.main()
