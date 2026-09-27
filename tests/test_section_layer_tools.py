"""MCP schemas, actual stdio, and a replay TCP peer (not real CloudCompare)."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import threading
from unittest.mock import patch

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
import numpy as np
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.section_layer_tools import KINDS
from test_section_layer_workflow import snapshot, live_args, native_result, rectangle
from test_section_layer_fixtures import generator, snapshot_from_file


def body(result):
    assert not isinstance(result, CallToolResult) or not result.isError
    content = result.content if isinstance(result, CallToolResult) else result
    return json.loads(content[0].text)


def test_registered_schemas_and_readonly_annotations():
    listing = asyncio.run(server.list_tools())
    by_name = {tool.name: tool for tool in listing}
    assert len(by_name) == len(listing)
    for name, (live, reconstruct) in KINDS.items():
        tool = by_name[name]
        jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
        args = live_args(reconstruct) if live else snapshot(reconstruct=reconstruct)
        jsonschema.validate(args, tool.inputSchema)
        assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
        assert tool.annotations.destructiveHint is False
        invalid = deepcopy(args)
        invalid['layer_parameters']['max_points'] = 20001
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, tool.inputSchema)


@pytest.mark.parametrize('available', [False, True])
def test_capabilities_do_not_change_accepted_profile_version(available):
    with patch.object(server, 'live_request', return_value={'region_query': {'available': available}}):
        result = body(server.handle_get_live_workflow_capabilities({}))
    assert result['python_cad_profiles']['version'] == '0.15.2'
    assert result['python_cad_profiles']['filled_section_boundary_version'] == '0.15.2'
    assert result['python_section_layers']['version'] == '0.15.3'
    assert result['python_section_layers']['live_layer_analysis'] is available
    assert result['python_section_layers']['live_layer_profile'] is available
    assert result['python_section_layers']['native_rebuild_required'] is False


@pytest.mark.parametrize('name', ['analyze_section_layers', 'reconstruct_section_layer_profile'])
def test_snapshot_dispatch_has_no_native_io(name):
    args = snapshot(reconstruct=name.startswith('reconstruct'))
    saved = deepcopy(args)
    with patch.object(server, 'live_request', side_effect=AssertionError('unexpected native I/O')) as native:
        with patch.object(socket, 'create_connection', side_effect=AssertionError('unexpected socket')):
            result = body(asyncio.run(server.call_tool(name, args)))
    native.assert_not_called()
    assert args == saved
    assert result['status'] in ('ready', 'candidate')
    assert 'samples_uvd' not in json.dumps(result)


@pytest.mark.parametrize('name', ['analyze_live_section_layers', 'reconstruct_live_section_layer_profile'])
def test_live_dispatch_uses_existing_transport(name):
    with patch.object(server, 'live_request', return_value=native_result()) as native:
        result = body(asyncio.run(server.call_tool(name, live_args(name.startswith('reconstruct')))))
    assert result['status'] in ('ready', 'candidate')
    native.assert_called_once()
    assert native.call_args.args[0] == 'cloud.region_query'


@pytest.mark.parametrize('name', list(KINDS))
def test_direct_invalid_arguments_return_structured_mcp_error(name):
    with patch.object(server, 'live_request', side_effect=AssertionError('unexpected native I/O')) as native:
        result = asyncio.run(server.call_tool(name, {'layer_parameters': {}}))
    assert isinstance(result, CallToolResult) and result.isError
    native.assert_not_called()


def test_snapshot_schema_requires_complete_assertion():
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == 'analyze_section_layers')
    args = snapshot()
    args['section']['acquisition_complete'] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(args, tool.inputSchema)


def stdio_parameters(port):
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src'),
           'CLOUDCOMPARE_MCP_HOST': '127.0.0.1', 'CLOUDCOMPARE_MCP_PORT': str(port),
           'CLOUDCOMPARE_MCP_TOKEN': ''}
    return StdioServerParameters(command=sys.executable, args=['-m', 'cloudcompare_mcp.server'], env=env)


def test_actual_stdio_snapshot_generated_file_without_bridge(tmp_path):
    output = tmp_path / 'generated'
    manifest = generator.generate(output)
    record = next(x for x in manifest['fixtures'] if x['name'] == 'single')
    _, args = snapshot_from_file(output, record)

    async def run():
        async with stdio_client(stdio_parameters('invalid-no-host')) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert set(KINDS) <= {t.name for t in (await session.list_tools()).tools}
                response = await session.call_tool('analyze_section_layers', args)
                assert not response.isError
                assert json.loads(response.content[0].text)['status'] == 'ready'
                response = await session.call_tool('reconstruct_section_layer_profile', args | {'profile_parameters': record['profile_parameters']})
                assert not response.isError
                result = json.loads(response.content[0].text)
                assert result['status'] == 'candidate'
                assert result['profile']['topology']['loop_count'] == 1
                bad = deepcopy(args)
                bad['section']['acquisition_complete'] = False
                response = await session.call_tool('analyze_section_layers', bad)
                assert response.isError
    asyncio.run(asyncio.wait_for(run(), timeout=45))


class ReplayHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        request = json.loads(self.rfile.readline(65536))
        self.server.requests.append(request)
        if request['method'] != 'cloud.region_query':
            response = {'ok': False, 'error': 'Replay permits only read-only cloud.region_query'}
        else:
            native = deepcopy(self.server.native)
            limit = request['params']['max_points']
            if limit < len(native['points']):
                native['points'] = native['points'][:limit]
                native['returned_count'] = limit
                native['truncated'] = True
                native['sample_strategy'] = 'deterministic_reservoir'
            response = {'ok': True, 'result': native}
        self.wfile.write((json.dumps(response, allow_nan=False) + '\n').encode())


class ReplayServer(socketserver.TCPServer):
    allow_reuse_address = True


def test_actual_stdio_live_tools_over_replay_tcp_with_generated_parallel_ply(tmp_path):
    output = tmp_path / 'generated'
    manifest = generator.generate(output)
    record = next(x for x in manifest['fixtures'] if x['name'] == 'parallel')
    xyz, _ = snapshot_from_file(output, record)
    native = native_result(xyz)
    saved = deepcopy(native)
    with ReplayServer(('127.0.0.1', 0), ReplayHandler) as peer:
        peer.native, peer.requests = native, []
        thread = threading.Thread(target=peer.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        thread.start()
        args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'layer_parameters')}
        args['cloud_id'] = 359
        params = stdio_parameters(peer.server_address[1])

        async def run():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    response = await session.call_tool('analyze_live_section_layers', args)
                    assert not response.isError
                    analysis = json.loads(response.content[0].text)
                    assert analysis['status'] == 'selection_required' and analysis['candidate_layer_count'] == 2
                    composite = args | {'profile_parameters': record['profile_parameters']}
                    response = await session.call_tool('reconstruct_live_section_layer_profile', composite)
                    assert not response.isError
                    assert json.loads(response.content[0].text)['blocked_stage'] == 'layer_selection'
                    composite.update(layer_id=analysis['candidate_layers'][0]['layer_id'],
                                     expected_analysis_fingerprint=analysis['analysis_fingerprint'])
                    response = await session.call_tool('reconstruct_live_section_layer_profile', composite)
                    assert not response.isError
                    result = json.loads(response.content[0].text)
                    assert result['status'] == 'candidate'
                    assert result['selection']['selected_point_count'] * 2 == len(xyz)
                    assert result['layer_analysis']['source']['global_scale'] == 2.5
                    assert 'position_global' not in json.dumps(result)
                    bad = deepcopy(args)
                    bad['layer_parameters']['max_points'] = 10
                    response = await session.call_tool('analyze_live_section_layers', bad)
                    assert response.isError
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=45))
        finally:
            peer.shutdown()
            thread.join(timeout=5)
        assert len(peer.requests) == 4
        assert all(r['method'] == 'cloud.region_query' for r in peer.requests)
        assert peer.native == saved
