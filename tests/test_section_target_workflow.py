"""Pure workflows plus native-result replay; not real CloudCompare validation."""
from copy import deepcopy
import json
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_layer_workflow import run_layer_workflow
from cloudcompare_mcp.section_target_workflow import run_target_workflow
from cloudcompare_mcp.section_layers import SectionLayerError
from test_section_layer_workflow import rectangle, native_result, LAYER, PROFILE
from test_section_targets import OPTIONS


def snapshot(points=None, reconstruct=False):
    points = rectangle() if points is None else points
    args = dict(section=dict(coordinate_space='section_uv_depth', units='native',
                             acquisition_complete=True, samples_uvd=points.tolist()),
                target_parameters=deepcopy(OPTIONS))
    if reconstruct:
        args.update(layer_parameters=deepcopy(LAYER), profile_parameters=deepcopy(PROFILE))
    return args


def live_args(reconstruct=False):
    args = dict(cloud_id=359, origin=[0, 0, 0], normal=[0, 0, 1], half_thickness=.5,
                target_parameters=deepcopy(OPTIONS))
    if reconstruct:
        args.update(layer_parameters=deepcopy(LAYER), profile_parameters=deepcopy(PROFILE))
    return args


def choose(args, candidate):
    return args | {'target_id': candidate['target_id'],
                   'expected_target_fingerprint': candidate['candidate_fingerprint']}


def test_snapshot_no_io_source_unchanged():
    args = snapshot(reconstruct=True)
    saved = deepcopy(args)
    native = Mock(side_effect=AssertionError('snapshot may not contact native'))
    result = run_target_workflow(args, reconstruct=True, request=native)
    assert result['status'] == 'candidate'
    assert result['layer_result']['profile']['version'] == '0.15.2'
    assert result['layer_result']['layer_analysis']['version'] == '0.15.3'
    assert result['layer_result']['profile']['topology']['loop_count'] == 1
    assert result['layer_result']['profile']['topology']['loops'][0]['profile']['primitives']
    assert result['point_accounting']['total_unselected_point_count'] == 0
    assert args == saved
    native.assert_not_called()
    assert len(json.dumps(result)) < 30000
    assert 'samples_uvd' not in json.dumps(result)


def test_target_then_layer_explicit_selections_account_for_all_points():
    points = np.vstack([rectangle(-.4), rectangle(.4), rectangle() + [20, 0, 0]])
    args = snapshot(points, True)
    first = run_target_workflow(args, reconstruct=True)
    assert first['blocked_stage'] == 'target_selection'
    assert first['target_analysis']['candidate_target_count'] == 2
    args = choose(args, first['target_analysis']['candidate_targets'][0])
    second = run_target_workflow(args, reconstruct=True)
    assert second['blocked_stage'] == 'layer_selection'
    layers = second['layer_result']['layer_analysis']
    assert layers['candidate_layer_count'] == 2
    args.update(layer_id=layers['candidate_layers'][0]['layer_id'],
                expected_layer_fingerprint=layers['analysis_fingerprint'])
    third = run_target_workflow(args, reconstruct=True)
    assert third['status'] == 'candidate'
    assert third['point_accounting'] == dict(input_point_count=3600, selected_target_point_count=2400,
        selected_layer_point_count=1200, unselected_target_point_count=1200,
        unselected_within_target_point_count=1200, total_unselected_point_count=2400)
    assert not third['manufacturing_intent_confirmed']


def test_distant_unsupported_clutter_is_retained_and_explicitly_unselected():
    args = snapshot(np.vstack([rectangle(), [[20, 0, 0], [20, .1, 0], [20, .2, 0]]]), True)
    first = run_target_workflow(args, reconstruct=True)
    assert first['blocked_stage'] == 'target_selection'
    assert len(first['target_analysis']['candidate_targets']) == 2
    chosen = choose(args, first['target_analysis']['candidate_targets'][0])
    result = run_target_workflow(chosen, reconstruct=True)
    assert result['status'] == 'candidate'
    assert result['target_selection']['unselected_point_count'] == 3
    assert result['target_selection']['unselected_unsupported_or_ambiguous_point_count'] == 3
    assert result['point_accounting']['total_unselected_point_count'] == 3


