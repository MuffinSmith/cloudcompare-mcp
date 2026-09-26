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
                "entity_id": 100 + index,
                "entity_name": f"fixture-{index}",
                "position_global": point,
                "position_native_local": point,
            }
            for index, point in enumerate(points)
        ],
    }


def _body(result) -> dict:
    return json.loads(result[0].text)


class LiveFeatureFitContractTests(unittest.TestCase):
    def test_fit_live_plane_uses_all_captured_global_picks_by_default(self) -> None:
        picks = _status(
            [[0, 0, 2], [4, 0, 2], [0, 3, 2], [4, 3, 2], [2, 1, 2]]
        )
        with patch.object(server, "live_request", return_value=picks) as request:
            result = server.handle_fit_live_plane({})

        request.assert_called_once_with("metrology.pick.status", {})
        body = _body(result)
        self.assertEqual(body["type"], "plane")
        self.assertEqual(body["coordinate_space"], "global")
        self.assertEqual(body["pick_indices"], [0, 1, 2, 3, 4])
        self.assertAlmostEqual(body["residuals"]["rms"], 0.0, places=12)
        self.assertAlmostEqual(abs(body["normal"][2]), 1.0, places=12)
        self.assertTrue(body["source_geometry_preserved"])

    def test_fit_live_plane_honors_explicit_pick_subset(self) -> None:
        picks = _status(
            [[0, 0, 0], [0, 0, 99], [1, 0, 0], [0, 1, 0], [1, 1, 0]]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_fit_live_plane(
                {"pick_indices": [0, 2, 3, 4]}
            )

        body = _body(result)
        self.assertEqual(body["pick_indices"], [0, 2, 3, 4])
        self.assertAlmostEqual(body["residuals"]["rms"], 0.0, places=12)

    def test_fit_live_circle_recovers_known_diameter(self) -> None:
        points = [
            [3.0 + 5.0 * math.cos(t), -2.0 + 5.0 * math.sin(t), 7.0]
            for t in [i * 2.0 * math.pi / 16.0 for i in range(16)]
        ]
        with patch.object(server, "live_request", return_value=_status(points)):
            result = server.handle_fit_live_circle({})

        body = _body(result)
        self.assertEqual(body["type"], "circle")
        self.assertAlmostEqual(body["diameter"], 10.0, places=10)
        self.assertAlmostEqual(body["center"][0], 3.0, places=10)
        self.assertAlmostEqual(body["center"][1], -2.0, places=10)
        self.assertAlmostEqual(body["center"][2], 7.0, places=10)
        self.assertGreater(body["arc_coverage_degrees"], 330.0)

    def test_pick_to_plane_known_distance(self) -> None:
        picks = _status(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [2, 3, 5]]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_measure_live_pick_to_plane(
                {
                    "point_pick": 4,
                    "plane_pick_indices": [0, 1, 2, 3],
                }
            )

        body = _body(result)
        self.assertAlmostEqual(
            body["measurement"]["absolute_distance"], 5.0, places=12
        )
        self.assertEqual(body["measurement"]["projected_point"], [2.0, 3.0, 0.0])
        self.assertTrue(body["source_geometry_preserved"])

    def test_compare_picked_planes_known_right_angle(self) -> None:
        picks = _status(
            [
                [0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
                [0, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 1],
            ]
        )
        with patch.object(server, "live_request", return_value=picks):
            result = server.handle_compare_live_picked_planes(
                {
                    "plane_a_pick_indices": [0, 1, 2, 3],
                    "plane_b_pick_indices": [4, 5, 6, 7],
                }
            )

        body = _body(result)
        self.assertAlmostEqual(
            body["relationship"]["acute_angle_degrees"], 90.0, places=10
        )

    def test_duplicate_or_insufficient_picks_are_model_readable_errors(self) -> None:
        picks = _status([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        with patch.object(server, "live_request", return_value=picks):
            duplicate = server.handle_fit_live_plane(
                {"pick_indices": [0, 0, 1]}
            )
            insufficient = server.handle_fit_live_plane(
                {"pick_indices": [0, 1]}
            )

        self.assertIsInstance(duplicate, CallToolResult)
        self.assertTrue(duplicate.isError)
        self.assertIn("duplicate", duplicate.content[0].text)
        self.assertIsInstance(insufficient, CallToolResult)
        self.assertTrue(insufficient.isError)
        self.assertIn("At least 3", insufficient.content[0].text)

    def test_capabilities_include_python_feature_fitting(self) -> None:
        native = {
            "plugin_version": "0.7.0",
            "workflow_revision": 5,
        }
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_get_live_workflow_capabilities({})

        body = _body(result)
        capabilities = body["python_feature_fitting"]
        self.assertTrue(capabilities["plane"]["available"])
        self.assertTrue(capabilities["circle"]["available"])
        self.assertTrue(capabilities["relationships"]["point_to_plane"])


if __name__ == "__main__":
    unittest.main()
