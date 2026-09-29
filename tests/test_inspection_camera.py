from copy import deepcopy
import base64
import hashlib
import math
import pytest
import numpy as np
from cloudcompare_mcp.inspection_camera import InspectionError, navigate, guard, camera_state, capture, encoded, fingerprint
VIEWS = {
    "top": ([0,0,-1],[0,1,0]), "bottom": ([0,0,1],[0,1,0]),
    "front": ([0,1,0],[0,0,1]), "back": ([0,-1,0],[0,0,1]),
    "left": ([1,0,0],[0,0,1]), "right": ([-1,0,0],[0,0,1]),
    "isometric": ([-1,-1,-1],[0,0,1]),
}
from inspection_replay import Host

@pytest.mark.parametrize('view',VIEWS)
def test_declared_views_move_restore(view):
    h=Host();start=navigate(h,{'action':'save'})
    direction,up=VIEWS[view]
    changed=navigate(h,{'action':'look','direction':direction,'up':up,**guard(start)})
    assert np.allclose(changed['parameters']['view_direction_host'],np.array(direction)/np.linalg.norm(direction))
    evidence,b64,size=capture(h,changed)
    assert evidence['png_sha256']==hashlib.sha256(base64.b64decode(b64)).hexdigest() and size>0
    restored=navigate(h,{'action':'restore','restore_token':start['restore_token'],**guard(changed)})
    assert guard(restored)==guard(start)
    navigate(h,{'action':'release','native_session':start['native_session'],'restore_token':start['restore_token']})
    assert not h.tokens

@pytest.mark.parametrize('angle',[0,37,-37,90,-90,180,-180])
def test_orbit_inverse(angle):
    h=Host();s=h.state()
    for a in [angle,-angle]:s=navigate(h,{'action':'orbit','axis_camera':[1,2,3],'degrees':a,**guard(s)})
    assert np.allclose(h.rotation,np.eye(3),atol=1e-14)

@pytest.mark.parametrize('action,values',[
 ('zoom',{'factor':True}),('zoom',{'factor':float('nan')}),('zoom',{'factor':0}),('zoom',{'factor':11}),
 ('zoom',{'factor':10**1000}),('pan',{'right_fraction':2,'up_fraction':0}),('pan',{'right_fraction':0,'up_fraction':False}),
 ('orbit',{'axis_camera':[0,0,0],'degrees':0}),('orbit',{'axis_camera':[1,0,0],'degrees':181}),
 ('look',{'direction':[0,0,0],'up':[0,1,0]}),('look',{'direction':[0,0,-1],'up':[0,1e-9,1]}),
 ('look',{'direction':[0,0,float('inf')],'up':[0,1,0]}),('look',{'direction':[True,0,-1],'up':[0,1,0]}),
 ('focus',{'entity_id':True}),('focus',{'entity_id':10,'min_global':[0,0,0],'max_global':[0,0,0]}),
 ('focus',{'entity_id':10,'min_global':[1,0,0],'max_global':[0,1,1]}),('focus',{'entity_id':10,'center_global':[0,0,0]}),
 ('focus',{'entity_id':10,'center_global':[0,0,0],'width_global':1,'min_global':[0,0,0]})])
def test_invalid_movement_has_zero_native_calls(action,values):
    h=Host();s=h.state()
    with pytest.raises(InspectionError):navigate(h,{'action':action,**guard(s),**values})
    assert h.calls==[]

@pytest.mark.parametrize('field,value',[('window_id',True),('native_session',''),('expected_camera_fingerprint','x'),('extra',0)])
def test_bad_guard_or_extra_has_zero_native_calls(field,value):
    h=Host()
    with pytest.raises(InspectionError):navigate(h,{'action':'zoom',**guard(h.state()),'factor':2,field:value})
    assert not h.calls

@pytest.mark.parametrize('scale',[.001,1,10,1e5])
def test_focus_large_global_shift_scale_pan_zoom(scale):
    points=np.array([[1e8+x,-2e8+y,3e8] for x in range(8) for y in range(8)])
    h=Host(points,[-1e8,2e8,-3e8],scale);s=h.state()
    s=navigate(h,{'action':'focus','entity_id':10,'min_global':points.min(axis=0).tolist(),'max_global':points.max(axis=0).tolist(),**guard(s)})
    assert np.allclose(h.pivot,[3.5*scale,3.5*scale,0])
    focal=h.focal
    s=navigate(h,{'action':'zoom','factor':2,**guard(s)});assert h.focal==focal/2
    c=h.center.copy();navigate(h,{'action':'pan','right_fraction':.2,'up_fraction':-.2,**guard(s)})
    assert h.center[0]>c[0] and h.center[1]<c[1]

@pytest.mark.parametrize('mutation',['camera','hash','dimension','crc','base64','not_png','contract'])
def test_capture_bad_provenance_or_bytes(mutation):
    h=Host();r=h('view.capture',{});h.calls.clear()
    if mutation=='camera':r['camera_state']['native_session']='replacement'
    if mutation=='hash':r['png_sha256']='0'*64
    if mutation=='dimension':r['width']+=1
    if mutation=='crc':
        raw=bytearray(base64.b64decode(r['png_base64']));raw[35]^=1;r['png_base64']=base64.b64encode(raw).decode();r['png_sha256']=hashlib.sha256(raw).hexdigest()
    if mutation=='base64':r['png_base64']='!!!'
    if mutation=='not_png':r['png_base64']=base64.b64encode(b'hello').decode()
    if mutation=='contract':r['capture_contract']='old'
    with pytest.raises(InspectionError):capture(lambda *a,**kw:r,h.state())

@pytest.mark.parametrize('field,value',[('object_centered',False),('perspective',1),('display_scale',[2,1]),('focal_distance',0),('camera_aspect_ratio',float('nan'))])
def test_malformed_native_state(field,value):
    s=Host().state();s['parameters'][field]=value
    with pytest.raises(InspectionError):camera_state(s)

@pytest.mark.parametrize('index,value',[(0,-1),(1,1),(12,1),(15,0),(0,True)])
def test_malformed_native_matrix(index,value):
    s=Host().state();s['parameters']['view_rotation_column_major'][index]=value
    with pytest.raises(InspectionError):camera_state(s)

def test_manual_restore_unequal_is_error_with_recovery():
    h=Host();s=h.state()
    with pytest.raises(InspectionError) as e:navigate(lambda *a,**k:s|{'restored_equal':False},{'action':'restore','restore_token':'token',**guard(s)})
    assert e.value.recovery['restore_token']=='token'

def test_fingerprints_separate_domains_and_json_limits():
    assert fingerprint('a',{'x':1})!=fingerprint('b',{'x':1})
    for v in [{'a':float('nan')},{'a':'x'*1000}]:
        with pytest.raises(InspectionError):encoded(v,100)
