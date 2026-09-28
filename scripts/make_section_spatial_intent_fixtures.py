"""Generate fixed deliberate-pick PLY fixtures OUTSIDE Git, never from the real fan.

Usage: python scripts/make_section_spatial_intent_fixtures.py /absolute/new/directory
Each PLY includes the actual anchor vertices, outside the fixed section slab in depth.
Their declared UV boundary role is independent of target or reconstruction quality.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('accepted_roi_fixture_io',
    Path(__file__).with_name('make_section_target_roi_fixtures.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROOT = base.ROOT
read_fixture_xyz = base.read_fixture_xyz
NAMES = ('safe', 'outside_clutter', 'one_of_two', 'two_inside', 'cross_left', 'cross_right',
         'cross_bottom', 'cross_top', 'narrow_bridge', 'parallel', 'overlap', 'alternating_thick',
         'sparse', 'transformed_safe', 'transformed_parallel', 'fan_like', 'near_edge', 'three_anchors')


def generate(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Generated fixtures must remain outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    cases = {c[0]: c for c in base.generated_cases()}
    records = []
    for name in NAMES:
        _, xyz, origin, normal, bounds, expected, options = cases.get(name, cases['safe'])
        bounds, expected = deepcopy(bounds), deepcopy(expected)
        if name == 'near_edge':
            bounds['u_min'] = -.5  # Fixed distance < one UV-cell guard; not tuned by fitting.
            expected = {'inside': 1200, 'edge': 'left', 'stage': 'roi_truncation_guard'}
        projection = base.io.project_points_to_section(xyz, origin, normal)
        frame = {k: projection[v] for k, v in [('origin_global','origin'), ('normal','normal'),
                                               ('basis_u','basis_u'), ('basis_v','basis_v')]}
        frame['frame_id'] = 'declared-' + name
        uvd = np.array([[bounds['u_min'], bounds['v_min'], 8.],
                        [bounds['u_max'], bounds['v_max'], -8.]])
        if name == 'three_anchors':
            uvd = np.vstack([uvd, [(bounds['u_min'] + bounds['u_max']) / 2, bounds['v_min'], 7.]])
        basis = np.array([frame[k] for k in ('basis_u', 'basis_v', 'normal')])
        anchors = uvd @ basis + origin
        points = np.vstack([xyz, anchors])
        path = output / (name + '.ply')
        base.io.write_ply(path, points)
        records.append(dict(name=name, file=path.name, point_count=len(points), slab_point_count=len(xyz),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), origin=origin.tolist(), normal=normal.tolist(),
            half_thickness=3., frame=frame, anchor_point_indices=list(range(len(xyz), len(points))),
            anchor_roles='deliberate_uv_boundary_anchors_not_target_points',
            declared_ideal_bounds=bounds, margin=0., frame_provenance={'declaration': frame['frame_id'],
                'basis_contract': 'accepted canonical section basis from explicit origin/normal'},
            target_parameters=deepcopy(base.TARGET) | options, layer_parameters=deepcopy(base.LAYER),
            profile_parameters=deepcopy(base.PROFILE), expected=expected))
    manifest = dict(version='0.15.7', units='native', fixtures=records, real_cloudcompare_validation=False,
        note='18 fixed fixtures with actual source anchor vertices. Bounds derive from acquired picks, not ideal manifest bounds. '
             'All slab depths retained. No fan data, ROI/padding/scale search, or quality-driven changes. '
             'Host quantization may change exact bounds/hashes; verify host evidence in its own context.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    manifest = generate(args.output)
    print(f'Created {len(manifest["fixtures"])} hashed pick/ROI PLY fixtures in {args.output.resolve()}')
