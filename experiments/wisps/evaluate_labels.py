"""Evaluate sparse human labels, without treating unlabeled points as clean.

Labels JSON: {"input_sha256":"...", "positive":[0,1], "negative":[2,3]}.
Indices are zero-based in the original input PLY, never in a filtered copy.
"""
import argparse,json
from pathlib import Path
import numpy as np

def evaluate(predicted, positive, negative):
    pos=np.asarray(positive,dtype=int);neg=np.asarray(negative,dtype=int)
    if np.intersect1d(pos,neg).size or any(np.any((a<0)|(a>=len(predicted))) for a in [pos,neg]):
        raise ValueError('Conflicting or out-of-range labels')
    if len(np.unique(pos))!=len(pos) or len(np.unique(neg))!=len(neg):
        raise ValueError('Duplicate labels')
    return {'labeled_wisps':len(pos),'caught_wisps':int(predicted[pos].sum()),
            'labeled_surface':len(neg),'surface_points_removed':int(predicted[neg].sum()),
            'recall_on_labeled_wisps':float(predicted[pos].mean()) if len(pos) else None,
            'surface_false_positive_rate':float(predicted[neg].mean()) if len(neg) else None,
            'unlabeled_points':len(predicted)-len(pos)-len(neg)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('labels',type=Path);args=p.parse_args()
    manifest=json.loads((args.run/'manifest.json').read_text());labels=json.loads(args.labels.read_text())
    matches=[i for i,r in enumerate(manifest['records']) if r['sha256']==labels['input_sha256']]
    if len(matches)!=1: raise ValueError('Label hash must match exactly one benchmark input')
    i=matches[0];paths=list(args.run.glob(f'{i:02d}_*_labels.npz'))
    if len(paths)!=1: raise ValueError('Expected one label archive')
    print(json.dumps(evaluate(np.load(paths[0])['removed'],labels.get('positive',[]),labels.get('negative',[])),indent=2))
