"""MCP schemas/dispatch/actual stdio; the TCP peer is replay, not real GUI."""
import asyncio
from copy import deepcopy
import json
import socket
import threading
from unittest.mock import patch

import jsonschema
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.section_target_diagnostic_tools import KINDS
from test_section_target_workflow import snapshot, live_args
from test_section_layer_tools import body, stdio_parameters, ReplayServer, ReplayHandler
from test_section_target_fixtures import generator, snapshot_from_file, native_from_file


@pytest.mark.parametrize('name', list(KINDS))
def test_diagnostic_schemas_annotations_and_rejection_of_selection_and_schedule(name):
    listing = asyncio.run(server.list_tools())
    assert len(listing) == len({t.name for t in listing})
    tool = next(t for t in listing if t.name == name)
    live = KINDS[name]
    args = live_args() if live else snapshot()
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    assert not tool.annotations.destructiveHint and tool.annotations.openWorldHint is live
    for extra in ({'target_id': 'x'}, {'scales': [1]}, {'profile_parameters': {}}, {'max_points': 90000}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(args | extra, tool.inputSchema)
    invalid = deepcopy(args)
    invalid['target_parameters']['max_cells'] = 20001
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, tool.inputSchema)


@pytest.mark.parametrize('available', [False, True])
def test_diagnostic_capabilities_preserve_accepted_versions(available):
    with patch.object(server, 'live_request', return_value={'region_query': {'available': available}}):
        result = body(server.handle_get_live_workflow_capabilities({}))
    assert result['python_cad_profiles']['version'] == '0.15.2'
    assert result['python_section_layers']['version'] == '0.15.3'
    parent = result['python_section_layers']['section_targets']
    assert parent['version'] == '0.15.4'
    caps = parent['scale_diagnostics']
    assert caps['version'] == '0.15.5' and caps['live'] is available
    assert caps['snapshot'] and caps['diagnostic_only']
    assert len(caps['fixed_schedule']) == 5
    assert not caps['scale_selection'] and not caps['target_selection']
    assert not caps['reconstruction'] and not caps['native_rebuild_required']


@pytest.mark.parametrize('name', list(KINDS))
def test_diagnostic_invalid_dispatch_returns_error_without_io(name):
    with patch.object(server, 'live_request', side_effect=AssertionError('unexpected I/O')) as native:
        result = asyncio.run(server.call_tool(name, {'scales': [1]}))
    assert isinstance(result, CallToolResult) and result.isError
    native.assert_not_called()


def test_diagnostic_snapshot_dispatch_does_not_open_socket():
    with patch.object(socket, 'create_connection', side_effect=AssertionError('unexpected socket')):
        result = body(asyncio.run(server.call_tool('diagnose_section_target_stability', snapshot())))
    assert result['diagnostic_only'] and not result['selection_authorized']


def test_actual_diagnostic_stdio_transformed_snapshot_without_native(tmp_path):
    output = tmp_path / 'generated'
    manifest = generator.generate(output)
    record = next(r for r in manifest['fixtures'] if r['name'] == 'transformed_single')
    _, args = snapshot_from_file(output, record)

    async def run():
        async with stdio_client(stdio_parameters('invalid-no-host')) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert set(KINDS) <= {t.name for t in (await session.list_tools()).tools}
                response = await session.call_tool('diagnose_section_target_stability', args)
                assert not response.isError
                report = json.loads(response.content[0].text)
                assert report['version'] == '0.15.5' and len(report['panels']) == 5
                assert report['panels'][0]['candidate_count'] == 1
                assert not report['live_connection_used'] and not report['selection_authorized']
                assert report['point_accounting']['unselected_point_count'] == record['point_count']
                bad = deepcopy(args)
                bad['section']['acquisition_complete'] = False
                assert (await session.call_tool('diagnose_section_target_stability', bad)).isError
                assert (await session.call_tool('diagnose_section_target_stability', args | {'scales': [1]})).isError
    asyncio.run(asyncio.wait_for(run(), timeout=45))


def test_actual_diagnostic_stdio_live_replay_one_acquisition_and_truncation(tmp_path):
    output = tmp_path / 'generated'
    manifest = generator.generate(output)
    record = next(r for r in manifest['fixtures'] if r['name'] == 'transformed_two')
    native = native_from_file(output, record)
    saved = deepcopy(native)
    args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters')}
    args['cloud_id'] = 359
    with ReplayServer(('127.0.0.1', 0), ReplayHandler) as peer:
        peer.native, peer.requests = native, []
        thread = threading.Thread(target=peer.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        thread.start()
        async def run():
            async with stdio_client(stdio_parameters(peer.server_address[1])) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    response = await session.call_tool('diagnose_live_section_target_stability', args)
                    assert not response.isError
                    report = json.loads(response.content[0].text)
                    assert len(peer.requests) == 1
                    assert report['panels'][0]['candidate_count'] == 2
                    assert not report['selection_authorized'] and not report['reconstruction_attempted']
                    assert report['source_coordinate_bookkeeping']['global_scale'] == 2.5
                    assert not report['source_coordinate_bookkeeping']['shift_scale_reapplied']
                    bad = deepcopy(args)
                    bad['target_parameters']['max_points'] = 10
                    assert (await session.call_tool('diagnose_live_section_target_stability', bad)).isError
                    assert len(peer.requests) == 2
                    assert (await session.call_tool('diagnose_live_section_target_stability', args | {'target_id': 'x'})).isError
                    assert len(peer.requests) == 2
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=45))
        finally:
            peer.shutdown()
            thread.join(timeout=5)
        assert peer.native == saved
        assert all(r['method'] == 'cloud.region_query' for r in peer.requests)
