"""Intent freshness and unchanged downstream refusal boundaries (no real GUI)."""
from copy import deepcopy
import json
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_spatial_intent_workflow import run_picked_roi_workflow as run
from cloudcompare_mcp.section_target_roi_workflow import run_roi_workflow
from test_section_spatial_intent import snapshot, authorize, state
from test_section_layer_workflow import rectangle, native_result, LAYER, PROFILE
from test_section_target_workflow import choose, live_args as target_live_args


def live_args(reconstruct=False):
    return target_live_args(reconstruct) | dict(frame_id='declared-live-xy',
        frame_provenance={'declaration': 'Explicit global XY/canonical section basis'},
        pick_indices=[0, 1], margin=0)


class NativeReplay:
    """In-process transport double, with independently mutable observed records."""
    def __init__(self, points=None):
        self.native = native_result(points)
        self.status = state()
        for p in self.status['picks']:
            p.update(entity_name=self.native['cloud_name'], global_shift=self.native['source_global_shift'],
                     global_scale=self.native['source_global_scale'])
            p['position_native_local'] = ((np.array(p['position_global']) + p['global_shift']) * p['global_scale']).tolist()
        self.current = {p['point_index']: deepcopy(p) for p in self.status['picks']}
        self.calls = []

    def __call__(self, method, params, **kwargs):
        self.calls.append((method, deepcopy(params)))
        if method == 'metrology.pick.status': return deepcopy(self.status)
        if method == 'metrology.point_info': return deepcopy(self.current[params['point_index']])
        if method == 'cloud.region_query': return deepcopy(self.native)
        raise AssertionError(f'Unexpected native mutation/method: {method}')


def test_clean_chain_provenance_readonly_and_compact():
    args = authorize(snapshot(np.vstack([rectangle(), [[20, 0, 0]]]), reconstruct=True))
    saved = deepcopy(args)
    r = run(args, action='reconstruct')
    assert r['status'] == 'candidate' and args == saved
    roi = r['roi_result']
    assert roi['version'] == '0.15.6'
    a = roi['roi_analysis']['target_analysis']
    assert a['upstream_section_spatial_intent']['intent_fingerprint'] == args['expected_intent_fingerprint']
    layer = roi['target_result']['layer_result']
    assert layer['layer_analysis']['version'] == '0.15.3'
    assert layer['profile']['version'] == '0.15.2'
    assert layer['profile']['topology']['loop_count'] == 1
    assert layer['profile']['topology']['loops'][0]['profile']['primitives']
    text = json.dumps(r, allow_nan=False)
    assert len(text) < 55000 and 'samples_uvd' not in text
    assert roi['point_accounting']['outside_roi_point_count'] == 1
    assert not r['scene_mutations_requested'] and not r['manufacturing_intent_confirmed']


@pytest.mark.parametrize('change', ['margin', 'pick', 'pick_click', 'source', 'frame', 'frame_source',
                                     'inside', 'outside', 'parameters', 'indices', 'snapshot_context'])
def test_changed_evidence_stales_intent_before_target_analysis(change):
    args = authorize(snapshot(np.vstack([rectangle(), [[20, 0, 0]]])))
    if change == 'margin': args['margin'] = .1
    elif change == 'pick': args['pick_state']['picks'][0]['position_global'][0] -= .1
    elif change == 'pick_click': args['pick_state']['picks'][0]['click']['x'] += 1
    elif change == 'source': args['section']['source']['cloud_name'] = args['pick_state']['picks'][0]['entity_name'] = args['pick_state']['picks'][1]['entity_name'] = 'renamed'
    elif change == 'frame': args['section']['frame']['origin_global'][0] += .1
    elif change == 'frame_source': args['frame_provenance']['declaration'] = 'another datum'
    elif change == 'inside': args['section']['samples_uvd'][0][0] += .001
    elif change == 'outside': args['section']['samples_uvd'][-1][0] += 1
    elif change == 'parameters': args['target_parameters']['perturbation_fraction'] = .15
    elif change == 'indices': args['section']['source_point_indices'] = list(range(1201))
    else: args['section']['provenance'] = {'acquisition': 'new snapshot'}
    with patch('cloudcompare_mcp.section_spatial_intent_workflow.analyze_roi_input', side_effect=AssertionError('stale reached solver')):
        with pytest.raises(SectionLayerError, match='Stale spatial intent'):
            run(args, action='analyze')


