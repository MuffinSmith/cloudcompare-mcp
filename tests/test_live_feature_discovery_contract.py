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
        "cloud_id": 5,
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


class LiveFeatureDiscoveryContractTests(unittest.TestCase):
    def test_region_grid_handler_enriches_and_compacts_covariance(self) -> None:
        native = {
            "cloud_id": 5,
            "coordinate_space": "global",
            "matched_count": 100,
            "grid_bounds_query_space": {
                "min": [0, 0, 0],
                "max": [10, 10, 10],
                "extent": [10, 10, 10],
            },
            "requested_divisions": [2, 2, 2],
            "effective_divisions": [2, 2, 2],
            "cell_size_query_space": [5, 5, 5],
            "nonempty_cell_count": 1,
            "eligible_cell_count": 1,
            "returned_cell_count": 1,
            "cells_truncated": False,
            "cells": [
                {
                    "index": [0, 0, 0],
                    "count": 100,
                    "fraction_of_matches": 1.0,
                    "centroid": [1, 2, 3],
                    "point_bounds": {
                        "min": [0, 0, 0],
                        "max": [2, 4, 6],
                        "extent": [2, 4, 6],
                    },
                    "covariance": [
                        [9, 0, 0],
                        [0, 4, 0],
                        [0, 0, 1],
                    ],
                }
            ],
            "source_geometry_preserved": True,
        }
        with patch.object(server, "live_request", return_value=native) as request:
            result = server.handle_describe_live_region_grid(
                {
                    "cloud_id": 5,
                    "divisions": [2, 2, 2],
                    "max_cells": 16,
                }
            )

        request.assert_called_once_with(
            "cloud.region_grid",
            {
                "cloud_id": 5,
                "coordinate_space": "global",
                "divisions": [2, 2, 2],
                "min_count": 1,
                "max_cells": 16,
            },
            timeout=300.0,
        )
        body = _body(result)
        cell = body["cells"][0]
        self.assertNotIn("covariance", cell)
        self.assertEqual(cell["principal_variances"], [9.0, 4.0, 1.0])
        self.assertFalse(body["image_required"])

    def test_discover_live_planes_finds_two_orthogonal_candidates(self) -> None:
        points: list[list[float]] = []
        for x in range(-5, 6):
            for y in range(-5, 6):
                points.append([x, y, 0.0])
        for y in range(-5, 6):
            for z in range(-5, 6):
                points.append([8.0, y, z])

        with patch.object(server, "live_request", return_value=_region(points)):
            result = server.handle_discover_live_planes(
                {
                    "cloud_id": 5,
                    "region": {
                        "type": "box",
                        "min": [-10, -10, -10],
                        "max": [10, 10, 10],
                    },
                    "distance_threshold": 0.01,
                    "max_planes": 3,
                    "min_points": 30,
                    "min_inlier_fraction": 0.2,
                    "iterations": 250,
                }
            )

        body = _body(result)
        self.assertEqual(body["candidate_count"], 2)
        self.assertFalse(body["image_required"])
        normals = [candidate["plane"]["normal"] for candidate in body["candidates"]]
        self.assertTrue(any(abs(normal[2]) > 0.999 for normal in normals))
        self.assertTrue(any(abs(normal[0]) > 0.999 for normal in normals))
        self.assertNotIn("points", body)

    def test_discover_live_planes_reports_region_sampling(self) -> None:
        points = [[x, y, 0.0] for x in range(5) for y in range(5)]
        native = _region(points, matched_count=10000)
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_discover_live_planes(
                {
                    "cloud_id": 5,
                    "region": {"type": "box", "min": [0, 0, -1], "max": [4, 4, 1]},
                    "distance_threshold": 0.01,
                    "min_points": 10,
                    "iterations": 100,
                }
            )
        body = _body(result)
        self.assertTrue(body["region_sample_truncated"])
        self.assertIn("sampling_warning", body)
        self.assertEqual(body["region_match_count"], 10000)

    def test_section_grid_is_sparse_and_image_free(self) -> None:
        points = [
            [1, 2, 0.0],
            [3, 4, 0.1],
            [-2, 5, -0.2],
            [4, -3, 0.2],
        ]
        with patch.object(server, "live_request", return_value=_region(points)):
            result = server.handle_describe_live_section_grid(
                {
                    "cloud_id": 5,
                    "origin": [0, 0, 0],
                    "normal": [0, 0, 1],
                    "half_thickness": 0.25,
                    "divisions": [4, 4],
                    "max_cells": 16,
                }
            )

        body = _body(result)
        self.assertEqual(body["type"], "live_section_occupancy")
        self.assertFalse(body["image_required"])
        self.assertEqual(body["occupancy"]["sample_count"], 4)
        self.assertNotIn("uv", body)
        self.assertNotIn("points_global", body)

    def test_discovery_capabilities_are_composed_with_native_bridge(self) -> None:
        native = {
            "plugin_version": "0.11.0",
            "workflow_revision": 7,
            "region_query": {
                "available": True,
                "region_types": ["sphere", "box", "slab", "nearest"],
            },
            "region_grid": {"available": True},
        }
        with patch.object(server, "live_request", return_value=native):
            result = server.handle_get_live_workflow_capabilities({})

        body = _body(result)
        self.assertEqual(body["plugin_version"], "0.11.0")
        self.assertEqual(body["workflow_revision"], 7)
        self.assertTrue(body["region_grid"]["available"])
        self.assertTrue(body["python_feature_discovery"]["structured_region_grid"])
        self.assertTrue(body["python_feature_discovery"]["plane_discovery"]["available"])
        self.assertFalse(body["python_feature_discovery"]["visible_overlays"])

    def test_new_tools_are_discoverable(self) -> None:
        names = {tool.name for tool in server.TOOLS}
        for name in (
            "describe_live_region_grid",
            "discover_live_planes",
            "describe_live_section_grid",
        ):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
