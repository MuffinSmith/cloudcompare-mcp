"""Revalidate intent, then compose unchanged accepted 0.15.6 ROI workflows."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .live import _config as bridge_config
from .section_layer_workflow import compact_copy, object_fields, text_field, vector3
from .section_layers import SectionLayerError, integer, positive
from .section_spatial_intent import (
    VERSION, bind_intent, derive_intent, margin_value, pick_indexes,
    selected_picks, verify_current_pick,
)
from .section_target_roi_workflow import _snapshot_input, analyze_roi_input, reconstruct_roi
from .section_target_workflow import live_target_input, validate_request


def prepare(args: Any, *, live: bool, action: str) -> tuple[dict, dict, list[int], float]:
    if action not in ('derive', 'analyze', 'reconstruct'):
        raise SectionLayerError('Unknown picked ROI action')
    required = ('pick_indices', 'margin', 'frame_provenance', 'target_parameters')
    geometry = ('cloud_id', 'origin', 'normal', 'half_thickness', 'frame_id') if live else ('section', 'pick_state')
    required = (*required, *geometry)
    allowed = (*required, 'query_timeout_seconds') if live else required
    if action != 'derive':
        required = (*required, 'expected_intent_fingerprint')
        allowed = (*allowed, 'expected_intent_fingerprint')
    if action == 'reconstruct':
        required = (*required, 'layer_parameters', 'profile_parameters')
        allowed = (*allowed, 'layer_parameters', 'profile_parameters', 'target_id',
                   'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint')
    object_fields(args, 'arguments', allowed, required)
    indexes, margin = pick_indexes(args['pick_indices']), margin_value(args['margin'])
    if not isinstance(args['frame_provenance'], dict) or not args['frame_provenance']:
        raise SectionLayerError('frame_provenance must explicitly describe the declared frame source')
    compact_copy(args['frame_provenance'], 'frame_provenance', 2048)
    if action != 'derive':
        token = text_field(args['expected_intent_fingerprint'], 'expected_intent_fingerprint', 64)
        if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise SectionLayerError('expected_intent_fingerprint must be a current SHA256 intent fingerprint')
    bridge_fields = {'pick_indices', 'margin', 'frame_provenance', 'frame_id', 'pick_state', 'expected_intent_fingerprint'}
    base = deepcopy({k: v for k, v in args.items() if k not in bridge_fields})
    # Accepted ROI source-index validation is reused without changing its solver.
    indices = None
    if not live and isinstance(base.get('section'), dict) and 'source_point_indices' in base['section']:
        indices = base['section'].pop('source_point_indices')
        if not isinstance(indices, (list, tuple)):
            raise SectionLayerError('source_point_indices must be an array')
    options = validate_request(base, live=live, reconstruct=action == 'reconstruct')
    if live:
        integer(base['cloud_id'], 'cloud_id', 1, 2**32 - 1)
        vector3(base['origin'], 'origin')
        if not any(vector3(base['normal'], 'normal')):
            raise SectionLayerError('normal has zero length')
        margin_value(base['half_thickness'])
        timeout = positive(base.get('query_timeout_seconds', 30), 'query_timeout_seconds')
        if timeout > 120:
            raise SectionLayerError('query_timeout_seconds must not exceed 120')
        text_field(args['frame_id'], 'frame_id', 128)
    else:
        # Stored separately, never forwarded as a new field to accepted validators.
        base['_intent_source_indices'] = indices
    return base, options, indexes, margin


def run_picked_roi_workflow(args: dict, *, live: bool = False, action: str = 'derive',
                            request: Callable[..., Any] | None = None) -> dict:
    base, options, indexes, margin = prepare(args, live=live, action=action)
    if live:
        if request is None:
            from .live import request
        host, port, _, _ = bridge_config()
        endpoint = {'host': host, 'port': port}
        timeout = base.get('query_timeout_seconds', 30)
        status = request('metrology.pick.status', {}, timeout=timeout)
        picks, before_hash = selected_picks(status, indexes, base['cloud_id'])
        current = {}
        for pick in picks:
            info = request('metrology.point_info', {'entity_id': base['cloud_id'],
                                                  'point_index': pick['point_index']}, timeout=timeout)
            current[str(pick['point_index'])] = verify_current_pick(pick, info)
        data = live_target_input(base, options, request)
        after = request('metrology.pick.status', {}, timeout=timeout)
        _, after_hash = selected_picks(after, indexes, base['cloud_id'])
        if before_hash != after_hash:
            raise SectionLayerError('Captured pick state changed during acquisition; freeze and derive fresh intent')
        host_after, port_after, _, _ = bridge_config()
        if endpoint != {'host': host_after, 'port': port_after}:
            raise SectionLayerError('Configured live bridge endpoint changed during acquisition')
        data.context['configured_bridge_endpoint'] = endpoint
        data.context['section_frame']['frame_id'] = args['frame_id']
        data.context['current_anchor_point_info_sha256'] = current
        data.context['pick_freshness_verification'] = 'stopped_status_bookends_and_current_anchor_point_info_not_atomic_scene'
    else:
        indices = base.pop('_intent_source_indices')
        data = _snapshot_input(base, options, indices)
        status = args['pick_state']
    intent = derive_intent(data, status, indexes, margin=margin,
                           frame_provenance=args['frame_provenance'], target_parameters=options)
    intent['numerical_roi_request_fields'] = {'roi': deepcopy(intent['roi']), 'target_parameters': deepcopy(options)}
    if live:
        intent['configured_bridge_endpoint'] = deepcopy(data.context['configured_bridge_endpoint'])
        intent['numerical_roi_request_fields'].update({k: deepcopy(base[k]) for k in
                                                      ('cloud_id', 'origin', 'normal', 'half_thickness')})
    else:
        intent['numerical_request_requires_original_section'] = True
    intent['native_call_accounting'] = {'region_queries': 1 if live else 0,
                                        'point_info_reads': len(indexes) if live else 0,
                                        'pick_status_reads': 2 if live else 0,
                                        'scope': 'calls_requested_by_this_wrapper_not_independent_host_instrumentation'}
    if action == 'derive':
        return intent
    if args['expected_intent_fingerprint'] != intent['intent_fingerprint']:
        raise SectionLayerError('Stale spatial intent: picks, source/acquisition, frame, margin or target parameters changed')
    bind_intent(data, intent)
    analysis = analyze_roi_input(data, intent['roi'], options)
    result = reconstruct_roi(analysis, base) if action == 'reconstruct' else analysis.public
    report = dict(type='picked_section_target_roi_' + ('profile' if action == 'reconstruct' else 'analysis'),
                  version=VERSION, status=result['status'], spatial_intent=intent, roi_result=result,
                  scene_mutations_requested=False, raw_cloud_points_returned=False,
                  manufacturing_intent_confirmed=False, user_accepted=False)
    for key in ('blocked_stage', 'reason'):
        if key in result:
            report[key] = result[key]
    return report
