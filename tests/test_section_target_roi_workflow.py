"""ROI composition, refusal, provenance and native replay; not real GUI evidence."""
from copy import deepcopy
import json
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_target_roi_workflow import run_roi_workflow
from cloudcompare_mcp.section_target_workflow import run_target_workflow
from test_section_target_workflow import snapshot as target_snapshot, live_args as target_live_args, choose
from test_section_layer_workflow import rectangle, native_result

ROI = dict(u_min=-3, u_max=11, v_min=-3, v_max=9)


def snapshot(points=None, reconstruct=False, roi=None):
    return target_snapshot(points, reconstruct) | {'roi': deepcopy(ROI if roi is None else roi)}


def live_args(reconstruct=False, roi=None):
    return target_live_args(reconstruct) | {'roi': deepcopy(ROI if roi is None else roi)}


def candidates(result):
    return result['target_analysis']['candidate_targets']


def test_safe_roi_outside_clutter_uses_accepted_chain_without_mutation():
    p = np.vstack([rectangle(), [[20, 0, 0], [20, .1, 0], [20, .2, 0]]])
    args = snapshot(p, True)
    saved = deepcopy(args)
    request = Mock(side_effect=AssertionError('snapshot I/O'))
    r = run_roi_workflow(args, reconstruct=True, request=request)
    assert r['status'] == 'candidate'
    assert r['roi_analysis']['target_analysis']['version'] == '0.15.4'
    layer = r['target_result']['layer_result']
    assert layer['layer_analysis']['version'] == '0.15.3'
    assert layer['profile']['version'] == '0.15.2'
    assert layer['profile']['topology']['loop_count'] == 1
    assert layer['profile']['topology']['loops'][0]['profile']['primitives']
    assert r['point_accounting'] == dict(input_point_count=1203, inside_roi_point_count=1200,
        outside_roi_point_count=3, selected_target_point_count=1200, selected_layer_point_count=1200,
        unselected_inside_roi_point_count=0, unselected_within_target_point_count=0,
        total_unselected_point_count=3)
    assert args == saved
    request.assert_not_called()
    text = json.dumps(r, allow_nan=False)
    assert len(text) < 40000
    assert 'samples_uvd' not in text and 'position_global' not in text
    assert not r['manufacturing_intent_confirmed']


def test_roi_before_target_budget_and_one_outside_supported_target():
    p = np.vstack([rectangle(), rectangle() + [20, 0, 0]])
    args = snapshot(p)
    args['target_parameters']['max_targets'] = 1
    with pytest.raises(SectionLayerError, match='max_targets'):
        run_target_workflow({k: v for k, v in args.items() if k != 'roi'})
    r = run_roi_workflow(args)
    assert r['status'] == 'ready'
    assert len(candidates(r)) == 1
    assert r['point_accounting']['outside_roi_point_count'] == 1200
    assert r['point_accounting']['target_classified_point_count'] == 1200


def test_multiple_inside_targets_require_choice_not_largest_or_closest():
    p = np.vstack([rectangle(), rectangle() + [20, 0, 0]])
    args = snapshot(p, True, ROI | {'u_max': 31})
    first = run_roi_workflow(args, reconstruct=True)
    assert first['blocked_stage'] == 'target_selection'
    a = first['roi_analysis']
    assert a['status'] == 'selection_required'
    assert len(candidates(a)) == 2
    assert a['target_analysis']['auto_selected_target_id'] is None
    for c in candidates(a):
        r = run_roi_workflow(choose(args, c), reconstruct=True)
        assert r['status'] == 'candidate'
        assert r['point_accounting']['total_unselected_point_count'] == 1200


@pytest.mark.parametrize('bounds,edge', [({'u_min': 4}, 'left'), ({'u_max': 4}, 'right'),
                                       ({'v_min': 3}, 'bottom'), ({'v_max': 3}, 'top')])
