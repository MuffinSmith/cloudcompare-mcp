"""Read-only MCP surface for fixed target-scale diagnostics, not target selection."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .feature_fit import FeatureFitError
from .live import LiveBridgeError
from .section_layers import SectionLayerError
from .section_target_diagnostics import VERSION, schedule
from .section_target_diagnostic_workflow import run_target_diagnostics

KINDS = {'diagnose_section_target_stability': False,
         'diagnose_live_section_target_stability': True}


def capabilities(*, live_available: bool = True) -> dict:
    return dict(version=VERSION, snapshot=True, live=bool(live_available),
                diagnostic_only=True, requires_complete_acquisition=True,
                fixed_schedule=schedule(), native_acquisitions_per_live_call=1,
                scale_selection=False, target_selection=False, reconstruction=False,
                native_rebuild_required=False)


def tools() -> list[Tool]:
    # Late imports avoid a registration cycle; parent tools delegate here.
    from .section_layer_tools import VEC3, section_schema
    from .section_target_tools import target_schema
    result = []
    for name, live in KINDS.items():
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
        description = ('Acquire one complete global-coordinate CloudCompare slab. ' if live else
                       'Use an asserted-complete section_uv_depth snapshot without native I/O. ')
        description += ('Compare accepted target evidence at five fixed settings: baseline, UV*0.75, '
                        'UV*1.25, depth*0.75, depth*1.25. All other thresholds and budgets remain unchanged. '
                        'Report exact point-membership splits/merges, blocking-reason changes, refused probes '
                        'and fully accounted bounded previews. Baseline refusal stops; probe refusal means '
                        'inconclusive. No adaptive search, recommended scale, selection token, profile or mutation. '
                        'No change observed is NOT proof of physical topology or manufacturing intent.')
        result.append(Tool(name=name, description=description, inputSchema={
            'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': required},
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                        idempotentHint=True, openWorldHint=live)))
    return result


def handle(args: dict, *, live: bool,
           request: Callable[..., Any] | None = None) -> list[TextContent] | CallToolResult:
    try:
        result = run_target_diagnostics(args, live=live, request=request)
        return [TextContent(type='text', text=json.dumps(result, separators=(',', ':'), allow_nan=False))]
    except (SectionLayerError, FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])


def handlers(request: Callable[..., Any] | None = None) -> dict[str, Callable]:
    return {name: partial(handle, live=live, request=request) for name, live in KINDS.items()}
