"""Write deterministic ASCII double-coordinate inspection fixtures outside Git.

These exercise geometry, provenance, and host-frame numerical proxies. They are not
viewport interpretation or actual CloudCompare global shift/scale validation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def generate(output: Path) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plane = np.array([[x,y,0.] for x in range(12) for y in range(12)])
    ring = np.array([[4*np.cos(t),4*np.sin(t),0.] for t in np.linspace(0,2*np.pi,128,endpoint=False)])
    cylinder = np.array([[3*np.cos(t),3*np.sin(t),z] for z in np.linspace(-4,4,8) for t in np.linspace(0,2*np.pi,40,endpoint=False)])
    rng = np.random.default_rng(20260927)
    specs = [('plane',plane,['plane'],[0,0,0],1.),
             ('parallel_planes',np.vstack([plane,plane+[0,0,2]]),['plane'],[0,0,0],1.),
             ('ring',ring,['circle'],[0,0,0],1.),
             ('cylinder',cylinder,['cylinder'],[0,0,0],1.),
             ('shifted_plane',plane+[1e8,-2e8,3e8],['plane'],[-1e8,2e8,-3e8],1.),
             ('scaled_plane',plane+[1e8,-2e8,3e8],['plane'],[-1e8,2e8,-3e8],.01),
             ('rotated_plane',plane @ np.array([[.8,0,.6],[0,1,0],[-.6,0,.8]]).T,['plane'],[0,0,0],1.),
             ('noisy_plane',plane+rng.normal(0,.002,plane.shape),['plane'],[0,0,0],1.),
             ('clutter_plane',np.vstack([plane,rng.uniform(-5,15,(64,3))]),['plane'],[0,0,0],1.)]
    fixtures=[]
    for name,points,kinds,shift,scale in specs:
        content=('ply\nformat ascii 1.0\ncomment deterministic visual-inspection-v1\n'
                 f'element vertex {len(points)}\nproperty double x\nproperty double y\nproperty double z\nend_header\n'
                 +''.join(' '.join(format(float(v),'.17g') for v in row)+'\n' for row in points)).encode('ascii')
        path=output/(name+'.ply')
        if path.exists() and path.read_bytes()!=content:
            raise FileExistsError(f'Refusing to replace different fixture: {path}')
        path.write_bytes(content)
        fixtures.append({'name':name,'file':path.name,'sha256':hashlib.sha256(content).hexdigest(),
                         'point_count':len(points),'global_shift':shift,'global_scale':scale,'kinds':kinds,
                         'distance_threshold':.02,'coordinate_policy':'file stores global doubles; replay transforms to native-local'})
    manifest={'contract':'visual-inspection-fixtures-v1','seed':20260927,'fixtures':fixtures}
    data=json.dumps(manifest,indent=2,sort_keys=True)+'\n'
    path=output/'manifest.json'
    if path.exists() and path.read_text()!=data:raise FileExistsError('Refusing to replace different fixture manifest')
    path.write_text(data)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    args=parser.parse_args();print(json.dumps(generate(args.output),indent=2))