def test_crossing_each_edge_blocks_even_explicit_id_before_downstream(bounds, edge):
    args = snapshot(reconstruct=True, roi=ROI | bounds)
    r = run_roi_workflow(args, reconstruct=True)
    a = r['roi_analysis']
    c = candidates(a)[0]
    guard = a['candidate_guards'][0]
    assert edge in guard['touched_edges'] and guard['possible_truncation']
    assert guard['edges'][edge]['outside_same_tangential_cell_point_count_all_depths'] > 0
    with patch('cloudcompare_mcp.section_target_roi_workflow.reconstruct_target', side_effect=AssertionError('guard bypass')):
        explicit = run_roi_workflow(choose(args, c), reconstruct=True)
    assert explicit['blocked_stage'] == 'roi_truncation_guard'
    assert explicit['point_accounting']['total_unselected_point_count'] == 1200
    assert explicit['point_accounting']['selected_target_point_count'] == 0


def test_narrow_bridge_exiting_roi_cannot_be_conveniently_clipped():
    bridge = np.array([[x, 3., 0.] for x in np.arange(8, 13, .2)])
    p = np.vstack([rectangle(), bridge])
    args = snapshot(p, True, ROI | {'u_max': 10})
    a = run_roi_workflow(snapshot(p, roi=args['roi']))
    assert a['point_accounting']['outside_roi_point_count'] > 0
    c = candidates(a)[0]
    assert 'right' in a['candidate_guards'][0]['touched_edges']
    assert run_roi_workflow(choose(args, c), reconstruct=True)['blocked_stage'] == 'roi_truncation_guard'


@pytest.mark.parametrize('roi', [dict(u_min=20, u_max=30, v_min=20, v_max=30),
                               dict(u_min=1, u_max=1.01, v_min=1, v_max=1.01),
                               dict(u_min=0, u_max=2, v_min=0, v_max=2)])
def test_empty_tiny_or_no_guard_clear_interior_has_bounded_refusal(roi):
    r = run_roi_workflow(snapshot(reconstruct=True, roi=roi), reconstruct=True)
    assert r['blocked_stage'] == 'roi_evidence'
    assert r['roi_analysis']['target_analysis'] is None
    assert r['point_accounting']['total_unselected_point_count'] == 1200


def test_sparse_unsupported_roi_cannot_be_overridden():
    p = np.array([[3, 3, 0], [3, 3.1, 0], [3, 3.2, 0]])
    args = snapshot(p, True)
    a = run_roi_workflow(snapshot(p))
    assert a['status'] == 'blocked' and not candidates(a)[0]['usable']
    assert run_roi_workflow(choose(args, candidates(a)[0]), reconstruct=True)['blocked_stage'] == 'target_selection'


def test_roi_keeps_all_depths_then_requires_accepted_layer_selection():
    p = np.vstack([rectangle(-.4), rectangle(.4), rectangle() + [20, 0, 0]])
    args = snapshot(p, True)
    r = run_roi_workflow(args, reconstruct=True)
    assert r['blocked_stage'] == 'layer_selection'
    assert r['point_accounting']['selected_target_point_count'] == 2400
    layer = r['target_result']['layer_result']['layer_analysis']
    assert layer['candidate_layer_count'] == 2
    args.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
    r = run_roi_workflow(args, reconstruct=True)
    assert r['status'] == 'candidate'
    assert r['point_accounting']['outside_roi_point_count'] == 1200
    assert r['point_accounting']['unselected_within_target_point_count'] == 1200
    assert r['point_accounting']['total_unselected_point_count'] == 2400


def test_thick_layer_stays_unsafe_after_explicit_roi_target_choice():
    p = rectangle()
    p[:, 2] = np.where(np.arange(len(p)) % 2, -.1, .1)
    args = snapshot(p, True)
    a = run_roi_workflow(snapshot(p))
    r = run_roi_workflow(choose(args, candidates(a)[0]), reconstruct=True)
    assert r['blocked_stage'] == 'layer_selection'
    layer = r['target_result']['layer_result']['layer_analysis']
    chosen = choose(args, candidates(a)[0]) | dict(layer_id=layer['candidate_layers'][0]['layer_id'],
                                                 expected_layer_fingerprint=layer['analysis_fingerprint'])
    assert run_roi_workflow(chosen, reconstruct=True)['blocked_stage'] == 'layer_selection'


