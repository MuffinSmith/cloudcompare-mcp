"""Snapshot and native-result replay. These are not real CloudCompare tests."""
from copy import deepcopy
import json
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_target_diagnostic_workflow import run_target_diagnostics
from cloudcompare_mcp.section_target_workflow import run_target_workflow
from test_section_target_workflow import snapshot, live_args
from test_section_layer_workflow import rectangle, native_result


def test_snapshot_never_connects_or_runs_downstream_or_mutates():
    args = snapshot()
    args['section']['source'] = {'cloud_id': 359, 'cloud_name': 'snapshot',
                                  'global_shift': [1, 2, 3], 'global_scale': 2.5}
    args['section']['provenance'] = {'purpose': 'test'}
    saved = deepcopy(args)
    native = Mock(side_effect=AssertionError('snapshot did native I/O'))
    with patch('cloudcompare_mcp.section_target_workflow.reconstruct_target', side_effect=AssertionError('profile')):
        result = run_target_diagnostics(args, request=native)
    assert args == saved
    native.assert_not_called()
    assert result['acquisition']['verification'] == 'caller_asserted_snapshot'
    assert result['source'] == args['section']['source']
    assert result['provenance'] == args['section']['provenance']
    assert not result['live_connection_used'] and not result['scene_mutations_requested']
    assert result['point_accounting']['unselected_point_count'] == 1200
    assert result['selection_authorized'] is False
    assert 'samples_uvd' not in json.dumps(result, allow_nan=False)


def test_live_acquires_exactly_once_and_preserves_metadata_and_indices():
    args, data = live_args(), native_result()
    before_args, before_data = deepcopy(args), deepcopy(data)
    request = Mock(return_value=data)
    result = run_target_diagnostics(args, live=True, request=request)
    request.assert_called_once_with('cloud.region_query', {
        'cloud_id': 359, 'coordinate_space': 'global', 'max_points': 20000,
        'region': {'type': 'slab', 'origin': [0., 0., 0.], 'normal': [0., 0., 1.], 'half_thickness': .5},
    }, timeout=30.)
    assert len(result['panels']) == 5
    assert data == before_data and args == before_args
    assert result['acquisition']['complete'] and not result['acquisition']['sample_truncated']
    assert result['source']['point_mapping_sha256']
    assert result['source_coordinate_bookkeeping'] == {
        'query_coordinate_space': 'global', 'global_shift': [123., -456., 789.],
        'global_scale': 2.5, 'shift_scale_reapplied': False}
    assert result['acquisition']['source_integrity_coverage'] == 'not_independently_measured_by_this_tool'
    assert all(p['point_accounting']['input_point_count'] == 1200 for p in result['panels'])
    assert not result['raw_points_returned']


@pytest.mark.parametrize('extra', [
    {'target_id': 'target_1'}, {'expected_target_fingerprint': 'x'}, {'layer_id': 'layer_1'},
    {'expected_layer_fingerprint': 'x'}, {'profile_parameters': {}}, {'layer_parameters': {}},
    {'scales': [1]}, {'schedule': []}, {'stop_on_success': True}, {'choose_largest': True},
])
def test_forbidden_arguments_refuse_before_io(extra):
    native = Mock(side_effect=AssertionError('invalid request did I/O'))
    for is_live, args in ((False, snapshot()), (True, live_args())):
        with pytest.raises(SectionLayerError):
            run_target_diagnostics(args | extra, live=is_live, request=native)
    native.assert_not_called()


@pytest.mark.parametrize('extra', [
    {'cloud_id': True}, {'cloud_id': 0}, {'normal': [0, 0, 0]}, {'origin': [0, 0, float('inf')]},
    {'half_thickness': -1}, {'query_timeout_seconds': 121}, {'query_timeout_seconds': False},
])
def test_bad_live_request_refuses_before_io(extra):
    native = Mock(side_effect=AssertionError('invalid request did I/O'))
    with pytest.raises(SectionLayerError):
        run_target_diagnostics(live_args() | extra, live=True, request=native)
    native.assert_not_called()


@pytest.mark.parametrize('update', [
    {'truncated': True}, {'truncated': 0}, {'matched_count': 1201}, {'returned_count': 1199},
    {'coordinate_space': 'local'}, {'cloud_id': 360}, {'source_global_scale': 0},
    {'source_global_shift': [float('nan'), 0, 0]},
])
def test_invalid_native_acquisition_stops_before_diagnostics(update):
    request = Mock(return_value=native_result() | update)
    with patch('cloudcompare_mcp.section_target_diagnostic_workflow.diagnose_target_analysis') as numerical:
        with pytest.raises(SectionLayerError):
            run_target_diagnostics(live_args(), live=True, request=request)
        numerical.assert_not_called()
    assert request.call_count == 1


