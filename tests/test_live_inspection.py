from copy import deepcopy
from unittest.mock import patch
import numpy as np
import pytest
from cloudcompare_mcp import live_inspection as mod
from cloudcompare_mcp.inspection_camera import InspectionError, guard, navigate
from inspection_replay import Host

ARGS={'distance_threshold':.02,'views':['top','isometric'],'kinds':['plane'],'sample_limit':128}


def inspected(host=None,**overrides):
    host=host or Host();store=mod.InspectionStore();packet,images=store.inspect(ARGS|overrides,host)
    return host,store,packet,images


def reviewed(store,packet,host,role='possible_mounting_face'):
    return store.propose({'inspection_id':packet['inspection_id'],'candidate_ids':[packet['candidates'][0]['candidate_id']],
                          'semantic_role':role,'question':'Is feature A a mounting face?',
                          'visual_observations':['Caller-reviewed test evidence; synthetic replay image only.'],
                          'capture_indexes':[0]},host)


def answer(store,packet,proposal,host,value='yes'):
    return store.confirm({'inspection_id':packet['inspection_id'],'proposal_id':proposal['proposal_id'],
                          'expected_proposal_fingerprint':proposal['proposal_fingerprint'],'answer':value,'answer_text':value},host)


def validate_args(packet,a):
    return {'inspection_id':packet['inspection_id'],'proposal_id':a['proposal_id'],'confirmation_fingerprint':a['confirmation_fingerprint']}


def test_actual_geometry_discovery_bounded_camera_restore_and_no_mutation():
    h=Host();before=(h.state(),h.points.copy(),h.scene(),deepcopy(h.overlay))
    h,store,p,images=inspected(h)
    assert len(images)==2 and len(p['captures'])==2 and p['candidates']
    assert p['candidates'][0]['kind']=='plane'
    assert p['camera_recovery']['status']=='restored' and not h.tokens
    assert guard(h.state())==guard(before[0]) and np.array_equal(h.points,before[1])
    assert h.scene()==before[2] and h.overlay==before[3]
    assert h.query_count==2 and h.capture_count==2
    assert p['native_calls_requested']==len(h.calls)==16
    assert sum(m=='view.camera' and a['action'] not in ('get','save','release','restore') for m,a in h.calls)==3
    assert 'points' not in p['sample_summary'] and not p['authorizes_reconstruction']
    assert all(c['requires_agent_review'] for c in p['proposals'])
    assert all(c['solver_code_sha256'] for c in p['candidates'])

@pytest.mark.parametrize('views',[['top'],['top','bottom','front'],['left','right','back','isometric']])
def test_view_budgets(views):
    h,s,p,images=inspected(views=views)
    assert len(images)==len(views) and h.query_count==2 and len(h.calls)==12+2*len(views)
    assert p['camera_recovery']['status']=='restored'

@pytest.mark.parametrize('patch_args',[
 {'distance_threshold':True},{'distance_threshold':-1},{'sample_limit':True},{'sample_limit':2049},
 {'views':[]},{'views':['top']*2},{'views':['top','bottom','left','right','front']},{'views':['mouse']},
 {'kinds':[]},{'kinds':['plane']*2},{'kinds':['mesh']},{'restore_camera':1},{'cloud_id':True},{'extra':0}])
def test_invalid_workflow_zero_io(patch_args):
    h=Host()
    with pytest.raises(InspectionError):mod.InspectionStore().inspect(ARGS|patch_args,h)
    assert h.calls==[]

