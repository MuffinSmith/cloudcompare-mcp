"""Pure fixed-stencil diagnostics: no MCP transport, native I/O or chosen scale."""
from copy import deepcopy
import json
from unittest.mock import patch as mock_patch

import numpy as np
import pytest

from cloudcompare_mcp import section_target_diagnostics as diag
from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_targets import SectionTargetAnalysis, analyze_section_targets_uvd
from test_section_targets import OPTIONS, patch


def run(points=None, **overrides):
    return diag.diagnose_section_targets_uvd(patch() if points is None else points, **(OPTIONS | overrides))


def panels(result):
    return {p['panel_id']: p for p in result['panels']}


def test_fixed_schedule_is_owned_and_not_outcome_dependent():
    one = diag.schedule()
    assert [(s['uv_factor'], s['depth_factor']) for s in one] == [
        (1, 1), (.75, 1), (1.25, 1), (1, .75), (1, 1.25)]
    one[0]['uv_factor'] = 99
    assert diag.schedule()[0]['uv_factor'] == 1
    with mock_patch.object(diag, 'analyze_section_targets_uvd', wraps=analyze_section_targets_uvd) as solver:
        result = run()
    assert solver.call_count == 5
    for call, spec in zip(solver.call_args_list, result['fixed_schedule']):
        assert call.kwargs['uv_cell_size'] == OPTIONS['uv_cell_size'] * spec['uv_factor']
        assert call.kwargs['depth_cell_size'] == OPTIONS['depth_cell_size'] * spec['depth_factor']
        for key in ('min_cell_points', 'perturbation_fraction'):
            assert call.kwargs[key] == OPTIONS[key]


def test_single_unchanged_evidence_is_not_authorization():
    d = run()
    assert d['status'] == 'no_change_observed'
    assert d['diagnostic_only'] and not d['selection_authorized']
    assert not d['reconstruction_attempted'] and not d['manufacturing_intent_confirmed']
    assert d['point_accounting'] == dict(input_point_count=900, selected_point_count=0, unselected_point_count=900)
    assert all(p['completed'] for p in d['panels'])
    assert all(p['candidate_count'] == 1 for p in d['panels'])
    assert all(p['baseline_comparison']['partition_unchanged'] for p in d['panels'][1:])
    text = json.dumps(d, allow_nan=False)
    for forbidden in ('samples_uvd', 'candidate_fingerprint', 'analysis_fingerprint', 'target_id', 'recommended_scale'):
        assert forbidden not in text
    assert len(text) < 20000


@pytest.mark.parametrize('dominant', [False, True])
def test_two_or_dominant_targets_remain_unselected(dominant):
    points = np.vstack([patch(width=10 if dominant else 6), patch(x=30)])
    d = run(points)
    assert all(p['candidate_count'] == 2 for p in d['panels'])
    assert all(p['accepted_solver_status'] == 'selection_required' for p in d['panels'])
    assert d['point_accounting']['unselected_point_count'] == len(points)


def test_sparse_clutter_accounted_even_when_supported_region_exists():
    points = np.vstack([patch(), [[20, 0, 0], [20, .1, 0], [20, .2, 0]]])
    d = run(points)
    for p in d['panels']:
        assert p['point_accounting']['classified_point_count'] == 903
        assert p['point_accounting']['unsupported_or_ambiguous_point_count'] == 3
        assert p['accepted_solver_status'] == 'selection_required'


@pytest.mark.parametrize('z, expected', [(np.nextafter(1.5, 0), 1), (1.5, 2)])
def test_exact_finer_depth_half_open_boundary(z, expected):
    d = run(np.vstack([patch(), patch(z=z)]))
    p = panels(d)['depth_finer']
    assert p['candidate_count'] == expected
    assert p['baseline_comparison']['split_baseline_candidate_count'] == expected - 1


@pytest.mark.parametrize('z, expected', [(np.nextafter(2.5, 0), 1), (2.5, 2)])
def test_exact_coarser_depth_half_open_boundary(z, expected):
    d = run(np.vstack([patch(), patch(z=z)]))
    p = panels(d)['depth_coarser']
    assert p['candidate_count'] == expected
    assert p['baseline_comparison']['merged_probe_candidate_count'] == 2 - expected


