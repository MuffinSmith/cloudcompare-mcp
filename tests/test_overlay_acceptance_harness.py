"""Test acceptance-harness input/safety behavior, not a substitute for a live host."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

path = Path(__file__).resolve().parents[1] / "scripts/live_overlay_acceptance.py"
spec = importlib.util.spec_from_file_location("overlay_acceptance", path)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def test_nested_scene_inventory():
    child = {"id": 2, "children": []}
    parent = {"id": 1, "children": [child]}
    assert harness.entities_by_id({"entities": [parent]}) == {1: parent, 2: child}


def test_specs_use_source_global_bounds():
    source = {"bounds_global_native": {"min": [100, 200, 300], "max": [120, 220, 320]}}
    plane, circle, cylinder, axis = harness.overlay_specs(source)
    assert plane["center"] == [110, 210, 310]
    assert circle["radius"] == pytest.approx(0.6)
    assert cylinder["show_axis"] is True
    assert axis["endpoint_a"] == pytest.approx([110, 210, 309.4])


@pytest.mark.parametrize("upper", [[0, 0, 0], [float("inf"), 1, 1], [float("nan"), 1, 1]])
def test_invalid_bounds_rejected(upper):
    with pytest.raises(ValueError):
        harness.overlay_specs({"bounds_global_native": {"min": [0, 0, 0], "max": upper}})


def test_preexisting_overlays_cause_no_scene_mutation():
    def fake_request(method, params):
        return {"active": True} if method == "fit.overlay.status" else {}
    with patch.object(harness, "request", side_effect=fake_request) as request:
        with pytest.raises(RuntimeError, match="not owned by this run"):
            harness.run_checks(42, {"checks": []})
    assert [call.args[0] for call in request.call_args_list] == [
        "ping", "capabilities.get", "fit.overlay.status",
    ]
