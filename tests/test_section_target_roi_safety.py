"""Additional scope and guard adversaries; accepted solvers remain unchanged."""
from copy import deepcopy
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_target_diagnostic_workflow import run_target_diagnostics
from cloudcompare_mcp.section_target_roi_workflow import run_roi_workflow
from test_section_target_roi_workflow import snapshot, live_args, candidates, ROI
from test_section_target_workflow import choose
from test_section_layer_workflow import rectangle, native_result


def test_one_guard_clear_candidate_does_not_automatically_replace_multiple_targets():
    p = np.vstack([rectangle(), rectangle() + [20, 0, 0]])
    args = snapshot(p, True, ROI | {'u_max': 24})
    r = run_roi_workflow(args, reconstruct=True)
    a = r['roi_analysis']
    assert len(candidates(a)) == 2
    assert sum(g['eligible_for_downstream'] for g in a['candidate_guards']) == 1
    assert a['status'] == 'selection_required'
    assert r['blocked_stage'] == 'target_selection'
    assert r['point_accounting']['selected_target_point_count'] == 0
    for c, guard in zip(candidates(a), a['candidate_guards']):
        selected = run_roi_workflow(choose(args, c), reconstruct=True)
        if guard['eligible_for_downstream']:
            assert selected['status'] == 'candidate'
            assert selected['point_accounting']['total_unselected_point_count'] == 1200
        else:
            assert selected['blocked_stage'] == 'roi_truncation_guard'


def test_inside_target_budget_refusal_keeps_outside_and_unclassified_accounting():
    p = np.vstack([rectangle(), rectangle() + [20, 0, 0], [[100, 100, 0]]])
    args = snapshot(p, True, ROI | {'u_max': 31})
    args['target_parameters']['max_targets'] = 1
    r = run_roi_workflow(args, reconstruct=True)
    assert r['blocked_stage'] == 'target_analysis' and 'max_targets' in r['reason']
    counts = r['roi_analysis']['point_accounting']
    assert counts['inside_roi_point_count'] == counts['target_unclassified_inside_point_count'] == 2400
    assert counts['target_classified_point_count'] == 0
    assert counts['outside_roi_point_count'] == 1
    assert r['point_accounting']['total_unselected_point_count'] == 2401


def test_diagnostic_report_fingerprint_is_not_roi_reconstruction_authorization():
    args = snapshot(reconstruct=True)
    a = run_roi_workflow(snapshot())
    diagnostic_args = {k: v for k, v in snapshot().items() if k != 'roi'}
    report = run_target_diagnostics(diagnostic_args)
    chosen = choose(args, candidates(a)[0])
    chosen['expected_target_fingerprint'] = report['report_fingerprint']
    with pytest.raises(SectionLayerError, match='fingerprint'):
        run_roi_workflow(chosen, reconstruct=True)


def test_live_changed_outside_geometry_and_acquisition_bookkeeping_stale_tokens():
    native = native_result(np.vstack([rectangle(), [[20, 0, 0]]]))
    a = run_roi_workflow(live_args(), live=True, request=Mock(return_value=native))
    chosen = choose(live_args(True), candidates(a)[0])
    for change in ('outside', 'scale', 'shift', 'strategy'):
        mutated = deepcopy(native)
        if change == 'outside': mutated['points'][-1]['position_global'][0] += 1
        elif change == 'scale': mutated['source_global_scale'] = 1
        elif change == 'shift': mutated['source_global_shift'][0] += 1
        else: mutated['sample_strategy'] = 'all_matches_new_acquisition_context'
        with pytest.raises(SectionLayerError, match='fingerprint'):
            run_roi_workflow(chosen, live=True, reconstruct=True, request=Mock(return_value=mutated))


def test_all_deep_outside_samples_remain_accounted_without_depth_filtering():
    outside = np.array([[20, 0, -1e5], [20, 0, 1e5], [20, 0, 0]])
    r = run_roi_workflow(snapshot(np.vstack([rectangle(), outside])))
    assert r['status'] == 'ready'
    assert r['outside_roi']['point_count'] == 3
    assert r['outside_roi']['bounds_uvd'][0][2] == -1e5
    assert r['outside_roi']['bounds_uvd'][1][2] == 1e5
