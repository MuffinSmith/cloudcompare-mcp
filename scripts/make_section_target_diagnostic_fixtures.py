"""Generate 20 exact diagnostic PLY fixtures outside Git; never tune to real fan data.

Usage: python scripts/make_section_target_diagnostic_fixtures.py /absolute/new/directory
Includes the 14 accepted target cases plus fixed split/merge/refusal evidence cases.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('accepted_target_fixture_io',
    Path(__file__).with_name('make_section_target_fixtures.py'))
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)
ROOT = accepted.ROOT
read_fixture_xyz = accepted.read_fixture_xyz
NAMES = (*accepted.NAMES, 'depth_split', 'depth_merge', 'probe_cell_budget',
         'probe_target_budget', 'transformed_depth_split', 'transformed_depth_merge')


def generated_cases():
    for name, xyz, origin, normal, status, count, overrides in accepted.generated_cases():
        yield name, xyz, origin, normal, overrides, dict(
            baseline_target_count=count, baseline_solver_status=status)
    base = accepted.io.rectangle()
    split = np.vstack([base, base + [0, 0, 1.6]])
    merge = np.vstack([base, base + [0, 0, 2.1]])
    dense = np.array([(x, y, 0.) for x in np.arange(0., 6., .2) for y in np.arange(0., 6., .2)])
    sparse = np.array([(x, y, 0.) for x in range(6) for y in range(6)])
    specs = [
        ('depth_split', split, {}, dict(baseline_target_count=1, panel_id='depth_finer',
             probe_target_count=2, split_count=1, diagnostic_status='sensitivity_observed')),
        ('depth_merge', merge, {}, dict(baseline_target_count=2, panel_id='depth_coarser',
             probe_target_count=1, merge_count=1, diagnostic_status='sensitivity_observed')),
        ('probe_cell_budget', dense, {'max_cells': 49}, dict(baseline_target_count=1,
             panel_id='uv_finer', refusal_contains='max_cells', diagnostic_status='inconclusive')),
        ('probe_target_budget', sparse, {'max_targets': 1, 'min_cell_points': 3},
             dict(baseline_target_count=1, panel_id='uv_finer', refusal_contains='max_targets',
                  diagnostic_status='inconclusive')),
    ]
    for name, xyz, overrides, expected in specs:
        yield name, xyz, np.zeros(3), np.array([0., 0., 1.]), overrides, expected
    axis = np.array([1., 2., 3.]); axis /= np.linalg.norm(axis)
    angle = np.deg2rad(37.)
    x, y, z = axis
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    rotation = (np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis)
                + np.sin(angle) * skew)
    translation = np.array([1e8, -2e8, 3e8])
    for name, xyz, overrides, expected in specs[:2]:
        yield 'transformed_' + name, xyz @ rotation.T + translation, translation, rotation[:, 2], overrides, expected


def generate(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Generated fixtures must remain outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    fixtures = []
    for name, xyz, origin, normal, overrides, expected in generated_cases():
        xyz = xyz[np.random.default_rng(15505).permutation(len(xyz))]
        path = output / f'{name}.ply'
        accepted.io.write_ply(path, xyz)
        projection = accepted.io.project_points_to_section(xyz, origin, normal)
        fixtures.append(dict(name=name, file=path.name, point_count=len(xyz),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            origin=origin.tolist(), normal=normal.tolist(), half_thickness=3.,
            frame={k: projection[v] for k, v in [('origin_global', 'origin'), ('normal', 'normal'),
                ('basis_u', 'basis_u'), ('basis_v', 'basis_v')]},
            target_parameters=deepcopy(accepted.TARGET) | overrides,
            layer_parameters=deepcopy(accepted.LAYER), profile_parameters=deepcopy(accepted.PROFILE),
            expected=deepcopy(expected)))
    manifest = dict(version='0.15.5', units='native', fixtures=fixtures,
        real_cloudcompare_validation=False,
        note='All diagnostic settings are fixed by product; fixture thresholds are declared here, not searched. '
             'Do not infer host precision, global shift/scale or source integrity from generated metadata.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    manifest = generate(args.output)
    print(f'Created {len(manifest["fixtures"])} hashed PLY fixtures in {args.output.resolve()}')
