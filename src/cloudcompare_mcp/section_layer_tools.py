"""Compact MCP schemas/handlers for depth-aware section-layer evidence."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .feature_fit import FeatureFitError
from .live import LiveBridgeError
from .section_layer_workflow import (
    LAYER_DEFAULTS, LAYER_REQUIRED, PROFILE_FLOATS, PROFILE_INTS, run_layer_workflow,
)
from .section_layers import SectionLayerError

VEC3 = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3}
NAME = {'type': 'string', 'minLength': 1, 'maxLength': 512}
KINDS = {
    'analyze_section_layers': (False, False),
    'analyze_live_section_layers': (True, False),
    'reconstruct_section_layer_profile': (False, True),
    'reconstruct_live_section_layer_profile': (True, True),
}


def capabilities(*, live_available: bool = True) -> dict[str, Any]:
    return {'version': '0.15.3', 'snapshot_layer_analysis': True,
            'live_layer_analysis': bool(live_available), 'snapshot_layer_profile': True,
            'live_layer_profile': bool(live_available), 'requires_complete_acquisition': True,
            'explicit_uv_and_depth_thresholds': True, 'max_points': 20000,
            'max_cells': 20000, 'max_components': 64, 'max_depth_modes_per_cell': 16,
            'native_rebuild_required': False, 'automatic_multi_layer_selection': False,
            'disconnected_patch_joining': False, 'manufacturing_intent_confirmed': False}


def layer_schema() -> dict:
    properties = {key: {'type': 'number', 'exclusiveMinimum': 0,
                        'description': 'Explicit threshold in native coordinate units.'}
                  for key in LAYER_REQUIRED}
    for key, low, high in (('min_cell_points', 1, 20000), ('min_layer_cells', 3, 20000),
                           ('max_points', 3, 20000), ('max_cells', 3, 20000), ('max_components', 1, 64)):
        properties[key] = {'type': 'integer', 'minimum': low, 'maximum': high, 'default': LAYER_DEFAULTS[key]}
    properties['max_points']['description'] = 'Complete acquisition budget, never a permission to use truncated samples.'
    return {'type': 'object', 'additionalProperties': False,
            'properties': properties, 'required': list(LAYER_REQUIRED)}


def profile_schema() -> dict:
    properties = {}
    for key, (default, low, high) in PROFILE_FLOATS.items():
        properties[key] = {'type': 'number', 'exclusiveMinimum': 0} if low == 0 else {'type': 'number', 'minimum': low}
        if default is not None:
            properties[key]['default'] = default
        if high is not None:
            properties[key]['maximum'] = high
    for key, (default, low, high) in PROFILE_INTS.items():
        properties[key] = {'type': 'integer', 'minimum': low, 'maximum': high, 'default': default}
    properties['require_grid_stability'] = {'type': 'boolean', 'default': True}
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': ['cell_size', 'max_edge_length', 'fit_tolerance']}


def section_schema() -> dict:
    return {'type': 'object', 'additionalProperties': False,
            'required': ['coordinate_space', 'units', 'acquisition_complete', 'samples_uvd'],
            'properties': {
                'coordinate_space': {'const': 'section_uv_depth'}, 'units': {'const': 'native'},
                'acquisition_complete': {'type': 'boolean', 'const': True,
                                         'description': 'Caller assertion; not independent live validation.'},
                'samples_uvd': {'type': 'array', 'items': deepcopy(VEC3), 'minItems': 3, 'maxItems': 20000},
                'frame': {'type': 'object', 'additionalProperties': False, 'properties': {
                    'frame_id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                    **{key: deepcopy(VEC3) for key in ('origin_global', 'basis_u', 'basis_v', 'normal')},
                }},
                'source': {'type': 'object', 'additionalProperties': False, 'properties': {
                    'cloud_id': {'type': 'integer', 'minimum': 1, 'maximum': 2**32 - 1},
                    'cloud_name': deepcopy(NAME), 'global_shift': deepcopy(VEC3),
                    'global_scale': {'type': 'number', 'exclusiveMinimum': 0},
                }},
                'provenance': {'type': 'object', 'description': 'Finite JSON metadata, at most 4096 UTF-8 bytes.'},
            }}


def tools() -> list[Tool]:
    result = []
    for name, (live, reconstruct) in KINDS.items():
        properties = {'layer_parameters': layer_schema()}
        if live:
            properties.update(cloud_id={'type': 'integer', 'minimum': 1, 'maximum': 2**32 - 1},
                              origin=deepcopy(VEC3), normal=deepcopy(VEC3),
                              half_thickness={'type': 'number', 'minimum': 0})
            required = list(properties)
            properties['query_timeout_seconds'] = {'type': 'number', 'exclusiveMinimum': 0,
                                                    'maximum': 120, 'default': 30}
        else:
            properties['section'] = section_schema()
            required = list(properties)
        if reconstruct:
            properties.update(profile_parameters=profile_schema(),
                              layer_id={'type': 'string', 'minLength': 1, 'maxLength': 128},
                              expected_analysis_fingerprint={'type': 'string', 'minLength': 1, 'maxLength': 128})
            required.append('profile_parameters')
        schema = {'type': 'object', 'additionalProperties': False,
                  'properties': properties, 'required': required}
        description = ('Read one complete live CloudCompare slab, retaining signed depth. ' if live else
                       'Analyze a caller-supplied complete section_uv_depth snapshot without live I/O. ')
        description += ('Infer bounded local depth modes and coherent 4-neighbor surface candidates before 2D flattening. '
                        'Return compact support, thickness, continuity, overlap and ambiguity evidence; no raw arrays. ')
        if reconstruct:
            description += ('Feed only a single safe or explicitly chosen usable layer to accepted 0.15.2 occupancy/topology/fitting. '
                            'Multiple layers return candidates/BLOCKED; explicit layer_id requires the current analysis fingerprint. ')
        description += 'No source mutation, sign-based selection, unsupported-point deletion, or confirmed manufacturing intent.'
        result.append(Tool(name=name, description=description, inputSchema=schema,
                           annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                                       idempotentHint=True, openWorldHint=live)))
    return result


def handle(args: dict, *, live: bool, reconstruct: bool,
           request: Callable[..., Any] | None = None) -> list[TextContent] | CallToolResult:
    try:
        result = run_layer_workflow(args, live=live, reconstruct=reconstruct, request=request)
        return [TextContent(type='text', text=json.dumps(result, separators=(',', ':'), allow_nan=False))]
    except (SectionLayerError, FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])


def handlers(request: Callable[..., Any] | None = None) -> dict[str, Callable]:
    return {name: partial(handle, live=live, reconstruct=reconstruct, request=request)
            for name, (live, reconstruct) in KINDS.items()}
