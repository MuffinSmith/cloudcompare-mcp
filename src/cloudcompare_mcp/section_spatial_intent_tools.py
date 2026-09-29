"""MCP surface: deliberate intent is separate from downstream authorization."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .feature_fit import FeatureFitError
from .live import LiveBridgeError
from .section_layer_tools import VEC3
from .section_layers import SectionLayerError
from .section_spatial_intent import CONTRACT, MAX_ANCHORS, VERSION
from .section_spatial_intent_workflow import run_picked_roi_workflow
from .section_target_roi_tools import tools as roi_tools

KINDS = {
    'derive_section_roi_from_picks': (False, 'derive'),
    'derive_live_section_roi_from_picks': (True, 'derive'),
    'analyze_picked_section_target_roi': (False, 'analyze'),
    'analyze_live_picked_section_target_roi': (True, 'analyze'),
    'reconstruct_picked_section_target_roi_profile': (False, 'reconstruct'),
    'reconstruct_live_picked_section_target_roi_profile': (True, 'reconstruct'),
}


def capabilities(*, live_available: bool = True) -> dict:
    return dict(version=VERSION, contract=CONTRACT, snapshot=True, live=bool(live_available),
                max_anchors=MAX_ANCHORS, explicit_frame_required=True, frame_from_picks=False,
                explicit_nonnegative_margin_required=True, stopped_live_picks_required=True,
                intent_bound_into_downstream_candidate_evidence=True,
                intent_fingerprint_authorizes_reconstruction=False, native_rebuild_required=False,
                one_complete_slab_query_per_valid_live_call=True,
                live_freshness_scope='observed_slab_and_anchors_not_whole_cloud_or_atomic_scene')


def pick_state_schema() -> dict:
    # Captured native records include optional attributes (color/scalar values).
    # Preserve and bind these, rather than stripping them in a schema projection.
    integer = {'type': 'integer', 'minimum': 0, 'maximum': 2**32 - 1}
    properties = {k: deepcopy(integer) for k in ('pick_index', 'point_index', 'item_index')}
    properties.update(entity_id=integer | {'minimum': 1}, entity_name={'type': 'string', 'minLength': 1},
                      entity_kind={'const': 'point_cloud'}, entity_center={'const': False},
                      global_scale={'type': 'number', 'exclusiveMinimum': 0})
    properties.update({k: deepcopy(VEC3) for k in ('position_global', 'position_native_local', 'global_shift')})
    return dict(type='object', required=['active', 'pick_count', 'picks'], properties={
        'active': {'const': False}, 'pick_count': {'type': 'integer', 'minimum': 2, 'maximum': 4096},
        'picks': {'type': 'array', 'minItems': 2, 'maxItems': 4096,
                  'items': {'type': 'object', 'required': list(properties), 'properties': properties}}})


def tools() -> list[Tool]:
    accepted = {t.name: t for t in roi_tools()}
    result = []
    for name, (live, action) in KINDS.items():
        template = ('reconstruct_' if action == 'reconstruct' else 'analyze_')
        template += 'live_' if live else ''
        template += 'section_target_roi' + ('_profile' if action == 'reconstruct' else '')
        schema = deepcopy(accepted[template].inputSchema)
        props, required = schema['properties'], schema['required']
        del props['roi']
        required.remove('roi')
        props.update(pick_indices={'type': 'array', 'minItems': 2, 'maxItems': MAX_ANCHORS,
                                    'uniqueItems': True, 'items': {'type': 'integer', 'minimum': 0, 'maximum': 4095}},
                     margin={'type': 'number', 'minimum': 0,
                             'description': 'Explicit native-unit padding. Zero means exactly projected anchors. Never searched.'},
                     frame_provenance={'type': 'object', 'minProperties': 1,
                                       'description': 'Finite compact declared frame source/reference, not inferred from anchor placement.'})
        required.extend(('pick_indices', 'margin', 'frame_provenance'))
        if live:
            props['frame_id'] = {'type': 'string', 'minLength': 1, 'maxLength': 128}
            required.append('frame_id')
        else:
            props['pick_state'] = pick_state_schema()
            required.append('pick_state')
            section = props['section']
            for field in ('source', 'frame'):
                if field not in section['required']:
                    section['required'].append(field)
            section['properties']['frame']['required'] = ['frame_id', 'origin_global', 'normal', 'basis_u', 'basis_v']
            section['properties']['source']['required'] = ['cloud_id', 'global_shift', 'global_scale']
        if action != 'derive':
            props['expected_intent_fingerprint'] = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
            required.append('expected_intent_fingerprint')
        description = ('Read stopped captured CloudCompare point picks, recheck selected source points and acquire one complete slab. '
                       if live else 'Use caller-asserted stopped pick records and complete section snapshot without native I/O. ')
        description += ('Require an explicitly declared frame and 2..32 distinct boundary anchors. Project all anchor depths; '
                        'derive exact half-open UV min/max plus explicit margin. No inferred frame, ROI search or automatic padding. ')
        if live:
            description += 'Origin/normal uses the existing canonical section basis, not an implicit datum X/Y orientation. '
        if action == 'derive':
            description += 'Freeze compact provenance-bound intent without running target analysis or reconstruction. '
        else:
            description += ('Recompute and reject stale intent, bind its fingerprint into unchanged accepted 0.15.6 ROI/target evidence. '
                            'Use this wrapper, not a bare numerical ROI call, to preserve picked-intent provenance. ')
        if action == 'reconstruct':
            description += ('Intent alone cannot authorize target/layer choice. Existing target_id/candidate fingerprint and '
                            'layer_id/analysis fingerprint rules apply. ROI guards and unsafe evidence remain authoritative. ')
        description += 'Read-only; no giant cloud arrays, whole-cloud freshness proof or atomic native scene guarantee.'
        result.append(Tool(name=name, description=description, inputSchema=schema,
                           annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                                       idempotentHint=True, openWorldHint=live)))
    return result


def handle(args: dict, *, live: bool, action: str,
           request: Callable[..., Any] | None = None) -> list[TextContent] | CallToolResult:
    try:
        result = run_picked_roi_workflow(args, live=live, action=action, request=request)
        return [TextContent(type='text', text=json.dumps(result, separators=(',', ':'), allow_nan=False))]
    except (SectionLayerError, FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])


def handlers(request: Callable[..., Any] | None = None) -> dict[str, Callable]:
    return {name: partial(handle, live=live, action=action, request=request)
            for name, (live, action) in KINDS.items()}
