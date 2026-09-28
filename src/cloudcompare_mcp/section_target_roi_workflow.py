"""Complete slab -> explicit UV ROI -> unchanged accepted target/layer/profile chain.

ROI intent is spatial only. The one-cell edge guard is an additional refusal, never
an override of target/layer safety. Report fingerprints are not selection tokens.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

import numpy as np

from .section_layers import SectionLayerError, integer
from .section_target_roi import CONTRACT, VERSION, SectionROI, candidate_roi_guard, classify_section_roi, validate_roi
from .section_target_workflow import (
    SectionTargetInput, live_target_input, snapshot_target_input,
    target_analysis_from_input, reconstruct_target, validate_request,
)
from .section_targets import SectionTargetAnalysis, SectionTargetError, select_section_target


@dataclass
class ROIAnalysis:
    public: dict
    roi: SectionROI
    target: SectionTargetAnalysis | None


def _fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _index_hash(indices: np.ndarray) -> str:
    return hashlib.sha256(np.sort(indices).astype('<u8').tobytes()).hexdigest()


def _request(args: Any, live: bool, reconstruct: bool) -> tuple[dict, dict, dict, Any]:
    if not isinstance(args, dict) or 'roi' not in args:
        raise SectionTargetError('arguments require an explicit roi object')
    bounds = validate_roi(args['roi'])
    base = {k: v for k, v in args.items() if k != 'roi'}
    indices = None
    if not live and isinstance(base.get('section'), dict):
        section = base['section']
        if 'source_point_indices' in section:
            indices = section['source_point_indices']
            if not isinstance(indices, (list, tuple)):
                raise SectionTargetError('source_point_indices must be an array of unique integer source indices')
            base['section'] = {k: v for k, v in section.items() if k != 'source_point_indices'}
    options = validate_request(base, live=live, reconstruct=reconstruct)
    return base, options, bounds, indices


def _snapshot_input(args: dict, options: dict, indices: Any) -> SectionTargetInput:
    data = snapshot_target_input(args, options)
    if indices is not None:
        if len(indices) != len(data.samples_uvd):
            raise SectionTargetError('source_point_indices must match every complete snapshot sample')
        source = np.asarray([integer(i, 'source_point_index', 0, 2**32 - 1) for i in indices], dtype=np.uint64)
        if len(np.unique(source)) != len(source):
            raise SectionTargetError('Duplicate snapshot source_point_indices cannot identify complete evidence')
        order = np.argsort(source)
        data.context['snapshot_source_index_mapping'] = {
            'verification': 'caller_asserted_indices_bound_to_section_samples',
            'point_mapping_sha256': hashlib.sha256(source[order].astype('<u8').tobytes()
                                                  + data.samples_uvd[order].astype('<f8').tobytes()).hexdigest()}
        data.source_indices = source
    return data


def analyze_roi_input(data: SectionTargetInput, bounds: dict, options: dict) -> ROIAnalysis:
    roi = classify_section_roi(data.samples_uvd, bounds, uv_cell_size=options['uv_cell_size'],
                               max_points=options['max_points'])
    public = deepcopy(roi.public)
    public.update(type='section_target_roi_analysis', version=VERSION, status='blocked',
                  coordinate_space='section_uv_depth', target_parameters=deepcopy(options),
                  manufacturing_intent_confirmed=False, user_accepted=False,
                  candidate_guards=[], target_analysis=None)
    public.update(deepcopy(data.context))
    inside, outside = roi.inside_indices, roi.outside_indices
    if data.source_indices is not None:
        public['source_index_accounting'] = {
            'available': True, 'whole_slab_indices_sha256': _index_hash(data.source_indices),
            'inside_roi_indices_sha256': _index_hash(data.source_indices[inside]),
            'outside_roi_indices_sha256': _index_hash(data.source_indices[outside])}
    else:
        public['source_index_accounting'] = {'available': False}
    # Bind ALL acquired geometry, not just the selected area. Context includes full
    # native index->XYZ mapping, source/frame/acquisition and shift/scale bookkeeping.
    public['roi_fingerprint'] = _fingerprint({
        'domain': CONTRACT, 'roi': bounds, 'whole_slab': roi.public['whole_slab'],
        'source_index_accounting': public['source_index_accounting'],
        'context': data.context, 'target_parameters': options})
    public['fingerprint_scope'] = 'ROI report/context only; selection requires nested target candidate_fingerprint'
    public['point_accounting'].update(target_classified_point_count=0,
                                      target_unclassified_inside_point_count=len(inside),
                                      selected_point_count=0, unselected_point_count=len(roi.samples_uvd))
    analysis = ROIAnalysis(public, roi, None)
    if len(inside) < 3 or not public['edge_guard']['guard_clear_interior_exists']:
        public.update(blocked_stage='roi_evidence',
                      reason='ROI has fewer than three points or no interior clear of the fixed one-cell edge guard')
        return analysis
    scope = {'contract': CONTRACT, 'roi_fingerprint': public['roi_fingerprint'],
             'roi': bounds, 'complete_slab_point_count': len(roi.samples_uvd),
             'inside_roi_point_count': len(inside), 'outside_roi_point_count': len(outside),
             'target_input_scope': 'all signed depths of every in-ROI sample; outside points explicitly unselected'}
    scoped = SectionTargetInput(
        data.samples_uvd[inside], deepcopy(data.context) | {'upstream_section_target_roi': scope},
        data.source_indices[inside] if data.source_indices is not None else None,
        data.points_global[inside] if data.points_global is not None else None)
    try:
        analysis.target = target_analysis_from_input(scoped, options)
    except SectionLayerError as exc:
        public.update(blocked_stage='target_analysis', reason=str(exc))
        return analysis
    target = analysis.target
    public['target_analysis'] = target.public
    public['point_accounting'].update(target_classified_point_count=len(inside),
                                      target_unclassified_inside_point_count=0)
    for candidate in target.public['candidate_targets']:
        ids = inside[target.target_source_indices[candidate['target_id']]]
        guard = candidate_roi_guard(roi, ids)
        guard.update(target_id=candidate['target_id'], candidate_fingerprint=candidate['candidate_fingerprint'],
                     target_usable=candidate['usable'],
                     eligible_for_downstream=bool(candidate['usable'] and guard['roi_guard_clear']))
        public['candidate_guards'].append(guard)
    auto = target.public['auto_selected_target_id']
    if auto is not None:
        guard = next(g for g in public['candidate_guards'] if g['target_id'] == auto)
        if guard['roi_guard_clear']:
            public['status'] = 'ready'
        else:
            public.update(blocked_stage='roi_truncation_guard', reason='The automatic target touches the fixed ROI edge guard')
    elif any(g['eligible_for_downstream'] for g in public['candidate_guards']):
        public.update(status='selection_required', reason='Explicit target choice remains required inside this ROI')
    else:
        public.update(blocked_stage='target_selection', reason='No supported guard-clear target; explicit IDs cannot override unsafe evidence')
    return analysis


def reconstruct_roi(analysis: ROIAnalysis, args: dict) -> dict:
    public = analysis.public
    counts = public['point_accounting']
    n, inside = counts['input_point_count'], counts['inside_roi_point_count']
    accounting = dict(input_point_count=n, inside_roi_point_count=inside,
                      outside_roi_point_count=counts['outside_roi_point_count'],
                      selected_target_point_count=0, selected_layer_point_count=0,
                      unselected_inside_roi_point_count=inside, unselected_within_target_point_count=0,
                      total_unselected_point_count=n)
    result = dict(type='section_target_roi_profile', version=VERSION, state='inferred_candidate',
                  status='blocked', roi_analysis=public, point_accounting=accounting,
                  raw_points_returned=False, scene_mutations_requested=False,
                  manufacturing_intent_confirmed=False, user_accepted=False)
    target = analysis.target
    if target is None:
        result.update(blocked_stage=public['blocked_stage'], reason=public['reason'])
        return result
    # Validate even unusable selections before testing the separate guard. A report
    # fingerprint (ROI/diagnostic) cannot substitute for a bound candidate token.
    subset = select_section_target(target, target_id=args.get('target_id'),
                                   expected_target_fingerprint=args.get('expected_target_fingerprint'))
    selected = args.get('target_id') or target.public['auto_selected_target_id']
    if selected is not None:
        guard = next(g for g in public['candidate_guards'] if g['target_id'] == selected)
        if not guard['roi_guard_clear']:
            result.update(blocked_stage='roi_truncation_guard',
                          reason='Selected target touches the fixed one-cell ROI edge guard; explicit selection cannot override possible truncation',
                          refused_target_id=selected)
            return result
    downstream = reconstruct_target(target, args)
    # Keep the accepted target analysis once, in roi_analysis, rather than duplicate it.
    result['target_result'] = {k: v for k, v in downstream.items() if k != 'target_analysis'}
    result['status'] = downstream['status']
    for key in ('blocked_stage', 'reason'):
        if key in downstream:
            result[key] = downstream[key]
    target_count = len(subset) if subset is not None else 0
    layer_count = downstream.get('point_accounting', {}).get('selected_layer_point_count', 0)
    accounting.update(selected_target_point_count=target_count, selected_layer_point_count=layer_count,
                      unselected_inside_roi_point_count=inside - target_count,
                      unselected_within_target_point_count=target_count - layer_count,
                      total_unselected_point_count=n - layer_count)
    return result


def run_roi_workflow(args: dict, *, live: bool = False, reconstruct: bool = False,
                     request: Callable[..., Any] | None = None) -> dict:
    base, options, bounds, indices = _request(args, live, reconstruct)
    data = live_target_input(base, options, request) if live else _snapshot_input(base, options, indices)
    analysis = analyze_roi_input(data, bounds, options)
    return reconstruct_roi(analysis, base) if reconstruct else analysis.public
