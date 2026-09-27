"""Pure workflow and replayed native-boundary tests, NOT real CloudCompare tests."""
from copy import deepcopy
import json
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.section_layer_workflow import run_layer_workflow
from cloudcompare_mcp.section_layers import SectionLayerError

LAYER = dict(uv_cell_size=0.5, depth_separation=0.3, max_layer_thickness=0.1,
             max_neighbor_depth_step=0.15, min_cell_points=1)
PROFILE = dict(cell_size=0.5, max_edge_length=1.1, fit_tolerance=0.35)


def rectangle(depth=0):
    return np.asarray([(float(x), float(y), float(depth))
                       for x in np.arange(0.1, 8, 0.2) for y in np.arange(0.1, 6, 0.2)])


def snapshot(points=None, reconstruct=False):
    points = rectangle() if points is None else points
    args = {'section': {'coordinate_space': 'section_uv_depth', 'units': 'native',
                        'acquisition_complete': True, 'samples_uvd': points.tolist()},
            'layer_parameters': deepcopy(LAYER)}
    if reconstruct:
        args['profile_parameters'] = deepcopy(PROFILE)
    return args


def live_args(reconstruct=False):
    args = dict(cloud_id=359, origin=[0, 0, 0], normal=[0, 0, 1], half_thickness=0.5,
                layer_parameters=deepcopy(LAYER))
    if reconstruct:
        args['profile_parameters'] = deepcopy(PROFILE)
    return args


def native_result(points=None):
    points = rectangle() if points is None else points
    return dict(cloud_id=359, cloud_name='layer-fixture', coordinate_space='global',
                matched_count=len(points), returned_count=len(points), truncated=False,
                sample_strategy='all_matches', source_global_shift=[123, -456, 789],
                source_global_scale=2.5,
                points=[{'point_index': i, 'position_global': row.tolist()} for i, row in enumerate(points)])


def test_snapshot_analysis_never_calls_transport():
    transport = Mock(side_effect=AssertionError('snapshot must not contact bridge'))
    result = run_layer_workflow(snapshot(), request=transport)
    assert result['status'] == 'ready'
    assert result['live_connection_used'] is False
    assert result['acquisition']['verification'] == 'caller_asserted_snapshot'
    transport.assert_not_called()


def test_one_layer_reuses_accepted_occupancy_topology_and_fitter():
    args = snapshot(reconstruct=True)
    saved = deepcopy(args)
    result = run_layer_workflow(args, reconstruct=True)
    assert result['status'] == 'candidate'
    assert result['profile']['version'] == '0.15.2'
    assert result['profile']['topology']['loop_count'] == 1
    assert result['profile']['topology']['loops'][0]['role_candidate'] == 'outer'
    assert result['profile']['topology']['loops'][0]['profile']['primitives']
    assert result['selection']['selected_point_count'] == len(rectangle())
    assert result['selection']['unselected_point_count'] == 0
    assert args == saved


def test_two_layers_return_candidates_until_explicit_current_choice():
    points = np.concatenate([rectangle(-0.4), rectangle(0.4)])
    args = snapshot(points, reconstruct=True)
    blocked = run_layer_workflow(args, reconstruct=True)
    assert blocked['status'] == 'blocked' and blocked['blocked_stage'] == 'layer_selection'
    assert 'profile' not in blocked
    analysis = blocked['layer_analysis']
    args['layer_id'] = analysis['candidate_layers'][1]['layer_id']
    args['expected_analysis_fingerprint'] = analysis['analysis_fingerprint']
    result = run_layer_workflow(args, reconstruct=True)
    assert result['status'] == 'candidate'
    assert result['selection']['mode'] == 'explicit_caller_choice'
    assert result['selection']['unselected_point_count'] == len(rectangle())
    assert result['manufacturing_intent_confirmed'] is False


def test_selected_layer_cannot_bypass_other_unsafe_evidence():
    points = np.concatenate([rectangle(), [[20, 20, 0]]])
    args = snapshot(points, reconstruct=True)
    result = run_layer_workflow(args, reconstruct=True)
    analysis = result['layer_analysis']
    args['layer_id'] = next(c['layer_id'] for c in analysis['candidate_layers'] if c['usable'])
    args['expected_analysis_fingerprint'] = analysis['analysis_fingerprint']
    assert run_layer_workflow(args, reconstruct=True)['status'] == 'blocked'


