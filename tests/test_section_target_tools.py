"""Schema/dispatch and actual stdio. TCP peer is replay, NOT real CloudCompare."""
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
import numpy as np
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.section_target_tools import KINDS
from test_section_target_workflow import snapshot, live_args
from test_section_layer_workflow import native_result, rectangle
from test_section_layer_tools import body, stdio_parameters, ReplayServer, ReplayHandler


def test_target_registered_schemas_and_annotations():
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
        invalid['target_parameters']['max_points'] = 20001
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, tool.inputSchema)
        if reconstruct:
            invalid = args | {'target_id': 'unpaired'}
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(invalid, tool.inputSchema)


@pytest.mark.parametrize('available', [False, True])
def test_target_capability_discovery_preserves_accepted_versions(available):
    with patch.object(server, 'live_request', return_value={'region_query': {'available': available}}):
        result = body(server.handle_get_live_workflow_capabilities({}))
    assert result['python_cad_profiles']['version'] == '0.15.2'
    assert result['python_section_layers']['version'] == '0.15.3'
    caps = result['python_section_layers']['section_targets']
    assert caps['version'] == '0.15.4'
    assert caps['live_target_analysis'] is available
    assert caps['live_target_profile'] is available
    assert caps['native_rebuild_required'] is False


@pytest.mark.parametrize('name', list(KINDS))
def test_target_dispatch_and_structured_errors(name):
    live, reconstruct = KINDS[name]
    args = live_args(reconstruct) if live else snapshot(reconstruct=reconstruct)
    with patch.object(server, 'live_request', return_value=native_result()) as native:
        result = body(asyncio.run(server.call_tool(name, args)))
    assert result['status'] in ('ready', 'candidate')
    assert native.call_count == int(live)
    with patch.object(server, 'live_request', side_effect=AssertionError('invalid request did I/O')) as native:
        bad = asyncio.run(server.call_tool(name, {'target_parameters': {}}))
    assert isinstance(bad, CallToolResult) and bad.isError
    native.assert_not_called()


def test_snapshot_dispatch_never_opens_socket():
    with patch.object(socket, 'create_connection', side_effect=AssertionError('unexpected I/O')):
        result = body(asyncio.run(server.call_tool('reconstruct_section_target_profile', snapshot(reconstruct=True))))
    assert result['status'] == 'candidate'


def test_actual_target_stdio_snapshot_no_bridge():
    async def run():
        async with stdio_client(stdio_parameters('invalid-no-host')) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert set(KINDS) <= {t.name for t in (await session.list_tools()).tools}
                response = await session.call_tool('analyze_section_target_regions', snapshot())
                analysis = body(response)
                assert analysis['status'] == 'ready'
                args = snapshot(reconstruct=True)
                response = await session.call_tool('reconstruct_section_target_profile', args)
                result = body(response)
                assert result['status'] == 'candidate'
                assert result['layer_result']['profile']['topology']['loop_count'] == 1
                args['section']['acquisition_complete'] = False
                assert (await session.call_tool('reconstruct_section_target_profile', args)).isError
    asyncio.run(asyncio.wait_for(run(), timeout=45))


def test_actual_target_stdio_live_tcp_replay_nested_choices_and_truncation():
    points = np.vstack([rectangle(-.4), rectangle(.4), rectangle() + [20, 0, 0]])
    native = native_result(points)
    saved = deepcopy(native)
    with ReplayServer(('127.0.0.1', 0), ReplayHandler) as peer:
        peer.native, peer.requests = native, []
        thread = threading.Thread(target=peer.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        thread.start()

        async def run():
            async with stdio_client(stdio_parameters(peer.server_address[1])) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    analysis = body(await session.call_tool('analyze_live_section_target_regions', live_args()))
                    assert analysis['candidate_target_count'] == 2
                    args = live_args(True)
                    result = body(await session.call_tool('reconstruct_live_section_target_profile', args))
                    assert result['blocked_stage'] == 'target_selection'
                    c = analysis['candidate_targets'][0]
                    args.update(target_id=c['target_id'], expected_target_fingerprint=c['candidate_fingerprint'])
                    result = body(await session.call_tool('reconstruct_live_section_target_profile', args))
                    assert result['blocked_stage'] == 'layer_selection'
                    layer = result['layer_result']['layer_analysis']
                    assert layer['candidate_layer_count'] == 2
                    args.update(layer_id=layer['candidate_layers'][0]['layer_id'],
                                expected_layer_fingerprint=layer['analysis_fingerprint'])
                    result = body(await session.call_tool('reconstruct_live_section_target_profile', args))
                    assert result['status'] == 'candidate'
                    assert result['point_accounting']['total_unselected_point_count'] == 2400
                    assert result['target_analysis']['source']['global_scale'] == 2.5
                    assert 'position_global' not in json.dumps(result)
                    stale = args | {'expected_target_fingerprint': 'stale'}
                    assert (await session.call_tool('reconstruct_live_section_target_profile', stale)).isError
                    bad = live_args()
                    bad['target_parameters']['max_points'] = 10
                    assert (await session.call_tool('analyze_live_section_target_regions', bad)).isError
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=45))
        finally:
            peer.shutdown()
            thread.join(timeout=5)
        assert len(peer.requests) == 6
        assert all(r['method'] == 'cloud.region_query' for r in peer.requests)
        assert peer.native == saved
