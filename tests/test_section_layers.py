"""Exact numerical core tests: no live or MCP validation is claimed here."""
from __future__ import annotations

import json

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import (
    SectionLayerError, analyze_section_layers_uvd, select_section_layer,
)
from cloudcompare_mcp.feature_fit import project_points_to_section

OPTIONS = dict(uv_cell_size=1.0, depth_separation=0.3,
               max_layer_thickness=0.1, max_neighbor_depth_step=0.15,
               min_cell_points=3, min_layer_cells=4)


def sheet(depth=0.0, xstart=0, xstop=4):
    return np.asarray([(x + a, y + b, depth)
                       for x in range(xstart, xstop) for y in range(4)
                       for a, b in ((0.1, 0.1), (0.3, 0.1), (0.1, 0.3), (0.3, 0.3))])


def analyze(points, **options):
    return analyze_section_layers_uvd(points, **(OPTIONS | options))


@pytest.mark.parametrize('count', [1, 2, 3])
def test_separated_layers_and_all_source_memberships(count):
    points = np.concatenate([sheet(1 + n) for n in range(count)])
    result = analyze(points)
    public = result.public
    assert public['candidate_layer_count'] == count
    assert public['status'] == ('ready' if count == 1 else 'selection_required')
    assert all(c['usable'] for c in public['candidate_layers'])
    assert public['multimodal_uv_cell_count'] == (0 if count == 1 else 16)
    ids = np.concatenate(list(result.layer_source_indices.values()))
    assert sorted(ids.tolist()) == list(range(len(points)))
    assert public['unusable_point_count'] == 0
    assert public['overlap_pair_count'] == count * (count - 1) // 2


def test_two_layers_on_same_depth_sign_are_not_collapsed():
    result = analyze(np.concatenate([sheet(2), sheet(3)]))
    assert result.public['status'] == 'selection_required'
    assert select_section_layer(result) is None


def test_partial_uv_overlap_is_explicit():
    result = analyze(np.concatenate([sheet(0, 0, 4), sheet(1, 2, 6)])).public
    assert result['candidate_layer_count'] == 2
    assert result['overlap_preview'][0]['uv_cell_count'] == 8
    assert all(c['overlap_uv_cell_count'] == 8 for c in result['candidate_layers'])


def test_sloped_surface_has_local_not_global_thickness():
    points = sheet()
    points[:, 2] = points[:, 0] * 0.08
    result = analyze(points).public
    assert result['status'] == 'ready'
    assert result['depth']['max'] - result['depth']['min'] > OPTIONS['max_layer_thickness']
    assert result['candidate_layers'][0]['max_local_depth_span'] < 0.1


def test_crossing_surfaces_are_blocked():
    first = sheet()
    first[:, 2] = (first[:, 0] - 1.6) * 0.4
    second = first.copy()
    second[:, 2] *= -1
    result = analyze(np.concatenate([first, second]), max_neighbor_depth_step=0.5).public
    assert result['status'] == 'blocked'
    assert result['thick_uv_cell_count'] or result['ambiguous_neighbor_pair_count']


def test_ambiguous_neighbor_correspondence_cannot_be_selected():
    result = analyze(np.concatenate([sheet(0), sheet(1)]), max_neighbor_depth_step=1.0)
    assert result.public['status'] == 'blocked'
    assert result.public['ambiguous_neighbor_pair_count'] > 0
    assert any('merging_or_crossing_depth_modes' in c['blocking_reasons']
               for c in result.public['candidate_layers'])
    chosen = result.public['candidate_layers'][0]['layer_id']
    assert select_section_layer(result, layer_id=chosen,
                                expected_analysis_fingerprint=result.public['analysis_fingerprint']) is None


@pytest.mark.parametrize('span, expected', [(0.0625, 'ready'), (0.125, 'ready'), (0.125001, 'blocked')])
def test_exact_local_thickness_threshold(span, expected):
    points = sheet()
    points[::2, 2] = span
    assert analyze(points, max_layer_thickness=0.125).public['status'] == expected


@pytest.mark.parametrize('gap, candidates', [(0.5, 1), (0.500001, 2)])
def test_separation_boundary_is_strict(gap, candidates):
    result = analyze(np.concatenate([sheet(0), sheet(gap)]), depth_separation=0.5).public
    assert result['candidate_layer_count'] == candidates
    assert result['status'] == ('blocked' if candidates == 1 else 'selection_required')


@pytest.mark.parametrize('step, expected', [(0.125, 'ready'), (0.125001, 'selection_required')])
def test_neighbor_step_boundary_is_inclusive(step, expected):
    points = sheet()
    points[points[:, 0] >= 2, 2] = step
    result = analyze(points, max_neighbor_depth_step=0.125).public
    assert result['status'] == expected


def test_sparse_observation_is_retained_not_removed():
    points = sheet()
    points = np.concatenate([points, [[8.1, 8.1, 0]]])
    result = analyze(points).public
    assert result['status'] == 'blocked'
    assert result['source_point_count'] == len(points)
    assert sum(c['source_point_count'] for c in result['candidate_layers']) == len(points)
    assert 'sparse_local_support' in result['warnings']


def test_duplicate_samples_do_not_manufacture_local_support():
    points = sheet()[::4]
    result = analyze(np.repeat(points, 10, axis=0)).public
    assert result['status'] == 'blocked'
    assert result['sparse_uv_cell_count'] == 16