def test_accepted_topology_refusal_retains_layer_and_boundary_diagnostics():
    args = snapshot(reconstruct=True)
    args['profile_parameters']['max_edge_length'] = 0.01
    result = run_layer_workflow(args, reconstruct=True)
    assert result['status'] == 'blocked'
    assert result['blocked_stage'] == 'boundary_or_topology'
    assert result['layer_analysis']['status'] == 'ready'
    assert result['boundary_evidence']['connected_contour_count'] == 1
    assert 'at least' in result['reason']


def test_context_and_source_changes_invalidate_explicit_choice():
    args = snapshot(reconstruct=True)
    old = run_layer_workflow(args, reconstruct=True)['layer_analysis']
    args['layer_id'] = old['auto_selected_layer_id']
    args['expected_analysis_fingerprint'] = old['analysis_fingerprint']
    args['section']['frame'] = {'frame_id': 'different-frame'}
    with pytest.raises(SectionLayerError, match='current expected'):
        run_layer_workflow(args, reconstruct=True)


@pytest.mark.parametrize('field,value', [('acquisition_complete', False), ('acquisition_complete', 1),
                                       ('coordinate_space', 'global'), ('units', 'mm'),
                                       ('provenance', 'unknown'), ('provenance', {'large': 'a'*5000}),
                                       ('provenance', {'bad': float('nan')}),
                                       ('frame', {'normal': [0, 0, 1]}),
                                       ('source', {'global_scale': -1})])
def test_snapshot_contract_errors(field, value):
    args = snapshot()
    args['section'][field] = value
    with pytest.raises(SectionLayerError):
        run_layer_workflow(args)


def test_complete_snapshot_frame_and_shift_scale_are_preserved_not_reapplied():
    args = snapshot()
    args['section']['frame'] = dict(origin_global=[1e8, -2e8, 3e8], basis_u=[1, 0, 0],
                                    basis_v=[0, 1, 0], normal=[0, 0, 1])
    args['section']['source'] = dict(cloud_id=359, cloud_name='fixture', global_shift=[1, 2, 3], global_scale=2.5)
    first = run_layer_workflow(args)
    args['section']['source']['global_scale'] = 1
    second = run_layer_workflow(args)
    assert first['source_geometry_sha256'] == second['source_geometry_sha256']
    assert first['analysis_fingerprint'] != second['analysis_fingerprint']
    args['section']['frame']['basis_v'] = [0, -1, 0]
    with pytest.raises(SectionLayerError, match='right-handed'):
        run_layer_workflow(args)


def test_live_single_read_complete_coordinates_and_source_mapping():
    native = native_result()
    before = deepcopy(native)
    transport = Mock(return_value=native)
    result = run_layer_workflow(live_args(), live=True, request=transport)
    assert result['status'] == 'ready' and result['source']['cloud_id'] == 359
    assert result['source']['global_scale'] == 2.5
    assert result['source_coordinate_bookkeeping']['shift_scale_reapplied'] is False
    assert result['acquisition']['matched_count'] == result['acquisition']['sampled_count'] == len(rectangle())
    assert result['acquisition']['source_integrity_coverage'] == 'not_independently_measured_by_this_tool'
    assert native == before
    transport.assert_called_once()
    method, params = transport.call_args.args
    assert method == 'cloud.region_query' and params['region']['type'] == 'slab'
    assert params['coordinate_space'] == 'global' and params['max_points'] == 20000
    assert transport.call_args.kwargs['timeout'] == 30
    assert result['candidate_layers'][0]['source_point_indices_sha256']
    dumped = json.dumps(result, allow_nan=False)
    assert len(dumped) < 9000
    assert 'position_global' not in dumped and 'signed_offsets' not in dumped


def test_live_record_permutation_preserves_full_public_output():
    native = native_result(np.concatenate([rectangle(-0.4), rectangle(0.4)]))
    first = run_layer_workflow(live_args(), live=True, request=Mock(return_value=native))
    native['points'] = native['points'][::-1]
    second = run_layer_workflow(live_args(), live=True, request=Mock(return_value=native))
    assert first == second


