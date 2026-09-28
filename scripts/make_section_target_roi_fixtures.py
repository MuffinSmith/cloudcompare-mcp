"""Generate exact disposable ROI PLY fixtures OUTSIDE Git, without real fan data.

Usage: python scripts/make_section_target_roi_fixtures.py /absolute/new/directory
Bounds and scales are declared below, not searched using reconstruction quality.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).with_name('make_section_target_fixtures.py')
spec = importlib.util.spec_from_file_location('accepted_target_fixture_io', SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
io = base.io
ROOT, TARGET, LAYER, PROFILE = base.ROOT, base.TARGET, base.LAYER, base.PROFILE
read_fixture_xyz = base.read_fixture_xyz
ROI = dict(u_min=-3., u_max=11., v_min=-3., v_max=9.)
NAMES = ('safe', 'outside_clutter', 'one_of_two', 'two_inside', 'cross_left',
         'cross_right', 'cross_bottom', 'cross_top', 'half_open', 'safe_margin',
         'narrow_bridge', 'sparse', 'empty', 'tiny', 'parallel', 'overlap',
         'alternating_thick', 'permuted_outside', 'fan_like', 'transformed_safe',
         'transformed_parallel', 'transformed_cross_left')


def generated_cases():
    rectangle = io.rectangle()
    clutter = np.vstack([rectangle, [[20, 0, 0], [20, .1, 0], [20, .2, 0]]])
    two = np.vstack([rectangle, rectangle + [20, 0, 0]])
    parallel = np.vstack([io.rectangle(-.35), io.rectangle(.35)])
    boundaries = []
    for axis in (0, 1):
        for bound in (0., 10.):
            for value in (np.nextafter(bound, -np.inf), bound, np.nextafter(bound, np.inf)):
                p = [5., 5., 0.]; p[axis] = value
                boundaries.append(p)
    bridge = np.array([[8 + i / 5, 3., 0.] for i in range(25)])
    thick = rectangle.copy()
    thick[:, 2] = np.where(np.arange(len(thick)) % 2, -.07, .07)
    cases = [
        ('safe', rectangle, ROI, {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}, {}),
        ('outside_clutter', clutter, ROI, {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}, {}),
        ('one_of_two', two, ROI, {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}, {}),
        ('two_inside', two, ROI | {'u_max': 31}, {'inside': 2400, 'status': 'selection_required', 'stage': 'target_selection'}, {}),
    ]
    for side, change, count in [('left', {'u_min': 4}, 600), ('right', {'u_max': 4}, 600),
                                 ('bottom', {'v_min': 3}, 600), ('top', {'v_max': 3}, 600)]:
        cases.append(('cross_' + side, rectangle, ROI | change,
                      {'inside': count, 'edge': side, 'stage': 'roi_truncation_guard'}, {}))
    cases.extend([
        ('half_open', np.asarray(boundaries), dict(u_min=0, u_max=10, v_min=0, v_max=10), {'inside': 6, 'status': 'blocked'}, {}),
        ('safe_margin', rectangle, dict(u_min=-1, u_max=9, v_min=-1, v_max=7), {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}, {}),
        ('narrow_bridge', np.vstack([rectangle, bridge]), ROI | {'u_max': 10}, {'inside': 1210, 'edge': 'right'}, {}),
        ('sparse', np.array([[x, y, 0] for x in range(6) for y in range(6)], dtype=float), ROI,
         {'inside': 36, 'status': 'blocked', 'stage': 'target_selection'}, {'min_cell_points': 3}),
        ('empty', rectangle, dict(u_min=20, u_max=30, v_min=20, v_max=30), {'inside': 0, 'stage': 'roi_evidence'}, {}),
        ('tiny', rectangle, dict(u_min=0, u_max=2, v_min=0, v_max=2), {'inside': 100, 'stage': 'roi_evidence'}, {}),
        ('parallel', parallel, ROI, {'inside': 2400, 'status': 'ready', 'stage': 'layer_selection'}, {}),
        ('overlap', np.vstack([io.rectangle(-2), io.rectangle(2)]), ROI, {'inside': 2400, 'status': 'blocked', 'stage': 'target_selection'}, {}),
        ('alternating_thick', thick, ROI, {'inside': 1200, 'status': 'ready', 'stage': 'layer_selection'}, {}),
        ('permuted_outside', clutter[::-1].copy(), ROI, {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}, {}),
    ])
    fan = next(case[1] for case in base.generated_cases() if case[0] == 'fan_like_many')
    cases.append(('fan_like', fan, dict(u_min=30, u_max=50, v_min=-10, v_max=10), {}, {}))
    for name, xyz, roi, expected, options in cases:
        yield name, xyz, np.zeros(3), np.array([0., 0., 1.]), roi, expected, options
    # True arbitrary rotation about [1,2,3], plus a large translation. Bounds are
    # fixed broad spatial intent, not computed from a fitted candidate's quality.
    transformed = {c[0]: c for c in base.generated_cases() if c[0].startswith('transformed_')}
    # The designed rectangle lies within radius 10 of the origin, so +/-15
    # encloses it in every orthonormal section basis without inspecting any fit.
    wide = dict(u_min=-15, u_max=15, v_min=-15, v_max=15)
    for name, source, bounds, expected in [
        ('transformed_safe', 'transformed_single', wide, {'inside': 1200, 'status': 'ready', 'reconstruct': 'candidate'}),
        ('transformed_parallel', 'transformed_parallel', wide, {'inside': 2400, 'status': 'ready', 'stage': 'layer_selection'}),
        ('transformed_cross_left', 'transformed_single', wide | {'u_min': 4}, {'edge': 'left'}),
    ]:
        _, xyz, origin, normal, *_ = transformed[source]
        yield name, xyz, origin, normal, bounds, expected, {}


def generate(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Generated fixtures must remain outside the repository')
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for name, xyz, origin, normal, roi, expected, options in generated_cases():
        path = output / (name + '.ply')
        io.write_ply(path, xyz)
        projection = io.project_points_to_section(xyz, origin, normal)
        records.append(dict(name=name, file=path.name, point_count=len(xyz),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), origin=origin.tolist(), normal=normal.tolist(),
            half_thickness=3., frame={k: projection[v] for k, v in [('origin_global', 'origin'), ('normal', 'normal'),
                                                                  ('basis_u', 'basis_u'), ('basis_v', 'basis_v')]},
            roi=deepcopy(roi), target_parameters=deepcopy(TARGET) | options,
            layer_parameters=deepcopy(LAYER), profile_parameters=deepcopy(PROFILE), expected=deepcopy(expected)))
    assert tuple(r['name'] for r in records) == NAMES
    manifest = dict(version='0.15.6', units='native', fixtures=records, real_cloudcompare_validation=False,
                    note='22 fixed ROI fixtures. All depths retained. No fan-derived data or parameter search. '
                         'Half-open nextafter expectations apply to exact doubles; real host imports may quantize. '
                         'Measure actual acquired geometry/shift/scale rather than demanding exact cross-context hashes.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = generate(args.output)
    print(f'Created {len(result["fixtures"])} hashed PLY fixtures in {args.output.resolve()}')
