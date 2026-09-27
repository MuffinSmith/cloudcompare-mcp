"""Generate disposable ASCII-double PLY layer fixtures OUTSIDE the repository.

Usage: python scripts/make_section_layer_fixtures.py /absolute/new/output/directory
No real fan data, reports, or generated point files belong in Git.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cloudcompare_mcp.feature_fit import project_points_to_section

LAYER = dict(uv_cell_size=0.5, depth_separation=0.2, max_layer_thickness=0.09,
             max_neighbor_depth_step=0.12, min_cell_points=1, min_layer_cells=4,
             max_points=20000, max_cells=20000, max_components=16)
PROFILE = dict(cell_size=0.5, max_edge_length=1.1, fit_tolerance=0.35,
               angular_tolerance_degrees=2.0, require_grid_stability=True)


def rectangle(depth=0.0):
    # Deliberately not tied to the real fan or selected by reconstruction quality.
    return np.asarray([(x, y, depth) for x in np.arange(0.1, 8, 0.2)
                       for y in np.arange(0.1, 6, 0.2)], dtype=np.float64)


def write_ply(path: Path, xyz: np.ndarray) -> None:
    with path.open('x', encoding='ascii', newline='\n') as stream:
        stream.write('ply\nformat ascii 1.0\n')
        stream.write(f'element vertex {len(xyz)}\nproperty double x\nproperty double y\nproperty double z\nend_header\n')
        for row in xyz:
            stream.write(' '.join(format(float(x), '.17g') for x in row) + '\n')


def read_fixture_xyz(path: Path) -> np.ndarray:
    """Strict fixture-file reader, not a general PLY importer."""
    with path.open('r', encoding='ascii') as stream:
        if stream.readline().strip() != 'ply' or stream.readline().strip() != 'format ascii 1.0':
            raise ValueError('Expected an ASCII layer fixture')
        count_line = stream.readline().split()
        if count_line[:2] != ['element', 'vertex']:
            raise ValueError('Missing fixture vertex count')
        count = int(count_line[2])
        if not 3 <= count <= 20000:
            raise ValueError('Fixture vertex budget exceeded')
        if [stream.readline().strip() for _ in range(4)] != [
            'property double x', 'property double y', 'property double z', 'end_header'
        ]:
            raise ValueError('Unexpected fixture properties')
        rows = [[float(x) for x in stream.readline().split()] for _ in range(count)]
        if stream.read().strip():
            raise ValueError('Unexpected trailing fixture geometry')
    xyz = np.asarray(rows, dtype=np.float64)
    if xyz.shape != (count, 3) or not np.isfinite(xyz).all():
        raise ValueError('Invalid fixture point rows')
    return xyz


def generated_cases():
    base = rectangle()
    parallel = np.concatenate([rectangle(-0.35), rectangle(0.35)])
    shifted = rectangle(0.35)
    shifted[:, 0] += 4
    slope = base.copy()
    slope[:, 2] = 0.02 * (slope[:, 0] - 4)
    crossing = base.copy()
    crossing[:, 2] = 0.15 * (crossing[:, 0] - 4)
    other = crossing.copy()
    other[:, 2] *= -1
    noisy = base.copy()
    noisy[:, 2] = 0.03 * np.sin(np.arange(len(noisy)))
    thick = base.copy()
    thick[:, 2] = np.where(np.arange(len(thick)) % 2, 0.07, -0.07)
    sparse = base.copy()
    keep = (sparse[:, 0] >= 0.6) | (sparse[:, 1] >= 0.6)
    keep[0] = True
    sparse = sparse[keep]
    fan_a, fan_b = base.copy(), base.copy()
    fan_a[:, 2] = -0.3 + 0.06 * np.sin(fan_a[:, 0])
    fan_b[:, 2] = 0.3 + 0.04 * np.cos(fan_b[:, 1])
    cases = [
        ('single', base, 'ready', 1, {}),
        ('parallel', parallel, 'selection_required', 2, {}),
        ('three', np.concatenate([rectangle(-0.35), base, rectangle(0.35)]), 'selection_required', 3, {}),
        ('partial_overlap', np.concatenate([rectangle(-0.35), shifted]), 'selection_required', 2, {}),
        ('sloped', slope, 'ready', 1, {}),
        ('crossing', np.concatenate([crossing, other]), 'blocked', None, {'max_neighbor_depth_step': 0.2}),
        ('noisy_within_bound', noisy, 'ready', 1, {}),
        ('too_thick', thick, 'blocked', 1, {}),
        ('sparse', sparse, 'blocked', 1, {'min_cell_points': 3}),
        ('fan_like', np.concatenate([fan_a, fan_b]), 'selection_required', 2, {}),
    ]
    # Rodrigues rotation around an arbitrary axis, not a special axis-aligned case.
    axis = np.asarray([1.0, 2.0, 3.0]); axis /= np.linalg.norm(axis)
    angle = np.deg2rad(37.0)
    x, y, z = axis
    skew = np.asarray([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    rotation = np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * skew
    for name, xyz, status, layers, overrides in cases:
        yield name, xyz, np.zeros(3), np.asarray([0., 0., 1.]), status, layers, overrides
    translation = np.asarray([1e8, -2e8, 3e8])
    for name, xyz, status, layers in [('transformed_single', base, 'ready', 1),
                                     ('transformed_parallel', parallel, 'selection_required', 2)]:
        yield name, xyz @ rotation.T + translation, translation, rotation[:, 2], status, layers, {}


def generate(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Generated fixtures must remain outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    fixtures = []
    for name, xyz, origin, normal, expected, count, overrides in generated_cases():
        path = output / f'{name}.ply'
        # Deterministic permutation prevents accidental dependence on file scan order.
        xyz = xyz[np.random.default_rng(15303).permutation(len(xyz))]
        write_ply(path, xyz)
        projection = project_points_to_section(xyz, origin, normal)
        record = dict(name=name, file=path.name, point_count=len(xyz),
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      origin=origin.tolist(), normal=normal.tolist(), half_thickness=1.0,
                      frame={k: projection[v] for k, v in [('origin_global', 'origin'), ('normal', 'normal'),
                                                          ('basis_u', 'basis_u'), ('basis_v', 'basis_v')]},
                      layer_parameters=deepcopy(LAYER) | overrides, profile_parameters=deepcopy(PROFILE),
                      expected_status=expected, expected_layer_count=count,
                      support_note='min_cell_points=1 explicitly permits singly sampled edge cells; sparse fixture requires 3')
        fixtures.append(record)
    manifest = dict(version='0.15.3', units='native', fixtures=fixtures,
                    real_cloudcompare_validation=False,
                    note='Fixture metadata describes generator intent; actual CloudCompare shift/scale must be measured.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New directory outside the repository')
    args = parser.parse_args()
    result = generate(args.output)
    print(f'Created {len(result["fixtures"])} fixtures and manifest in {args.output.resolve()}')
