"""Numerical target isolation only: no MCP transport or native acquisition."""
from copy import deepcopy
import json

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_targets import (
    _articulation_count, analyze_section_targets_uvd, select_section_target,
)

OPTIONS = dict(uv_cell_size=1., depth_cell_size=1., perturbation_fraction=.1,
               min_cell_points=1)


def patch(x=0., y=0., z=0., width=6, height=6):
    return np.array([[x + i / 5, y + j / 5, z]
                     for i in range(width * 5) for j in range(height * 5)])


def analyze(points, **options):
    return analyze_section_targets_uvd(points, **(OPTIONS | options))


def test_single_target_complete_compact_no_mutation():
    p = patch()
    saved = p.copy()
    analysis = analyze(p)
    result = analysis.public
    assert result['status'] == 'ready'
    assert result['candidate_target_count'] == 1
    assert result['point_accounting']['assigned_point_count'] == len(p)
    assert result['point_accounting']['unassigned_point_count'] == 0
    assert len(select_section_target(analysis)) == len(p)
    assert result['warnings'] == []
    assert all(probe['partition_unchanged'] for probe in result['perturbation_probes'])
    assert len(json.dumps(result, allow_nan=False)) < 8000
    assert 'samples_uvd' not in json.dumps(result)
    np.testing.assert_array_equal(p, saved)


@pytest.mark.parametrize('dominant', [False, True])
def test_separated_targets_never_choose_largest(dominant):
    p = np.vstack([patch(width=10 if dominant else 6), patch(x=20)])
    analysis = analyze(p)
    result = analysis.public
    assert result['candidate_target_count'] == 2
    assert result['status'] == 'selection_required'
    assert result['auto_selected_target_id'] is None
    assert select_section_target(analysis) is None
    assert all(c['usable'] for c in result['candidate_targets'])
    assert sum(c['source_point_count'] for c in result['candidate_targets']) == len(p)
    c = result['candidate_targets'][0]
    selected = select_section_target(analysis, target_id=c['target_id'],
                                    expected_target_fingerprint=c['candidate_fingerprint'])
    assert len(selected) == c['source_point_count']
    assert c['nearest_other_bbox_distance_lower_bound'] > 10
    selected[:] = 0  # A returned selection does not alias server-side membership.
    assert len(np.unique(analysis.target_source_indices[c['target_id']])) > 1


def test_sparse_clutter_remains_explicit_and_does_not_auto_select():
    p = np.vstack([patch(), [[20, 0, 0], [20, .1, 0], [20, .2, 0]]])
    a = analyze(p)
    assert a.public['status'] == 'selection_required'
    assert a.public['candidate_target_count'] == 2
    assert a.public['point_accounting']['unsupported_or_ambiguous_point_count'] == 3
    assert select_section_target(a) is None
    good, bad = a.public['candidate_targets']
    assert good['usable'] and not bad['usable']
    assert len(select_section_target(a, target_id=good['target_id'],
                                    expected_target_fingerprint=good['candidate_fingerprint'])) == len(p) - 3
    assert select_section_target(a, target_id=bad['target_id'],
                                 expected_target_fingerprint=bad['candidate_fingerprint']) is None


def test_narrow_bridge_is_not_blindly_joined():
    # Two 4x4 blocks joined by one occupied-cell-wide path.
    cells = {(x, y, 0) for x in range(4) for y in range(4)}
    cells |= {(x, y, 0) for x in range(7, 11) for y in range(4)}
    cells |= {(x, 1, 0) for x in range(4, 7)}
    a = analyze(sorted(cells))
    assert a.public['candidate_target_count'] == 1
    c = a.public['candidate_targets'][0]
    assert c['articulation_cell_count'] > 0
    assert c['uv_eroded_component_count'] == 2
    assert a.public['status'] == 'blocked'
    assert select_section_target(a, target_id=c['target_id'],
                                 expected_target_fingerprint=c['candidate_fingerprint']) is None


def test_thin_target_refuses_even_without_articulation():
    a = analyze(patch(width=2))
    assert a.public['status'] == 'blocked'
    assert 'uv_one_cell_erosion_sensitive' in a.public['warnings']


def test_depth_overlapping_targets_block():
    a = analyze(np.vstack([patch(), patch(z=4)]))
    assert a.public['candidate_target_count'] == 2
    assert a.public['status'] == 'blocked'
    assert a.public['ambiguity_pair_count'] == 1
    for c in a.public['candidate_targets']:
        assert c['overlap_target_count'] == 1
        assert 'uv_overlap_with_other_target' in c['blocking_reasons']


def test_one_spatial_target_retains_two_depth_layers():
    a = analyze(np.vstack([patch(z=-.3), patch(z=.3)]))
    assert a.public['status'] == 'ready'
    assert a.public['candidate_target_count'] == 1
    c = a.public['candidate_targets'][0]
    assert c['depth']['min'] == -.3 and c['depth']['max'] == .3
    assert c['source_point_count'] == 1800


def test_diagonal_only_contacts_are_explicit():
    points = [(x, y, 0) for x in range(4) for y in range(4)]
    points += [(x, y, 0) for x in range(4, 8) for y in range(4, 8)]
    a = analyze(points)
    assert a.public['candidate_target_count'] == 2
    assert a.public['status'] == 'blocked'
    assert 'marginal_edge_or_corner_contact' in a.public['warnings']


def test_fixed_perturbation_detects_changed_membership():
    p = patch(width=2, height=5)
    p[:, 0] *= 1.05  # right edge 1.89, second target starts 3.05
    a = analyze(np.vstack([p, p + [3.05, 0, 0]]), perturbation_fraction=.2)
    assert a.public['candidate_target_count'] == 2
    assert 'grid_origin_membership_sensitive' in a.public['warnings']
    assert any(not probe['partition_unchanged'] for probe in a.public['perturbation_probes'])


