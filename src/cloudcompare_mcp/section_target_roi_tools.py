"""Read-only explicit section ROI MCP contracts; no discovery/search of bounds."""
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
from .section_target_roi import BOUNDS, CONTRACT, VERSION
from .section_target_roi_workflow import run_roi_workflow
from .section_target_tools import target_schema

KINDS = {
    'analyze_section_target_roi': (False, False),
    'analyze_live_section_target_roi': (True, False),
    'reconstruct_section_target_roi_profile': (False, True),
    'reconstruct_live_section_target_roi_profile': (True, True),
}


def capabilities(*, live_available: bool = True) -> dict:
    return {'version': VERSION, 'contract': CONTRACT, 'snapshot': True,
            'live': bool(live_available), 'requires_complete_acquisition': True,
            'explicit_uv_bounds_required': True, 'half_open_membership': True,
            'all_signed_depths_retained': True, 'outside_point_accounting': True,
            'edge_guard_width': 'one declared target uv_cell_size, inner threshold inclusive',
            'roi_report_fingerprint_authorizes_selection': False,
            'explicit_selection_overrides_truncation': False, 'automatic_roi_search': False,
            'native_rebuild_required': False}


def tools() -> list[Tool]:
    result = []
    for name, (live, reconstruct) in KINDS.items():
        properties = {'roi': {'type': 'object', 'additionalProperties': False,
                             'required': list(BOUNDS),
                             'properties': {k: {'type': 'number'} for k in BOUNDS},
                             'description': 'Explicit native-unit [u_min,u_max) x [v_min,v_max); positive spans, all depths.'},
                      'target_parameters': target_schema()}
        if live:
            properties.update(cloud_id={'type': 'integer', 'minimum': 1, 'maximum': 2**32 - 1},
                              origin=deepcopy(VEC3), normal=deepcopy(VEC3),
                              half_thickness={'type': 'number', 'minimum': 0})
            required = list(properties)
            properties['query_timeout_seconds'] = {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 120, 'default': 30}
        else:
            section = section_schema()
            section['properties']['source_point_indices'] = {
                'type': 'array', 'minItems': 3, 'maxItems': 20000, 'uniqueItems': True,
                'items': {'type': 'integer', 'minimum': 0, 'maximum': 2**32 - 1},
                'description': 'Optional exact source index per snapshot sample, same order and length.'}
            properties['section'] = section
            required = list(properties)
        schema = {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': required}
        if reconstruct:
            properties.update(layer_parameters=layer_schema(), profile_parameters=profile_schema())
            required.extend(('layer_parameters', 'profile_parameters'))
            for key in ('target_id', 'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint'):
                properties[key] = {'type': 'string', 'minLength': 1, 'maxLength': 128}
            schema['dependentRequired'] = {
                'target_id': ['expected_target_fingerprint'], 'expected_target_fingerprint': ['target_id'],
                'layer_id': ['expected_layer_fingerprint'], 'expected_layer_fingerprint': ['layer_id']}
        description = ('Acquire one complete global-coordinate CloudCompare slab; ' if live else
                       'Use a complete section_uv_depth snapshot without CloudCompare; ')
        description += ('classify every point inside/outside the caller-declared UV ROI, retain all depths, '
                        'report one-cell edge/truncation evidence, then run unchanged accepted target analysis. '
                        'ROI is spatial intent, not a part/manufacturing claim. No raw arrays or source mutation. ')
        if reconstruct:
            description += ('Multiple targets require target_id plus the nested target candidate_fingerprint as '
                            'expected_target_fingerprint. The ROI report fingerprint is NOT authorization. '
                            'A selected target touching any ROI guard refuses even with explicit ID. '
                            'Only supported guard-clear targets reach accepted layer/boundary/topology/fitting. '
                            'Layer choice uses layer_id plus layer_analysis.analysis_fingerprint as expected_layer_fingerprint. ')
        description += 'No ROI resizing/search, scale selection, depth cropping, largest-target preference or unsafe-evidence override.'
        result.append(Tool(name=name, description=description, inputSchema=schema,
                           annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                                       idempotentHint=True, openWorldHint=live)))
    return result


def handle(args: dict, *, live: bool, reconstruct: bool,
           request: Callable[..., Any] | None = None) -> list[TextContent] | CallToolResult:
    try:
        result = run_roi_workflow(args, live=live, reconstruct=reconstruct, request=request)
        return [TextContent(type='text', text=json.dumps(result, separators=(',', ':'), allow_nan=False))]
    except (SectionLayerError, FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])


def handlers(request: Callable[..., Any] | None = None) -> dict[str, Callable]:
    return {name: partial(handle, live=live, reconstruct=reconstruct, request=request)
            for name, (live, reconstruct) in KINDS.items()}
