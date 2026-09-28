"""Real MCP schema/dispatch/subprocess transport; replay images are not real GUI."""
import asyncio
from copy import deepcopy
from importlib.metadata import version
import json
import socketserver
import threading
from unittest.mock import patch
import jsonschema
from mcp import ClientSession
from mcp.client.stdio import stdio_client
import pytest
from cloudcompare_mcp import server, inspection_tools as tools
from cloudcompare_mcp.inspection_camera import guard
from cloudcompare_mcp.live_inspection import InspectionStore
from inspection_replay import Host
from test_live_inspection import ARGS, reviewed, answer, validate_args
from test_section_layer_tools import stdio_parameters


def parsed(result):
    content=result.content if hasattr(result,'content') else result
    return json.loads(next(c.text for c in content if c.type=='text'))

@pytest.mark.parametrize('name',tools.SCHEMAS)
def test_actual_registered_schema_dispatch(name):
    listing=asyncio.run(server.list_tools());assert len(listing)==len({t.name for t in listing})
    tool=next(t for t in listing if t.name==name)
    assert tool.annotations.destructiveHint is False
    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
    h=Host();store=InspectionStore()
    if name=='get_live_camera':args={'save':True}
    elif name=='set_live_camera':args={'action':'orbit','axis_camera':[0,1,0],'degrees':30,**guard(h.state())}
    elif name=='inspect_live_part':args=ARGS
    else:
        p,_=store.inspect(ARGS,h)
        if name=='propose_live_semantic_feature':
            args={'inspection_id':p['inspection_id'],'candidate_ids':[p['candidates'][0]['candidate_id']],
                  'semantic_role':'possible_mounting_face','question':'Is A the mounting face?',
                  'capture_indexes':[0],'visual_observations':['Agent reports review of the synthetic evidence.']}
        elif name=='release_live_inspection':args={'inspection_id':p['inspection_id'],'inspection_fingerprint':p['inspection_fingerprint']}
        else:
            pr=reviewed(store,p,h)
            args={'inspection_id':p['inspection_id'],'proposal_id':pr['proposal_id'],'expected_proposal_fingerprint':pr['proposal_fingerprint'],
                  'answer':'yes','answer_text':'Yes, A is the face.'} if name=='confirm_live_semantic_feature' else validate_args(p,answer(store,p,pr,h))
    jsonschema.validate(args,tool.inputSchema);saved=deepcopy(args)
    with patch.object(server,'live_request',side_effect=h),patch.object(tools,'STORE',store):result=asyncio.run(server.call_tool(name,args))
    assert not getattr(result,'isError',False) and args==saved and parsed(result)
    if name=='inspect_live_part':assert len([c for c in result if c.type=='image'])==2

@pytest.mark.parametrize('name',tools.SCHEMAS)
def test_actual_dispatch_invalid_schema_zero_native_io(name):
    with patch.object(server,'live_request',side_effect=AssertionError('must not query host')):
        result=asyncio.run(server.call_tool(name,{'unexpected':True}))
        assert result.isError and parsed(result)['status']=='blocked'


def test_get_live_camera_can_own_auto_pivot_suspension_only_with_save():
    h=Host()
    with patch.object(server,'live_request',side_effect=h):
        invalid=asyncio.run(server.call_tool('get_live_camera',{'save':False,'suspend_auto_pivot':True}))
        assert invalid.isError and not h.tokens and h.auto_pivot is True
        saved=parsed(asyncio.run(server.call_tool('get_live_camera',{'save':True,'suspend_auto_pivot':True})))
        assert saved['auto_pivot_suspended_by_token'] is True
        assert saved['saved_auto_pick_pivot_at_center'] is True
        assert saved['auto_pick_pivot_at_center'] is False and h.auto_pivot is False
        released=parsed(asyncio.run(server.call_tool('set_live_camera',{
            'action':'release','restore_token':saved['restore_token'],'native_session':saved['native_session']})))
        assert released['released'] and released['auto_pivot_restored_to_original'] and h.auto_pivot is True