def test_permutation_invariance_including_fingerprints():
    p = np.vstack([patch(), patch(x=15), patch(z=5)])
    a = analyze(p).public
    np.random.default_rng(981).shuffle(p)
    assert analyze(p).public == a


def test_signed_zero_normalization_without_mutation():
    p = patch()
    p[:, 2] = -0.
    original = p.tobytes()
    a = analyze(p)
    assert p.tobytes() == original
    q = p.copy()
    q[:, 2] = 0.
    assert analyze(q).public == a.public


def test_large_section_coordinate_translation():
    p = patch()
    a = analyze(p).public
    b = analyze(p + [1e8, -2e8, 3e8]).public
    assert b['status'] == 'ready'
    assert b['candidate_target_count'] == a['candidate_target_count']
    np.testing.assert_allclose(b['candidate_targets'][0]['extent_uvd'],
                               a['candidate_targets'][0]['extent_uvd'], atol=1e-7)
    assert b['analysis_fingerprint'] != a['analysis_fingerprint']


def test_duplicate_samples_do_not_manufacture_support():
    p = np.array([(x, y, 0) for x in range(4) for y in range(4)], dtype=float)
    a = analyze(np.repeat(p, 5, axis=0), min_cell_points=2)
    assert a.public['source_point_count'] == 80
    assert a.public['candidate_targets'][0]['unique_point_count'] == 16
    assert a.public['status'] == 'blocked'
    assert 'sparse_voxel_support' in a.public['warnings']


@pytest.mark.parametrize('minimum, usable', [(1, True), (2, True), (3, False)])
def test_exact_support_threshold(minimum, usable):
    points = [(x + d, y, 0) for x in range(4) for y in range(4) for d in (0., .1)]
    a = analyze(points, min_cell_points=minimum)
    assert a.public['candidate_targets'][0]['usable'] is usable


def test_cell_boundary_equality_is_half_open():
    p = np.array([(x, y, 0) for x in range(4) for y in range(4)], dtype=float)
    a = analyze(p).public
    assert a['occupied_cell_count'] == 16
    assert a['candidate_target_count'] == 1
    b = analyze(p, uv_cell_size=.999).public
    assert b['occupied_cell_count'] == 16


@pytest.mark.parametrize('change', ['geometry', 'parameter'])
def test_stale_selection_rejected(change):
    p = patch()
    a = analyze(p)
    candidate = a.public['candidate_targets'][0]
    if change == 'geometry':
        p[0, 2] += .01
        b = analyze(p)
    else:
        b = analyze(p, perturbation_fraction=.15)
    with pytest.raises(SectionLayerError, match='Unknown|fingerprint'):
        select_section_target(b, target_id=candidate['target_id'],
                              expected_target_fingerprint=candidate['candidate_fingerprint'])


def test_explicit_selection_requires_matching_token_and_id():
    a = analyze(patch())
    c = a.public['candidate_targets'][0]
    with pytest.raises(SectionLayerError, match='fingerprint'):
        select_section_target(a, target_id=c['target_id'])
    with pytest.raises(SectionLayerError, match='requires an explicit'):
        select_section_target(a, expected_target_fingerprint=c['candidate_fingerprint'])
    with pytest.raises(SectionLayerError, match='Unknown'):
        select_section_target(a, target_id='target_unknown', expected_target_fingerprint='x')


@pytest.mark.parametrize('key,value', [
    ('uv_cell_size', 0), ('uv_cell_size', True), ('uv_cell_size', float('inf')),
    ('depth_cell_size', -1), ('depth_cell_size', float('nan')),
    ('perturbation_fraction', 0), ('perturbation_fraction', .25001),
    ('min_cell_points', 0), ('min_cell_points', 1.5), ('min_target_cells', 2),
    ('max_points', 20001), ('max_points', False), ('max_cells', 2),
    ('max_targets', 0), ('max_targets', 65),
])
def test_malformed_options(key, value):
    with pytest.raises(SectionLayerError):
        analyze(patch(), **{key: value})


@pytest.mark.parametrize('points', [[], [[0, 0, 0]] * 2, [[0, 0]] * 3,
                                     [[0, 0, float('nan')]] * 3,
                                     [[0, 0, True]] * 3, [[0, 0, '1']] * 3])
def test_malformed_samples(points):
    with pytest.raises(SectionLayerError):
        analyze(points)


@pytest.mark.parametrize('options, message', [
    ({'max_points': 10}, 'complete samples'),
    ({'max_cells': 3}, 'max_cells'),
    ({'max_targets': 1}, 'max_targets'),
    ({'uv_cell_size': 1e-20}, 'precision'),
])
def test_explicit_budgets(options, message):
    with pytest.raises(SectionLayerError, match=message):
        analyze(np.vstack([patch(), patch(x=20)]), **options)


def test_long_graph_does_not_recurse():
    assert _articulation_count([(i, 0, 0) for i in range(5000)]) == 4998


def test_many_targets_compact_and_fully_accounted():
    p = np.vstack([patch(x=(i % 5) * 10, y=(i // 5) * 10, width=3, height=3) for i in range(20)])
    a = analyze(p)
    assert a.public['candidate_target_count'] == 20
    assert a.public['status'] == 'selection_required'
    assert sum(c['source_point_count'] for c in a.public['candidate_targets']) == len(p)
    assert len(json.dumps(a.public)) < 50000
