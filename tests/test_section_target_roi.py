"""Exact numeric ROI membership/edge semantics; not native GUI validation."""
from copy import deepcopy
import json

import numpy as np
import pytest

from cloudcompare_mcp.section_target_roi import classify_section_roi, candidate_roi_guard, validate_roi, EDGES
from cloudcompare_mcp.section_layers import SectionLayerError

ROI = dict(u_min=0, u_max=10, v_min=0, v_max=10)


def classify(points, roi=None, **kwargs):
    return classify_section_roi(points, ROI if roi is None else roi, uv_cell_size=1, **kwargs)


@pytest.mark.parametrize('axis', [0, 1])
@pytest.mark.parametrize('bound', [0., 10.])
def test_half_open_and_nextafter_each_boundary(axis, bound):
    vals = [np.nextafter(bound, -np.inf), bound, np.nextafter(bound, np.inf)]
    points = np.full((3, 3), 5.)
    points[:, axis] = vals
    r = classify(points)
    expected = [1, 2] if bound == 0 else [0]
    assert r.inside_indices.tolist() == expected
    assert sorted([*r.inside_indices, *r.outside_indices]) == [0, 1, 2]
    assert r.public['point_accounting']['unclassified_point_count'] == 0


@pytest.mark.parametrize('side', range(4))
def test_inclusive_one_cell_guard_threshold_nextafter(side):
    axis = 0 if side < 2 else 1
    bound = 1. if side % 2 == 0 else 9.
    points = np.full((3, 3), 5.)
    points[:, axis] = [np.nextafter(bound, -np.inf), bound, np.nextafter(bound, np.inf)]
    r = classify(points)
    assert r.inside_indices.tolist() == [0, 1, 2]
    assert r.inside_edge_masks[:, side].tolist() == ([True, True, False] if side % 2 == 0 else [False, True, True])
    c = candidate_roi_guard(r, r.inside_indices)
    assert c['touched_edges'] == [EDGES[side]]
    assert c['possible_truncation']


@pytest.mark.parametrize('key', ['u_min', 'u_max', 'v_min', 'v_max'])
@pytest.mark.parametrize('bad', [True, False, float('nan'), float('inf'), -float('inf'), '1', None, [], 10**400])
def test_invalid_numeric_bounds(key, bad):
    with pytest.raises(SectionLayerError):
        validate_roi(ROI | {key: bad})


@pytest.mark.parametrize('bad', [None, [], [0, 1, 0, 1], {}, ROI | {'depth_min': 0},
                                ROI | {'u_min': 10}, ROI | {'v_max': 0},
                                ROI | {'u_min': 11}, ROI | {'v_max': -1},
                                ROI | {'u_min': -1e308, 'u_max': 1e308}])
def test_malformed_inverted_degenerate_bounds(bad):
    with pytest.raises(SectionLayerError):
        validate_roi(bad)


def test_all_depths_source_immutability_and_exact_accounting():
    points = np.array([[5, 5, -1000], [5, 5, 0], [5, 5, 1000], [-1, 5, 0], [10, 5, 0.]])
    saved = points.copy()
    bounds = deepcopy(ROI)
    r = classify(points)
    np.testing.assert_array_equal(r.samples_uvd[r.inside_indices, 2], [-1000, 0, 1000])
    np.testing.assert_array_equal(points, saved)
    assert ROI == bounds
    assert r.public['point_accounting'] == dict(input_point_count=5, inside_roi_point_count=3,
                                              outside_roi_point_count=2, unclassified_point_count=0)
    assert r.public['edge_guard']['outside_adjacent_point_count'] == 2
    assert candidate_roi_guard(r, r.inside_indices)['roi_guard_clear']
    assert 'samples_uvd' not in json.dumps(r.public)
    assert len(json.dumps(r.public)) < 5000


def test_corners_side_counts_overlap_but_union_counts_are_exact():
    r = classify([[0, 0, 0], [.2, .2, 0], [5, 5, 0]])
    g = r.public['edge_guard']
    assert g['inside_guard_point_count'] == 2
    assert sum(e['inside_guard_point_count'] for e in g['edges'].values()) == 4
    assert candidate_roi_guard(r, r.inside_indices)['touched_edges'] == ['left', 'bottom']


@pytest.mark.parametrize('roi, expected', [(dict(u_min=20, u_max=30, v_min=20, v_max=30), 0),
                                         (dict(u_min=4.9, u_max=5.1, v_min=4.9, v_max=5.1), 1)])
def test_empty_and_tiny_roi_accounting(roi, expected):
    r = classify([[3, 3, 0], [5, 5, 0], [7, 7, 0]], roi)
    assert len(r.inside_indices) == expected
    assert len(r.outside_indices) == 3 - expected
    if expected:
        assert not r.public['edge_guard']['guard_clear_interior_exists']


def test_permutation_invariance():
    points = np.array([[.2, 5, 0], [5, 5, 0], [10, 5, 0], [-.5, 5, 100], [20, 20, 0]])
    a = classify(points)
    b = classify(points[::-1])
    assert a.public == b.public
    assert candidate_roi_guard(a, a.inside_indices) == candidate_roi_guard(b, b.inside_indices)


def test_outside_support_is_projected_evidence_not_depth_selection():
    r = classify([[.2, 5, -100], [.4, 5, 100], [5, 5, 0], [-.5, 5, 1000], [-.5, 8, 0]])
    c = candidate_roi_guard(r, r.inside_indices)
    assert c['edges']['left']['outside_same_tangential_cell_point_count_all_depths'] == 1
    assert c['outside_support_proves_connection'] is False
    assert c['possible_truncation']


def test_complete_input_budget_precedes_roi():
    with pytest.raises(SectionLayerError, match='complete samples'):
        classify(np.zeros((4, 3)), max_points=3)


def test_unrepresentable_grid_and_distances_refuse():
    with pytest.raises(SectionLayerError, match='ROI grid'):
        classify([[5, 5, 0]] * 3, ROI | {'u_min': -1e16})
    with pytest.raises(SectionLayerError, match='ROI distances'):
        classify([[1e308, 5, 0]] * 3, ROI | {'u_min': -1e308, 'u_max': -9e307})
