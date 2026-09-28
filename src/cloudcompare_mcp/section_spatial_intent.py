"""Deliberate boundary anchors in an explicit frame, not ROI/feature discovery.

This module has no native I/O and never runs a target or reconstruction solver.
Fingerprints describe observed evidence; they are not authenticated scene epochs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from numbers import Real
from typing import Any

import numpy as np

from .section_layer_workflow import compact_copy, text_field, vector3
from .section_layers import SectionLayerError, canonical_sha256, integer, positive, precision_floor
from .section_target_roi import validate_roi
from .section_target_workflow import SectionTargetInput

VERSION = '0.15.7'
CONTRACT = 'explicit-picked-section-roi-v1'
MAX_ANCHORS = 32
GEOMETRY_KEYS = ('entity_id', 'point_index', 'entity_name', 'position_global',
                 'position_native_local', 'global_shift', 'global_scale')


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def margin_value(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
        raise SectionLayerError('margin must be an explicit finite nonnegative native-unit number')
    return float(value)


def pick_indexes(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= MAX_ANCHORS:
        raise SectionLayerError(f'pick_indices requires 2..{MAX_ANCHORS} explicit boundary anchors')
    result = [integer(i, 'pick_index', 0, 4095) for i in value]
    if len(set(result)) != len(result):
        raise SectionLayerError('Duplicate pick_indices are not independent boundary anchors')
    return sorted(result)  # Selection order has no frame-construction semantics.


def selected_picks(status: Any, indexes: list[int], cloud_id: int) -> tuple[list[dict], str]:
    if not isinstance(status, dict) or status.get('active') is not False:
        raise SectionLayerError('Stop/freeze picking before declaring section ROI intent')
    records = status.get('picks')
    if not isinstance(records, list) or not 2 <= len(records) <= 4096:
        raise SectionLayerError('pick_state requires a bounded captured picks list')
    count = integer(status.get('pick_count'), 'pick_count', 2, 4096)
    if count != len(records):
        raise SectionLayerError('pick_count does not match captured picks')
    state = compact_copy(status, 'pick_state', 262144)
    # The native allowed-ID set has no ordering semantics.
    if 'allowed_entity_ids' in state:
        allowed = state['allowed_entity_ids']
        if not isinstance(allowed, list):
            raise SectionLayerError('allowed_entity_ids must be an array')
        state['allowed_entity_ids'] = sorted(integer(i, 'allowed_entity_id', 1, 2**32 - 1) for i in allowed)
    selected = []
    for index in indexes:
        if index >= count or not isinstance(records[index], dict):
            raise SectionLayerError('Selected captured pick is missing or malformed')
        record = records[index]
        if integer(record.get('pick_index'), 'captured pick_index', 0, 4095) != index:
            raise SectionLayerError('Captured pick identity does not match its session index')
        if record.get('entity_kind') != 'point_cloud' or record.get('entity_center') is not False:
            raise SectionLayerError('Boundary anchors must be actual standalone-cloud point picks, not mesh/center picks')
        if integer(record.get('entity_id'), 'pick.entity_id', 1, 2**32 - 1) != cloud_id:
            raise SectionLayerError('Mixed-source or wrong-cloud boundary anchors are refused')
        point = integer(record.get('point_index'), 'pick.point_index', 0, 2**32 - 1)
        if integer(record.get('item_index'), 'pick.item_index', 0, 2**32 - 1) != point:
            raise SectionLayerError('Captured item_index must identify the picked source point')
        text_field(record.get('entity_name'), 'pick.entity_name')
        for key in ('position_global', 'position_native_local', 'global_shift'):
            vector3(record.get(key), f'pick.{key}')
        positive(record.get('global_scale'), 'pick.global_scale')
        selected.append(compact_copy(record, 'selected pick', 8192))
    if len({r['point_index'] for r in selected}) != len(selected):
        raise SectionLayerError('Duplicate source points cannot supply distinct boundary anchors')
    if len({tuple(r['position_global']) for r in selected}) != len(selected):
        raise SectionLayerError('Duplicate picked coordinates cannot supply distinct boundary anchors')
    return selected, fingerprint(state)


def verify_current_pick(pick: dict, current: Any) -> str:
    """Detect stale cached picks with an independent existing point-info read."""
    if not isinstance(current, dict):
        raise SectionLayerError('Current source point-info must be an object')
    integer(current.get('entity_id'), 'current.entity_id', 1, 2**32 - 1)
    integer(current.get('point_index'), 'current.point_index', 0, 2**32 - 1)
    for key in ('position_global', 'position_native_local', 'global_shift'):
        vector3(current.get(key), f'current.{key}')
    positive(current.get('global_scale'), 'current.global_scale')
    for key in GEOMETRY_KEYS:
        if current.get(key) != pick.get(key):
            raise SectionLayerError(f'Stale captured pick: current source {key} changed; recapture deliberately')
    return fingerprint(compact_copy(current, 'current anchor point-info', 8192))


def derive_intent(data: SectionTargetInput, status: dict, indexes: list[int], *,
                  margin: float, frame_provenance: dict, target_parameters: dict) -> dict:
    """Return compact intent bound to verified acquisition, without ROI analysis."""
    margin = margin_value(margin)
    indexes = pick_indexes(indexes)
    if not isinstance(frame_provenance, dict) or not frame_provenance:
        raise SectionLayerError('frame_provenance must explicitly describe the declared frame source')
    provenance = compact_copy(frame_provenance, 'frame_provenance', 2048)
    source, frame = data.context['source'], data.context['section_frame']
    cloud_id = integer(source.get('cloud_id'), 'source.cloud_id', 1, 2**32 - 1)
    text_field(frame.get('frame_id'), 'frame_id', 128)
    origin = vector3(frame.get('origin_global'), 'frame.origin_global')
    basis = np.asarray([vector3(frame.get(k), f'frame.{k}') for k in ('basis_u', 'basis_v', 'normal')])
    if not np.allclose(basis @ basis.T, np.eye(3), atol=1e-8, rtol=0) or np.linalg.det(basis) < 0:
        raise SectionLayerError('Explicit section frame must be orthonormal and right-handed')
    shift = vector3(source.get('global_shift'), 'source.global_shift')
    scale = positive(source.get('global_scale'), 'source.global_scale')
    picks, state_hash = selected_picks(status, indexes, cloud_id)
    for pick in picks:
        if pick['global_shift'] != shift or pick['global_scale'] != scale:
            raise SectionLayerError('Picked and acquired source global bookkeeping differs; no conversion is applied')
        if 'cloud_name' in source and pick['entity_name'] != source['cloud_name']:
            raise SectionLayerError('Picked and acquired source names differ; source context is stale')
    xyz = np.asarray([p['position_global'] for p in picks], dtype=np.float64)
    floor = precision_floor(np.vstack([xyz, origin]))
    with np.errstate(over='ignore', invalid='ignore'):
        uvd = (xyz - origin) @ basis.T  # Global positions are already global. No shift/scale application.
    if not np.isfinite(uvd).all():
        raise SectionLayerError('Anchor projection exceeds finite coordinate range')
    raw_min, raw_max = uvd[:, :2].min(axis=0), uvd[:, :2].max(axis=0)
    spans = raw_max - raw_min
    if not np.isfinite(spans).all() or np.any(spans <= floor):
        raise SectionLayerError('Boundary anchors need positive U and V spans above acquired-coordinate precision; margin cannot repair a degenerate intent')
    bounds = validate_roi(dict(u_min=float(raw_min[0] - margin), u_max=float(raw_max[0] + margin),
                               v_min=float(raw_min[1] - margin), v_max=float(raw_max[1] + margin)))
    # Cross-check known in-slab anchors without requiring boundary anchors to be in
    # the slab. Their depth is evidence, never a new depth-crop selector.
    if data.source_indices is not None:
        lookup = {int(index): row for row, index in enumerate(data.source_indices)}
        for pick, projected in zip(picks, uvd):
            row = lookup.get(pick['point_index'])
            if row is not None:
                if data.points_global is not None:
                    consistent = np.array_equal(data.points_global[row], pick['position_global'])
                else:
                    consistent = np.all(np.abs(data.samples_uvd[row] - projected) <= floor)
                if not consistent:
                    raise SectionLayerError('Captured anchor disagrees with acquired source-index geometry')
    context = deepcopy(data.context)
    mode = 'live' if context['live_connection_used'] else 'snapshot'
    payload = dict(contract=CONTRACT, context_mode=mode, context=context,
                   complete_slab_geometry_sha256=canonical_sha256(data.samples_uvd),
                   pick_state_sha256=state_hash, selected_pick_indices=indexes,
                   frame_provenance=provenance, margin=margin, roi=bounds,
                   target_parameters=target_parameters)
    intent_hash = fingerprint(payload)
    anchors = []
    for pick, projected in zip(picks, uvd):
        anchors.append({k: deepcopy(pick[k]) for k in ('pick_index', 'point_index', 'position_global',
                                                      'position_native_local')} |
                       dict(record_sha256=fingerprint(pick), uv=projected[:2].tolist(),
                            signed_depth=float(projected[2])))
    return dict(type='section_spatial_intent', version=VERSION, contract=CONTRACT,
                status='ready', context_mode=mode, intent_fingerprint=intent_hash,
                intent_fingerprint_authorizes_reconstruction=False, source=deepcopy(source),
                section_frame=deepcopy(frame), frame_provenance=provenance,
                pick_state_sha256=state_hash, pick_indices=indexes, anchor_count=len(picks),
                anchors=anchors, anchor_role='deliberate_roi_boundary_not_target_points',
                selection_order_semantics='unordered_anchor_set_with_captured_session_identities',
                margin=margin, roi=bounds, span_u=bounds['u_max'] - bounds['u_min'],
                span_v=bounds['v_max'] - bounds['v_min'],
                anchor_depth_range=[float(uvd[:, 2].min()), float(uvd[:, 2].max())],
                anchor_depth_used_for_cropping=False, half_open=True,
                complete_slab_geometry_sha256=payload['complete_slab_geometry_sha256'],
                source_coordinate_precision_floor=floor, shift_scale_reapplied=False,
                target_parameters=deepcopy(target_parameters),
                freshness_scope='observed_complete_slab_and_selected_anchors_not_whole_source_or_atomic_scene',
                raw_cloud_points_returned=False, scene_mutations_requested=False,
                manufacturing_intent_confirmed=False, user_accepted=False,
                warnings=['Upper ROI boundaries exclude points exactly on them; no hidden epsilon or padding.',
                          'Use picked-ROI wrappers to retain intent binding; numerical 0.15.6 calls alone do not prove pick provenance.',
                          'Snapshot freshness is caller asserted; native live calls have no scene/session generation counter.'])


def bind_intent(data: SectionTargetInput, intent: dict) -> None:
    """Bind only compact context; full anchor evidence remains in the parent report."""
    data.context['upstream_section_spatial_intent'] = {
        k: deepcopy(intent[k]) for k in ('contract', 'intent_fingerprint', 'context_mode',
                                        'pick_state_sha256', 'pick_indices', 'margin', 'roi')}
