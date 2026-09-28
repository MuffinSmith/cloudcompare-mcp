"""Event-turn/transport regressions. Replay PNGs are NOT visible-host evidence."""
import asyncio
import base64
from copy import deepcopy
import hashlib
import json
import numpy as np
import threading
from unittest.mock import patch

import jsonschema
import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from cloudcompare_mcp import live, inspection_camera as camera, inspection_tools, live_inspection, server
from inspection_replay import Host, png_bytes
from test_inspection_tools import Peer, Handler, parsed
from test_live_inspection import ARGS
from test_section_layer_tools import stdio_parameters


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class GuardHost(Host):
    """Independent event-aware double; actual Qt hash rules run separately in CTest."""
    def __init__(self):
        super().__init__()
        self.style = {'point_size': 1., 'line_width': 1.}
        self.extra_parameters = {'near_clipping_depth': None, 'far_clipping_depth': None, 'z_near_coefficient': .005}
        self.on_redraw = self.on_grab = None
        self.history = []

    def state(self):
        s = super().state()
        s['parameters'].update(self.extra_parameters | self.style)
        full = {k: s[k] for k in ('contract', 'native_session', 'window_id', 'viewport_width', 'viewport_height', 'parameters')}
        s['camera_fingerprint'] = hashed(full)
        payload = deepcopy(full)
        payload['contract'] = 'cc-camera-guard-v1'
        for key in ('point_size', 'line_width', 'view_direction_host', 'up_direction_host'):
            payload['parameters'].pop(key, None)
        s['camera_guard_contract'] = 'cc-camera-guard-v1'
        s['camera_guard_fingerprint'] = hashed(payload)
        self.history = (self.history + [deepcopy(s)])[-32:]
        return s

    def refusal(self, stage, before, current):
        details = {'contract': 'cc-camera-diagnostics-v1', 'stage': stage, 'reference': before,
                   'current': current, 'authorizes_retry': False}
        raise live.LiveBridgeError('Camera guard refusal', details)

    def check(self, args, state, stage):
        modern = 'expected_camera_guard_fingerprint' in args
        name = 'camera_guard_fingerprint' if modern else 'camera_fingerprint'
        expected = args.get('expected_' + name, state[name])
        valid = (not ('expected_camera_guard_fingerprint' in args and 'expected_camera_fingerprint' in args)
                 and expected == state[name]
                 and args.get('native_session', state['native_session']) == state['native_session']
                 and args.get('window_id', state['window_id']) == state['window_id'])
        if not valid:
            before = next((s for s in reversed(self.history) if s[name] == expected), {})
            self.refusal(stage, before, state)

    def __call__(self, method, args, **kwargs):
        if method == 'view.capture':
            self.calls.append((method, deepcopy(args)))
            self.capture_count += 1
            before = self.state()
            self.check(args, before, 'capture.precondition')
            if self.on_redraw:
                self.on_redraw(self)
            start = self.state()
            key = 'camera_fingerprint' if 'expected_camera_fingerprint' in args else 'camera_guard_fingerprint'
            if before[key] != start[key]:
                self.refusal('capture.after_redraw', before, start)
            png = png_bytes(self.width, self.height)
            if self.on_grab:
                self.on_grab(self)
            after = self.state()
            if start['camera_fingerprint'] != after['camera_fingerprint']:
                self.refusal('capture.after_grab', start, after)
            return {'capture_contract': 'cc-viewport-capture-v1', 'camera_state': after,
                    'camera_before_redraw': before, 'redraw_difference': camera.camera_difference(before, start),
                    'png_base64': base64.b64encode(png).decode(), 'width': self.width, 'height': self.height,
                    'png_sha256': hashlib.sha256(png).hexdigest()}
        if method == 'view.camera' and args['action'] not in ('get', 'save', 'release'):
            current = self.state()
            try:
                self.check(args, current, 'movement.precondition')
            except live.LiveBridgeError:
                self.calls.append((method, deepcopy(args)))
                raise
            modern = 'expected_camera_guard_fingerprint' in args
            translated = {k: v for k, v in args.items() if k != 'expected_camera_guard_fingerprint'}
            translated['expected_camera_fingerprint'] = current['camera_fingerprint']
            baseline = self.tokens[args['restore_token']][0] if args['action'] == 'restore' else None
            if baseline is not None and not modern:
                self.style = {k: baseline['parameters'][k] for k in self.style}
            result = super().__call__(method, translated, **kwargs)
            self.calls[-1] = (method, deepcopy(args))
            if baseline is not None:
                result['restored_guard_equal'] = result['camera_guard_fingerprint'] == baseline['camera_guard_fingerprint']
                result['restoration_scope'] = 'navigation_preserving_current_point_line_size' if modern else 'legacy_full_viewport'
            return result
        return super().__call__(method, args, **kwargs)