def test_additive_capabilities_and_capture_metadata():
    h=Host()
    with patch.object(server,'live_request',side_effect=h):
        r=parsed(server.handle_get_live_workflow_capabilities({}))
        assert r['python_visual_inspection']['version']=='0.16.2' and r['python_visual_inspection']['available']
        assert r['python_section_layers']['version']=='0.15.3'
        capture=server.handle_capture_live_view({})
        assert parsed(capture)['camera_state']['contract']=='cc-camera-v1'
        assert len([c for c in capture if c.type=='image'])==1


class Peer(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        data=json.loads(self.rfile.readline(1024*1024))
        try:r={'ok':True,'result':self.server.host(data['method'],data.get('params',{}))}
        except Exception as e:r={'ok':False,'error':str(e)}
        self.wfile.write((json.dumps(r,allow_nan=False)+'\n').encode())


def test_actual_installed_stdio_full_semantic_cycle_counted_tcp():
    assert version('cloudcompare-mcp')=='0.16.2'
    h=Host();baseline=h.state();source=h.points.copy()
    with Peer(('127.0.0.1',0),Handler) as peer:
        peer.host=h;thread=threading.Thread(target=peer.serve_forever,daemon=True);thread.start()
        params=stdio_parameters(peer.server_address[1]);params.env.pop('PYTHONPATH',None)
        async def exercise():
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    assert set(tools.SCHEMAS)<={t.name for t in (await session.list_tools()).tools}
                    result=await session.call_tool('inspect_live_part',ARGS);assert not result.isError
                    p=parsed(result);assert len([c for c in result.content if c.type=='image'])==2
                    pr_args={'inspection_id':p['inspection_id'],'candidate_ids':[p['candidates'][0]['candidate_id']],
                             'semantic_role':'possible_mounting_face','question':'Is A a mounting face?',
                             'capture_indexes':[0],'visual_observations':['Test caller explicitly reviewed the replay image.']}
                    result=await session.call_tool('propose_live_semantic_feature',pr_args);assert not result.isError;pr=parsed(result)
                    result=await session.call_tool('confirm_live_semantic_feature',{'inspection_id':p['inspection_id'],
                        'proposal_id':pr['proposal_id'],'expected_proposal_fingerprint':pr['proposal_fingerprint'],
                        'answer':'yes','answer_text':'Yes.'});assert not result.isError;a=parsed(result)
                    result=await session.call_tool('validate_live_semantic_confirmation',validate_args(p,a));assert parsed(result)['fresh']
                    h.selected=[10]
                    result=await session.call_tool('validate_live_semantic_confirmation',validate_args(p,a));assert parsed(result)['status']=='stale'
                    result=await session.call_tool('release_live_inspection',{'inspection_id':p['inspection_id'],'inspection_fingerprint':p['inspection_fingerprint']})
                    assert parsed(result)['released']
                    assert not a['authorizes_reconstruction']
        try:asyncio.run(asyncio.wait_for(exercise(),timeout=45))
        finally:peer.shutdown();thread.join(timeout=5)
    assert len(h.calls)==44 and h.query_count==6 and h.capture_count==2 and not h.tokens
    assert (h.points==source).all() and guard(h.state())==guard(baseline)


def test_installed_stdio_schema_without_bridge():
    params=stdio_parameters('invalid-unavailable');params.env.pop('PYTHONPATH',None)
    async def exercise():
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                for t in (await session.list_tools()).tools:
                    if t.name in tools.SCHEMAS:jsonschema.Draft202012Validator.check_schema(t.inputSchema)
                r=await session.call_tool('inspect_live_part',{'distance_threshold':True})
                assert r.isError
                r=await session.call_tool('get_live_camera',{})
                assert r.isError
    asyncio.run(asyncio.wait_for(exercise(),timeout=30))