def test_live_selected_composite_reacquires_and_rejects_changed_source():
    args = live_args(reconstruct=True)
    native = native_result(np.concatenate([rectangle(-0.4), rectangle(0.4)]))
    first = run_layer_workflow(args, live=True, reconstruct=True, request=Mock(return_value=native))
    analysis = first['layer_analysis']
    args['layer_id'] = analysis['candidate_layers'][0]['layer_id']
    args['expected_analysis_fingerprint'] = analysis['analysis_fingerprint']
    second = run_layer_workflow(args, live=True, reconstruct=True, request=Mock(return_value=native))
    assert second['status'] == 'candidate'
    native['source_global_shift'][0] += 1
    with pytest.raises(SectionLayerError, match='current expected'):
        run_layer_workflow(args, live=True, reconstruct=True, request=Mock(return_value=native))


@pytest.mark.parametrize('field,value', [('truncated', True), ('truncated', None),
                                       ('matched_count', True), ('matched_count', 1300),
                                       ('returned_count', None), ('returned_count', 20001),
                                       ('coordinate_space', 'native_local'), ('cloud_id', 360),
                                       ('cloud_id', True), ('source_global_shift', [0, 0]),
                                       ('source_global_shift', [0, 0, float('nan')]),
                                       ('source_global_scale', 0), ('cloud_name', '')])
def test_live_malformed_or_incomplete_acquisition_is_refused(field, value):
    native = native_result()
    native[field] = value
    with pytest.raises(SectionLayerError):
        run_layer_workflow(live_args(), live=True, request=Mock(return_value=native))


@pytest.mark.parametrize('change,match', [('count', 'every returned record'),
                                        ('duplicate', 'Duplicate'), ('nonfinite', 'finite'),
                                        ('outside', 'outside the requested slab'),
                                        ('boolean', 'numeric'), ('missing_index', 'point_index')])
def test_live_point_records_are_checked_without_filtering(change, match):
    native = native_result()
    if change == 'count':
        native['points'].pop()
    elif change == 'duplicate':
        native['points'][0]['point_index'] = native['points'][1]['point_index']
    elif change == 'missing_index':
        native['points'][0].pop('point_index')
    else:
        native['points'][0]['position_global'][2] = {'nonfinite': float('nan'), 'outside': 0.7, 'boolean': True}[change]
    with pytest.raises(SectionLayerError, match=match):
        run_layer_workflow(live_args(), live=True, request=Mock(return_value=native))


@pytest.mark.parametrize('field,value', [('cloud_id', True), ('normal', [0, 0, 0]),
                                       ('normal', [0, 0, '1']), ('half_thickness', -1),
                                       ('half_thickness', True), ('query_timeout_seconds', 121),
                                       ('layer_parameters', LAYER | {'depth_separation': 0})])
def test_bad_live_requests_fail_before_io(field, value):
    args = live_args()
    args[field] = value
    transport = Mock()
    with pytest.raises(SectionLayerError):
        run_layer_workflow(args, live=True, request=transport)
    transport.assert_not_called()


def test_bad_profile_parameters_fail_before_io():
    args = live_args(reconstruct=True)
    args['profile_parameters']['require_grid_stability'] = 'false'
    transport = Mock()
    with pytest.raises(SectionLayerError):
        run_layer_workflow(args, live=True, reconstruct=True, request=transport)
    transport.assert_not_called()


def test_live_large_translation_bookkeeping_and_subprecision_request():
    points = rectangle()
    origin = np.asarray([1e8, -2e8, 3e8])
    args = live_args()
    args['origin'] = origin.tolist()
    native = native_result(points + origin)
    result = run_layer_workflow(args, live=True, request=Mock(return_value=native))
    assert result['status'] == 'ready'
    assert result['section_frame']['origin_global'] == origin.tolist()
    assert result['depth']['min'] == result['depth']['max'] == 0
    args['layer_parameters']['max_layer_thickness'] = 1e-10
    with pytest.raises(SectionLayerError, match='source global-coordinate precision floor'):
        run_layer_workflow(args, live=True, request=Mock(return_value=native))


def test_large_finite_depth_summaries_are_finite():
    args = snapshot(rectangle(1e308))
    args['layer_parameters'].update(depth_separation=1e295, max_layer_thickness=1e294, max_neighbor_depth_step=1e294)
    result = run_layer_workflow(args)
    assert result['status'] == 'ready'
    assert result['depth']['median'] == 1e308
    json.dumps(result, allow_nan=False)
