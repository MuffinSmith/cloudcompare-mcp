"""ROI schemas and MCP dispatch; actual stdio file tests live in the fixture module."""
import asyncio
from copy import deepcopy
import json
import socket
from unittest.mock import patch

import jsonschema
from mcp.types import CallToolResult
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.section_target_roi_tools import KINDS
from test_section_layer_tools import body
from test_section_layer_workflow import native_result
from test_section_target_roi_workflow import snapshot, live_args


@pytest.mark.parametrize('name', list(KINDS))
def test_roi_schema_annotation_and_dispatch(name):
    listing = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in listing}
    assert len(by_name) == len(listing)
    live, reconstruct = KINDS[name]
    tool = by_name[name]
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    args = live_args(reconstruct) if live else snapshot(reconstruct=reconstruct)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    assert not tool.annotations.destructiveHint
    with patch.object(server, 'live_request', return_value=native_result()) as request:
        r = body(asyncio.run(server.call_tool(name, args)))
    assert r['version'] == '0.15.6' and r['status'] in ('ready', 'candidate')
    assert request.call_count == int(live)
    assert 'samples_uvd' not in json.dumps(r)
    for change in ({'roi': {}}, {'roi': args['roi'] | {'u_min': True}}, {'depth_min': 0}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(args | change, tool.inputSchema)
    if reconstruct:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(args | {'target_id': 'unpaired'}, tool.inputSchema)


@pytest.mark.parametrize('available', [False, True])
def test_roi_capabilities_additive_without_changing_accepted_versions(available):
    with patch.object(server, 'live_request', return_value={'region_query': {'available': available}}):
        r = body(server.handle_get_live_workflow_capabilities({}))
    assert r['python_cad_profiles']['version'] == '0.15.2'
    assert r['python_section_layers']['version'] == '0.15.3'
    target = r['python_section_layers']['section_targets']
    assert target['version'] == '0.15.4'
    assert target['scale_diagnostics']['version'] == '0.15.5'
    roi = target['roi_isolation']
    assert roi['version'] == '0.15.6' and roi['live'] is available and roi['snapshot']
    assert not roi['automatic_roi_search'] and not roi['explicit_selection_overrides_truncation']
    assert not roi['native_rebuild_required']


@pytest.mark.parametrize('name', list(KINDS))
def test_roi_malformed_dispatch_errors_without_io(name):
    live, reconstruct = KINDS[name]
    args = live_args(reconstruct) if live else snapshot(reconstruct=reconstruct)
    args['roi']['u_min'] = float('nan')
    with patch.object(server, 'live_request', side_effect=AssertionError('invalid request I/O')) as request:
        r = asyncio.run(server.call_tool(name, args))
    assert isinstance(r, CallToolResult) and r.isError
    request.assert_not_called()


def test_roi_snapshot_no_socket_and_source_indices_schema():
    args = snapshot()
    args['section']['source_point_indices'] = list(range(1200))
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == 'analyze_section_target_roi')
    jsonschema.validate(args, tool.inputSchema)
    with patch.object(socket, 'create_connection', side_effect=AssertionError('snapshot socket')):
        r = body(asyncio.run(server.call_tool(tool.name, args)))
    assert r['source_index_accounting']['available']
    invalid = deepcopy(args)
    invalid['section']['source_point_indices'][0] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, tool.inputSchema)
