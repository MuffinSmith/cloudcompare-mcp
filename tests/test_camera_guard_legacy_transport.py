"""Retain the exact argument allowlist of the previously accepted native bridge."""
from cloudcompare_mcp.inspection_camera import capture
from inspection_replay import Host


def test_legacy_capture_does_not_send_new_identity_fields_to_native_0130():
    host = Host()
    state = host.state()
    def legacy_request(method, args, **kwargs):
        assert method == "view.capture"
        assert args == {"expected_camera_fingerprint": state["camera_fingerprint"]}
        return host(method, args, **kwargs)
    evidence, image, size = capture(legacy_request, state)
    assert image and size > 0 and evidence["camera"]["camera_fingerprint"] == state["camera_fingerprint"]
    assert len(host.calls) == 1
