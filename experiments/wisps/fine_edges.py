"""Optional fine edge pass using outward-facing surface normals.

Requires three aligned scans with consistently outward-oriented normals. A flat
face cannot veto evidence that a point lies outside the adjacent side wall.
Missing coverage is unknown. Retained point records are never moved.
"""
import argparse, hashlib, json, warnings, platform, importlib.metadata
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from plyfile import PlyData,PlyElement
from detect_wisps import local_features,read_cloud


def exterior_evidence(p, ref, normals, spacing, tolerance):
    tree=cKDTree(ref);outside=np.zeros(len(p),bool);known=np.zeros(len(p),bool)
    strength=np.zeros(len(p))
    for start in range(0,len(p),2000):
        x=p[start:start+2000];sc=spacing[start:start+len(x)]
        d,ix=tree.query(x,k=min(96,len(ref)),workers=4);delta=ref[ix]-x[:,None];ns=normals[ix]
        any_out=np.zeros(len(x),bool);any_known=np.zeros(len(x),bool);score=np.zeros(len(x))
        for seed in [0,4,12,28,52]:
            if seed>=ix.shape[1]:continue
            orient=np.einsum('nki,ni->nk',ns,ns[:,seed])>.97
            both=np.ones(len(x),bool)
            for factor in [3,5]:
                radius=np.maximum(factor*sc,tolerance*4)
                valid=orient&(d<radius[:,None]);num=valid.sum(axis=1)
                avg=np.einsum('nk,nki->ni',valid,ns);avg/=np.maximum(np.linalg.norm(avg,axis=1)[:,None],1e-12)
                center=np.einsum('nk,nki->ni',valid,delta)/np.maximum(num[:,None],1)
                tangential=center-np.einsum('ni,ni->n',center,avg)[:,None]*avg
                offset=np.einsum('nki,ni->nk',delta,avg);offset[~valid]=np.nan
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',RuntimeWarning)
                    med=np.nanmedian(offset,axis=1);sigma=1.4826*np.nanmedian(abs(offset-med[:,None]),axis=1)
                reliable=(num>=8)&(sigma<tolerance*.5)&(np.linalg.norm(tangential,axis=1)<radius*.6)
                threshold=np.maximum(tolerance,4*sigma)
                both&=reliable&(-med>threshold)
                any_known|=reliable
                score=np.maximum(score,np.where(reliable,-med/threshold,0))
            any_out|=both
        sl=slice(start,start+len(x));outside[sl]=any_out;known[sl]=any_known;strength[sl]=score
    return outside,known,strength


def detect_fine_edges(p,references,tolerance=.10):
    if len(references)<2:raise ValueError('Fine edges require two independent reference scans')
    if not np.isfinite(tolerance) or tolerance<=0:raise ValueError('Positive finite tolerance required')
    spacing,_,_,density=local_features(p);s=float(np.median(spacing[spacing>0]));spacing=np.clip(spacing,s*.5,s*2)
    votes=np.zeros(len(p),int);coverage=np.zeros(len(p),int);strength=np.zeros(len(p))
    for ref,n in references:
        out,seen,score=exterior_evidence(p,ref,n,spacing,tolerance)
        votes+=out;coverage+=seen;strength=np.maximum(strength,score)
    candidate=(votes>=2)&(votes==coverage)
    remove=np.zeros(len(p),bool);idx=np.flatnonzero(candidate)
    if len(idx):
        pairs=cKDTree(p[idx]).query_pairs(3*s,output_type='ndarray')
        graph=coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(idx),len(idx)))
        _,label=connected_components(graph,directed=False);size=np.bincount(label)
        # Pointwise density gate: no growth of a seed into a whole rim or surface.
        remove[idx]=(size[label]<=40)&(density[idx]>1.15)
    return remove,{'candidate':candidate,'votes':votes,'coverage':coverage,'density_ratio':density,'severity':strength}


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('inputs',type=Path,nargs='+');a.add_argument('--output',type=Path,required=True);a.add_argument('--tolerance',type=float,default=.10);args=a.parse_args()
    if len(args.inputs)<3 or len({p.resolve() for p in args.inputs})!=len(args.inputs):a.error('At least three distinct independent scans required')
    if not np.isfinite(args.tolerance) or args.tolerance<=0:a.error('Positive finite tolerance required')
    clouds=[read_cloud(p) for p in args.inputs];args.output.mkdir(parents=True,exist_ok=False);records=[]
    for i,(path,(v,p,n)) in enumerate(zip(args.inputs,clouds)):
        print('Fine edges:',path.name,flush=True)
        mask,features=detect_fine_edges(p,[(q,qn) for j,(_,q,qn) in enumerate(clouds) if j!=i],args.tolerance)
        for suffix,data in [('after',v[~mask]),('removed',v[mask]),('review',v[features['candidate']&~mask])]:
            target=args.output/f'{i:02d}_{suffix}.ply';PlyData([PlyElement.describe(data,'vertex')],text=False).write(target)
            assert np.array_equal(PlyData.read(target)['vertex'].data,data)
        np.savez_compressed(args.output/f'{i:02d}_labels.npz',removed=mask,**features)
        rec={'input':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'points':len(v),'removed':int(mask.sum()),'review_only':int((features['candidate']&~mask).sum())};records.append(rec);print(rec,flush=True)
    source_hashes={}
    for name in ['fine_edges.py','detect_wisps.py']:
        source=Path(__file__).with_name(name).read_bytes();(args.output/name).write_bytes(source)
        source_hashes[name]=hashlib.sha256(source).hexdigest()
    (args.output/'manifest.json').write_text(json.dumps({'experimental':True,'tolerance':args.tolerance,
        'source_hashes':source_hashes,'environment':{'python':platform.python_version(),
        **{k:importlib.metadata.version(k) for k in ['numpy','scipy','plyfile']}},'records':records},indent=2))

if __name__=='__main__':main()