@pytest.mark.parametrize('failure',['capture','query_after','restore','concurrent_camera','endpoint_after_move','scene_after','overlay_after'])
def test_failure_and_recovery_boundaries(failure,monkeypatch):
    h=Host();baseline=h.state();configured={'host':'localhost','port':8765}
    monkeypatch.setattr(mod,'endpoint',lambda:configured.copy())
    triggered=[]
    def fault(host,m,a):
        if failure=='capture' and m=='view.capture':raise RuntimeError('capture failed')
        if failure=='query_after' and m=='cloud.region_query' and host.query_count==1:raise RuntimeError('read failed')
        if failure=='restore' and m=='view.camera' and a['action']=='restore':raise RuntimeError('restore failed')
        if failure=='concurrent_camera' and m=='view.capture':host.center[0]+=1;raise RuntimeError('human camera move')
        if failure=='endpoint_after_move' and m=='view.capture':configured['port']=9999;raise RuntimeError('endpoint changed')
        if failure=='scene_after' and m=='cloud.region_query' and host.query_count==1:host.selected=[10]
        if failure=='overlay_after' and m=='cloud.region_query' and host.query_count==1:host.overlay['entities'].append({'id':902})
    h.fault=fault
    with pytest.raises(InspectionError) as e:mod.InspectionStore().inspect(ARGS,h)
    assert e.value.recovery
    if failure in ('capture','query_after','scene_after','overlay_after'):
        assert e.value.recovery['status']=='restored' and guard(h.state())==guard(baseline) and not h.tokens
    else:
        assert e.value.recovery['status']=='not_restored' and h.tokens
        assert 'restore_token' in e.value.recovery['baseline']


def test_retain_then_explicit_restore_and_release():
    h,s,p,_=inspected(restore_camera=False)
    r=p['camera_recovery'];assert r['status']=='retained_by_request' and len(h.tokens)==1
    navigate(h,{'action':'restore','restore_token':r['baseline']['restore_token'],**guard(h.state())})
    navigate(h,{'action':'release','restore_token':r['baseline']['restore_token'],'native_session':r['baseline']['native_session']})
    out=s.release({'inspection_id':p['inspection_id'],'inspection_fingerprint':p['inspection_fingerprint']})
    assert out['released'] and not s.records and not h.tokens


def test_release_does_not_touch_native_camera_or_unrelated_inspection():
    h,s,p,_=inspected();q,_=s.inspect(ARGS,h);n=len(h.calls)
    with pytest.raises(InspectionError):s.release({'inspection_id':p['inspection_id'],'inspection_fingerprint':'0'*64})
    s.release({'inspection_id':p['inspection_id'],'inspection_fingerprint':p['inspection_fingerprint']})
    assert len(h.calls)==n and list(s.records)==[q['inspection_id']]


def test_only_one_source_or_explicit_id_no_largest_guess():
    h=Host();other=h.scene()['entities'][0];other['id']=11;h.extra=[other]
    with pytest.raises(InspectionError) as e:mod.InspectionStore().inspect(ARGS,h)
    assert len(e.value.recovery['source_candidates'])==2 and not h.tokens and h.capture_count==0
    assert not any(m=='view.camera' and a['action']=='save' for m,a in h.calls)
    assert inspected(h,cloud_id=10)[2]['source']['id']==10


def test_managed_overlay_source_is_excluded():
    h=Host();overlay=h.scene()['entities'][0];overlay['id']=901
    h.extra=[{'id':900,'kind':'group','enabled':True,'visible':True,'children':[overlay]}]
    assert inspected(h)[2]['source']['id']==10

@pytest.mark.parametrize('flag',['pending','invisible','ancestor_disabled','mesh_vertices'])
def test_ineligible_source_does_not_move(flag):
    h=Host()
    if flag=='pending':h.pending=True
    else:
        original=h.scene
        def scene():
            result=original();source=result['entities'][0]
            if flag=='invisible':source['visible']=False
            else:result['entities']=[{'id':20,'kind':'mesh' if flag=='mesh_vertices' else 'group','visible':True,'enabled':flag=='mesh_vertices','children':[source]}]
            return result
        h.scene=scene
    with pytest.raises(InspectionError):mod.InspectionStore().inspect(ARGS,h)
    assert not h.tokens and h.capture_count==0