@pytest.mark.parametrize('field,value,stage', [('target_parameters', {'max_cells': 3}, 'target_analysis'),
                                             ('layer_parameters', {'max_cells': 3}, 'layer_analysis'),
                                             ('profile_parameters', {'max_edge_length': .01}, 'boundary_or_topology')])
def test_fixed_budget_and_downstream_refusals_keep_roi_accounting(field, value, stage):
    args = snapshot(np.vstack([rectangle(), [[20, 0, 0]]]), True)
    args[field].update(value)
    r = run_roi_workflow(args, reconstruct=True)
    assert r['blocked_stage'] == stage
    assert r['point_accounting']['outside_roi_point_count'] == 1
    if stage == 'target_analysis':
        assert r['roi_analysis']['point_accounting']['target_unclassified_inside_point_count'] == 1200


@pytest.mark.parametrize('change', ['bounds', 'outside', 'inside', 'source', 'frame', 'provenance', 'parameters'])
def test_any_bound_context_change_invalidates_prior_target_choice(change):
    args = snapshot(np.vstack([rectangle(), [[20, 0, 0]]]), True)
    a = run_roi_workflow({k: v for k, v in args.items() if k not in ('layer_parameters', 'profile_parameters')})
    args = choose(args, candidates(a)[0])
    if change == 'bounds': args['roi']['u_min'] -= .1
    elif change == 'outside': args['section']['samples_uvd'][-1][0] += 1
    elif change == 'inside': args['section']['samples_uvd'][0][0] += .001
    elif change == 'source': args['section']['source'] = {'cloud_id': 999}
    elif change == 'frame': args['section']['frame'] = {'frame_id': 'changed'}
    elif change == 'provenance': args['section']['provenance'] = {'acquisition': 'different'}
    else: args['target_parameters']['perturbation_fraction'] = .15
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        run_roi_workflow(args, reconstruct=True)


@pytest.mark.parametrize('token_kind', ['roi_report', 'plain_target', 'plain_analysis'])
def test_report_and_other_workflow_tokens_are_not_roi_authorization(token_kind):
    a = run_roi_workflow(snapshot())
    args = choose(snapshot(reconstruct=True), candidates(a)[0])
    plain = run_target_workflow(target_snapshot())
    args['expected_target_fingerprint'] = (a['roi_fingerprint'] if token_kind == 'roi_report' else
        plain['candidate_targets'][0]['candidate_fingerprint'] if token_kind == 'plain_target' else plain['analysis_fingerprint'])
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_roi_workflow(args, reconstruct=True)
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(choose(target_snapshot(reconstruct=True), candidates(a)[0]), reconstruct=True)


def test_roi_changes_invalidate_downstream_layer_selection():
    args = snapshot(np.vstack([rectangle(-.4), rectangle(.4)]), True)
    r = run_roi_workflow(args, reconstruct=True)
    layer = r['target_result']['layer_result']['layer_analysis']
    args.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
    args['roi']['u_max'] += .1
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_roi_workflow(args, reconstruct=True)


def test_snapshot_index_mapping_and_permutation_preserve_evidence():
    args = snapshot(np.vstack([rectangle(), [[20, 0, 0]]]))
    n = len(args['section']['samples_uvd'])
    args['section']['source_point_indices'] = list(range(n))
    first = run_roi_workflow(args)
    perm = deepcopy(args)
    perm['section']['samples_uvd'].reverse()
    perm['section']['source_point_indices'].reverse()
    assert run_roi_workflow(perm) == first
    assert first['source_index_accounting']['available']
    # Same geometry / same set of indices, but a changed point->index mapping.
    perm['section']['source_point_indices'][0], perm['section']['source_point_indices'][1] = perm['section']['source_point_indices'][1], perm['section']['source_point_indices'][0]
    assert run_roi_workflow(perm)['roi_fingerprint'] != first['roi_fingerprint']
    assert candidates(first)[0]['source_point_indices_sha256']


