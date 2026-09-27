"""MCP target evidence and selected-target profile contracts; read-only native I/O."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .feature_fit import FeatureFitError
from .live import LiveBridgeError
from .section_layer_tools import VEC3, layer_schema, profile_schema, section_schema
from .section_layers import SectionLayerError
from .section_target_workflow import run_target_workflow
from .section_targets import DEFAULTS, REQUIRED

KINDS = {
    'analyze_section_target_regions': (False, False),
    'analyze_live_section_target_regions': (True, False),
    'reconstruct_section_target_profile': (False, True),
    'reconstruct_live_section_target_profile': (True, True),
}


def capabilities(*, live_available: bool = True) -> dict:
    from .section_target_diagnostic_tools import capabilities as diagnostic_capabilities
    return {'version': '0.15.4', 'snapshot_target_analysis': True,
            'live_target_analysis': bool(live_available), 'snapshot_target_profile': True,
            'live_target_profile': bool(live_available), 'requires_complete_acquisition': True,
            'target_before_layer_analysis': True, 'explicit_voxel_sizes_and_perturbation': True,
            'max_points': 20000, 'max_cells': 20000, 'max_targets': 64,
            'native_rebuild_required': False, 'automatic_largest_target_selection': False,
            'manufacturing_intent_confirmed': False,
            'scale_diagnostics': diagnostic_capabilities(live_available=live_available)}


def target_schema() -> dict:
    properties = {key: {'type': 'number', 'exclusiveMinimum': 0,
                        'description': 'Explicit voxel size in native units, not a fitted or searched value.'}
                  for key in ('uv_cell_size', 'depth_cell_size')}
    properties['perturbation_fraction'] = {
        'type': 'number', 'exclusiveMinimum': 0, 'maximum': .25,
        'description': 'Declared +/- grid-origin probes as a fraction of each axis cell size; diagnostics only.'}
    for key, low, high in (('min_cell_points', 1, 20000), ('min_target_cells', 3, 20000),
                           ('max_points', 3, 20000), ('max_cells', 3, 20000), ('max_targets', 1, 64)):
        properties[key] = {'type': 'integer', 'minimum': low, 'maximum': high, 'default': DEFAULTS[key]}
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': list(REQUIRED)}


def tools() -> list[Tool]:
    result = []
    for name, (live, reconstruct) in KINDS.items():
        properties = {'target_parameters': target_schema()}
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
        schema = {'type': 'object', 'additionalProperties': False,
                  'properties': properties, 'required': required}
        if reconstruct:
            properties.update(layer_parameters=layer_schema(), profile_parameters=profile_schema())
            required.extend(('layer_parameters', 'profile_parameters'))
            for key in ('target_id', 'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint'):
                properties[key] = {'type': 'string', 'minLength': 1, 'maxLength': 128}
            schema['dependentRequired'] = {
                'target_id': ['expected_target_fingerprint'], 'expected_target_fingerprint': ['target_id'],
                'layer_id': ['expected_layer_fingerprint'], 'expected_layer_fingerprint': ['layer_id']}
        description = ('Read one complete global-coordinate CloudCompare slab. ' if live else
                       'Analyze an asserted-complete section_uv_depth snapshot without native I/O. ')
        description += ('Report bounded spatial targets BEFORE depth-layer analysis using declared anisotropic voxels, '
                        'six-neighbor connectivity and fixed ambiguity diagnostics. Every point remains accounted for; no raw arrays. ')
        if reconstruct:
            description += ('Multiple targets require target_id and its candidate_fingerprint as expected_target_fingerprint. '
                            'Only a supported target passes to unchanged accepted layer/boundary/topology/fitting checks. '
                            'When layers require selection, use layer_id and layer_analysis.analysis_fingerprint as expected_layer_fingerprint. ')
        description += ('No largest-target preference, parameter search, source mutation, unsupported-target override, '
                        'or confirmation of manufacturing intent.')
        result.append(Tool(name=name, description=description, inputSchema=schema,
                           annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                                       idempotentHint=True, openWorldHint=live)))
    from .section_target_diagnostic_tools import tools as diagnostic_tools
    return result + diagnostic_tools()


def handle(args: dict, *, live: bool, reconstruct: bool,
           request: Callable[..., Any] | None = None) -> list[TextContent] | CallToolResult:
    try:
        result = run_target_workflow(args, live=live, reconstruct=reconstruct, request=request)
        return [TextContent(type='text', text=json.dumps(result, separators=(',', ':'), allow_nan=False))]
    except (SectionLayerError, FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])


def handlers(request: Callable[..., Any] | None = None) -> dict[str, Callable]:
    from .section_target_diagnostic_tools import handlers as diagnostic_handlers
    return {name: partial(handle, live=live, reconstruct=reconstruct, request=request)
            for name, (live, reconstruct) in KINDS.items()} | diagnostic_handlers(request)
