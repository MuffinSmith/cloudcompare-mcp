from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from cloudcompare_mcp import live, server
from cloudcompare_mcp.live import LiveBridgeError


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_legacy_bridge_falls_back_to_conservative_handshake(self) -> None:
        with patch.object(
            live,
            "_raw_request",
            side_effect=[
                LiveBridgeError("Unknown bridge method: runtime.handshake"),
                {
                    "protocol_version": 1,
                    "plugin": "qMCPBridge",
                    "process_id": 1234,
                    "application_version": "",
                },
            ],
        ):
            runtime = live.runtime_handshake()

        self.assertFalse(runtime["compatible"])
        self.assertTrue(runtime["legacy_bridge"])
        self.assertEqual(runtime["compatibility_status"], "legacy_bridge")
        self.assertIn("scene.list", runtime["supported_operations"])
        self.assertNotIn("entity.export", runtime["supported_operations"])
        self.assertTrue(runtime["recovery"]["requires_cloudcompare_restart"])

    def test_legacy_bridge_blocks_current_operation_before_dispatch(self) -> None:
        with patch.object(
            live,
            "_raw_request",
            side_effect=[
                LiveBridgeError("Unknown bridge method: runtime.handshake"),
                {"protocol_version": 1, "plugin": "qMCPBridge", "process_id": 1},
            ],
        ) as raw:
            with self.assertRaisesRegex(LiveBridgeError, "entity.export.*unavailable"):
                live.request("entity.export", {"entity_id": 7, "path": r"C:\\scan\\x.ply"})

        self.assertEqual(raw.call_count, 2)
        self.assertEqual(raw.call_args_list[0].args[0], "runtime.handshake")
        self.assertEqual(raw.call_args_list[1].args[0], "ping")

    def test_legacy_bridge_allows_documented_baseline_operation(self) -> None:
        with patch.object(
            live,
            "_raw_request",
            side_effect=[
                LiveBridgeError("Unknown bridge method: runtime.handshake"),
                {"protocol_version": 1, "plugin": "qMCPBridge", "process_id": 1},
                {"entities": [], "selected_ids": []},
            ],
        ) as raw:
            result = live.request("scene.list", {"recursive": True})

        self.assertEqual(result["entities"], [])
        self.assertEqual(raw.call_count, 3)
        self.assertEqual(raw.call_args_list[-1].args[0], "scene.list")

    def test_new_runtime_rejects_unadvertised_operation(self) -> None:
        handshake = {
            "handshake_contract": "cc-runtime-handshake-v1",
            "protocol_version": 1,
            "workflow_revision": 10,
            "plugin_version": "0.14.0",
            "supported_operations": ["scene.list", "runtime.handshake"],
        }
        with patch.object(live, "_raw_request", return_value=handshake) as raw:
            with self.assertRaisesRegex(LiveBridgeError, "entity.export.*unavailable"):
                live.request("entity.export", {})

        raw.assert_called_once()


class RuntimeServerContractTests(unittest.TestCase):
    def test_get_live_info_uses_runtime_handshake(self) -> None:
        with patch.object(
            server,
            "runtime_handshake",
            return_value={"compatible": False, "compatibility_status": "legacy_bridge"},
        ) as handshake:
            server.handle_get_live_cloudcompare_info({})
        handshake.assert_called_once_with()

    def test_save_project_is_full_scene_native_operation(self) -> None:
        with patch.object(server, "_live_call", return_value=[]) as call:
            server.handle_save_live_project({"path": r"C:\\scan\\checkpoint.bin"})

        call.assert_called_once_with(
            "project.save",
            {"path": r"C:\\scan\\checkpoint.bin", "overwrite": False},
            timeout=1200.0,
        )

    def test_legacy_capability_query_returns_diagnosis_without_calling_native_catalog(self) -> None:
        runtime = {
            "compatible": False,
            "compatibility_status": "legacy_bridge",
            "supported_operations": ["scene.list"],
        }
        with patch.object(server, "runtime_handshake", return_value=runtime), patch.object(
            server, "live_request"
        ) as request:
            result = server.handle_get_live_workflow_capabilities({})

        request.assert_not_called()
        payload = json.loads(result[0].text)
        self.assertFalse(payload["native_capabilities_available"])
        self.assertEqual(payload["runtime"]["compatibility_status"], "legacy_bridge")

    def test_scene_summary_marks_missing_legacy_metadata_partial(self) -> None:
        runtime = {
            "compatible": False,
            "compatibility_status": "legacy_bridge",
            "supported_operations": ["scene.list"],
        }
        scene = {
            "selected_ids": [],
            "entities": [
                {
                    "id": 7,
                    "name": "legacy cloud",
                    "kind": "point_cloud",
                    "visible": True,
                    "enabled": True,
                }
            ],
        }
        with patch.object(server, "runtime_handshake", return_value=runtime), patch.object(
            server, "live_request", return_value=scene
        ):
            result = server.handle_summarize_live_scene({})

        payload = json.loads(result[0].text)
        self.assertEqual(payload["response_completeness"], "partial")
        self.assertIn("point_count", payload["missing_fields_by_entity"][0]["missing_fields"])


if __name__ == "__main__":
    unittest.main()