@pytest.mark.parametrize('kind', ['duplicate_index', 'outside_slab', 'nonfinite', 'missing_record'])
def test_bad_records_never_dropped_or_reacquired(kind):
    data = native_result()
    if kind == 'duplicate_index':
        data['points'][1]['point_index'] = data['points'][0]['point_index']
    elif kind == 'outside_slab':
        data['points'][0]['position_global'][2] = 2
    elif kind == 'nonfinite':
        data['points'][0]['position_global'][0] = float('nan')
    else:
        data['points'].pop()
    request = Mock(return_value=data)
    with pytest.raises(SectionLayerError):
        run_target_diagnostics(live_args(), live=True, request=request)
    assert request.call_count == 1


@pytest.mark.parametrize('complete', [False, 1, 'true', None])
def test_snapshot_requires_literal_complete(complete):
    args = snapshot()
    args['section']['acquisition_complete'] = complete
    with pytest.raises(SectionLayerError):
        run_target_diagnostics(args)


@pytest.mark.parametrize('change', ['geometry', 'source', 'frame', 'provenance', 'parameters'])
def test_snapshot_report_bound_to_all_relevant_context(change):
    args = snapshot()
    first = run_target_diagnostics(args)
    if change == 'geometry':
        args['section']['samples_uvd'][0][0] += .01
    elif change == 'source':
        args['section']['source'] = {'cloud_id': 777}
    elif change == 'frame':
        args['section']['frame'] = {'origin_global': [1, 2, 3], 'basis_u': [1, 0, 0],
                                  'basis_v': [0, 1, 0], 'normal': [0, 0, 1]}
    elif change == 'provenance':
        args['section']['provenance'] = {'file_sha256': 'different'}
    else:
        args['target_parameters']['max_targets'] = 31
    assert run_target_diagnostics(args)['report_fingerprint'] != first['report_fingerprint']


@pytest.mark.parametrize('change', ['index', 'shift', 'scale', 'name'])
def test_live_report_bound_to_mapping_and_source_metadata(change):
    data = native_result()
    first = run_target_diagnostics(live_args(), live=True, request=Mock(return_value=data))
    if change == 'index':
        data['points'][0]['point_index'] = 5000
    elif change == 'shift':
        data['source_global_shift'][0] += 1
    elif change == 'scale':
        data['source_global_scale'] = 1
    else:
        data['cloud_name'] = 'renamed'
    later = run_target_diagnostics(live_args(), live=True, request=Mock(return_value=data))
    assert first['report_fingerprint'] != later['report_fingerprint']
    assert first['panels'] == later['panels']


def test_live_record_permutation_is_invariant_and_snapshot_token_distinct():
    data = native_result()
    first = run_target_diagnostics(live_args(), live=True, request=Mock(return_value=data))
    np.random.default_rng(158).shuffle(data['points'])
    second = run_target_diagnostics(live_args(), live=True, request=Mock(return_value=data))
    assert second == first
    assert first['report_fingerprint'] != run_target_diagnostics(snapshot())['report_fingerprint']


def test_diagnostic_fingerprint_cannot_authorize_accepted_target_selection():
    points = np.vstack([rectangle(), rectangle() + [20, 0, 0]])
    args = snapshot(points, reconstruct=True)
    analysis = run_target_workflow(args, reconstruct=True)
    target = analysis['target_analysis']['candidate_targets'][0]
    report = run_target_diagnostics(snapshot(points))
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(args | {'target_id': target['target_id'],
            'expected_target_fingerprint': report['report_fingerprint']}, reconstruct=True)


def test_diagnostic_does_not_change_existing_layer_refusal_or_attempt_reconstruction():
    points = rectangle()
    points[:, 2] = np.where(np.arange(len(points)) % 2, -.1, .1)
    args = snapshot(points, reconstruct=True)
    first = run_target_workflow(args, reconstruct=True)
    with patch('cloudcompare_mcp.section_target_workflow.reconstruct_target', side_effect=AssertionError('profile')):
        report = run_target_diagnostics(snapshot(points))
    assert not report['reconstruction_attempted']
    assert run_target_workflow(args, reconstruct=True) == first
    assert first['blocked_stage'] == 'layer_selection'