def modern_args(state, **extra):
    return {'action': 'zoom', 'factor': 1.2, **camera.guard(state), **extra}


@pytest.mark.parametrize('field', ['point_size', 'line_width'])
def test_style_drift_no_false_ownership_loss_and_restore_does_not_overwrite_it(field):
    h = GuardHost()
    saved = camera.navigate(h, {'action': 'save'})
    last = camera.navigate(h, modern_args(saved))
    h.style[field] = 3.0
    evidence, _, _ = camera.capture(h, last)
    assert evidence['camera_difference']['parameter_fields'] == [field]
    assert evidence['camera_difference']['guard_equal'] and not evidence['camera_difference']['full_equal']
    assert evidence['camera']['parameters'][field] == 3
    restored = camera.navigate(h, {'action': 'restore', 'restore_token': saved['restore_token'], **camera.guard(h.state())})
    assert restored['restored_guard_equal'] and not restored['restored_equal'] and h.style[field] == 3
    camera.navigate(h, {'action': 'release', 'restore_token': saved['restore_token'], 'native_session': saved['native_session']})
    assert not h.tokens


@pytest.mark.parametrize('field', ['point_size', 'line_width'])
def test_legacy_full_guard_remains_strict(field):
    h = GuardHost(); old = h.state(); h.style[field] += 1
    with pytest.raises(camera.InspectionError) as e:
        camera.navigate(h, {'action': 'zoom', 'factor': 2, 'native_session': old['native_session'],
                            'window_id': old['window_id'], 'expected_camera_fingerprint': old['camera_fingerprint']})
    assert e.value.recovery['camera_diagnostics']['stage'] == 'movement.precondition'
    assert h.focal == 10 and len(h.calls) == 1


@pytest.mark.parametrize('field', ['center', 'pivot', 'focal', 'rotation', 'session', 'window', 'width', 'height',
    'near_clipping_depth', 'far_clipping_depth', 'z_near_coefficient', 'fov_degrees', 'camera_aspect_ratio',
    'perspective', 'clipping_enabled', 'display_scale', 'object_centered', 'bubble_view', 'stereo', 'future_control'])
def test_real_navigation_projection_identity_and_unknown_fields_still_refuse(field):
    h = GuardHost(); before = h.state()
    if field in ('center', 'pivot'): getattr(h, field)[0] += .001
    elif field == 'rotation': h.rotation[0, 1] += .001
    elif field == 'session': h.session = 'replacement'
    elif field in ('focal', 'window', 'width', 'height'): setattr(h, field, getattr(h, field) + 1)
    else: h.extra_parameters[field] = True if field in ('perspective', 'clipping_enabled', 'bubble_view', 'stereo') else 2
    with pytest.raises(camera.InspectionError) as e: camera.navigate(h, modern_args(before))
    assert e.value.recovery['camera_diagnostics']['stage'] == 'movement.precondition'
    assert len(h.calls) == 1


@pytest.mark.parametrize('stage,field,restored', [('redraw','style',True), ('redraw','center',False), ('grab','style',True), ('grab','center',False)])
def test_event_turn_drift_vs_framebuffer_instability(stage, field, restored):
    h = GuardHost()
    def drift(host):
        if field == 'style': host.style['point_size'] += 1
        else: host.center[0] += .5
    setattr(h, 'on_' + stage, drift)
    if stage == 'redraw' and field == 'style':
        p, images = live_inspection.InspectionStore().inspect(ARGS, h)
        assert len(images) == 2 and p['camera_recovery']['restored_guard_equal']
        assert not p['camera_recovery']['restored_full_equal']
        assert p['captures'][0]['redraw_difference']['parameter_fields'] == ['point_size']
        assert h.query_count == 2 and len(h.calls) == 16
    else:
        with pytest.raises(camera.InspectionError) as e: live_inspection.InspectionStore().inspect(ARGS, h)
        recovery = e.value.recovery
        assert recovery['status'] == ('restored' if restored else 'not_restored')
        assert recovery['failure_diagnostics']['camera_diagnostics']['stage'] == 'capture.after_' + stage
        assert h.capture_count == 1 # No retry with a refreshed expected guard.
        assert bool(h.tokens) != restored