def test_partition_split_and_merge_evidence_uses_all_records():
    for z, panel, field in [(1.6, 'depth_finer', 'split_baseline_candidate_count'),
                            (2., 'depth_coarser', 'merged_probe_candidate_count')]:
        d = run(np.vstack([patch(), patch(z=z)]))
        assert d['status'] == 'sensitivity_observed'
        c = panels(d)[panel]['baseline_comparison']
        assert c[field] == 1
        assert c['changed_membership_point_count'] == 1800
        assert c['unchanged_membership_point_count'] == 0
        assert c['accounted_relation_point_count'] == 1800


def partition(groups):
    pts = np.arange(18, dtype=float).reshape(6, 3)
    summaries, memberships = [], {}
    for i, group in enumerate(groups):
        key = f'target_{i}'
        memberships[key] = np.asarray(group, dtype=np.int64)
        summaries.append(dict(target_id=key, source_point_count=len(group),
                              source_geometry_sha256=key, blocking_reasons=[]))
    return SectionTargetAnalysis(dict(candidate_targets=summaries), pts, memberships)


def test_equal_counts_do_not_hide_rearranged_membership_or_pick_largest_match():
    a = partition([[0, 1, 2], [3, 4, 5]])
    b = partition([[0, 1, 3], [2, 4, 5]])
    c = diag._compare_partitions(a, b)
    assert c['baseline_candidate_count'] == c['probe_candidate_count'] == 2
    assert not c['partition_unchanged']
    assert c['split_baseline_candidate_count'] == c['merged_probe_candidate_count'] == 2
    assert c['changed_membership_point_count'] == 6
    assert c['blocking_reason_uncompared_point_count'] == 6
    assert c['accounted_relation_point_count'] == 6


def test_identical_partition_reason_changes_are_separate_from_membership():
    a = partition([[0, 1, 2], [3, 4, 5]])
    b = deepcopy(a)
    b.public['candidate_targets'][1]['blocking_reasons'] = ['sparse_voxel_support']
    c = diag._compare_partitions(a, b)
    assert c['partition_unchanged']
    assert c['blocking_reason_changed_exact_match_count'] == 1
    assert c['blocking_reason_changed_exact_match_point_count'] == 3


def test_source_record_mismatch_refuses_comparison():
    a = partition([[0, 1, 2], [3, 4, 5]])
    b = deepcopy(a)
    b.samples_uvd = b.samples_uvd[::-1]
    with pytest.raises(SectionLayerError, match='same source'):
        diag._compare_partitions(a, b)


@pytest.mark.parametrize('groups', [[[0, 1], [2, 3, 4]], [[0, 1, 2], [2, 3, 4, 5]]])
def test_internal_accounting_guard(groups):
    with pytest.raises(SectionLayerError, match='exactly one'):
        diag._compare_partitions(partition([[0, 1, 2], [3, 4, 5]]), partition(groups))


def test_probe_budget_refusal_is_inconclusive_with_no_retry():
    with mock_patch.object(diag, 'analyze_section_targets_uvd', wraps=analyze_section_targets_uvd) as solver:
        d = run(max_cells=49)
    assert d['status'] == 'inconclusive'
    assert d['refused_panel_count'] == 1
    refused = panels(d)['uv_finer']
    assert not refused['completed']
    assert 'max_cells' in refused['refusal']
    assert refused['point_accounting']['unclassified_point_count'] == 900
    assert refused['point_accounting']['classified_point_count'] == 0
    assert solver.call_count == 5
    assert all(c.kwargs['max_cells'] == 49 for c in solver.call_args_list)


def test_baseline_budget_failure_stops_before_probes():
    with mock_patch.object(diag, 'analyze_section_targets_uvd', wraps=analyze_section_targets_uvd) as solver:
        with pytest.raises(SectionLayerError, match='max_targets'):
            run(np.vstack([patch(), patch(x=20)]), max_targets=1)
    assert solver.call_count == 1


