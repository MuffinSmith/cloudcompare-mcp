"""Independent in-memory/TCP host double; NEVER real CloudCompare viewport evidence."""
from copy import deepcopy
import base64
import hashlib
import json
import math
import struct
import zlib
import numpy as np


def png_bytes(width=64, height=48):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress((b'\0'+b'\x80'*width*3)*height))+chunk(b'IEND',b''))


class Host:
    def __init__(self, points=None, shift=(0,0,0), scale=1.0):
        self.points = np.array(points if points is not None else [[x,y,0] for x in range(10) for y in range(10)],dtype=float)
        self.shift, self.scale = list(shift), float(scale)
        self.calls=[]; self.tokens={}; self.sequence=0; self.session='native-test-session'; self.window=3
        self.rotation=np.eye(3);self.pivot=np.zeros(3);self.center=np.array([0.,0.,10.]);self.focal=10.
        self.width,self.height=64,48;self.selected=[];self.extra=[];self.pending=False
        self.auto_pivot=True
        self.overlay={'group_id':900,'entities':[{'id':901,'name':'unrelated axis'}]}
        self.fault=None;self.capture_count=0;self.query_count=0

    def state(self):
        m=np.eye(4);m[:3,:3]=self.rotation
        p={'perspective':False,'object_centered':True,'bubble_view':False,'stereo':False,'clipping_enabled':False,
           'display_scale':[1.,1.],'pivot_host':self.pivot.tolist(),'camera_center_host':self.center.tolist(),
           'view_direction_host':(-self.rotation[2]).tolist(),'up_direction_host':self.rotation[1].tolist(),
           'focal_distance':float(self.focal),'fov_degrees':50.,'camera_aspect_ratio':1.,
           'view_rotation_column_major':m.ravel(order='F').tolist()}
        s={'contract':'cc-camera-v1','native_session':self.session,'window_id':self.window,
           'viewport_width':self.width,'viewport_height':self.height,'navigation_supported':True,'parameters':p}
        s['camera_fingerprint']=hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest()
        s['auto_pivot_contract']='cc-camera-auto-pivot-v1'
        s['auto_pick_pivot_at_center']=self.auto_pivot
        return deepcopy(s)

    def scene(self):
        source={'id':10,'name':'synthetic-source','kind':'point_cloud','visible':True,'enabled':True,
                'point_count':len(self.points),'global_shift':self.shift,'global_scale':self.scale,
                'pending_transform_in_hierarchy':self.pending,
                'bounds_global_native':{'min':self.points.min(axis=0).tolist(),'max':self.points.max(axis=0).tolist()}}
        return deepcopy({'entities':[source]+self.extra,'selected_ids':self.selected})

    def __call__(self, method, args, **kwargs):
        self.calls.append((method,deepcopy(args)))
        if self.fault:
            result=self.fault(self,method,args)
            if result is not None:return result
        if method=='scene.list':return self.scene()
        if method=='fit.overlay.status':return deepcopy(self.overlay)
        if method=='view.capture':
            self.capture_count+=1
            assert args.get('expected_camera_fingerprint',self.state()['camera_fingerprint'])==self.state()['camera_fingerprint']
            png=png_bytes(self.width,self.height)
            return {'capture_contract':'cc-viewport-capture-v1','camera_state':self.state(),
                    'png_base64':base64.b64encode(png).decode(),'width':self.width,'height':self.height,
                    'png_sha256':hashlib.sha256(png).hexdigest()}
        if method=='cloud.region_query':
            self.query_count+=1
            n=min(len(self.points),args['max_points']);indexes=np.linspace(0,len(self.points)-1,n,dtype=int)
            return {'cloud_id':10,'coordinate_space':'global','region_type':'box','source_geometry_preserved':True,
                    'matched_count':len(self.points),'returned_count':n,'truncated':n<len(self.points),
                    'sample_strategy':'deterministic_reservoir' if n<len(self.points) else 'all_matches',
                    'source_global_shift':self.shift,'source_global_scale':self.scale,
                    'points':[{'point_index':int(i),'position_global':self.points[i].tolist(),
                               'position_native_local':((self.points[i]+self.shift)*self.scale).tolist()} for i in indexes]}
        if method=='capabilities.get':return {'camera':{'available':True,'contract':'cc-camera-v1'},'region_query':{'available':True}}
        assert method=='view.camera',method
        action=args['action']
        if action=='get':return self.state()
        if action=='save':
            assert len(self.tokens)<8
            self.sequence+=1;token='saved-'+str(self.sequence)
            before=self.state();suspend=args.get('suspend_auto_pivot',False);original=self.auto_pivot
            self.tokens[token]=(before,self.rotation.copy(),self.pivot.copy(),self.center.copy(),self.focal,suspend,original)
            if suspend:self.auto_pivot=False
            return self.state()|{'restore_token':token,'auto_pivot_suspended_by_token':suspend,
                                 'saved_auto_pick_pivot_at_center':original}
        assert args['native_session']==self.session
        if action=='release':
            before,rotation,pivot,center,focal,suspend,original=self.tokens[args['restore_token']]
            result={'released':True}
            if suspend:
                external=self.auto_pivot
                if not external:self.auto_pivot=original
                result|={'auto_pivot_contract':'cc-camera-auto-pivot-v1',
                         'auto_pivot_original_enabled':original,
                         'auto_pivot_external_override_preserved':external,
                         'auto_pivot_restored_to_original':self.auto_pivot==original,
                         'auto_pivot_current_enabled':self.auto_pivot,
                         'camera_state':self.state()}
            del self.tokens[args['restore_token']];return result
        assert args['window_id']==self.window and args['expected_camera_fingerprint']==self.state()['camera_fingerprint']
        if action=='restore':
            before,rotation,pivot,center,focal,suspend,original=self.tokens[args['restore_token']]
            assert before['window_id']==self.window and before['viewport_width']==self.width and before['viewport_height']==self.height
            self.rotation,self.pivot,self.center,self.focal=rotation.copy(),pivot.copy(),center.copy(),focal
            return self.state()|{'restored_equal':self.state()['camera_fingerprint']==before['camera_fingerprint']}
        if action=='look':
            f=np.array(args['direction'],dtype=float);f/=np.linalg.norm(f)
            up=np.array(args['up'],dtype=float);up/=np.linalg.norm(up)
            right=np.cross(f,up);right/=np.linalg.norm(right);up=np.cross(right,f)
            self.rotation=np.stack([right,up,-f])
        elif action=='orbit':
            axis=np.array(args['axis_camera'],dtype=float);axis/=np.linalg.norm(axis)
            x,y,z=axis;skew=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
            a=math.radians(args['degrees']);r=np.eye(3)*math.cos(a)+(1-math.cos(a))*np.outer(axis,axis)+math.sin(a)*skew
            self.rotation=r@self.rotation
        elif action=='pan':
            span=self.focal*2*math.tan(math.radians(25))
            self.center[:2]+=[args['right_fraction']*span,args['up_fraction']*span*self.height/self.width]
        elif action=='zoom':
            self.focal/=args['factor'];self.center[2]=self.pivot[2]+self.focal
        elif action=='focus':
            assert args['entity_id']==10 and not self.pending
            lo,hi=self.points.min(axis=0),self.points.max(axis=0)
            if 'center_global' in args:center=np.array(args['center_global']);width=args['width_global']*self.scale
            else:
                lo=np.array(args.get('min_global',lo));hi=np.array(args.get('max_global',hi))
                center=lo+(hi-lo)/2;width=np.linalg.norm(hi-lo)*self.scale*1.1
            self.pivot=(center+self.shift)*self.scale;self.center=self.pivot.copy()
            self.focal=width*max(1,self.width/self.height)/(2*math.tan(math.radians(25)))
            self.center[2]+=self.focal
        else:raise AssertionError(action)
        return self.state()