@pytest.mark.parametrize('args', [{'expected_camera_guard_fingerprint': True}, {'expected_camera_guard_fingerprint': ''},
    {'expected_camera_guard_fingerprint': 'A'*64}, {'expected_camera_fingerprint': '0'*64}, {'window_id': True}])
def test_malformed_or_mixed_guards_rejected_before_io(args):
    h = GuardHost(); values = modern_args(h.state(), **args)
    with pytest.raises(camera.InspectionError): camera.navigate(h, values)
    assert not h.calls
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(values, inspection_tools.SCHEMAS['set_live_camera'])


@pytest.mark.parametrize('change', ['missing_digest', 'missing_contract', 'bad_contract', 'bad_digest', 'response_downgrade'])
def test_no_partial_contract_or_silent_response_downgrade(change):
    h = GuardHost(); state = h.state(); before = deepcopy(state)
    if change in ('missing_digest', 'response_downgrade'): state.pop('camera_guard_fingerprint')
    if change in ('missing_contract', 'response_downgrade'): state.pop('camera_guard_contract')
    if change == 'bad_contract': state['camera_guard_contract'] = 'future'
    if change == 'bad_digest': state['camera_guard_fingerprint'] = 'bad'
    if change == 'response_downgrade':
        with pytest.raises(camera.InspectionError): camera.navigate(lambda *a, **k: state, modern_args(before))
    else:
        with pytest.raises(camera.InspectionError): camera.camera_state(state)


def test_capture_compares_raw_owned_fields_even_if_native_claims_unchanged_digest():
    h = GuardHost(); old = h.state(); result = h('view.capture', {})
    result['camera_state']['parameters']['camera_center_host'][0] += .1
    with pytest.raises(camera.InspectionError): camera.capture(lambda *a, **k: result, old)


def test_legacy_public_capture_does_not_drop_native_diagnostic_text():
    h = GuardHost(); h.on_redraw = lambda host: setattr(host, 'focal', 99.)
    with patch.object(server, 'live_request', side_effect=h): result = server.handle_capture_live_view({})
    assert 'capture.after_redraw' in str(result)


class DetailedHandler(Handler):
    def handle(self):
        self.request.settimeout(10)
        data = json.loads(self.rfile.readline(1024*1024))
        try: result = {'ok': True, 'result': self.server.host(data['method'], data.get('params', {}))}
        except live.LiveBridgeError as e: result = {'ok': False, 'error': e.args[0], 'error_details': e.details}
        self.wfile.write((json.dumps(result, allow_nan=False) + '\n').encode())


def test_actual_installed_stdio_style_drift_and_failure_diagnostics():
    h = GuardHost(); source = h.points.copy()
    h.on_redraw = lambda host: host.style.update(point_size=host.style['point_size'] + 1)
    with Peer(('127.0.0.1', 0), DetailedHandler) as peer:
        peer.host = h
        thread = threading.Thread(target=peer.serve_forever, daemon=True); thread.start()
        params = stdio_parameters(peer.server_address[1]); params.env.pop('PYTHONPATH', None)
        async def exercise():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    p = parsed(await session.call_tool('inspect_live_part', ARGS))
                    assert p['camera_recovery']['restored_guard_equal'] and not p['camera_recovery']['restored_full_equal']
                    pr = parsed(await session.call_tool('propose_live_semantic_feature', {
                        'inspection_id': p['inspection_id'], 'candidate_ids': [p['candidates'][0]['candidate_id']],
                        'semantic_role': 'possible_mounting_face', 'question': 'Is A a mounting face?',
                        'capture_indexes': [0], 'visual_observations': ['Explicitly scripted replay review, not human acceptance.']}))
                    result = await session.call_tool('confirm_live_semantic_feature', {
                        'inspection_id': p['inspection_id'], 'proposal_id': pr['proposal_id'],
                        'expected_proposal_fingerprint': pr['proposal_fingerprint'], 'answer': 'unsure', 'answer_text': 'Unsure.'})
                    assert parsed(result)['status'] == 'uncertain'
                    await session.call_tool('release_live_inspection', {'inspection_id': p['inspection_id'], 'inspection_fingerprint': p['inspection_fingerprint']})
                    h.on_redraw = lambda host: setattr(host, 'focal', host.focal + 1)
                    result = await session.call_tool('inspect_live_part', ARGS)
                    assert result.isError
                    recovery = parsed(result)['recovery']
                    assert recovery['status'] == 'not_restored'
                    assert recovery['failure_diagnostics']['camera_diagnostics']['stage'] == 'capture.after_redraw'
                    assert recovery['camera_difference']['parameter_fields'] == ['focal_distance']
                    baseline = recovery['baseline']
                    result = await session.call_tool('set_live_camera', {'action': 'release', 'native_session': baseline['native_session'], 'restore_token': baseline['restore_token']})
                    assert parsed(result)['released']
        try: asyncio.run(asyncio.wait_for(exercise(), timeout=45))
        finally: peer.shutdown(); thread.join(timeout=5)
    assert h.capture_count == 3 and not h.tokens and (source == h.points).all()
    assert len(h.calls) == 40 and h.query_count == 5