@pytest.mark.parametrize('indices', [None, '0,1,2', [], [0, 0, 1], [True, 1, 2], [-1, 1, 2], [2**32, 1, 2]])
def test_bad_snapshot_source_indices_refuse(indices):
    args = snapshot(np.array([[3, 3, 0], [3, 3.1, 0], [3, 3.2, 0]]))
    args['section']['source_point_indices'] = indices
    with pytest.raises(SectionLayerError):
        run_roi_workflow(args)


def test_live_replay_one_complete_acquisition_shift_scale_and_source_mapping():
    native = native_result(np.vstack([rectangle(), rectangle() + [20, 0, 0]]))
    saved = deepcopy(native)
    request = Mock(return_value=native)
    r = run_roi_workflow(live_args(True), live=True, reconstruct=True, request=request)
    assert r['status'] == 'candidate'
    assert request.call_count == 1
    assert request.call_args.args[1]['region']['type'] == 'slab'
    assert request.call_args.args[1]['max_points'] == 20000
    assert native == saved
    a = r['roi_analysis']
    assert a['acquisition']['matched_count'] == 2400
    assert a['source_coordinate_bookkeeping']['shift_scale_reapplied'] is False
    assert a['source_coordinate_bookkeeping']['global_scale'] == 2.5
    layer = r['target_result']['layer_result']['layer_analysis']
    assert layer['source']['global_shift'] == [123, -456, 789]
    assert r['point_accounting']['outside_roi_point_count'] == 1200
    native['points'].reverse()
    permuted = run_roi_workflow(live_args(True), live=True, reconstruct=True, request=request)
    assert permuted['roi_analysis'] == r['roi_analysis']
    assert permuted['point_accounting'] == r['point_accounting']
    assert permuted['target_result']['layer_result']['layer_analysis'] == layer
    # Accepted boundary provenance records local input-order indices; those hashes
    # legitimately differ. Geometric topology/fits and bound selection do not.
    assert permuted['target_result']['layer_result']['profile']['topology'] == r['target_result']['layer_result']['profile']['topology']


@pytest.mark.parametrize('mutation', [{'truncated': True}, {'matched_count': 1201}, {'returned_count': 1199},
                                    {'source_global_scale': 0}, {'coordinate_space': 'local'}])
def test_incomplete_or_bad_live_acquisition_is_never_roi_proof(mutation):
    with pytest.raises(SectionLayerError):
        run_roi_workflow(live_args(), live=True, request=Mock(return_value=native_result() | mutation))


def test_snapshot_live_context_and_native_mapping_are_distinct():
    a = run_roi_workflow(snapshot())
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        run_roi_workflow(choose(live_args(True), candidates(a)[0]), live=True, reconstruct=True,
                         request=Mock(return_value=native_result()))
    n = native_result()
    first = run_roi_workflow(live_args(), live=True, request=Mock(return_value=n))
    n['points'][0]['point_index'], n['points'][1]['point_index'] = 1, 0
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_roi_workflow(choose(live_args(True), candidates(first)[0]), live=True, reconstruct=True,
                         request=Mock(return_value=n))


@pytest.mark.parametrize('mutation', [{'roi': {}}, {'roi': ROI | {'u_min': True}}, {'depth_min': 0},
                                    {'roi': ROI | {'u_min': 20}}, {'target_parameters': {}},
                                    {'target_id': 'unpaired'}])
def test_bad_request_refuses_before_live_io(mutation):
    request = Mock(side_effect=AssertionError('invalid request I/O'))
    with pytest.raises(SectionLayerError):
        run_roi_workflow(live_args(True) | mutation, live=True, reconstruct=True, request=request)
    request.assert_not_called()
