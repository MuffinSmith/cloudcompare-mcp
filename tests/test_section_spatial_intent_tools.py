"""Actual MCP schema/dispatch and installed stdio over a counted TCP replay peer."""
import asyncio
from copy import deepcopy
from importlib.metadata import version
import json
import socket
import socketserver
import threading
from unittest.mock import patch

import jsonschema
from mcp import ClientSession
from mcp.client.stdio import stdio_client
import pytest

from cloudcompare_mcp import server
from cloudcompare_mcp.section_spatial_intent_tools import KINDS
from cloudcompare_mcp.section_target_tools import capabilities
from test_section_layer_tools import body, stdio_parameters, ReplayServer
from test_section_spatial_intent import snapshot, authorize
from test_section_spatial_intent_workflow import live_args, NativeReplay
from test_section_spatial_intent_fixtures import intent_files, record_named, inputs_from_file


def installed_stdio_parameters(port):
    params = stdio_parameters(port)
    params.env.pop('PYTHONPATH', None)
    return params


@pytest.mark.parametrize('name', KINDS)
def test_actual_registered_schema_and_dispatch(name):
    live, action = KINDS[name]
    peer = NativeReplay()
    args = live_args(action == 'reconstruct') if live else snapshot(reconstruct=action == 'reconstruct')
    if action != 'derive':
        if live:
            derive = {k:v for k,v in args.items() if k not in ('layer_parameters','profile_parameters')}
            with patch.object(server, 'live_request', side_effect=peer):
                intent = body(asyncio.run(server.call_tool('derive_live_section_roi_from_picks', derive)))
            args['expected_intent_fingerprint'] = intent['intent_fingerprint']
        else: args = authorize(args)
    listing = asyncio.run(server.list_tools())
    assert len(listing) == len({t.name for t in listing})
    tool = next(t for t in listing if t.name == name)
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    jsonschema.validate(args, tool.inputSchema)
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    assert tool.annotations.destructiveHint is False
    saved = deepcopy(args)
    with patch.object(server, 'live_request', side_effect=peer if live else AssertionError('snapshot native I/O')):
        r = body(asyncio.run(server.call_tool(name,args)))
    assert args == saved and r['version'] == '0.15.7'
    assert r['status'] == ('candidate' if action == 'reconstruct' else 'ready')
    for key, value in [('margin',True), ('margin',-1), ('pick_indices',[0,0]), ('frame_provenance',{})]:
        invalid = args | {key:value}
        with pytest.raises(jsonschema.ValidationError): jsonschema.validate(invalid,tool.inputSchema)
        with patch.object(server, 'live_request', side_effect=AssertionError('invalid input native I/O')):
            assert asyncio.run(server.call_tool(name,invalid)).isError


@pytest.mark.parametrize('available', [False, True])
def test_additive_capabilities_do_not_relabel_accepted_solvers(available):
    result = capabilities(live_available=available)
    assert result['version'] == '0.15.4' and result['roi_isolation']['version'] == '0.15.6'
    intent = result['picked_spatial_intent']
    assert intent['version'] == '0.15.7' and intent['live'] is available
    assert intent['native_rebuild_required'] is False
    assert intent['intent_fingerprint_authorizes_reconstruction'] is False


class PickReplayHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        request = json.loads(self.rfile.readline(65536))
        self.server.requests.append(request)
        try:
            result = self.server.peer(request['method'], request.get('params', {}))
            if request['method'] == 'cloud.region_query':
                limit = request['params']['max_points']
                if limit < result['returned_count']:
                    result['points'] = result['points'][:limit]
                    result['returned_count'], result['truncated'] = limit, True
            response = {'ok':True, 'result':result}
        except (KeyError, AssertionError) as exc:
            response = {'ok':False, 'error':str(exc)}
        self.wfile.write((json.dumps(response,allow_nan=False) + '\n').encode())