def test_target_selection_cannot_bypass_thick_layer_evidence():
    points = rectangle()
    points[:, 2] = np.where(np.arange(len(points)) % 2, -.1, .1)
    args = snapshot(points, True)
    first = run_target_workflow(args, reconstruct=True)
    target = first['target_analysis']['candidate_targets'][0]
    assert target['usable']
    second = run_target_workflow(choose(args, target), reconstruct=True)
    assert second['blocked_stage'] == 'layer_selection'
    layer = second['layer_result']['layer_analysis']
    assert layer['status'] == 'blocked'
    args = choose(args, target) | dict(layer_id=layer['candidate_layers'][0]['layer_id'],
                                      expected_layer_fingerprint=layer['analysis_fingerprint'])
    assert run_target_workflow(args, reconstruct=True)['blocked_stage'] == 'layer_selection'


def test_whole_slab_is_not_analyzed_as_layers_before_isolation():
    # 20 well-separated targets exceed accepted default layer-component budget 16.
    points = np.vstack([rectangle() + [i * 20, 0, 0] for i in range(17)])
    # Keep this test under 20k points while retaining dense complete patches.
    points = points[::2]
    args = snapshot(points, True)
    analysis = run_target_workflow(snapshot(points))
    assert analysis['candidate_target_count'] == 17
    with patch('cloudcompare_mcp.section_target_workflow.analyze_section_layers_uvd',
               wraps=__import__('cloudcompare_mcp.section_layers', fromlist=['analyze_section_layers_uvd']).analyze_section_layers_uvd) as layers:
        result = run_target_workflow(choose(args, analysis['candidate_targets'][0]), reconstruct=True)
    assert result['target_selection']['selected_point_count'] == 600
    assert len(layers.call_args.args[0]) == 600
    assert layers.call_args.kwargs['max_components'] == 16


def test_layer_budget_refusal_preserves_target_evidence():
    args = snapshot(reconstruct=True)
    args['layer_parameters']['max_cells'] = 3
    result = run_target_workflow(args, reconstruct=True)
    assert result['blocked_stage'] == 'layer_analysis'
    assert result['target_analysis']['status'] == 'ready'
    assert 'max_cells' in result['reason']


def test_accepted_topology_refusal_retains_all_upstream_diagnostics():
    args = snapshot(reconstruct=True)
    args['profile_parameters']['max_edge_length'] = .01
    result = run_target_workflow(args, reconstruct=True)
    assert result['blocked_stage'] == 'boundary_or_topology'
    assert result['target_analysis']['status'] == 'ready'
    assert result['layer_result']['boundary_evidence']['connected_contour_count'] == 1


@pytest.mark.parametrize('section_change', [
    {'frame': {'frame_id': 'changed'}}, {'source': {'cloud_id': 400}},
    {'source': {'global_scale': 2.5}}, {'source': {'global_shift': [1, 2, 3]}},
    {'provenance': {'acquisition': 'different'}},
])
def test_target_fingerprint_binds_context(section_change):
    args = snapshot(reconstruct=True)
    analysis = run_target_workflow(snapshot())
    args = choose(args, analysis['candidate_targets'][0])
    args['section'].update(section_change)
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(args, reconstruct=True)


def test_downstream_layer_fingerprint_binds_upstream_target_parameters():
    args = snapshot(np.vstack([rectangle(-.4), rectangle(.4)]), True)
    before = run_target_workflow(args, reconstruct=True)['layer_result']['layer_analysis']
    args['target_parameters']['perturbation_fraction'] = .15
    args.update(layer_id=before['candidate_layers'][0]['layer_id'],
                expected_layer_fingerprint=before['analysis_fingerprint'])
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(args, reconstruct=True)


