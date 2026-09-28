"""Read-only target -> accepted layer -> boundary/topology/profile workflow.

The acquisition verifier mirrors the accepted layer verifier without invoking layer
analysis before isolation. Shared validation/projection and accepted solvers are
imported, not forked. No cache, source mutation or filtered acquisition is used.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
from numbers import Real
from typing import Any, Callable

import numpy as np

from .feature_fit import project_points_to_section
from .section_layer_workflow import (
    LAYER_REQUIRED, bind_context, compact_copy, layer_options, object_fields,
    profile_options, reconstruct_selected, snapshot_context, text_field, vector3,
)
from .section_layers import (
    SectionLayerError, analyze_section_layers_uvd, canonical_sha256, integer,
    positive, precision_floor, samples_array,
)
from .section_targets import (
    DEFAULTS, REQUIRED, SectionTargetAnalysis, SectionTargetError,
    analyze_section_targets_uvd, refresh_candidate_fingerprints,
    select_section_target, validate_options,
)


@dataclass
class SectionTargetInput:
    """Verified complete input; arrays stay private until an explicit workflow scopes them."""

    samples_uvd: np.ndarray
    context: dict
    source_indices: np.ndarray | None = None
    points_global: np.ndarray | None = None


def target_options(value: Any) -> dict:
    params = object_fields(value, 'target_parameters', (*REQUIRED, *DEFAULTS), REQUIRED)
    return validate_options(**(DEFAULTS | params))


def validate_request(args: Any, *, live: bool, reconstruct: bool) -> dict:
    required = ('cloud_id', 'origin', 'normal', 'half_thickness', 'target_parameters') if live else ('section', 'target_parameters')
    allowed = (*required, 'query_timeout_seconds') if live else required
    if reconstruct:
        required = (*required, 'layer_parameters', 'profile_parameters')
        allowed = (*allowed, 'layer_parameters', 'profile_parameters', 'target_id',
                   'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint')
    object_fields(args, 'arguments', allowed, required)
    options = target_options(args['target_parameters'])
    if reconstruct:
        layer_options(args['layer_parameters'])
        profile_options(args['profile_parameters'])
        for key in ('target_id', 'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint'):
            if key in args:
                text_field(args[key], key, 128)
        for identifier, token in (('target_id', 'expected_target_fingerprint'), ('layer_id', 'expected_layer_fingerprint')):
            if (identifier in args) != (token in args):
                raise SectionTargetError(f'{identifier} and {token} must be supplied together')
    return options


def bind_target_context(analysis: SectionTargetAnalysis, context: dict) -> SectionTargetAnalysis:
    bind_context(analysis, context)
    refresh_candidate_fingerprints(analysis)
    return analysis


def snapshot_target_input(args: dict, options: dict) -> SectionTargetInput:
    section = object_fields(args['section'], 'section',
                            ('coordinate_space', 'units', 'acquisition_complete', 'samples_uvd',
                             'frame', 'source', 'provenance'),
                            ('coordinate_space', 'units', 'acquisition_complete', 'samples_uvd'))
    if section['coordinate_space'] != 'section_uv_depth' or section['units'] != 'native':
        raise SectionTargetError('section requires coordinate_space=section_uv_depth and units=native')
    if section['acquisition_complete'] is not True:
        raise SectionTargetError('Target analysis requires acquisition_complete=true; no sampled topology proof')
    context = snapshot_context(section)
    return SectionTargetInput(samples_array(section['samples_uvd'], options['max_points']), context)


def live_target_input(args: dict, options: dict, request: Callable[..., Any] | None) -> SectionTargetInput:
    cloud_id = integer(args['cloud_id'], 'cloud_id', 1, 2**32 - 1)
    origin = vector3(args['origin'], 'origin')
    normal = np.asarray(vector3(args['normal'], 'normal'))
    magnitude = float(np.abs(normal).max())
    if magnitude == 0:
        raise SectionLayerError('normal has zero length')
    normal = normal / magnitude
    normal = normal / np.linalg.norm(normal)
    half = args['half_thickness']
    if isinstance(half, bool) or not isinstance(half, Real) or not math.isfinite(half) or half < 0:
        raise SectionLayerError('half_thickness must be finite and non-negative')
    timeout = positive(args.get('query_timeout_seconds', 30.0), 'query_timeout_seconds')
    if timeout > 120:
        raise SectionLayerError('query_timeout_seconds must not exceed 120')
    if request is None:
        from .live import request
    native = request('cloud.region_query', {
        'cloud_id': cloud_id, 'coordinate_space': 'global', 'max_points': options['max_points'],
        'region': {'type': 'slab', 'origin': origin, 'normal': normal.tolist(), 'half_thickness': float(half)},
    }, timeout=timeout)
    if not isinstance(native, dict):
        raise SectionLayerError('Native region result must be an object')
    if native.get('coordinate_space') != 'global' or native.get('cloud_id') != cloud_id or isinstance(native.get('cloud_id'), bool):
        raise SectionLayerError('Native result must identify the requested cloud and global coordinates')
    matched = integer(native.get('matched_count'), 'matched_count', 3, options['max_points'])
    returned = integer(native.get('returned_count'), 'returned_count', 3, options['max_points'])
    if matched != returned or native.get('truncated') is not False:
        raise SectionLayerError('Target analysis requires complete slab acquisition: matched == returned and truncated=false')
    records = native.get('points')
    if not isinstance(records, list) or len(records) != returned:
        raise SectionLayerError('Native returned_count must match every returned record')
    if any(not isinstance(record, dict) for record in records):
        raise SectionLayerError('Native point records must be objects')
    indices = np.asarray([integer(record.get('point_index'), 'point_index', 0, 2**32 - 1)
                          for record in records], dtype=np.uint64)
    if len(np.unique(indices)) != returned:
        raise SectionLayerError('Duplicate native point_index values cannot prove complete acquisition')
    xyz = samples_array([record.get('position_global') for record in records], options['max_points'])
    shift = vector3(native.get('source_global_shift'), 'source_global_shift')
    scale = positive(native.get('source_global_scale'), 'source_global_scale')
    name = text_field(native.get('cloud_name'), 'cloud_name')
    source_floor = precision_floor(np.vstack([xyz, origin]))
    for key in ('uv_cell_size', 'depth_cell_size'):
        if options[key] * options['perturbation_fraction'] < source_floor:
            raise SectionLayerError(f'{key} is below source global-coordinate precision floor {source_floor:.17g}')
    if 'layer_parameters' in args:
        for key in LAYER_REQUIRED:
            if args['layer_parameters'][key] < source_floor:
                raise SectionTargetError(f'{key} is below source global-coordinate precision floor {source_floor:.17g}')
    if 'profile_parameters' in args:
        for key in ('cell_size', 'max_edge_length', 'fit_tolerance'):
            if args['profile_parameters'][key] < source_floor:
                raise SectionLayerError(f'{key} is below source global-coordinate precision floor {source_floor:.17g}')
    # No half-thickness filter here: silently filtering invalid records would erase evidence.
    projection = project_points_to_section(xyz, origin, normal.tolist())
    uvd = np.column_stack([projection['uv'], projection['signed_offsets']])
    if np.any(np.abs(uvd[:, 2]) > half + source_floor):
        raise SectionLayerError('Native returned points outside the requested slab; no records were discarded')
    order = np.argsort(indices)
    mapping = hashlib.sha256(indices[order].astype('<u8').tobytes() + xyz[order].astype('<f8').tobytes()).hexdigest()
    context = {
        'section_frame': {'origin_global': origin, 'normal': projection['normal'],
                          'basis_u': projection['basis_u'], 'basis_v': projection['basis_v'],
                          'normal_orientation_policy': projection['normal_orientation_policy'],
                          'half_thickness': float(half)},
        'source': {'cloud_id': cloud_id, 'cloud_name': name, 'global_shift': shift, 'global_scale': scale,
                   'global_geometry_sha256': canonical_sha256(xyz), 'point_mapping_sha256': mapping},
        'source_coordinate_bookkeeping': {'query_coordinate_space': 'global', 'global_shift': shift,
                                         'global_scale': scale, 'shift_scale_reapplied': False},
        'live_connection_used': True, 'scene_mutations_requested': False,
        'source_global_coordinate_precision_floor': source_floor,
        'acquisition': {'complete': True, 'verification': 'native_counts_and_unique_returned_indices',
                        'matched_count': matched, 'sampled_count': returned, 'sample_truncated': False,
                        'sample_strategy': compact_copy(native.get('sample_strategy'), 'sample_strategy', 128),
                        'source_integrity_coverage': 'not_independently_measured_by_this_tool'},
    }
    return SectionTargetInput(uvd, context, indices, xyz)


def target_analysis_from_input(data: SectionTargetInput, options: dict) -> SectionTargetAnalysis:
    """Run the unchanged accepted solver after acquisition (or explicit ROI scoping)."""
    analysis = analyze_section_targets_uvd(data.samples_uvd, **options)
    if data.source_indices is not None:
        for candidate in analysis.public['candidate_targets']:
            subset = analysis.target_source_indices[candidate['target_id']]
            candidate['source_point_indices_sha256'] = hashlib.sha256(
                np.sort(data.source_indices[subset]).astype('<u8').tobytes()).hexdigest()
            if data.points_global is not None:
                candidate['source_global_geometry_sha256'] = canonical_sha256(data.points_global[subset])
    return bind_target_context(analysis, data.context)


def snapshot_target_analysis(args: dict, options: dict) -> SectionTargetAnalysis:
    return target_analysis_from_input(snapshot_target_input(args, options), options)


def live_target_analysis(args: dict, options: dict, request: Callable[..., Any] | None) -> SectionTargetAnalysis:
    return target_analysis_from_input(live_target_input(args, options, request), options)



def reconstruct_target(analysis: SectionTargetAnalysis, args: dict) -> dict:
    subset = select_section_target(analysis, target_id=args.get('target_id'),
                                   expected_target_fingerprint=args.get('expected_target_fingerprint'))
    result = {'type': 'section_target_profile', 'version': '0.15.4', 'state': 'inferred_candidate',
              'target_analysis': analysis.public, 'status': 'blocked',
              'raw_points_returned': False, 'scene_mutations_requested': False,
              'manufacturing_intent_confirmed': False, 'user_accepted': False}
    if subset is None:
        result.update(blocked_stage='target_selection',
                      reason='Select a usable explicit spatial target with its current candidate fingerprint; no largest-target or clutter-deletion fallback')
        return result
    selected = args.get('target_id') or analysis.public['auto_selected_target_id']
    candidate = next(c for c in analysis.public['candidate_targets'] if c['target_id'] == selected)
    selection = {'target_id': selected, 'candidate_fingerprint': candidate['candidate_fingerprint'],
                 'mode': 'explicit_caller_choice' if args.get('target_id') else 'single_usable_target',
                 'selected_point_count': len(subset), 'unselected_point_count': len(analysis.samples_uvd) - len(subset),
                 'unselected_unsupported_or_ambiguous_point_count': analysis.public['point_accounting']['unsupported_or_ambiguous_point_count'],
                 'source_geometry_sha256': candidate['source_geometry_sha256']}
    result['target_selection'] = selection
    # The selected target contains every one of its depth samples; layer safety is unchanged.
    try:
        layer = analyze_section_layers_uvd(analysis.samples_uvd[subset], **layer_options(args['layer_parameters']))
    except SectionLayerError as exc:
        result.update(blocked_stage='layer_analysis', reason=str(exc))
        return result
    context = {key: deepcopy(analysis.public[key]) for key in (
        'section_frame', 'source', 'acquisition', 'live_connection_used', 'scene_mutations_requested')}
    for key in ('provenance', 'source_coordinate_bookkeeping', 'source_global_coordinate_precision_floor'):
        if key in analysis.public:
            context[key] = deepcopy(analysis.public[key])
    context['upstream_target_selection'] = selection
    context['upstream_target_analysis_fingerprint'] = analysis.public['analysis_fingerprint']
    context['layer_input_scope'] = 'complete selected spatial target; parent acquisition and unselected counts retained'
    bind_context(layer, context)
    layer_args = {'profile_parameters': args['profile_parameters']}
    if 'layer_id' in args:
        layer_args.update(layer_id=args['layer_id'], expected_analysis_fingerprint=args['expected_layer_fingerprint'])
    downstream = reconstruct_selected(layer, layer_args)
    result['layer_result'] = downstream
    result['status'] = downstream['status']
    if downstream['status'] == 'blocked':
        result['blocked_stage'] = downstream['blocked_stage']
        result['reason'] = downstream['reason']
    if 'selection' in downstream:
        count = downstream['selection']['selected_point_count']
        result['point_accounting'] = {'input_point_count': len(analysis.samples_uvd),
                                      'selected_target_point_count': len(subset),
                                      'selected_layer_point_count': count,
                                      'unselected_target_point_count': len(analysis.samples_uvd) - len(subset),
                                      'unselected_within_target_point_count': len(subset) - count,
                                      'total_unselected_point_count': len(analysis.samples_uvd) - count}
    return result


def run_target_workflow(args: dict, *, live: bool = False, reconstruct: bool = False,
                        request: Callable[..., Any] | None = None) -> dict:
    options = validate_request(args, live=live, reconstruct=reconstruct)
    analysis = live_target_analysis(args, options, request) if live else snapshot_target_analysis(args, options)
    return reconstruct_target(analysis, args) if reconstruct else analysis.public