def test_fresh_intent_cannot_launder_old_target_candidate_or_plain_roi_token():
    args = snapshot(reconstruct=True)
    authorized = authorize(args)
    first = run(authorized, action='reconstruct')['roi_result']['roi_analysis']
    candidate = first['target_analysis']['candidate_targets'][0]
    changed = choose(deepcopy(args), candidate)
    changed['margin'] = .2
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        run(authorize(changed), action='reconstruct')
    ordinary = run_roi_workflow({'section': args['section'], 'target_parameters': args['target_parameters'],
                                'roi': dict(u_min=-3, u_max=11, v_min=-3, v_max=9)})
    foreign = ordinary['target_analysis']['candidate_targets'][0]
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        run(choose(authorized, foreign), action='reconstruct')
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run(choose(authorized, candidate) | {'expected_target_fingerprint': authorized['expected_intent_fingerprint']}, action='reconstruct')


@pytest.mark.parametrize('anchors,edge', [(((4,-3,8),(11,9,-8)), 'left'), (((-3,-3,8),(4,9,-8)), 'right'),
                                        (((-3,3,8),(11,9,-8)), 'bottom'), (((-3,-3,8),(11,3,-8)), 'top')])
def test_crossed_roi_edges_cannot_be_overridden_by_picks_or_ids(anchors, edge):
    args = authorize(snapshot(anchors=anchors, reconstruct=True))
    r = run(args, action='reconstruct')
    assert r['blocked_stage'] == 'roi_truncation_guard'
    a = r['roi_result']['roi_analysis']
    assert edge in a['candidate_guards'][0]['touched_edges']
    explicit = choose(args, a['target_analysis']['candidate_targets'][0])
    with patch('cloudcompare_mcp.section_target_roi_workflow.reconstruct_target', side_effect=AssertionError('guard bypass')):
        assert run(explicit, action='reconstruct')['blocked_stage'] == 'roi_truncation_guard'


def test_two_targets_keep_choice_and_parallel_layers_keep_fresh_selection_context():
    points = np.vstack([rectangle(-.4), rectangle(.4), rectangle() + [20, 0, 0]])
    args = authorize(snapshot(points, anchors=((-3,-3,8),(31,9,-8)), reconstruct=True))
    r = run(args, action='reconstruct')
    assert r['blocked_stage'] == 'target_selection'
    candidates = r['roi_result']['roi_analysis']['target_analysis']['candidate_targets']
    target = next(c for c in candidates if c['source_point_count'] == 2400)
    chosen = choose(args, target)
    r = run(chosen, action='reconstruct')
    assert r['blocked_stage'] == 'layer_selection'
    layer = r['roi_result']['target_result']['layer_result']['layer_analysis']
    chosen.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
    r = run(chosen, action='reconstruct')
    assert r['status'] == 'candidate'
    assert r['roi_result']['point_accounting']['selected_layer_point_count'] == 1200
    changed = deepcopy(chosen)
    changed['margin'] += .1
    changed = authorize(changed)
    fresh_a = run({k:v for k,v in changed.items() if k not in ('layer_parameters','profile_parameters','target_id','expected_target_fingerprint','layer_id','expected_layer_fingerprint')}, action='analyze')
    fresh_target = next(c for c in fresh_a['roi_result']['target_analysis']['candidate_targets'] if c['source_point_count'] == 2400)
    with pytest.raises(SectionLayerError, match='fingerprint|Unknown'):
        run(choose(changed, fresh_target), action='reconstruct')