def test_component_budget_is_not_raised_for_finer_probe():
    d = run(np.array([(x, y, 0) for x in range(6) for y in range(6)]), max_targets=1)
    assert d['status'] == 'inconclusive'
    assert 'max_targets' in panels(d)['uv_finer']['refusal']
    assert panels(d)['baseline']['candidate_count'] == 1


def test_global_precision_guard_refuses_smaller_probes_not_baseline():
    base = analyze_section_targets_uvd(patch(), **OPTIONS)
    base.public['source_global_coordinate_precision_floor'] = .08
    d = diag.diagnose_target_analysis(base)
    assert d['status'] == 'inconclusive'
    assert d['refused_panel_count'] == 2
    for name in ('uv_finer', 'depth_finer'):
        assert 'precision floor' in panels(d)[name]['refusal']
    assert d['source_global_coordinate_precision_floor'] == .08


def test_overflowed_derived_size_is_refused_without_nonfinite_json():
    d = run(patch() * [1e-13, 1e-13, 1], uv_cell_size=1e-13, depth_cell_size=1.6e308)
    assert not panels(d)['depth_coarser']['completed']
    json.dumps(d, allow_nan=False)


def test_permutation_duplicate_records_and_signed_zero_invariant_without_mutation():
    p = np.vstack([patch(), patch(), patch(x=20)])
    p[:, 2] = -0.
    saved = p.tobytes()
    first = run(p)
    assert p.tobytes() == saved
    p = p[np.random.default_rng(991).permutation(len(p))]
    p[:, 2] = 0.
    assert run(p) == first
    assert first['panels'][0]['point_accounting']['classified_point_count'] == 2700


def test_baseline_and_returned_public_values_do_not_alias():
    base = analyze_section_targets_uvd(patch(), **OPTIONS)
    saved = deepcopy(base)
    d = diag.diagnose_target_analysis(base)
    d['parameters']['min_cell_points'] = 100
    d['panels'][0]['candidate_preview'][0]['blocking_reasons'].append('injected')
    assert base.public == saved.public
    np.testing.assert_array_equal(base.samples_uvd, saved.samples_uvd)
    for key in base.target_source_indices:
        np.testing.assert_array_equal(base.target_source_indices[key], saved.target_source_indices[key])


def test_many_targets_preview_omissions_have_exact_candidate_and_relation_counts():
    points = np.vstack([patch(x=i * 20, width=3, height=3) for i in range(20)])
    d = run(points)
    for p in d['panels']:
        assert p['candidate_count'] == 20
        assert p['omitted_candidate_count'] == 12
        assert p['candidate_preview_truncated']
        assert sum(c['source_point_count'] for c in p['candidate_preview']) + p['omitted_candidate_point_count'] == len(points)
        if 'baseline_comparison' in p:
            c = p['baseline_comparison']
            assert c['omitted_relation_count'] == 4
            assert sum(x['shared_point_count'] for x in c['relation_preview']) + c['omitted_relation_point_count'] == len(points)
    assert len(json.dumps(d, allow_nan=False)) < 75000


def test_point_budget_exact_limit():
    assert run(max_points=900)['point_accounting']['input_point_count'] == 900
    with pytest.raises(SectionLayerError, match='899'):
        run(max_points=899)


@pytest.mark.parametrize('overrides', [
    {'uv_cell_size': 0}, {'depth_cell_size': -1}, {'uv_cell_size': float('nan')},
    {'depth_cell_size': float('inf')}, {'uv_cell_size': True}, {'perturbation_fraction': 0},
    {'perturbation_fraction': .251}, {'max_points': 20001}, {'max_cells': 20001},
    {'max_targets': 65}, {'max_targets': False}, {'min_target_cells': 2}, {'min_cell_points': 0},
])
def test_invalid_parameters_refuse(overrides):
    with pytest.raises(SectionLayerError):
        run(**overrides)


@pytest.mark.parametrize('points', [[], [[0, 0, 0]] * 2, [[0, 0]] * 3,
                                    [[True, 0, 0]] * 3, [[float('nan'), 0, 0]] * 3,
                                    [[float('inf'), 0, 0]] * 3, [['x', 0, 0]] * 3])
def test_malformed_nonfinite_geometry_refuses(points):
    with pytest.raises(SectionLayerError):
        run(points)
