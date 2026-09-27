"""Layer workflow contracts independent of MCP transport and the GUI server.

Live calls use one bounded read-only region query. No cache, native mutation,
filtered acquisition, or post-hoc layer selection by reconstruction quality.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from numbers import Real
from typing import Any, Callable

import numpy as np

from .feature_fit import project_points_to_section
from .section_boundary import (
    SectionBoundaryError, extract_section_boundary_evidence_2d,
    reconstruct_filled_section_profile_2d,
)
from .section_layers import (
    SectionLayerAnalysis, SectionLayerError, analyze_section_layers_uvd,
    canonical_sha256, integer, positive, precision_floor, samples_array,
    select_section_layer, validate_options,
)

LAYER_REQUIRED = ('uv_cell_size', 'depth_separation', 'max_layer_thickness',
                  'max_neighbor_depth_step')
LAYER_DEFAULTS = dict(min_cell_points=3, min_layer_cells=4, max_points=20000,
                      max_cells=20000, max_components=16)
PROFILE_FLOATS = {
    'cell_size': (None, 0, None), 'max_edge_length': (None, 0, None),
    'fit_tolerance': (None, 0, None), 'angular_tolerance_degrees': (1.0, 0, 45),
    'minimum_arc_angle_degrees': (12.0, 1, 180),
}
PROFILE_INTS = {
    'min_cell_support': (1, 1, 20000), 'min_component_cells': (2, 1, 100000),
    'max_cells': (100000, 1, 100000), 'max_boundary_points': (2048, 8, 2048),
    'minimum_loop_points': (6, 3, 2048), 'max_loops': (16, 1, 32),
    'max_segments_per_loop': (64, 1, 128),
}


def object_fields(value: Any, label: str, allowed, required=()) -> dict:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise SectionLayerError(f'{label} must be an object with string keys')
    missing, extra = set(required) - value.keys(), value.keys() - set(allowed)
    if missing or extra:
        raise SectionLayerError(f'{label}: missing {sorted(missing)}, unknown {sorted(extra)}')
    return value


def compact_copy(value: Any, label: str, max_bytes: int = 4096) -> Any:
    try:
        text = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(text.encode()) > max_bytes:
            raise SectionLayerError(f'{label} exceeds {max_bytes}-byte metadata budget')
        return json.loads(text)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SectionLayerError(f'{label} must be bounded finite JSON: {exc}') from exc


def vector3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SectionLayerError(f'{label} must contain three finite numbers')
    if any(isinstance(x, bool) or not isinstance(x, Real) for x in value):
        raise SectionLayerError(f'{label} must contain three finite numbers')
    result = [float(x) for x in value]
    if not all(math.isfinite(x) for x in result):
        raise SectionLayerError(f'{label} must contain three finite numbers')
    return result


def text_field(value: Any, label: str, max_length: int = 512) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= max_length:
        raise SectionLayerError(f'{label} must be a nonempty string of at most {max_length} characters')
    return value


def layer_options(value: Any) -> dict:
    params = object_fields(value, 'layer_parameters', (*LAYER_REQUIRED, *LAYER_DEFAULTS), LAYER_REQUIRED)
    return validate_options(**(LAYER_DEFAULTS | params))


def profile_options(value: Any) -> dict:
    params = object_fields(value, 'profile_parameters',
                           (*PROFILE_FLOATS, *PROFILE_INTS, 'require_grid_stability'),
                           ('cell_size', 'max_edge_length', 'fit_tolerance'))
    result = {}
    for key, (default, low, high) in PROFILE_FLOATS.items():
        number = positive(params.get(key, default), key)
        if number < low or (high is not None and number > high):
            raise SectionLayerError(f'{key} is outside the supported bounds')
        result[key] = number
    for key, (default, low, high) in PROFILE_INTS.items():
        result[key] = integer(params.get(key, default), key, low, high)
    stable = params.get('require_grid_stability', True)
    if not isinstance(stable, bool):
        raise SectionLayerError('require_grid_stability must be a boolean')
    result['require_grid_stability'] = stable
    return result


def validate_request(args: Any, *, live: bool, reconstruct: bool) -> dict:
    required = ('cloud_id', 'origin', 'normal', 'half_thickness', 'layer_parameters') if live else ('section', 'layer_parameters')
    allowed = (*required, 'query_timeout_seconds') if live else required
    if reconstruct:
        required = (*required, 'profile_parameters')
        allowed = (*allowed, 'profile_parameters', 'layer_id', 'expected_analysis_fingerprint')
    object_fields(args, 'arguments', allowed, required)
    options = layer_options(args['layer_parameters'])
    if reconstruct:
        profile_options(args['profile_parameters'])
        for key in ('layer_id', 'expected_analysis_fingerprint'):
            if key in args:
                text_field(args[key], key, 128)
    return options


def snapshot_context(section: dict) -> dict:
    frame = object_fields(section.get('frame', {}), 'frame',
                          ('frame_id', 'origin_global', 'basis_u', 'basis_v', 'normal'))
    frame = deepcopy(frame)
    vectors = ('origin_global', 'basis_u', 'basis_v', 'normal')
    if any(k in frame for k in vectors):
        if not all(k in frame for k in vectors):
            raise SectionLayerError('A geometric frame requires origin_global, basis_u, basis_v and normal')
        for key in vectors:
            frame[key] = vector3(frame[key], f'frame.{key}')
        basis = np.asarray([frame[k] for k in ('basis_u', 'basis_v', 'normal')])
        with np.errstate(over='ignore', invalid='ignore'):
            valid = np.allclose(basis @ basis.T, np.eye(3), atol=1e-8, rtol=0)
        if not valid or np.linalg.det(basis) < 0:
            raise SectionLayerError('Section basis must be orthonormal and right-handed')
    if 'frame_id' in frame:
        text_field(frame['frame_id'], 'frame_id', 128)
    source = object_fields(section.get('source', {}), 'source',
                           ('cloud_id', 'cloud_name', 'global_shift', 'global_scale'))
    source = deepcopy(source)
    if 'cloud_id' in source:
        integer(source['cloud_id'], 'source.cloud_id', 1, 2**32 - 1)
    if 'cloud_name' in source:
        text_field(source['cloud_name'], 'source.cloud_name')
    if 'global_shift' in source:
        source['global_shift'] = vector3(source['global_shift'], 'source.global_shift')
    if 'global_scale' in source:
        source['global_scale'] = positive(source['global_scale'], 'source.global_scale')
    provenance = section.get('provenance', {})
    if not isinstance(provenance, dict):
        raise SectionLayerError('provenance must be a compact object')
    return {'section_frame': frame, 'source': source,
            'provenance': compact_copy(provenance, 'provenance'),
            'live_connection_used': False, 'scene_mutations_requested': False,
            'acquisition': {'complete': True, 'verification': 'caller_asserted_snapshot'}}


def bind_context(analysis: SectionLayerAnalysis, context: dict) -> SectionLayerAnalysis:
    # Selection tokens bind geometry AND the frame/source/acquisition, not a depth sign.
    context = compact_copy(context, 'section context', 16384)
    payload = {'numerical_fingerprint': analysis.public['analysis_fingerprint'], 'context': context}
    analysis.public['analysis_fingerprint'] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    analysis.public.update(context)
    analysis.public['coordinate_space'] = 'section_uv_depth'
    analysis.public['units'] = 'native'
    return analysis


def snapshot_analysis(args: dict, options: dict) -> SectionLayerAnalysis:
    section = object_fields(args['section'], 'section',
                            ('coordinate_space', 'units', 'acquisition_complete', 'samples_uvd',
                             'frame', 'source', 'provenance'),
                            ('coordinate_space', 'units', 'acquisition_complete', 'samples_uvd'))
    if section['coordinate_space'] != 'section_uv_depth' or section['units'] != 'native':
        raise SectionLayerError('section requires coordinate_space=section_uv_depth and units=native')
    if section['acquisition_complete'] is not True:
        raise SectionLayerError('Layer analysis requires acquisition_complete=true; no sampled topology proof')
    context = snapshot_context(section)
    result = analyze_section_layers_uvd(section['samples_uvd'], **options)
    return bind_context(result, context)


def live_analysis(args: dict, options: dict, request: Callable[..., Any] | None) -> SectionLayerAnalysis:
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
        raise SectionLayerError('Layer analysis requires complete slab acquisition: matched == returned and truncated=false')
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
    for key in LAYER_REQUIRED:
        if options[key] < source_floor:
            raise SectionLayerError(f'{key} is below source global-coordinate precision floor {source_floor:.17g}')
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
    analysis = analyze_section_layers_uvd(uvd, **options)
    for layer in analysis.public['candidate_layers']:
        subset = analysis.layer_source_indices[layer['layer_id']]
        layer['source_point_indices_sha256'] = hashlib.sha256(
            np.sort(indices[subset]).astype('<u8').tobytes()).hexdigest()
        layer['source_global_geometry_sha256'] = canonical_sha256(xyz[subset])
    return bind_context(analysis, context)


def reconstruct_selected(analysis: SectionLayerAnalysis, args: dict) -> dict:
    params = profile_options(args['profile_parameters'])
    subset = select_section_layer(analysis, layer_id=args.get('layer_id'),
                                  expected_analysis_fingerprint=args.get('expected_analysis_fingerprint'))
    result = {'type': 'section_layer_profile', 'version': '0.15.3', 'state': 'inferred_candidate',
              'layer_analysis': analysis.public, 'status': 'blocked',
              'manufacturing_intent_confirmed': False, 'user_accepted': False,
              'scene_mutations_requested': False, 'raw_points_returned': False}
    if subset is None:
        result['blocked_stage'] = 'layer_selection'
        result['reason'] = ('Unusable layer evidence; isolate the source more carefully'
                            if analysis.public['status'] == 'blocked' else
                            'Multiple credible layers require layer_id and exact expected_analysis_fingerprint')
        return result
    selected = args.get('layer_id') or analysis.public['auto_selected_layer_id']
    result['selection'] = {'layer_id': selected,
                           'mode': 'explicit_caller_choice' if args.get('layer_id') else 'single_usable_component',
                           'selected_point_count': len(subset),
                           'unselected_point_count': len(analysis.samples_uvd) - len(subset)}
    # Keep accepted occupancy, topology and fitting entirely unchanged.
    uv = analysis.samples_uvd[subset, :2]
    try:
        result['profile'] = reconstruct_filled_section_profile_2d(uv, **params)
        result['status'] = 'candidate'
    except SectionBoundaryError as exc:
        result['blocked_stage'] = 'boundary_or_topology'
        result['reason'] = str(exc)
        # Preserve available occupancy diagnostics when the topology handoff refuses.
        try:
            extraction_keys = ('cell_size', 'min_cell_support', 'min_component_cells',
                               'max_cells', 'max_boundary_points')
            result['boundary_evidence'] = extract_section_boundary_evidence_2d(
                uv, **{k: params[k] for k in extraction_keys}).public
        except SectionBoundaryError as boundary_exc:
            result['boundary_error'] = str(boundary_exc)
    return result


def run_layer_workflow(args: dict, *, live: bool = False, reconstruct: bool = False,
                       request: Callable[..., Any] | None = None) -> dict:
    """Validated workflow boundary; exceptions remain available to MCP or Python callers."""
    options = validate_request(args, live=live, reconstruct=reconstruct)
    analysis = live_analysis(args, options, request) if live else snapshot_analysis(args, options)
    return reconstruct_selected(analysis, args) if reconstruct else analysis.public
