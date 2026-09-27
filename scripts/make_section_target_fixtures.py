"""Generate exact disposable target-isolation PLY files OUTSIDE the repository.

Usage: python scripts/make_section_target_fixtures.py /absolute/new/output/directory
Distances are native units. Neither fixtures nor parameters derive from the real fan.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

# Reuse the accepted strict ASCII-double file format and independent layer settings.
SCRIPT = Path(__file__).with_name('make_section_layer_fixtures.py')
spec = importlib.util.spec_from_file_location('accepted_layer_fixture_io', SCRIPT)
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)
ROOT, LAYER, PROFILE = io.ROOT, io.LAYER, io.PROFILE
read_fixture_xyz = io.read_fixture_xyz
TARGET = dict(uv_cell_size=1., depth_cell_size=1., perturbation_fraction=.1,
              min_cell_points=1, min_target_cells=4, max_points=20000,
              max_cells=20000, max_targets=32)
NAMES = ('single', 'coherent_clutter', 'two_targets', 'dominant', 'narrow_bridge',
         'parallel', 'nested_choices', 'sparse', 'overlap', 'fan_like_many',
         'permuted_two', 'transformed_single', 'transformed_two', 'transformed_parallel')


def generated_cases():
    base = io.rectangle()
    two = np.vstack([base, base + [20, 0, 0]])
    parallel = np.vstack([io.rectangle(-.35), io.rectangle(.35)])
    bridge = np.array([(x, y, 0) for x in np.arange(8.1, 14, .2)
                       for y in np.arange(2.1, 3, .2)])
    patches = []
    for angle in np.arange(20) * 2 * np.pi / 20:
        local = np.array([(x, y) for x in np.arange(-3, 3, .2) for y in np.arange(-2, 2, .2)])
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        uv = local @ rotation.T + 40 * np.array([np.cos(angle), np.sin(angle)])
        patches.append(np.column_stack([uv, np.full(len(uv), .05 * np.sin(angle))]))
    cases = [
        ('single', base, 'ready', 1, {}),
        ('coherent_clutter', np.vstack([base, [[20, 0, 0], [20, .1, 0], [20, .2, 0]]]), 'selection_required', 2, {}),
        ('two_targets', two, 'selection_required', 2, {}),
        ('dominant', np.vstack([base, base + [8, 0, 0], base + [30, 0, 0]]), 'selection_required', 2, {}),
        ('narrow_bridge', np.vstack([base, base + [14, 0, 0], bridge]), 'blocked', 1, {}),
        ('parallel', parallel, 'ready', 1, {}),
        ('nested_choices', np.vstack([io.rectangle(-.4), io.rectangle(.4), base + [20, 0, 0]]), 'selection_required', 2, {}),
        ('sparse', np.array([(x, y, 0) for x in range(6) for y in range(6)], dtype=float), 'blocked', 1, {'min_cell_points': 3}),
        ('overlap', np.vstack([io.rectangle(-2), io.rectangle(2)]), 'blocked', 2, {}),
        ('fan_like_many', np.vstack(patches), 'selection_required', 20, {}),
        ('permuted_two', two[::-1].copy(), 'selection_required', 2, {}),
    ]
    for name, xyz, status, count, overrides in cases:
        yield name, xyz, np.zeros(3), np.array([0., 0., 1.]), status, count, overrides
    axis = np.array([1., 2., 3.]); axis /= np.linalg.norm(axis)
    angle = np.deg2rad(37.)
    x, y, z = axis
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    rotation = np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * skew
    translation = np.array([1e8, -2e8, 3e8])
    for name, xyz, status, count in [('transformed_single', base, 'ready', 1),
                                     ('transformed_two', two, 'selection_required', 2),
                                     ('transformed_parallel', parallel, 'ready', 1)]:
        yield name, xyz @ rotation.T + translation, translation, rotation[:, 2], status, count, {}


def generate(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Generated fixtures must remain outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    fixtures = []
    for name, xyz, origin, normal, status, count, overrides in generated_cases():
        xyz = xyz[np.random.default_rng(15404).permutation(len(xyz))]
        path = output / f'{name}.ply'
        io.write_ply(path, xyz)
        projection = io.project_points_to_section(xyz, origin, normal)
        fixtures.append(dict(name=name, file=path.name, point_count=len(xyz),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), origin=origin.tolist(), normal=normal.tolist(),
            half_thickness=3., frame={k: projection[v] for k, v in [('origin_global', 'origin'), ('normal', 'normal'),
                                                                  ('basis_u', 'basis_u'), ('basis_v', 'basis_v')]},
            target_parameters=deepcopy(TARGET) | overrides, layer_parameters=deepcopy(LAYER),
            profile_parameters=deepcopy(PROFILE), expected_status=status, expected_target_count=count))
    manifest = dict(version='0.15.4', units='native', fixtures=fixtures, real_cloudcompare_validation=False,
                    note='min_cell_points=1 explicitly permits singly sampled edge voxels except sparse=3. '
                         'Fan-like data exercises compact evidence, not a required profile or universally usable targets. '
                         'Measure actual host shift/scale; generator metadata is not live validation.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    manifest = generate(args.output)
    print(f'Created {len(manifest["fixtures"])} hashed PLY fixtures in {args.output.resolve()}')