@pytest.mark.parametrize('details', [None, [], {'contract': 'unknown'},
    {'contract': 'cc-camera-diagnostics-v1', 'x': float('nan')},
    {'contract': 'cc-camera-diagnostics-v1', 'x': 'a'*16384}])
def test_malformed_or_oversize_native_details_do_not_break_refusals(details):
    exc = live.LiveBridgeError('Refused', details)
    assert exc.details is None and str(exc) == 'Refused'


def test_native_diagnostic_evidence_is_frozen_not_a_mutable_alias():
    details = {'contract': 'cc-camera-diagnostics-v1', 'stage': 'capture.after_redraw',
               'difference': {'parameter_fields': ['camera_center_host']}}
    exc = live.LiveBridgeError('Refused', details)
    details['difference']['parameter_fields'].clear()
    assert exc.details['difference']['parameter_fields'] == ['camera_center_host']
    assert 'capture.after_redraw' in str(exc)


class AutoPivotHost(GuardHost):
    """Replay CloudCompare's center-screen auto-pivot translation after redraw."""
    def __init__(self):
        super().__init__()
        self.auto_pivot_candidate = np.array([1.25, -2.5, 3.75])

    def suspension_active(self):
        return any(data[5] for data in self.tokens.values())

    def apply_auto_pivot(self, candidate=None):
        if not self.auto_pivot:
            return
        candidate = np.array(self.auto_pivot_candidate if candidate is None else candidate, dtype=float)
        delta = candidate - self.pivot
        self.pivot = candidate.copy()
        self.center = self.center + delta  # CloudCompare setPivotPoint(..., autoUpdateCameraPos=true)

    def __call__(self, method, args, **kwargs):
        if method == 'view.capture' and self.suspension_active() and self.auto_pivot:
            current = self.state()
            self.refusal('capture.auto_pivot_ownership', current | {'auto_pick_pivot_at_center': False}, current)
        if method == 'view.camera' and args.get('action') not in ('get', 'save', 'release'):
            if self.suspension_active() and self.auto_pivot:
                current = self.state()
                self.refusal('movement.auto_pivot_ownership', current | {'auto_pick_pivot_at_center': False}, current)
            result = super().__call__(method, args, **kwargs)
            # Native 0.13.2 completes one redraw/event turn before returning moves.
            if args['action'] != 'restore' and self.auto_pivot:
                applied = deepcopy(result)
                self.apply_auto_pivot()
                current = self.state()
                if applied['camera_guard_fingerprint'] != current['camera_guard_fingerprint']:
                    self.refusal('movement.after_redraw', applied, current)
                result = current
            return result
        if method == 'view.camera' and args.get('action') == 'release':
            data = self.tokens.get(args['restore_token'])
            baseline_pivot = None if data is None else np.array(data[0]['parameters']['pivot_host'], dtype=float)
            suspended = bool(data and data[5]); original = bool(data and data[6])
            external = self.auto_pivot if suspended else False
            result = super().__call__(method, args, **kwargs)
            if suspended and original and not external:
                # Re-enabling the host feature schedules one redraw. At the restored
                # baseline view its center candidate should reproduce the saved pivot.
                self.apply_auto_pivot(baseline_pivot)
                result['camera_state'] = self.state()
                result['auto_pivot_current_enabled'] = self.auto_pivot
                result['auto_pivot_restored_to_original'] = True
            return result
        return super().__call__(method, args, **kwargs)