def test_snapshot_vs_live_selection_tokens_are_separate():
    candidate = run_target_workflow(snapshot())['candidate_targets'][0]
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        run_target_workflow(choose(live_args(True), candidate), live=True, reconstruct=True,
                            request=Mock(return_value=native_result()))


def test_live_replay_complete_bookkeeping_no_mutation_or_double_shift():
    native = native_result()
    saved = deepcopy(native)
    request = Mock(return_value=native)
    result = run_target_workflow(live_args(True), live=True, reconstruct=True, request=request)
    assert result['status'] == 'candidate'
    target = result['target_analysis']
    assert target['acquisition']['sampled_count'] == target['acquisition']['matched_count'] == 1200
    assert target['source_coordinate_bookkeeping']['global_scale'] == 2.5
    assert not target['source_coordinate_bookkeeping']['shift_scale_reapplied']
    assert result['layer_result']['layer_analysis']['source']['global_shift'] == [123, -456, 789]
    assert target['candidate_targets'][0]['source_point_indices_sha256']
    assert native == saved
    request.assert_called_once()
    assert request.call_args.args[0] == 'cloud.region_query'
    assert request.call_args.args[1]['coordinate_space'] == 'global'
    assert request.call_args.args[1]['max_points'] == 20000
    assert 'position_global' not in json.dumps(result)


def test_native_record_permutation_preserves_bound_fingerprints():
    native = native_result()
    first = run_target_workflow(live_args(), live=True, request=Mock(return_value=native))
    native['points'].reverse()
    second = run_target_workflow(live_args(), live=True, request=Mock(return_value=native))
    assert first == second


@pytest.mark.parametrize('change', [
    {'truncated': True}, {'returned_count': 1199}, {'matched_count': 1201},
    {'coordinate_space': 'local'}, {'cloud_id': 1}, {'cloud_id': True},
    {'source_global_scale': 0}, {'source_global_shift': [1, 2]}, {'cloud_name': ''},
])
def test_bad_native_result_refused(change):
    native = native_result() | change
    with pytest.raises(SectionLayerError):
        run_target_workflow(live_args(), live=True, request=Mock(return_value=native))


def test_duplicate_native_indices_refused():
    native = native_result()
    native['points'][1]['point_index'] = native['points'][0]['point_index']
    with pytest.raises(SectionLayerError, match='Duplicate'):
        run_target_workflow(live_args(), live=True, request=Mock(return_value=native))


def test_native_points_outside_slab_not_silently_filtered():
    native = native_result()
    native['points'][0]['position_global'][2] = 10
    with pytest.raises(SectionLayerError, match='outside'):
        run_target_workflow(live_args(), live=True, request=Mock(return_value=native))


@pytest.mark.parametrize('field,value', [
    ('acquisition_complete', False), ('acquisition_complete', 1), ('units', 'mm'),
    ('coordinate_space', 'global'), ('source', {'global_scale': -1}),
    ('frame', {'normal': [0, 0, 1]}), ('provenance', {'bad': float('nan')}),
    ('provenance', {'large': 'a' * 5000}),
])
def test_snapshot_contract_errors(field, value):
    args = snapshot()
    args['section'][field] = value
    with pytest.raises(SectionLayerError):
        run_target_workflow(args)


@pytest.mark.parametrize('mutation', [
    {'target_parameters': {}}, {'target_id': 'unknown'}, {'expected_layer_fingerprint': 'x'},
    {'layer_parameters': {}}, {'profile_parameters': {}}, {'unexpected': True},
    {'normal': [0, 0, 0]}, {'query_timeout_seconds': 121},
])
def test_invalid_request_refuses_before_io(mutation):
    request = Mock(side_effect=AssertionError('invalid request performed native I/O'))
    with pytest.raises(SectionLayerError):
        run_target_workflow(live_args(True) | mutation, live=True, reconstruct=True, request=request)
    request.assert_not_called()