def test_actual_installed_stdio_snapshot_exact_files_without_bridge(intent_files):
    assert version('cloudcompare-mcp') == '0.16.1'
    output, manifest = intent_files
    async def exercise():
        async with stdio_client(installed_stdio_parameters('invalid-no-host')) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                assert set(KINDS) <= {t.name for t in (await session.list_tools()).tools}
                for name in ('safe','transformed_safe','two_inside','parallel','near_edge','three_anchors'):
                    record = record_named(manifest,name)
                    _, args, _, _ = inputs_from_file(output,record)
                    intent = body(await session.call_tool('derive_section_roi_from_picks',args))
                    args['expected_intent_fingerprint'] = intent['intent_fingerprint']
                    a = body(await session.call_tool('analyze_picked_section_target_roi',args))
                    assert a['roi_result']['version'] == '0.15.6'
                    composite = args | {'layer_parameters':record['layer_parameters'],'profile_parameters':record['profile_parameters']}
                    r = body(await session.call_tool('reconstruct_picked_section_target_roi_profile',composite))
                    if 'stage' in record['expected']: assert r['blocked_stage'] == record['expected']['stage']
                    if 'reconstruct' in record['expected']: assert r['status'] == record['expected']['reconstruct']
                    stale = composite | {'margin':.1}
                    assert (await session.call_tool('reconstruct_picked_section_target_roi_profile',stale)).isError
    asyncio.run(asyncio.wait_for(exercise(),timeout=45))


def test_actual_installed_stdio_live_exact_files_counted_readonly_tcp_replay(intent_files):
    output, manifest = intent_files
    with ReplayServer(('127.0.0.1',0),PickReplayHandler) as transport:
        transport.requests = []
        thread = threading.Thread(target=transport.serve_forever,kwargs={'poll_interval':.05},daemon=True)
        thread.start()
        async def exercise():
            async with stdio_client(installed_stdio_parameters(transport.server_address[1])) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    async def call(tool,args,*,error=False,count=5):
                        before = len(transport.requests)
                        result = await session.call_tool(tool,args)
                        observed = transport.requests[before:]
                        assert len(observed) == count
                        if count >= 5:
                            assert sum(r['method']=='cloud.region_query' for r in observed) == 1
                            assert [observed[0]['method'], observed[-1]['method']] == ['metrology.pick.status'] * 2
                        assert bool(result.isError) is error
                        return result if error else body(result)
                    for name in ('safe','two_inside','parallel','cross_left','near_edge','alternating_thick','transformed_safe','three_anchors'):
                        record = record_named(manifest,name)
                        _, _, transport.peer, args = inputs_from_file(output,record)
                        saved = deepcopy((transport.peer.native,transport.peer.status,transport.peer.current))
                        count = 3 + len(args['pick_indices'])
                        intent = await call('derive_live_section_roi_from_picks',args,count=count)
                        args['expected_intent_fingerprint'] = intent['intent_fingerprint']
                        a = await call('analyze_live_picked_section_target_roi',args,count=count)
                        composite = args | dict(layer_parameters=record['layer_parameters'],profile_parameters=record['profile_parameters'])
                        r = await call('reconstruct_live_picked_section_target_roi_profile',composite,count=count)
                        if 'stage' in record['expected']: assert r['blocked_stage'] == record['expected']['stage']
                        if 'reconstruct' in record['expected']: assert r['status'] == record['expected']['reconstruct']
                        if name in ('two_inside','parallel','cross_left','near_edge','alternating_thick'):
                            c = a['roi_result']['target_analysis']['candidate_targets'][0]
                            chosen = composite | dict(target_id=c['target_id'],expected_target_fingerprint=c['candidate_fingerprint'])
                            explicit = await call('reconstruct_live_picked_section_target_roi_profile',chosen,count=count)
                            if name in ('cross_left','near_edge'): assert explicit['blocked_stage'] == 'roi_truncation_guard'
                            if name in ('parallel','alternating_thick'):
                                layer = explicit['roi_result']['target_result']['layer_result']['layer_analysis']
                                chosen.update(layer_id=layer['candidate_layers'][0]['layer_id'],expected_layer_fingerprint=layer['analysis_fingerprint'])
                                selected = await call('reconstruct_live_picked_section_target_roi_profile',chosen,count=count)
                                assert selected['status'] == ('candidate' if name=='parallel' else 'blocked')
                            if name=='two_inside': assert explicit['status']=='candidate'
                        await call('analyze_live_picked_section_target_roi',args|{'margin':.1},error=True,count=count)
                        await call('analyze_live_picked_section_target_roi',args|{'margin':True},error=True,count=0)
                        assert (transport.peer.native,transport.peer.status,transport.peer.current) == saved
                        first = next(iter(transport.peer.current.values()))
                        first['position_global'][0] += .001
                        await call('analyze_live_picked_section_target_roi',args,error=True,count=2)
        try:
            asyncio.run(asyncio.wait_for(exercise(),timeout=45))
        finally:
            transport.shutdown()
            thread.join(timeout=5)
        assert not thread.is_alive()
        assert all(r['method'] in ('metrology.pick.status','metrology.point_info','cloud.region_query') for r in transport.requests)