def test_collinear_support_is_not_a_filled_surface():
    points = np.asarray([[x / 10, x / 10, 0] for x in range(40)])
    result = analyze(points).public
    assert result['status'] == 'blocked'
    assert 'insufficient_two_dimensional_support' in result['warnings']


def test_geometry_and_all_diagnostics_are_permutation_deterministic_and_read_only():
    points = np.concatenate([sheet(0), sheet(1)])
    saved = points.copy()
    first = analyze(points)
    for seed in (153, 154, 155):
        shuffled = points[np.random.default_rng(seed).permutation(len(points))]
        assert analyze(shuffled).public == first.public
    assert np.array_equal(points, saved)
    first.samples_uvd[:] = 5
    assert np.array_equal(points, saved)


def test_compact_json_has_no_raw_arrays_or_confirmed_intent():
    public = analyze(sheet()).public
    text = json.dumps(public, allow_nan=False)
    assert len(text) < 7000
    assert 'samples_uvd' not in public and 'source_indices' not in public
    assert public['raw_points_returned'] is False
    assert public['manufacturing_intent_confirmed'] is False


def test_explicit_choice_requires_exact_fingerprint_and_never_uses_result_quality():
    result = analyze(np.concatenate([sheet(1), sheet(2)]))
    candidate = result.public['candidate_layers'][1]
    chosen = candidate['layer_id']
    with pytest.raises(SectionLayerError, match='current expected'):
        select_section_layer(result, layer_id=chosen)
    indices = select_section_layer(result, layer_id=chosen,
                                  expected_analysis_fingerprint=result.public['analysis_fingerprint'])
    assert np.all(result.samples_uvd[indices, 2] == 2)
    with pytest.raises(SectionLayerError, match='Unknown'):
        select_section_layer(result, layer_id='missing',
                             expected_analysis_fingerprint=result.public['analysis_fingerprint'])
    with pytest.raises(SectionLayerError, match='requires an explicit'):
        select_section_layer(result, expected_analysis_fingerprint='anything')
    changed = analyze(np.concatenate([sheet(1), sheet(2)]), depth_separation=0.4)
    with pytest.raises(SectionLayerError, match='current expected'):
        select_section_layer(changed, layer_id=chosen,
                             expected_analysis_fingerprint=result.public['analysis_fingerprint'])


@pytest.mark.parametrize('points', [[], [[0, 0, 0]] * 2, [[0, 0]] * 3,
                                  [[True, 0, 0]] * 3, [['1', 0, 0]] * 3,
                                  [[float('nan'), 0, 0]] * 3,
                                  [[float('inf'), 0, 0]] * 3, None])
def test_malformed_nonfinite_and_empty_inputs(points):
    with pytest.raises(SectionLayerError):
        analyze(points)


@pytest.mark.parametrize('options', [dict(uv_cell_size=0), dict(depth_separation=True),
                                    dict(max_layer_thickness=0.3), dict(min_cell_points=1.5),
                                    dict(max_points=20001), dict(max_components=65),
                                    dict(max_layer_thickness=float('nan'))])
def test_invalid_options(options):
    with pytest.raises(SectionLayerError):
        analyze(sheet(), **options)


@pytest.mark.parametrize('options, message', [(dict(max_points=20), 'complete samples'),
                                             (dict(max_cells=4), 'cell budget'),
                                             (dict(max_components=1), 'component budget')])
def test_budgets_are_refusals_not_truncation(options, message):
    with pytest.raises(SectionLayerError, match=message):
        analyze(np.concatenate([sheet(0), sheet(1)]), **options)


def test_local_mode_budget_is_bounded():
    with pytest.raises(SectionLayerError, match='mode budget'):
        analyze(np.concatenate([sheet(n) for n in range(17)]), max_components=64)


def test_subprecision_and_extreme_inputs_are_explicit_errors():
    points = sheet()
    points[:, :2] += 1e8
    with pytest.raises(SectionLayerError, match='precision floor'):
        analyze(points, uv_cell_size=1e-10)
    with pytest.raises(SectionLayerError, match='precision'):
        analyze(sheet(), uv_cell_size=1e200)
    with pytest.raises(SectionLayerError, match='precision'):
        analyze([[-1e308, 0, 0], [1e308, 0, 0], [0, 1, 0]])


def test_arbitrary_2d_rotation_on_dense_supported_layer():
    points = np.asarray([(x, y, 0.0) for x in np.arange(0, 4, 0.1)
                        for y in np.arange(0, 4, 0.1)])
    angle = np.deg2rad(31)
    points[:, :2] = points[:, :2] @ np.asarray([[np.cos(angle), np.sin(angle)],
                                               [-np.sin(angle), np.cos(angle)]])
    result = analyze(points, min_cell_points=1).public
    assert result['candidate_layer_count'] == 1
    assert result['status'] == 'ready'


def test_arbitrary_3d_section_frame_and_large_translation():
    points = sheet()
    normal = np.asarray([1.0, 2.0, 3.0])
    normal /= np.linalg.norm(normal)
    u = np.cross(normal, [0, 0, 1])
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    origin = np.asarray([1e8, -2e8, 3e8])
    xyz = origin + points[:, 0, None] * u + points[:, 1, None] * v
    projected = project_points_to_section(xyz, origin=origin.tolist(), normal=normal.tolist())
    uvd = np.column_stack([projected['uv'], projected['signed_offsets']])
    result = analyze(uvd, min_cell_points=1).public
    assert result['candidate_layer_count'] == 1
    assert result['status'] == 'ready'
    assert result['candidate_layers'][0]['max_local_depth_span'] < 1e-6