@pytest.mark.parametrize('kind', ['sparse', 'thick', 'bridge'])
def test_unsafe_evidence_remains_refused(kind):
    points = rectangle()
    if kind == 'sparse': points = np.array([[3,3,0], [3,3.1,0], [3,3.2,0]])
    if kind == 'thick': points[:,2] = np.where(np.arange(len(points)) % 2, -.1, .1)
    if kind == 'bridge': points = np.vstack([points, [[x,3,0] for x in np.arange(8,14,.2)]])
    args = authorize(snapshot(points, reconstruct=True))
    r = run(args, action='reconstruct')
    assert r['status'] == 'blocked'
    assert r['blocked_stage'] == {'sparse':'target_selection', 'thick':'layer_selection','bridge':'target_selection'}[kind]
    if kind == 'bridge':
        a = r['roi_result']['roi_analysis']
        assert a['candidate_guards'][0]['possible_truncation']
        explicit = choose(args, a['target_analysis']['candidate_targets'][0])
        assert run(explicit, action='reconstruct')['blocked_stage'] == 'roi_truncation_guard'


def test_live_stopped_status_bookends_current_anchors_and_one_slab_read():
    peer = NativeReplay()
    args = live_args()
    saved = deepcopy((peer.native, peer.status, peer.current, args))
    intent = run(args, live=True, request=peer)
    assert [m for m,p in peer.calls] == ['metrology.pick.status', 'metrology.point_info', 'metrology.point_info', 'cloud.region_query', 'metrology.pick.status']
    assert intent['native_call_accounting']['region_queries'] == 1
    assert intent['source']['global_scale'] == 2.5 and not intent['shift_scale_reapplied']
    r = run(args | {'expected_intent_fingerprint': intent['intent_fingerprint']}, live=True, action='analyze', request=peer)
    assert r['status'] == 'ready'
    assert (peer.native, peer.status, peer.current, args) == saved
    assert intent['intent_fingerprint'] != run(snapshot())['intent_fingerprint']


@pytest.mark.parametrize('change', ['current_point', 'current_shift', 'status_during', 'slab', 'live_frame', 'live_margin'])
def test_live_stale_reads_refuse(change):
    peer = NativeReplay()
    args = live_args()
    intent = run(args, live=True, request=peer)
    args['expected_intent_fingerprint'] = intent['intent_fingerprint']
    if change == 'current_point': peer.current[100000]['position_global'][0] += .01
    if change == 'current_shift': peer.current[100000]['global_shift'][0] += 1
    if change == 'slab': peer.native['points'][0]['position_global'][0] += .001
    if change == 'live_frame': args['frame_id'] = 'different declared frame'
    if change == 'live_margin': args['margin'] += .1
    def request(method, params, **kwargs):
        result = peer(method, params, **kwargs)
        if change == 'status_during' and method == 'cloud.region_query':
            peer.status['picks'][0]['click']['x'] += 1
        return result
    with pytest.raises(SectionLayerError, match='Stale|changed'):
        run(args, live=True, action='analyze', request=request)


@pytest.mark.parametrize('key,value', [('cloud_id', True), ('normal',[0,0,0]), ('origin',[True,0,0]),
                                     ('half_thickness',True), ('margin',-1), ('frame_id',''), ('pick_indices',[0,0])])
def test_malformed_live_intent_is_refused_before_native_io(key,value):
    native = Mock(side_effect=AssertionError('invalid request contacted native'))
    with pytest.raises(SectionLayerError): run(live_args() | {key:value}, live=True, request=native)
    native.assert_not_called()


def test_captured_source_index_geometry_crosscheck():
    args = snapshot()
    args['section']['source_point_indices'] = list(range(1200))
    args['pick_state']['picks'][0].update(point_index=0,item_index=0)
    with pytest.raises(SectionLayerError, match='disagrees'): run(args)