def test_unsuspended_focus_reproduces_fan_auto_pivot_failure_shape():
    h = AutoPivotHost()
    saved = camera.navigate(h, {'action': 'save'})
    before = deepcopy(saved)
    with pytest.raises(camera.InspectionError) as e:
        camera.navigate(h, {'action': 'focus', 'entity_id': 10, **camera.guard(saved)})
    d = e.value.recovery['camera_diagnostics']
    assert d['stage'] == 'movement.after_redraw'
    current = d['current']
    # Rotation and focal distance are unchanged while pivot and camera translate together.
    assert current['parameters']['view_rotation_column_major'] == before['parameters']['view_rotation_column_major']
    assert current['parameters']['focal_distance'] == pytest.approx(current['parameters']['camera_center_host'][2] - current['parameters']['pivot_host'][2])
    assert set(camera.camera_difference(d['reference'], current)['parameter_fields']) == {'pivot_host', 'camera_center_host'}
    camera.navigate(h, {'action': 'release', 'restore_token': saved['restore_token'], 'native_session': saved['native_session']})


def test_auto_pivot_suspension_allows_focus_look_capture_restore_release():
    h = AutoPivotHost(); initial = h.state()
    saved = camera.navigate(h, {'action': 'save', 'suspend_auto_pivot': True})
    assert saved['auto_pivot_suspended_by_token'] and saved['saved_auto_pick_pivot_at_center']
    assert saved['auto_pick_pivot_at_center'] is False and h.auto_pivot is False
    focused = camera.navigate(h, {'action': 'focus', 'entity_id': 10, **camera.guard(saved)})
    looked = camera.navigate(h, {'action': 'look', 'direction': [-1,-1,-1], 'up': [0,0,1], **camera.guard(focused)})
    evidence, _, _ = camera.capture(h, looked)
    assert evidence['camera']['auto_pick_pivot_at_center'] is False
    restored = camera.navigate(h, {'action': 'restore', 'restore_token': saved['restore_token'], **camera.guard(looked)})
    assert restored['restored_guard_equal'] and h.auto_pivot is False
    released = camera.navigate(h, {'action': 'release', 'restore_token': saved['restore_token'], 'native_session': saved['native_session']})
    assert released['auto_pivot_restored_to_original'] and released['camera_state']['auto_pick_pivot_at_center'] is True
    assert camera.camera_difference(initial, released['camera_state'])['guard_equal']
    assert released['camera_state']['parameters']['pivot_host'] == initial['parameters']['pivot_host']
    assert not h.tokens and h.auto_pivot is True


def test_auto_pivot_human_reenable_during_owned_suspension_refuses_without_move():
    h = AutoPivotHost()
    saved = camera.navigate(h, {'action': 'save', 'suspend_auto_pivot': True})
    h.auto_pivot = True  # model an external UI toggle while the token owns FALSE
    pose = deepcopy(h.center)
    with pytest.raises(camera.InspectionError) as e:
        camera.navigate(h, {'action': 'look', 'direction': [0,1,0], 'up': [0,0,1], **camera.guard(saved)})
    assert e.value.recovery['camera_diagnostics']['stage'] == 'movement.auto_pivot_ownership'
    assert np.array_equal(h.center, pose)
    released = camera.navigate(h, {'action': 'release', 'restore_token': saved['restore_token'], 'native_session': saved['native_session']})
    assert released['auto_pivot_external_override_preserved']
    assert not h.tokens


def test_bounded_inspection_suspends_host_auto_pivot_and_restores_original_mode():
    h = AutoPivotHost(); initial = h.state()
    packet, images = live_inspection.InspectionStore().inspect(ARGS, h)
    assert len(images) == len(ARGS['views'])
    assert packet['camera_recovery']['status'] == 'restored'
    assert packet['camera_recovery']['auto_pivot_restored_to_original'] is True
    assert packet['camera_recovery']['release_camera_difference']['control_fields'] == ['auto_pick_pivot_at_center']
    assert camera.camera_difference(initial, h.state())['guard_equal']
    assert h.auto_pivot is True and not h.tokens


def test_post_release_auto_pivot_drift_reports_irreversible_token_release():
    h = AutoPivotHost()
    original_apply = h.apply_auto_pivot
    def shifted(candidate=None):
        candidate = np.array(h.auto_pivot_candidate if candidate is None else candidate, dtype=float)
        original_apply(candidate + np.array([0., 0., 1.]))
    h.apply_auto_pivot = shifted
    with pytest.raises(camera.InspectionError) as e:
        live_inspection.InspectionStore().inspect(ARGS, h)
    recovery = e.value.recovery
    assert recovery['token_released'] is True
    assert recovery['release']['released'] is True
    assert recovery['error'].startswith('Camera changed while restoring CloudCompare automatic pivot mode')
    assert not h.tokens and h.auto_pivot is True
