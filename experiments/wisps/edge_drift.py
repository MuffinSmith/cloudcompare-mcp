"""Reversible scan-boundary drift cleanup using other scans' locked interiors.

Boundary proximity is an uncertainty cue, never sufficient reason to delete.
No scanner confidence channel is inferred: confidence here is geometric support.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from plyfile import PlyData, PlyElement
from detect_wisps import read_cloud


def tangent_frame(n):
    axis = np.eye(3)[np.argmin(abs(n), axis=1)]
    u = np.cross(n, axis)
    u /= np.maximum(np.linalg.norm(u, axis=1)[:, None], 1e-12)
    return u, np.cross(n, u)


def angular_gap(u, v, valid):
    a = np.where(valid, np.arctan2(v, u), np.inf)
    a.sort(axis=1)
    count = valid.sum(axis=1)
    last = np.where(count > 0, a[np.arange(len(a)), np.maximum(count-1, 0)], 0.)
    diff = np.zeros((len(a), a.shape[1]-1))
    np.subtract(a[:, 1:], a[:, :-1], out=diff,
                where=np.arange(a.shape[1]-1)[None] < count[:, None]-1)
    first = np.where(count > 0, a[:, 0], 0.)
    gap = np.maximum(diff.max(axis=1), 2*np.pi-last+first)
    return np.where(count >= 6, gap, 2*np.pi)


def boundary_features(p, n, band=4.):
    """Tangent angular gaps, then a bounded same-face band; computed only once."""
    tree = cKDTree(p)
    spacing = np.empty(len(p)); gaps = np.empty(len(p))
    for start in range(0, len(p), 3000):
        sl = slice(start, start+3000); x = p[sl]; normals = n[sl]
        d, ix = tree.query(x, k=min(49, len(p)), workers=4)
        d, ix = d[:, 1:], ix[:, 1:]
        s = np.median(d[:, :4], axis=1)
        delta = p[ix]-x[:, None]; u, v = tangent_frame(normals)
        a = np.einsum('nki,ni->nk', delta, u)
        b = np.einsum('nki,ni->nk', delta, v)
        compatible = np.einsum('nki,ni->nk', n[ix], normals) > .8
        g = []
        for radius in [3., 4.5]:
            valid = compatible & (d < radius*s[:, None]) & (a*a+b*b > (s[:, None]*.2)**2)
            g.append(angular_gap(a, b, valid))
        spacing[sl] = s; gaps[sl] = np.minimum(*g)
    floor = np.median(spacing[spacing > 0])
    if not np.isfinite(floor):
        raise ValueError('Nondegenerate point spacing required')
    spacing = np.clip(spacing, floor*.5, floor*2)
    boundary = gaps > np.deg2rad(135)
    distance = np.full(len(p), np.inf)
    if boundary.any():
        bp, bn = p[boundary], n[boundary]
        bt = cKDTree(bp)
        for start in range(0, len(p), 4000):
            sl = slice(start, start+4000)
            d, ix = bt.query(p[sl], k=list(range(1, min(12, len(bp))+1)), workers=4)
            compatible = np.einsum('nki,ni->nk', bn[ix], n[sl]) > .8
            distance[sl] = np.min(np.where(compatible, d, np.inf), axis=1)
    near = distance <= band*spacing
    # Fixed references and removable bands are disjoint. No mutual rim erosion.
    interior = distance > (band+2)*spacing
    return dict(spacing=spacing, boundary=boundary, angular_gap=gaps,
                edge_distance=distance, edge_band=near, interior=interior)


def patch_evidence(p, n, ref, rn, tolerance):
    """Two-scale robust quadratic interpolation inside a reference footprint."""
    residual = np.full(len(p), np.nan); uncertainty = np.full(len(p), np.nan)
    if len(ref) < 32:
        return residual, uncertainty
    tree = cKDTree(ref)
    for start in range(0, len(p), 1000):
        sl = slice(start, start+1000); x = p[sl]
        d, ix = tree.query(x, k=min(80, len(ref)), workers=4)
        ns = rn[ix]; normal = ns[:, 0]; u, v = tangent_frame(normal)
        delta = ref[ix]-x[:, None]
        a = np.einsum('nki,ni->nk', delta, u)
        b = np.einsum('nki,ni->nk', delta, v)
        z = np.einsum('nki,ni->nk', delta, normal)
        rd, _ = tree.query(ref[ix[:, 0]], k=5, workers=4)
        reference_spacing = np.median(rd[:, 1:], axis=1)
        # Surrounding angles alone can bridge a hole. Require nearby actual
        # samples in the tangent plane as well as interpolation support.
        sampled_here = np.sqrt(a[:, 0]**2+b[:, 0]**2) <= 2.5*reference_spacing
        compatible = (np.einsum('nki,ni->nk', ns, normal) > .9)
        same_face = np.einsum('ni,ni->n', normal, n[sl]) > .5
        values = []; sigmas = []; reliable = []
        for k in [32, min(64, len(ref))]:
            radius = np.maximum(d[:, k-1], 1e-9)
            valid = compatible & (d <= radius[:, None])
            gap = angular_gap(a, b, valid & (a*a+b*b > 1e-12))
            aa, bb = a/radius[:, None], b/radius[:, None]
            A = np.stack([np.ones_like(a), aa, bb, aa*aa, aa*bb, bb*bb], axis=2)
            w = valid.astype(float)
            conditioned = np.ones(len(x), bool)
            for _ in range(3):
                gram = np.einsum('nki,nk,nkj->nij', A, w, A)
                eig = np.linalg.eigvalsh(gram)
                conditioned &= eig[:, 0] > np.maximum(eig[:, -1], 1e-12)*1e-6
                rhs = np.einsum('nki,nk,nk->ni', A, w, z)
                coef = np.linalg.solve(gram+np.eye(6)[None]*1e-10, rhs[..., None])[..., 0]
                err = z-np.einsum('nki,ni->nk', A, coef)
                # Median over a finite masked array, avoiding all-NaN warnings.
                med = np.ma.median(np.ma.array(err, mask=~valid), axis=1).filled(np.nan)
                sigma = 1.4826*np.ma.median(np.ma.array(abs(err-med[:, None]), mask=~valid), axis=1).filled(np.nan)
                w = valid*np.minimum(1., np.maximum(sigma, tolerance*.08)[:, None]*2.5/np.maximum(abs(err), 1e-12))
            good = same_face & sampled_here & conditioned & (valid.sum(axis=1) >= 16) & (gap < np.deg2rad(150))
            good &= (sigma < tolerance*.35) & (radius < tolerance*12)
            values.append(coef[:, 0]); sigmas.append(sigma); reliable.append(good)
        good = reliable[0] & reliable[1] & (abs(values[0]-values[1]) < tolerance*.35)
        residual[sl] = np.where(good, (values[0]+values[1])*.5, np.nan)
        uncertainty[sl] = np.where(good, np.maximum(*sigmas), np.nan)
    return residual, uncertainty


def detect_edge_drift(clouds, tolerance=.18, band=4.):
    if len(clouds) < 2 or not np.isfinite(tolerance) or tolerance <= 0 or not np.isfinite(band) or band <= 0:
        raise ValueError('Need >=2 independent scans, positive finite tolerance and band')
    features = [boundary_features(p, n, band) for p, n in clouds]
    results = []
    for i, ((p, n), f) in enumerate(zip(clouds, features)):
        idx = np.flatnonzero(f['edge_band'])
        residuals = []; sigmas = []
        for j, ((q, qn), rf) in enumerate(zip(clouds, features)):
            if i == j:
                continue
            r, s = patch_evidence(p[idx], n[idx], q[rf['interior']], qn[rf['interior']], tolerance)
            residuals.append(r); sigmas.append(s)
        r = np.array(residuals).T; sig = np.array(sigmas).T
        known = np.isfinite(r)
        strong = known & (abs(r) > np.maximum(tolerance, 4*sig))
        marginal = known & (abs(r) > np.maximum(tolerance*.5, 3*sig))
        # Every reference with usable interior evidence must agree, including sign.
        sign_agrees = ~(np.any(known & (r > 0), axis=1) & np.any(known & (r < 0), axis=1))
        seeds = known.any(axis=1) & np.all(strong | ~known, axis=1) & sign_agrees
        eligible = known.any(axis=1) & np.all(marginal | ~known, axis=1) & sign_agrees
        trim = np.zeros(len(idx), bool)
        if seeds.any():
            d, nearest = cKDTree(p[idx[seeds]]).query(p[idx], workers=4)
            seed_normals = n[idx[seeds]][nearest]
            trim = eligible & (d <= 2*f['spacing'][idx]) & (np.einsum('ni,ni->n', n[idx], seed_normals) > .9)
        remove = np.zeros(len(p), bool); remove[idx] = seeds | trim
        f = dict(f)
        for key, value in [('coverage', known.sum(axis=1)), ('drift_seed', seeds), ('trim_fringe', trim & ~seeds)]:
            arr = np.zeros(len(p), dtype=value.dtype); arr[idx] = value; f[key] = arr
        f['query_indices'] = idx; f['reference_residuals'] = r; f['reference_sigma'] = sig
        results.append((remove, f))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tolerance', type=float, default=.18)
    parser.add_argument('--band', type=float, default=4., help='Maximum boundary-band width in local spacings')
    args = parser.parse_args()
    if len(args.inputs) < 2 or len(set(p.resolve() for p in args.inputs)) != len(args.inputs):
        parser.error('Need distinct independent captures')
    if not all(np.isfinite(x) and x > 0 for x in [args.tolerance, args.band]):
        parser.error('Positive finite tolerance and band required')
    clouds = [read_cloud(p) for p in args.inputs]
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in args.inputs]
    if len(set(hashes)) != len(hashes):
        parser.error('Duplicate scan contents are not independent captures')
    args.output.mkdir(parents=True, exist_ok=False)
    print('Computing fixed scan boundaries and interior reference patches', flush=True)
    results = detect_edge_drift([(p, n) for _, p, n in clouds], args.tolerance, args.band)
    records = []
    for i, ((v, p, n), (removed, f)) in enumerate(zip(clouds, results)):
        for suffix, data in [('after', v[~removed]), ('removed', v[removed]), ('review', v[f['edge_band'] & ~removed])]:
            out = args.output/f'{i:02d}_{suffix}.ply'
            PlyData([PlyElement.describe(data, 'vertex')], text=False).write(out)
            if not np.array_equal(PlyData.read(out)['vertex'].data, data):
                raise RuntimeError('Point-record roundtrip mismatch')
        np.savez_compressed(args.output/f'{i:02d}_labels.npz', removed=removed, **f)
        rec = dict(input=str(args.inputs[i].resolve()), sha256=hashes[i], points=len(p),
                   removed=int(removed.sum()), drift_seeds=int(f['drift_seed'].sum()),
                   fringe_trim=int(f['trim_fringe'].sum()), edge_band=int(f['edge_band'].sum()),
                   locked_interior=int(f['interior'].sum()))
        records.append(rec); print(rec, flush=True)
    source_hashes = {}
    for name in ['edge_drift.py', 'detect_wisps.py']:
        data = Path(__file__).with_name(name).read_bytes()
        (args.output/name).write_bytes(data); source_hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = dict(experimental=True, tolerance=args.tolerance, band=args.band,
                    source_hashes=source_hashes, records=records,
                    environment=dict(python=platform.python_version(), **{k: importlib.metadata.version(k) for k in ['numpy', 'scipy', 'plyfile']}))
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
