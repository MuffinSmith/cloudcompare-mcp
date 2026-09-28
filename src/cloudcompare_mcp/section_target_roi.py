"""Explicit half-open UV isolation and conservative one-cell truncation evidence.

No target solver, depth crop, bounds search, repair or manufacturing inference.
Every complete input point remains in one of two private index sets.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Any

import numpy as np

from .section_layer_workflow import object_fields
from .section_layers import canonical_sha256, integer, positive, samples_array
from .section_targets import SectionTargetError

VERSION = '0.15.6'
CONTRACT = 'explicit_uv_roi_v1_half_open_inclusive_one_cell_guard'
BOUNDS = ('u_min', 'u_max', 'v_min', 'v_max')
EDGES = ('left', 'right', 'bottom', 'top')


@dataclass
class SectionROI:
    public: dict
    samples_uvd: np.ndarray
    inside_indices: np.ndarray
    outside_indices: np.ndarray
    edge_distances: np.ndarray
    inside_edge_masks: np.ndarray
    outside_edge_masks: np.ndarray
    uv_cells: np.ndarray


def validate_roi(value: Any) -> dict[str, float]:
    obj = object_fields(value, 'roi', BOUNDS, BOUNDS)
    result = {}
    for key in BOUNDS:
        v = obj[key]
        if isinstance(v, bool) or not isinstance(v, Real):
            raise SectionTargetError(f'roi.{key} must be a finite number, not a boolean')
        try:
            v = float(v)
        except (ValueError, OverflowError) as exc:
            raise SectionTargetError(f'roi.{key} must be a finite number') from exc
        if not math.isfinite(v):
            raise SectionTargetError(f'roi.{key} must be a finite number')
        result[key] = v
    for axis in ('u', 'v'):
        width = result[axis + '_max'] - result[axis + '_min']
        if not math.isfinite(width) or width <= 0:
            raise SectionTargetError(f'roi requires {axis}_min < {axis}_max with a finite positive span')
    return result


def _summary(points: np.ndarray) -> dict:
    return {'point_count': len(points), 'geometry_sha256': canonical_sha256(points),
            'bounds_uvd': [points.min(axis=0).tolist(), points.max(axis=0).tolist()] if len(points) else None}


def _cell_count(cells: np.ndarray, mask: np.ndarray) -> int:
    return len(np.unique(cells[mask], axis=0))


def classify_section_roi(samples_uvd, roi: dict, *, uv_cell_size: float,
                         max_points: int = 20000) -> SectionROI:
    """Classify exactly once. Guard side counts can overlap; union counts never do."""
    bounds = validate_roi(roi)
    size = positive(uv_cell_size, 'uv_cell_size')
    limit = integer(max_points, 'max_points', 3, 20000)
    points = samples_array(samples_uvd, limit)
    uv = points[:, :2]
    lower = np.array([bounds['u_min'], bounds['v_min']])
    upper = np.array([bounds['u_max'], bounds['v_max']])
    # Membership uses original float64 comparisons, no epsilon snapping/subtraction.
    inside = np.all((uv >= lower) & (uv < upper), axis=1)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            low_distance, high_distance = uv - lower, upper - uv
            distance = np.column_stack([low_distance[:, 0], high_distance[:, 0],
                                        low_distance[:, 1], high_distance[:, 1]])
    except FloatingPointError as exc:
        raise SectionTargetError('ROI distances exceed representable precision') from exc
    inward = (distance <= size) & inside[:, None]
    outward = np.zeros((len(points), 4), dtype=bool)
    for side, axis in enumerate((0, 0, 1, 1)):
        tangent = 1 - axis
        along_edge = (uv[:, tangent] >= lower[tangent]) & (uv[:, tangent] < upper[tangent])
        beyond = uv[:, axis] < lower[axis] if side % 2 == 0 else uv[:, axis] >= upper[axis]
        outward[:, side] = ~inside & along_edge & beyond & (distance[:, side] >= -size)
    relevant = inside | outward.any(axis=1)
    cells = np.zeros((len(points), 2), dtype=np.int64)
    if relevant.any():
        try:
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                indices = np.floor((uv[relevant] - lower) / size)
        except FloatingPointError as exc:
            raise SectionTargetError('ROI grid exceeds representable precision') from exc
        if not np.isfinite(indices).all() or np.abs(indices).max() >= 2**48:
            raise SectionTargetError('ROI grid exceeds representable index precision')
        cells[relevant] = indices.astype(np.int64)
    guard = inward.any(axis=1)
    adjacent = outward.any(axis=1)
    edges = {}
    for side, name in enumerate(EDGES):
        edges[name] = {'inside_guard_point_count': int(inward[:, side].sum()),
                       'inside_guard_uv_cell_count': _cell_count(cells, inward[:, side]),
                       'outside_adjacent_point_count': int(outward[:, side].sum()),
                       'outside_adjacent_uv_cell_count': _cell_count(cells, outward[:, side])}
    public = {
        'contract': CONTRACT, 'roi': bounds, 'units': 'native',
        'membership': '[u_min,u_max) x [v_min,v_max); all signed depths retained',
        'point_accounting': {'input_point_count': len(points), 'inside_roi_point_count': int(inside.sum()),
                             'outside_roi_point_count': int((~inside).sum()), 'unclassified_point_count': 0},
        'whole_slab': _summary(points), 'inside_roi': _summary(points[inside]),
        'outside_roi': _summary(points[~inside]),
        'edge_guard': {'width': size, 'derived_from': 'target_parameters.uv_cell_size',
                       'inner_threshold_inclusive': True,
                       'guard_clear_interior_exists': bool(np.all((upper - lower) / 2 > size)),
                       'inside_guard_point_count': int(guard.sum()),
                       'inside_guard_uv_cell_count': _cell_count(cells, guard),
                       'outside_adjacent_point_count': int(adjacent.sum()),
                       'side_counts_overlap_at_corners': True, 'edges': edges,
                       'outside_support_scope': 'one-cell outward strips along half-open edge extents; all depths',
                       'outside_support_proves_connection': False},
        'raw_points_returned': False, 'scene_mutations_requested': False,
    }
    return SectionROI(public, points, np.flatnonzero(inside), np.flatnonzero(~inside),
                      distance, inward, outward, cells)


def candidate_roi_guard(roi: SectionROI, source_indices: np.ndarray) -> dict:
    """Membership is supplied by the unchanged accepted target solver, never grown."""
    masks = roi.inside_edge_masks[source_indices]
    touched = [name for i, name in enumerate(EDGES) if masks[:, i].any()]
    edges = {}
    for side, name in enumerate(EDGES):
        ids = source_indices[masks[:, side]]
        tangent = 1 if side < 2 else 0
        outside = roi.outside_edge_masks[:, side]
        # Projected tangential support only: no depth filtering or physical-connection claim.
        same_tangent = np.isin(roi.uv_cells[:, tangent], np.unique(roi.uv_cells[ids, tangent]))
        edges[name] = {
            'minimum_sample_distance': float(roi.edge_distances[source_indices, side].min()),
            'guard_point_count': len(ids),
            'guard_uv_cell_count': len(np.unique(roi.uv_cells[ids], axis=0)),
            'outside_same_tangential_cell_point_count_all_depths': int((outside & same_tangent).sum()),
        }
    guard_ids = source_indices[masks.any(axis=1)]
    return {'touched_edges': touched, 'connects_to_inward_guard': bool(touched),
            'possible_truncation': bool(touched), 'roi_guard_clear': not touched,
            'guard_point_count': len(guard_ids),
            'guard_uv_cell_count': len(np.unique(roi.uv_cells[guard_ids], axis=0)),
            'edges': edges, 'outside_support_proves_connection': False}
