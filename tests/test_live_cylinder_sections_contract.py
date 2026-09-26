from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from mcp.types import CallToolResult

from cloudcompare_mcp import server


def _status(points: list[list[float]]) -> dict:
    return {
        "active": False,
        "pick_count": len(points),
        "picks": [
            {
                "pick_index": index,
                "entity_id": 200 + index,
                "entity_name": f"fixture-{index}",
                "position_global": point,
                "position_native_local": point,
            }
            for index, point in enumerate(points)
        ],
    }


def _body(result) -> dict:
    return json.loads(result[0].text)


class LiveCylinderSectionContractTests(unittest.TestCase):
    def test_fit_live_line_uses_global_picks(self) -> None:
        picks = _status([[0, 0, 0], [2, 0, 0], [4, 0, 0], [6, 0, 0]])
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_fit_live_line({})

        body = _body(result)
        self.assertEqual(body["type"], "line")
        self.assertEqual(body["coordinate_space"], "global")
        self.assertAlmostEqual(body["residuals"]["rms"], 0.0, places=12)
        self.assertAlmostEqual(abs(body["direction"][0]), 1.0, places=12)
        self.assertTrue(body["source_geometry_preserved"])

    def test_fit_live_cylinder_recovers_known_diameter(self) -> None:
        points: list[list[float]] = []
        for z in (-4.0, 0.0, 4.0):
            for i in range(12):
                theta = i * 2.0 * math.pi / 12.0
                points.append(
                    [
                        3.0 + 5.0 * math.cos(theta),
                        -2.0 + 5.0 * math.sin(theta),
                        7.0 + z,
                    ]
                )

        with patch.object(server, "live_request", return_value=_status(points)):
            result = server.handle_fit_live_cylinder({})

        body = _body(result)
        self.assertEqual(body["type"], "cylinder")
        self.assertAlmostEqual(body["diameter"], 10.0, places=8)
        self.assertAlmostEqual(body["axis_point"][0], 3.0, places=8)
        self.assertAlmostEqual(body["axis_point"][1], -2.0, places=8)
        self.assertAlmostEqual(abs(body["axis_direction"][2]), 1.0, places=8)
        self.assertTrue(body["source_geometry_preserved"])

    def test_compare_live_picked_lines_known_offset(self) -> None:
        picks = _status(
            [
                [0, 0, 0], [10, 0, 0], [20, 0, 0],
                [0, 3, 4], [10, 3, 4], [20, 3, 4],
            ]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_compare_live_picked_lines(
                {
                    "line_a_pick_indices": [0, 1, 2],
                    "line_b_pick_indices": [3, 4, 5],
                }
            )

        body = _body(result)
        relationship = body["relationship"]
        self.assertAlmostEqual(relationship["acute_angle_degrees"], 0.0, places=12)
        self.assertAlmostEqual(relationship["shortest_distance"], 5.0, places=12)

    def test_compare_live_line_to_plane_known_intersection(self) -> None:
        picks = _status(
            [
                [2, 3, -5], [2, 3, 5], [2, 3, 10],
                [0, 0, 0], [5, 0, 0], [0, 5, 0], [5, 5, 0],
            ]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_compare_live_line_to_plane(
                {
                    "line_pick_indices": [0, 1, 2],
                    "plane_pick_indices": [3, 4, 5, 6],
                }
            )

        body = _body(result)
        relationship = body["relationship"]
        self.assertAlmostEqual(relationship["angle_to_plane_degrees"], 90.0, places=10)
        for got, expected in zip(relationship["intersection_point"], [2.0, 3.0, 0.0]):
            self.assertAlmostEqual(got, expected, places=10)

    def test_project_live_picks_to_section_filters_profile(self) -> None:
        picks = _status(
            [
                [0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
                [1, 2, 0], [3, 4, 0.1], [-2, 5, -0.2], [9, 9, 2.0],
            ]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_project_live_picks_to_section(
                {
                    "section_plane_pick_indices": [0, 1, 2, 3],
                    "profile_pick_indices": [4, 5, 6, 7],
                    "half_thickness": 0.25,
                }
            )

        body = _body(result)
        projection = body["projection"]
        self.assertEqual(projection["selected_count"], 3)
        self.assertEqual(body["selected_profile_pick_indices"], [4, 5, 6])
        self.assertFalse(body["full_cloud_slab_extraction"])

    def test_cylinder_insufficient_or_duplicate_picks_are_errors(self) -> None:
        points = _status([[1, 0, 0], [1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0], [1, 0, 1]])
        with patch.object(server, "live_request", return_value=points):
            result = server.handle_fit_live_cylinder({})

        self.assertIsInstance(result, CallToolResult)
        self.assertTrue(result.isError)
        self.assertIn("distinct", result.content[0].text)

    def test_capabilities_include_line_cylinder_and_section(self) -> None:
        native = {"plugin_version": "0.7.0", "workflow_revision": 5}
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_get_live_workflow_capabilities({})

        body = _body(result)
        capabilities = body["python_feature_fitting"]
        self.assertTrue(capabilities["line"]["available"])
        self.assertTrue(capabilities["cylinder"]["available"])
        self.assertTrue(capabilities["cross_section_projection"]["available"])
        self.assertFalse(
            capabilities["cross_section_projection"]["full_cloud_slab_extraction"]
        )


if __name__ == "__main__":
    unittest.main()