@pytest.mark.parametrize('scale',[.01,1.,100.])
def test_shifted_scaled_actual_fitting(scale):
    points=np.array([[1e8+x,-2e8+y,3e8] for x in range(10) for y in range(10)])
    h=Host(points,[-1e8,2e8,-3e8],scale)
    h,s,p,_=inspected(h)
    assert p['candidates'] and p['source']['global_scale']==scale and p['camera_recovery']['status']=='restored'
    assert h.query_count==2

@pytest.mark.parametrize('kind',['circle','cylinder'])
def test_accepted_nonplane_discoveries_are_called_once(kind):
    if kind=='circle':points=[[5*np.cos(a),5*np.sin(a),0] for a in np.linspace(0,2*np.pi,100,endpoint=False)]
    else:points=[[3*np.cos(a),3*np.sin(a),z] for z in np.linspace(-4,4,8) for a in np.linspace(0,2*np.pi,32,endpoint=False)]
    h,s,p,_=inspected(Host(points),kinds=[kind],sample_limit=512)
    assert p['discovery'][0]['kind']==kind and len(p['discovery'])==1
    assert p['candidates'] and all(c['kind']==kind for c in p['candidates']) and h.query_count==2


def test_fit_refusal_is_not_retried_or_promoted_to_semantic_evidence():
    with patch.object(mod.feature_discovery,'discover_planes',side_effect=mod.feature_fit.FeatureFitError('fixed failure')) as fn:
        h,s,p,_=inspected()
    assert fn.call_count==1 and not p['candidates'] and p['discovery'][0]['status']=='refused'
    assert not p['proposals'] and p['camera_recovery']['status']=='restored'


def test_inspection_cache_budget_zero_io_when_full(monkeypatch):
    monkeypatch.setitem(mod.LIMITS,'cached_inspections',1)
    h,s,p,_=inspected();h.calls.clear()
    with pytest.raises(InspectionError):s.inspect(ARGS,h)
    assert not h.calls


def test_metadata_size_failure_retains_recovery_token(monkeypatch):
    real=mod.encoded
    def small(value,*a,**k):
        if isinstance(value,dict) and value.get('contract')=='live-inspection-v1':raise InspectionError('packet size')
        return real(value,*a,**k)
    monkeypatch.setattr(mod,'encoded',small)
    h=Host()
    with pytest.raises(InspectionError) as e:mod.InspectionStore().inspect(ARGS|{'restore_camera':False},h)
    assert e.value.recovery['status']=='retained_by_request' and len(h.tokens)==1


def test_draft_cannot_be_confirmed_and_returned_packet_cannot_rewrite_evidence():
    h,s,p,_=inspected();draft=p['proposals'][0]
    with pytest.raises(InspectionError):answer(s,p,draft,h)
    p['candidates'][0]['candidate_fingerprint']='0'*64
    proposal=reviewed(s,p,h)
    assert proposal['candidate_fingerprints'][0]!='0'*64

@pytest.mark.parametrize('value,status',[('yes','confirmed'),('no','rejected'),('unsure','uncertain')])
def test_explicit_answer_binds_exact_issued_evidence(value,status):
    h,s,p,_=inspected();proposal=reviewed(s,p,h);n=len(h.calls)
    a=answer(s,p,proposal,h,value)
    assert a['status']==status and a['answer_text']==value and a['proposal_fingerprint']==proposal['proposal_fingerprint']
    assert len(h.calls)-n==7 and not a['authorizes_reconstruction']
    r=s.validate(validate_args(p,a),h)
    assert r['fresh'] and r['semantic_intent_usable']==(value=='yes')

