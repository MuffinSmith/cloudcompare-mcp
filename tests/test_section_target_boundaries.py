"""Exact budget boundaries, representability and live provenance refusal regressions."""
from copy import deepcopy
import json
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_target_workflow import run_target_workflow
from test_section_targets import analyze, patch
from test_section_target_workflow import live_args, choose
from test_section_layer_workflow import native_result


@pytest.mark.parametrize('size', [1., np.nextafter(1., 0.), np.nextafter(1., 2.)])
def test_exact_cell_boundary_changes_are_not_rounded_away(size):
    points = np.array([(x, y, 0.) for x in range(4) for y in range(4)])
    result = analyze(points, uv_cell_size=size).public
    assert result['occupied_cell_count'] == (9 if size > 1 else 16)
    assert sum(c['source_point_count'] for c in result['candidate_targets']) == 16


def test_max_cells_includes_all_fixed_probes_not_just_baseline():
    points = np.array([(x, y, 0.) for x in range(4) for y in range(4)])
    result = analyze(points, max_cells=16, max_points=16, max_targets=1).public
    assert result['status'] == 'ready'
    assert all(p['occupied_cell_count'] <= 16 for p in result['perturbation_probes'])
    # Dense points can occupy an additional edge row under a declared origin probe.
    with pytest.raises(SectionLayerError, match='max_cells'):
        analyze(patch(width=4, height=4), max_cells=16)


@pytest.mark.parametrize('minimum, expected', [(16, 'ready'), (17, 'blocked')])
def test_exact_minimum_target_cells(minimum, expected):
    points = np.array([(x, y, 0.) for x in range(4) for y in range(4)])
    assert analyze(points, min_target_cells=minimum).public['status'] == expected


@pytest.mark.parametrize('options', [
    {'uv_cell_size': 1e200, 'depth_cell_size': 1e200},
    {'uv_cell_size': 1e-200, 'depth_cell_size': 1e-200},
])
def test_unrepresentable_volume_or_tolerance_refuses_finite_input(options):
    with pytest.raises(SectionLayerError, match='precision|volume'):
        analyze(patch(), **options)


def test_unrepresentable_span_refuses_without_infinite_summary():
    points = patch()
    points[0, 0], points[1, 0] = -1e308, 1e308
    with pytest.raises(SectionLayerError, match='precision'):
        analyze(points)


@pytest.mark.parametrize('field,value', [
    ('source_global_scale', 3.), ('source_global_shift', [1, 2, 3]),
    ('cloud_name', 'different identity'), ('sample_strategy', 'different provenance'),
])
def test_live_token_binds_source_and_acquisition_metadata(field, value):
    native = native_result()
    analysis = run_target_workflow(live_args(), live=True, request=Mock(return_value=native))
    args = choose(live_args(True), analysis['candidate_targets'][0])
    native[field] = value
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(args, live=True, reconstruct=True, request=Mock(return_value=native))


def test_live_token_binds_point_index_mapping_not_only_geometry():
    native = native_result()
    analysis = run_target_workflow(live_args(), live=True, request=Mock(return_value=native))
    args = choose(live_args(True), analysis['candidate_targets'][0])
    for point in native['points']:
        point['point_index'] += 5000
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_target_workflow(args, live=True, reconstruct=True, request=Mock(return_value=native))


@pytest.mark.parametrize('parameter', ['uv_cell_size', 'depth_cell_size'])
def test_live_declared_perturbations_must_exceed_source_precision(parameter):
    native = native_result()
    translation = [1e8, -2e8, 3e8]
    for point in native['points']:
        point['position_global'] = (np.array(point['position_global']) + translation).tolist()
    args = live_args() | {'origin': translation}
    args['target_parameters'][parameter] = 1e-9
    with pytest.raises(SectionLayerError, match='precision floor'):
        run_target_workflow(args, live=True, request=Mock(return_value=native))


def test_extreme_finite_normal_is_safely_normalized():
    native = native_result()
    result = run_target_workflow(live_args() | {'normal': [0, 0, 1e308]}, live=True,
                                request=Mock(return_value=native))
    assert result['status'] == 'ready'
    json.dumps(result, allow_nan=False)


def test_input_iterator_bounded_before_any_topology_decision():
    consumed = []
    def stream():
        for i in range(1000):
            consumed.append(i)
            yield [i, 0., 0.]
    with pytest.raises(SectionLayerError, match='complete samples'):
        analyze(stream(), max_points=10)
    assert len(consumed) == 11
