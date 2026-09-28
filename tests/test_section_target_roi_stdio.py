"""Actual installed MCP stdio with exact PLY inputs; TCP is replay, not a GUI."""
import asyncio
from copy import deepcopy
from importlib.metadata import version
import threading

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from cloudcompare_mcp.section_target_roi_tools import KINDS
from test_section_layer_tools import body, stdio_parameters, ReplayServer, ReplayHandler
from test_section_target_roi_fixtures import roi_files, record_named, snapshot_from_file, native_from_file


def installed_stdio_parameters(port):
    params = stdio_parameters(port)
    params.env.pop('PYTHONPATH', None)  # Exercise the installed package, not source-path injection.
    return params


def test_actual_roi_stdio_installed_snapshot_fixtures_with_bridge_unavailable(roi_files):
    assert version('cloudcompare-mcp') == '0.16.0'
    output, manifest = roi_files

    async def run():
        async with stdio_client(installed_stdio_parameters('invalid-no-host')) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert set(KINDS) <= {t.name for t in (await session.list_tools()).tools}
                for name in ('outside_clutter', 'transformed_safe', 'half_open', 'two_inside'):
                    record = record_named(manifest, name)
                    _, args = snapshot_from_file(output, record)
                    a = body(await session.call_tool('analyze_section_target_roi', args))
                    assert a['version'] == '0.15.6' and not a['live_connection_used']
                    assert a['point_accounting']['inside_roi_point_count'] == record['expected']['inside']
                    composite = args | {'layer_parameters': record['layer_parameters'], 'profile_parameters': record['profile_parameters']}
                    r = body(await session.call_tool('reconstruct_section_target_roi_profile', composite))
                    if name in ('outside_clutter', 'transformed_safe'):
                        assert r['status'] == 'candidate'
                        assert r['target_result']['layer_result']['profile']['topology']['loop_count'] == 1
                    if name == 'two_inside':
                        assert r['blocked_stage'] == 'target_selection'
                        c = a['target_analysis']['candidate_targets'][1]
                        chosen = composite | {'target_id': c['target_id'], 'expected_target_fingerprint': c['candidate_fingerprint']}
                        assert body(await session.call_tool('reconstruct_section_target_roi_profile', chosen))['status'] == 'candidate'
                        chosen['expected_target_fingerprint'] = a['roi_fingerprint']
                        assert (await session.call_tool('reconstruct_section_target_roi_profile', chosen)).isError
                    bad = deepcopy(args)
                    bad['section']['acquisition_complete'] = False
                    assert (await session.call_tool('analyze_section_target_roi', bad)).isError
    asyncio.run(asyncio.wait_for(run(), timeout=45))


def test_actual_roi_stdio_live_one_query_per_call_guard_layer_and_truncation(roi_files):
    output, manifest = roi_files
    with ReplayServer(('127.0.0.1', 0), ReplayHandler) as peer:
        peer.requests = []
        thread = threading.Thread(target=peer.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        thread.start()

        async def run():
            async with stdio_client(installed_stdio_parameters(peer.server_address[1])) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def call(name, args, *, error=False, queries=1):
                        before = len(peer.requests)
                        r = await session.call_tool(name, args)
                        assert len(peer.requests) == before + queries
                        assert bool(r.isError) is error
                        return r if error else body(r)

                    for name in ('one_of_two', 'cross_left', 'transformed_safe', 'parallel', 'two_inside', 'alternating_thick', 'overlap'):
                        record = record_named(manifest, name)
                        peer.native = native_from_file(output, record)
                        saved = deepcopy(peer.native)
                        args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters', 'roi')}
                        args['cloud_id'] = 359
                        a = await call('analyze_live_section_target_roi', args)
                        assert a['source_coordinate_bookkeeping']['global_scale'] == 2.5
                        assert not a['source_coordinate_bookkeeping']['shift_scale_reapplied']
                        composite = args | {'layer_parameters': record['layer_parameters'], 'profile_parameters': record['profile_parameters']}
                        r = await call('reconstruct_live_section_target_roi_profile', composite)
                        if 'stage' in record['expected']:
                            assert r['blocked_stage'] == record['expected']['stage']
                        if name in ('one_of_two', 'transformed_safe'):
                            assert r['status'] == 'candidate'
                        c = a['target_analysis']['candidate_targets'][0]
                        chosen = composite | {'target_id': c['target_id'], 'expected_target_fingerprint': c['candidate_fingerprint']}
                        if name == 'cross_left':
                            refused = await call('reconstruct_live_section_target_roi_profile', chosen)
                            assert refused['blocked_stage'] == 'roi_truncation_guard'
                            assert refused['point_accounting']['total_unselected_point_count'] == record['point_count']
                        if name == 'parallel':
                            # Explicit target selection changes upstream selection context.
                            # Obtain its own layer evidence before selecting that layer.
                            explicit_target = await call('reconstruct_live_section_target_roi_profile', chosen)
                            layer = explicit_target['target_result']['layer_result']['layer_analysis']
                            chosen.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
                            selected = await call('reconstruct_live_section_target_roi_profile', chosen)
                            assert selected['status'] == 'candidate'
                            assert selected['point_accounting']['selected_layer_point_count'] == 1200
                        if name == 'two_inside':
                            assert (await call('reconstruct_live_section_target_roi_profile', chosen))['status'] == 'candidate'
                        if name == 'overlap':
                            assert (await call('reconstruct_live_section_target_roi_profile', chosen))['blocked_stage'] == 'target_selection'
                        stale = deepcopy(chosen)
                        stale['roi']['u_min'] -= .01
                        await call('reconstruct_live_section_target_roi_profile', stale, error=True)
                        assert peer.native == saved
                    record = record_named(manifest, 'one_of_two')
                    peer.native = native_from_file(output, record)
                    args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters', 'roi')}
                    args = deepcopy(args) | {'cloud_id': 359}
                    args['target_parameters']['max_points'] = 100
                    await call('analyze_live_section_target_roi', args, error=True)
                    args['roi']['u_min'] = True
                    await call('analyze_live_section_target_roi', args, error=True, queries=0)
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=45))
        finally:
            peer.shutdown()
            thread.join(timeout=5)
        assert not thread.is_alive()
        assert all(r['method'] == 'cloud.region_query' for r in peer.requests)