@pytest.mark.parametrize('change',['points','selection','overlay','shift','scale','session','window','bounds','source_hidden','endpoint'])
def test_confirmations_stale_on_observed_change_and_stay_stale(change,monkeypatch):
    h,s,p,_=inspected();proposal=reviewed(s,p,h);a=answer(s,p,proposal,h)
    saved=deepcopy(h.__dict__)
    if change=='points':h.points[45,2]=.1
    if change=='selection':h.selected=[10]
    if change=='overlay':h.overlay['entities'][0]['name']='changed'
    if change=='shift':h.shift[0]+=1
    if change=='scale':h.scale*=2
    if change=='session':h.session='new-session'
    if change=='window':h.window+=1
    if change=='bounds':h.points[-1,0]+=1
    if change=='source_hidden':
        original=h.scene
        def scene():
            v=original();v['entities'][0]['visible']=False;return v
        h.scene=scene
    old_endpoint=mod.endpoint
    if change=='endpoint':monkeypatch.setattr(mod,'endpoint',lambda:{'host':'changed','port':8765})
    assert s.validate(validate_args(p,a),h)['status']=='stale'
    h.__dict__.clear();h.__dict__.update(saved)
    if change=='endpoint':monkeypatch.setattr(mod,'endpoint',old_endpoint)
    assert s.validate(validate_args(p,a),h)['status']=='stale'


def test_camera_pose_change_alone_does_not_rewrite_frozen_capture_or_stale_intent():
    h,s,p,_=inspected();proposal=reviewed(s,p,h);a=answer(s,p,proposal,h)
    navigate(h,{'action':'orbit','axis_camera':[0,1,0],'degrees':30,**guard(h.state())})
    assert s.validate(validate_args(p,a),h)['fresh']
    assert proposal['capture_fingerprints']==[p['captures'][0]['capture_fingerprint']]


def test_offsample_geometry_not_claimed_detected():
    points=np.array([[x,y,0] for x in range(30) for y in range(30)])
    h,s,p,_=inspected(Host(points),sample_limit=64);proposal=reviewed(s,p,h);a=answer(s,p,proposal,h)
    sampled=set(np.linspace(0,len(points)-1,64,dtype=int));index=next(i for i in range(31,850) if i not in sampled)
    h.points[index,0]+=.01
    assert s.validate(validate_args(p,a),h)['fresh']
    assert any('not unobserved whole-cloud' in x for x in p['limitations'])


def test_superseded_confirmation_and_fingerprint_tampering():
    h,s,p,_=inspected();proposal=reviewed(s,p,h);a=answer(s,p,proposal,h)
    wrong=deepcopy(proposal);wrong['proposal_fingerprint']='0'*64
    with pytest.raises(InspectionError):answer(s,p,wrong,h)
    b=answer(s,p,proposal,h,'no')
    assert s.validate(validate_args(p,a),h)['status']=='unknown_or_superseded'
    assert s.validate(validate_args(p,b),h)['status']=='rejected'


def test_overlapping_conflicting_roles_require_review():
    h,s,p,_=inspected();pa=reviewed(s,p,h);a=answer(s,p,pa,h)
    pb=reviewed(s,p,h,'possible_scan_clutter');b=answer(s,p,pb,h)
    assert b['semantic_review_required'] and not b['semantic_intent_usable']
    assert s.validate(validate_args(p,a),h)['semantic_review_required']
    answer(s,p,pb,h,'no')
    assert s.validate(validate_args(p,a),h)['semantic_intent_usable']

@pytest.mark.parametrize('patch_args',[{'answer':True},{'answer':'maybe'},{'answer_text':''},{'answer_text':'x'*2049},{'expected_proposal_fingerprint':'bad'}])
def test_bad_answers_do_not_query_native(patch_args):
    h,s,p,_=inspected();pr=reviewed(s,p,h);h.calls.clear()
    args={'inspection_id':p['inspection_id'],'proposal_id':pr['proposal_id'],'expected_proposal_fingerprint':pr['proposal_fingerprint'],'answer':'yes','answer_text':'yes'}|patch_args
    with pytest.raises(InspectionError):s.confirm(args,h)
    assert not h.calls


def test_proposal_budget_and_restart_unknown(monkeypatch):
    h,s,p,_=inspected();monkeypatch.setitem(mod.LIMITS,'proposals_per_inspection',len(p['proposals']))
    with pytest.raises(InspectionError):reviewed(s,p,h)
    with pytest.raises(InspectionError):mod.InspectionStore()._record(p['inspection_id'])
