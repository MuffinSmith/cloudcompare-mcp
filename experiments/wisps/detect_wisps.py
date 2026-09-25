"""Experimental, reversible multi-scan wisp detector. Coordinates are never moved.

Run with --help. Requires aligned point-only PLYs containing x/y/z and nx/ny/nz.
No part-specific axes, circles, regions, or manually selected point indices are used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import warnings
import platform
import importlib.metadata
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from plyfile import PlyData, PlyElement


def local_features(p, k=24):
    tree = cKDTree(p)
    scale = np.empty(len(p)); linear = np.empty(len(p)); rough = np.empty(len(p))
    for start in range(0, len(p), 4000):
        x = p[start:start+4000]
        d, ix = tree.query(x, k=min(k+1, len(p)), workers=4)
        q = p[ix[:, 1:]]; q = q-q.mean(axis=1)[:, None]
        e = np.linalg.eigvalsh(np.einsum('nki,nkj->nij', q, q)/q.shape[1])
        scale[start:start+len(x)] = np.median(d[:, 1:5], axis=1)
        linear[start:start+len(x)] = 1-e[:, 1]/np.maximum(e[:, 2], 1e-15)
        rough[start:start+len(x)] = e[:, 0]/np.maximum(e.sum(axis=1), 1e-15)
    _, near = tree.query(p, k=min(25, len(p)), workers=4)
    density_ratio = scale/np.maximum(np.median(scale[near[:, 1:]], axis=1), 1e-12)
    return scale, linear, rough, density_ratio


def reference_evidence(p, ref, normals, scale, tolerance):
    """Fit local, similarly oriented reference observations at two radii.

    A point's own potentially corrupted normal does not choose the reference face.
    Multiple faces near a corner veto rejection when any face supports the point.
    Missing coverage is explicitly unknown, never evidence for removal.
    """
    tree = cKDTree(ref)
    confirmed = np.zeros(len(p), bool); supported = np.zeros(len(p), bool)
    severity = np.zeros(len(p)); count = np.zeros(len(p), np.int32)
    for start in range(0, len(p), 2500):
        x = p[start:start+2500]; sc = scale[start:start+len(x)]
        d, ix = tree.query(x, k=min(64, len(ref)), workers=4)
        ns = normals[ix]; delta = ref[ix]-x[:, None]
        reliable_any = np.zeros(len(x), bool); supported_any = np.zeros(len(x), bool)
        rejected_votes = np.zeros(len(x), int); max_score = np.zeros(len(x))
        # Different seeds handle top/side/bottom faces without averaging them together.
        for seed in [0, 8, 24]:
            if seed >= ix.shape[1]:
                continue
            direction = ns[:, seed]
            orient = np.einsum('nki,ni->nk', ns, direction) > .92
            scale_votes = np.zeros(len(x), int)
            for radius_factor in [6, 10]:
                radius = np.maximum(radius_factor*sc, tolerance*4)
                valid = orient & (d < radius[:, None])
                num = valid.sum(axis=1)
                avg = np.einsum('nk,nki->ni', valid, ns)
                avg /= np.maximum(np.linalg.norm(avg, axis=1)[:, None], 1e-12)
                offset = np.einsum('nki,ni->nk', delta, avg)
                offset[~valid] = np.nan
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', RuntimeWarning)
                    median = np.nanmedian(offset, axis=1)
                    sigma = 1.4826*np.nanmedian(abs(offset-median[:, None]), axis=1)
                # A curved/poorly aligned reference patch is not a reliable plane.
                reliable = (num >= 10) & (sigma < tolerance*.65)
                threshold = np.maximum(tolerance, 4*sigma)
                reliable_any |= reliable
                supported_any |= reliable & (abs(median) <= threshold)
                scale_votes += reliable & (abs(median) > threshold)
                max_score = np.maximum(max_score, np.where(reliable, abs(median)/threshold, 0))
            rejected_votes += scale_votes == 2
        sl = slice(start, start+len(x))
        confirmed[sl] = (rejected_votes > 0) & ~supported_any
        supported[sl] = reliable_any
        severity[sl] = max_score
        count[sl] = rejected_votes
    return confirmed, supported, severity, count


def detect(p, references, tolerance=.15, max_component=200):
    spacing, linear, rough, density_ratio = local_features(p)
    valid_spacing = spacing[spacing>0]
    global_scale = float(np.median(valid_spacing))
    spacing = np.clip(spacing, global_scale*.5, global_scale*2)
    votes = np.zeros(len(p), int); coverage = np.zeros(len(p), int)
    severity = np.zeros(len(p))
    for ref, normals in references:
        bad, seen, score, _ = reference_evidence(p, ref, normals, spacing, tolerance)
        votes += bad; coverage += seen; severity = np.maximum(severity, score)
    # At least one independent capture must contradict a point. A capture with
    # reliable supporting geometry vetoes it. Agreement of missing views is not used.
    candidate = (votes > 0) & (votes == coverage)
    # Geometry-only line/roughness evidence is a review cue, not a deletion rule:
    # genuine narrow rims also have line-like neighborhoods.
    remove = np.zeros(len(p), bool); component_id = np.full(len(p), -1, np.int32)
    ix = np.flatnonzero(candidate)
    if len(ix):
        pairs = cKDTree(p[ix]).query_pairs(global_scale*4, output_type='ndarray')
        graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(ix), len(ix)))
        n, labels = connected_components(graph, directed=False)
        sizes = np.bincount(labels); component_id[ix] = labels
        # Large patches can indicate registration error or legitimate thin detail.
        seed = (density_ratio[ix] > 1.5) & (severity[ix] > 2) & (votes[ix] >= min(2,len(references)))
        seeded = np.bincount(labels, weights=seed, minlength=n)>0
        eligible = (sizes[labels] <= max_component) & seeded[labels]
        remove[ix[eligible]] = True
    return remove, {'candidate': candidate, 'coverage': coverage, 'votes': votes,
                    'severity': severity, 'linearity': linear, 'roughness': rough,
                    'component': component_id, 'spacing': spacing, 'density_ratio': density_ratio}


def read_cloud(path):
    ply = PlyData.read(path)
    if len(ply.elements) != 1 or ply.elements[0].name != 'vertex':
        raise ValueError(f'{path}: point-only PLY required; meshes are not supported')
    v = ply['vertex'].data
    p = np.column_stack([v[k] for k in ('x', 'y', 'z')]).astype(float)
    n = np.column_stack([v[k] for k in ('nx', 'ny', 'nz')]).astype(float)
    if len(p)<65 or not np.isfinite(p).all() or not np.isfinite(n).all():
        raise ValueError('Need >=65 finite points and finite normals')
    lengths = np.linalg.norm(n, axis=1)
    if np.any(lengths<1e-10):
        raise ValueError('Zero normals are unsupported')
    return v, p, n/lengths[:, None]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--tolerance', type=float, default=.15, help='Residual floor in native scan units; must exceed alignment uncertainty')
    parser.add_argument('--max-component', type=int, default=200)
    args = parser.parse_args()
    if len(args.inputs)<2 or not np.isfinite(args.tolerance) or args.tolerance<=0 or args.max_component<1:
        parser.error('Need >=2 aligned scans, positive tolerance and component size')
    if len({p.resolve() for p in args.inputs}) != len(args.inputs):
        parser.error('Inputs must be distinct independent captures')
    # Never silently overwrite a previous benchmark or a source scan.
    args.output.mkdir(parents=True, exist_ok=False)
    clouds = [read_cloud(p) for p in args.inputs]; records=[]
    for i, (path, (v, p, n)) in enumerate(zip(args.inputs, clouds)):
        print('Analyzing', path.name, flush=True)
        mask, features = detect(p, [(q, qn) for j, (_, q, qn) in enumerate(clouds) if j!=i], args.tolerance, args.max_component)
        stem=f'{i:02d}_{path.stem}'
        for suffix, data in [('after', v[~mask]), ('removed', v[mask]),
                             ('review',v[features['candidate']&~mask])]:
            target=args.output/f'{stem}_{suffix}.ply'
            PlyData([PlyElement.describe(data, 'vertex')], text=False).write(target)
            assert np.array_equal(PlyData.read(target)['vertex'].data, data)
        np.savez_compressed(args.output/f'{stem}_labels.npz', removed=mask, **features)
        record={'input':str(path.resolve()), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'points':len(v), 'removed':int(mask.sum()), 'review_only':int((features['candidate']&~mask).sum()),
                'output':str((args.output/f'{stem}_after.ply').resolve())}
        records.append(record);print(record, flush=True)
    source=Path(__file__).read_bytes()
    (args.output/'detector-snapshot.py').write_bytes(source)
    (args.output/'manifest.json').write_text(json.dumps({'experimental':True,
        'detector_sha256':hashlib.sha256(source).hexdigest(),
        'environment':{'python':platform.python_version(),**{k:importlib.metadata.version(k) for k in ['numpy','scipy','plyfile']}},
        'parameters':vars(args)|{'inputs':[str(p) for p in args.inputs],'output':str(args.output)},'records':records},indent=2,default=str))

if __name__ == '__main__':
    main()
