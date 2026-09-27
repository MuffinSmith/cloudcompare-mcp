"""Fixed target-scale evidence comparisons, never scale selection or reconstruction.

The accepted 0.15.4 solver and its baseline partition are not modified. Four probes
change one cell-size axis at a time, with the same support and acquisition budgets.
Only bounded summaries leave this module; exact source-record memberships stay here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable, Sequence

import numpy as np

from .section_layers import SectionLayerError
from .section_targets import SectionTargetAnalysis, analyze_section_targets_uvd

VERSION = '0.15.5'
CANDIDATE_PREVIEW_LIMIT = 8
RELATION_PREVIEW_LIMIT = 16
# Fixed, public, nonadaptive stencil. Neither the caller nor outcomes add probes.
STENCIL = (('baseline', 1., 1.), ('uv_finer', .75, 1.),
           ('uv_coarser', 1.25, 1.), ('depth_finer', 1., .75),
           ('depth_coarser', 1., 1.25))
CONTEXT_KEYS = ('section_frame', 'source', 'source_coordinate_bookkeeping',
                'live_connection_used', 'source_global_coordinate_precision_floor',
                'acquisition', 'provenance')


def schedule() -> list[dict[str, Any]]:
    """Return an owned description; callers cannot mutate the actual stencil."""
    return [dict(panel_id=name, uv_factor=uv, depth_factor=depth)
            for name, uv, depth in STENCIL]


def _candidate_summary(candidate: dict) -> dict:
    fields = ('source_point_count', 'unique_point_count', 'bounds_uvd',
              'occupied_cell_count', 'unique_support_per_cell', 'blocking_reasons',
              'articulation_cell_count', 'uv_eroded_component_count',
              'nearest_other_bbox_distance_lower_bound')
    return dict(region_geometry_sha256=candidate['source_geometry_sha256'],
                **{key: deepcopy(candidate[key]) for key in fields})


def _panel(analysis: SectionTargetAnalysis, spec: dict) -> dict:
    public = analysis.public
    candidates = public['candidate_targets']
    preview = candidates[:CANDIDATE_PREVIEW_LIMIT]  # Spatial order, not size/quality.
    reasons = []
    for reason in public['warnings']:
        affected = [c for c in candidates if reason in c['blocking_reasons']]
        reasons.append(dict(reason=reason, candidate_count=len(affected),
                            point_count=sum(c['source_point_count'] for c in affected)))
    unsupported = public['point_accounting']['unsupported_or_ambiguous_point_count']
    return dict(
        **spec, completed=True, parameters=deepcopy(public['parameters']),
        accepted_solver_status=public['status'],
        candidate_count=len(candidates), occupied_cell_count=public['occupied_cell_count'],
        usable_candidate_count=sum(c['usable'] for c in candidates),
        point_accounting=dict(input_point_count=public['source_point_count'],
                              classified_point_count=public['source_point_count'],
                              unclassified_point_count=0,
                              unsupported_or_ambiguous_point_count=unsupported,
                              supported_point_count=public['source_point_count'] - unsupported),
        blocking_reason_totals=reasons, blocking_reason_totals_overlap=True,
        candidate_preview=[_candidate_summary(c) for c in preview],
        candidate_preview_truncated=len(candidates) > len(preview),
        omitted_candidate_count=len(candidates) - len(preview),
        omitted_candidate_point_count=sum(c['source_point_count'] for c in candidates[len(preview):]),
        origin_probe_changed_target_counts=[p['changed_target_count'] for p in public['perturbation_probes']],
    )


def _labels(analysis: SectionTargetAnalysis) -> np.ndarray:
    labels = np.full(len(analysis.samples_uvd), -1, dtype=np.int64)
    visits = np.zeros(len(labels), dtype=np.int64)
    for i, candidate in enumerate(analysis.public['candidate_targets']):
        indices = analysis.target_source_indices[candidate['target_id']]
        if len(indices) != candidate['source_point_count']:
            raise SectionLayerError('Diagnostic partition count disagrees with membership')
        labels[indices] = i
        np.add.at(visits, indices, 1)
    if np.any(visits != 1):
        raise SectionLayerError('Diagnostic partition requires exactly one assignment per source record')
    return labels


def _compare_partitions(baseline: SectionTargetAnalysis, probe: SectionTargetAnalysis) -> dict:
    """Exact intersections. Same candidate counts do NOT imply the same partition."""
    if not np.array_equal(baseline.samples_uvd, probe.samples_uvd):
        raise SectionLayerError('Diagnostic panels must use the same source records in the same order')
    left, right = baseline.public['candidate_targets'], probe.public['candidate_targets']
    table = np.zeros((len(left), len(right)), dtype=np.int64)
    np.add.at(table, (_labels(baseline), _labels(probe)), 1)
    present = table > 0
    row_degree, column_degree = present.sum(axis=1), present.sum(axis=0)
    unchanged_points = reason_changed_points = unchanged_count = reason_changed_count = 0
    for i, candidate in enumerate(left):
        js = np.flatnonzero(present[i])
        if len(js) == 1 and column_degree[js[0]] == 1:
            unchanged_count += 1
            unchanged_points += candidate['source_point_count']
            if candidate['blocking_reasons'] != right[js[0]]['blocking_reasons']:
                reason_changed_count += 1
                reason_changed_points += candidate['source_point_count']
    pairs = np.argwhere(present)
    preview = []
    for i, j in pairs[:RELATION_PREVIEW_LIMIT]:
        preview.append(dict(baseline_region_sha256=left[i]['source_geometry_sha256'],
                            probe_region_sha256=right[j]['source_geometry_sha256'],
                            shared_point_count=int(table[i, j]),
                            baseline_splits=bool(row_degree[i] > 1),
                            probe_merges=bool(column_degree[j] > 1)))
    n = len(baseline.samples_uvd)
    return dict(
        method='exact_source_record_intersections',
        partition_unchanged=unchanged_points == n,
        baseline_candidate_count=len(left), probe_candidate_count=len(right),
        split_baseline_candidate_count=int(np.sum(row_degree > 1)),
        merged_probe_candidate_count=int(np.sum(column_degree > 1)),
        unchanged_baseline_candidate_count=unchanged_count,
        changed_baseline_candidate_count=len(left) - unchanged_count,
        unchanged_membership_point_count=unchanged_points,
        changed_membership_point_count=n - unchanged_points,
        blocking_reason_changed_exact_match_count=reason_changed_count,
        blocking_reason_changed_exact_match_point_count=reason_changed_points,
        blocking_reason_comparison_scope='one-to-one identical membership only',
        blocking_reason_uncompared_point_count=n - unchanged_points,
        relation_count=len(pairs), relation_preview=preview,
        relation_preview_truncated=len(pairs) > len(preview),
        omitted_relation_count=len(pairs) - len(preview),
        omitted_relation_point_count=n - sum(p['shared_point_count'] for p in preview),
        accounted_relation_point_count=int(table.sum()),
    )


def diagnose_target_analysis(baseline: SectionTargetAnalysis) -> dict:
    """Compare an already completed, trusted product analysis; blocked is allowed.

    The workflow supplies a context-bound analysis from accepted acquisition. An
    over-budget/incomplete baseline must fail there, before this function is called.
    """
    options = baseline.public['parameters']
    n = len(baseline.samples_uvd)
    specs = schedule()
    panels = [_panel(baseline, specs[0])]
    for spec in specs[1:]:
        changed = options | dict(uv_cell_size=options['uv_cell_size'] * spec['uv_factor'],
                                 depth_cell_size=options['depth_cell_size'] * spec['depth_factor'])
        try:
            # The snapshot core checks section-relative precision; live global
            # quantization must additionally remain meaningful at the smaller size.
            floor = baseline.public.get('source_global_coordinate_precision_floor', 0.)
            if min(changed['uv_cell_size'], changed['depth_cell_size']) * changed['perturbation_fraction'] < floor:
                raise SectionLayerError('Diagnostic cell perturbation is below source global-coordinate precision floor')
            analysis = analyze_section_targets_uvd(baseline.samples_uvd, **changed)
        except SectionLayerError as exc:
            # Refusal is evidence, not permission to change a budget or ignore a panel.
            # Report factors, not potentially overflowed derived sizes (finite JSON).
            panels.append(dict(**spec, completed=False, refusal=str(exc),
                               point_accounting=dict(input_point_count=n, classified_point_count=0,
                                                     unclassified_point_count=n)))
            continue
        panel = _panel(analysis, spec)
        panel['baseline_comparison'] = _compare_partitions(baseline, analysis)
        panels.append(panel)
    comparisons = [p['baseline_comparison'] for p in panels if 'baseline_comparison' in p]
    partition_changed = any(not c['partition_unchanged'] for c in comparisons)
    reasons_changed = any(c['blocking_reason_changed_exact_match_count'] for c in comparisons)
    complete = all(p['completed'] for p in panels)
    status = ('inconclusive' if not complete else 'sensitivity_observed' if
              partition_changed or reasons_changed else 'no_change_observed')
    # Context-bound accepted hash is an input, never returned as a selection token.
    payload = dict(algorithm='section_target_scale_diagnostics_v1',
                   baseline=baseline.public['analysis_fingerprint'], stencil=specs)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                      allow_nan=False).encode()).hexdigest()
    result = dict(
        type='section_target_scale_diagnostics', version=VERSION, status=status,
        diagnostic_only=True, selection_authorized=False, reconstruction_attempted=False,
        report_fingerprint='target-diagnostic-v1:' + digest,
        source_geometry_sha256=baseline.public['source_geometry_sha256'],
        coordinate_space='section_uv_depth', units='native',
        parameters=deepcopy(options), fixed_schedule=specs,
        comparison_scope='sampled partitions and blocking-reason sets at five fixed settings',
        all_panels_completed=complete, completed_panel_count=sum(p['completed'] for p in panels),
        refused_panel_count=sum(not p['completed'] for p in panels),
        any_partition_change_observed=partition_changed,
        any_blocking_reason_change_observed=bool(reasons_changed),
        panels=panels, point_accounting=dict(input_point_count=n, selected_point_count=0,
                                             unselected_point_count=n),
        candidate_preview_limit=CANDIDATE_PREVIEW_LIMIT,
        relation_preview_limit=RELATION_PREVIEW_LIMIT,
        accepted_target_solver_version='0.15.4', raw_points_returned=False,
        scene_mutations_requested=False, manufacturing_intent_confirmed=False,
        assumptions=[
            'diagnostics only: no selected or recommended scale, target or profile',
            'baseline must complete; a refused probe makes the report inconclusive',
            'all five settings share source records, support thresholds and budgets',
            'reason totals overlap; preview omissions are summaries, never acquisition truncation',
            'no change observed is not physical topology, full-cloud integrity or universal stability proof',
            'different numerical support values are reported but do not alone mean membership changed',
            'finer/coarser refer to UV or depth cell size alone, not improved evidence quality',
        ],
    )
    result.update({key: deepcopy(baseline.public[key]) for key in CONTEXT_KEYS if key in baseline.public})
    return result


def diagnose_section_targets_uvd(samples_uvd: Iterable[Sequence[float]], **target_parameters: Any) -> dict:
    """Independent numerical entry point; no live acquisition or MCP imports."""
    return diagnose_target_analysis(analyze_section_targets_uvd(samples_uvd, **target_parameters))
