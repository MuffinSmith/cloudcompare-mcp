"""Bounded spatial targets before layer interpretation; no point deletion/repair.

Six-neighbor anisotropic voxels preserve signed depth. Fixed grid-origin probes,
articulation cells and one UV-cell erosion are diagnostics, never alternate inputs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from itertools import product
import json
import math
from typing import Any, Iterable, Sequence

import numpy as np

from .section_layers import (
    SectionLayerError, canonical_sha256, depth_summary, integer, positive,
    precision_floor, samples_array,
)

MAX_POINTS = 20000
MAX_CELLS = 20000
MAX_TARGETS = 64
REQUIRED = ('uv_cell_size', 'depth_cell_size', 'perturbation_fraction')
DEFAULTS = dict(min_cell_points=3, min_target_cells=4, max_points=MAX_POINTS,
                max_cells=MAX_CELLS, max_targets=32)
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
UV_FACES = ((1, 0), (-1, 0), (0, 1), (0, -1))


class SectionTargetError(SectionLayerError):
    """Invalid or over-budget target evidence; no partial topology result."""


@dataclass
class SectionTargetAnalysis:
    public: dict[str, Any]
    samples_uvd: np.ndarray
    target_source_indices: dict[str, np.ndarray]


def validate_options(*, uv_cell_size: float, depth_cell_size: float,
                     perturbation_fraction: float, min_cell_points: int = 3,
                     min_target_cells: int = 4, max_points: int = MAX_POINTS,
                     max_cells: int = MAX_CELLS, max_targets: int = 32) -> dict:
    result = {key: positive(value, key) for key, value in (
        ('uv_cell_size', uv_cell_size), ('depth_cell_size', depth_cell_size),
        ('perturbation_fraction', perturbation_fraction))}
    if result['perturbation_fraction'] > 0.25:
        raise SectionTargetError('perturbation_fraction must be in (0, 0.25]')
    for key, value, low, high in (
        ('min_cell_points', min_cell_points, 1, MAX_POINTS),
        ('min_target_cells', min_target_cells, 3, MAX_CELLS),
        ('max_points', max_points, 3, MAX_POINTS),
        ('max_cells', max_cells, 3, MAX_CELLS),
        ('max_targets', max_targets, 1, MAX_TARGETS),
    ):
        result[key] = integer(value, key, low, high)
    return result


def _neighbors(cell, offsets):
    for offset in offsets:
        yield tuple(a + b for a, b in zip(cell, offset))


def _components(cells, offsets):
    unseen = set(cells)
    groups = []
    # Sort once, not repeated min(unseen), to bound disconnected-clutter cost.
    for start in sorted(cells):
        if start not in unseen:
            continue
        unseen.remove(start)
        stack, group = [start], []
        while stack:
            cell = stack.pop()
            group.append(cell)
            for other in _neighbors(cell, offsets):
                if other in unseen:
                    unseen.remove(other)
                    stack.append(other)
        groups.append(sorted(group))
    return groups


def _grid(points, origin, sizes, options, shift=None):
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            relative = (points - origin) / sizes
            if shift is not None:
                relative = relative - shift
            indices = np.floor(relative)
        except FloatingPointError as exc:
            raise SectionTargetError('Target grid exceeds representable precision') from exc
    if not np.isfinite(indices).all() or np.abs(indices).max() >= 2**48:
        raise SectionTargetError('Target grid exceeds representable index precision')
    cells = defaultdict(list)
    for i, row in enumerate(indices.astype(np.int64)):
        cells[tuple(map(int, row))].append(i)
        if len(cells) > options['max_cells']:
            raise SectionTargetError('Target occupied-cell budget exceeds max_cells')
    groups = _components(cells, FACES)
    if len(groups) > options['max_targets']:
        raise SectionTargetError('Target count exceeds max_targets; no components were discarded')
    return cells, groups


def _articulation_count(cells):
    """Iterative Tarjan DFS; bounded even for a 20k-cell path (no recursion)."""
    cells = set(cells)
    first = min(cells)
    discovery, low, parent, children = {first: 0}, {first: 0}, {}, defaultdict(int)
    cuts = set()
    stack = [(first, iter(n for n in _neighbors(first, FACES) if n in cells))]
    while stack:
        cell, neighbors = stack[-1]
        other = next(neighbors, None)
        if other is None:
            stack.pop()
            if cell in parent:
                p = parent[cell]
                low[p] = min(low[p], low[cell])
                if p in parent and low[cell] >= discovery[p]:
                    cuts.add(p)
            elif children[cell] > 1:
                cuts.add(cell)
            continue
        if other not in discovery:
            parent[other] = cell
            children[cell] += 1
            discovery[other] = low[other] = len(discovery)
            stack.append((other, iter(n for n in _neighbors(other, FACES) if n in cells)))
        elif parent.get(cell) != other:
            low[cell] = min(low[cell], discovery[other])
    return len(cuts)


def refresh_candidate_fingerprints(analysis: SectionTargetAnalysis) -> None:
    """Call again after binding acquisition context; tokens cannot cross contexts."""
    for candidate in analysis.public['candidate_targets']:
        payload = analysis.public['analysis_fingerprint'] + ':' + candidate['target_id']
        candidate['candidate_fingerprint'] = hashlib.sha256(payload.encode()).hexdigest()


def analyze_section_targets_uvd(samples_uvd: Iterable[Sequence[float]], *,
                                uv_cell_size: float, depth_cell_size: float,
                                perturbation_fraction: float, min_cell_points: int = 3,
                                min_target_cells: int = 4, max_points: int = MAX_POINTS,
                                max_cells: int = MAX_CELLS, max_targets: int = 32) -> SectionTargetAnalysis:
    options = validate_options(
        uv_cell_size=uv_cell_size, depth_cell_size=depth_cell_size,
        perturbation_fraction=perturbation_fraction, min_cell_points=min_cell_points,
        min_target_cells=min_target_cells, max_points=max_points, max_cells=max_cells,
        max_targets=max_targets)
    points = samples_array(samples_uvd, max_points)
    floors = np.array([precision_floor(points[:, :2])] * 2 + [precision_floor(points[:, 2:])])
    sizes = np.array([options['uv_cell_size']] * 2 + [options['depth_cell_size']])
    if np.any(sizes * options['perturbation_fraction'] < floors):
        raise SectionTargetError('Cell sizes and declared perturbations must exceed coordinate precision floors')
    origin = points.min(axis=0)
    cells, groups = _grid(points, origin, sizes, options)
    with np.errstate(over='raise', invalid='raise', under='ignore'):
        try:
            volume = float(np.prod(sizes) * len(cells))
        except FloatingPointError as exc:
            raise SectionTargetError('Occupied voxel volume exceeds representable precision') from exc
    if not math.isfinite(volume) or volume <= 0:
        raise SectionTargetError('Occupied voxel volume exceeds representable precision')
    labels = np.empty(len(points), dtype=np.int64)
    memberships, summaries, footprints, reasons = {}, [], [], []
    cell_labels = {}
    for label, group in enumerate(groups):
        indices = np.array(sorted(i for cell in group for i in cells[cell]), dtype=np.int64)
        labels[indices] = label
        for cell in group:
            cell_labels[cell] = label
        p = points[indices]
        p = p[np.lexsort((p[:, 2], p[:, 1], p[:, 0]))]
        footprint = {cell[:2] for cell in group}
        footprints.append(footprint)
        unique_counts = [len(np.unique(points[cells[cell]], axis=0)) for cell in group]
        why = set()
        if min(unique_counts) < min_cell_points:
            why.add('sparse_voxel_support')
        if len(group) < min_target_cells:
            why.add('insufficient_target_cells')
        relative = p[:, :2] - p[0, :2]
        singular = np.linalg.svd(relative / max(1., float(np.abs(relative).max())), compute_uv=False)
        rank = int(np.sum(singular > 8 * np.finfo(float).eps * max(relative.shape) * singular[0]))
        if rank < 2:
            why.add('insufficient_two_dimensional_support')
        cuts = _articulation_count(group)
        if cuts:
            why.add('single_voxel_bridge_or_appendage')
        eroded = {cell for cell in footprint if all(n in footprint for n in _neighbors(cell, UV_FACES))}
        erosion_count = len(_components(eroded, UV_FACES))
        if erosion_count != 1:
            why.add('uv_one_cell_erosion_sensitive')
        geometry_sha = canonical_sha256(p)
        target_id = 'target_' + geometry_sha[:24]
        memberships[target_id] = indices
        bounds = [p.min(axis=0).tolist(), p.max(axis=0).tolist()]
        summaries.append({
            'target_id': target_id, 'state': 'inferred_candidate',
            'source_point_count': len(indices), 'source_geometry_sha256': geometry_sha,
            'unique_point_count': sum(unique_counts), 'occupied_cell_count': len(group),
            'uv_cell_count': len(footprint), 'uv_bounds': [b[:2] for b in bounds],
            'bounds_uvd': bounds, 'extent_uvd': np.ptp(p, axis=0).tolist(),
            'depth': depth_summary(p[:, 2]),
            'unique_support_per_cell': {'min': min(unique_counts), 'median': float(np.median(unique_counts)),
                                        'max': max(unique_counts)},
            'connectivity': '6-neighbor anisotropic section voxels',
            'articulation_cell_count': cuts, 'uv_eroded_component_count': erosion_count,
            'uv_erosion_removed_cell_count': len(footprint) - len(eroded),
            'overlap_target_count': 0, 'marginal_contact_target_count': 0,
            'nearest_other_bbox_distance_lower_bound': None,
        })
        reasons.append(why)

    # A diagonal edge/corner contact is evidence, not a join or a reason to drop points.
    contacts = set()
    diagonal_offsets = [o for o in product((-1, 0, 1), repeat=3) if sum(abs(x) for x in o) > 1]
    for cell, a in cell_labels.items():
        for neighbor in _neighbors(cell, diagonal_offsets):
            b = cell_labels.get(neighbor)
            if b is not None and a != b:
                contacts.add(tuple(sorted((a, b))))
    pair_evidence = []
    for a in range(len(groups)):
        for b in range(a + 1, len(groups)):
            overlap = len(footprints[a] & footprints[b])
            contact = (a, b) in contacts
            if overlap or contact:
                for i in (a, b):
                    if overlap:
                        reasons[i].add('uv_overlap_with_other_target')
                        summaries[i]['overlap_target_count'] += 1
                    if contact:
                        reasons[i].add('marginal_edge_or_corner_contact')
                        summaries[i]['marginal_contact_target_count'] += 1
                pair_evidence.append({'target_ids': [summaries[a]['target_id'], summaries[b]['target_id']],
                                      'overlap_uv_cell_count': overlap, 'marginal_contact': contact})
            alo, ahi = np.asarray(summaries[a]['bounds_uvd'])
            blo, bhi = np.asarray(summaries[b]['bounds_uvd'])
            gap = np.maximum(0., np.maximum(alo - bhi, blo - ahi))
            distance = math.hypot(*map(float, gap))
            if not math.isfinite(distance):
                raise SectionTargetError('Target separation exceeds representable precision')
            for i in (a, b):
                old = summaries[i]['nearest_other_bbox_distance_lower_bound']
                summaries[i]['nearest_other_bbox_distance_lower_bound'] = distance if old is None else min(old, distance)

    probes = []
    for axis in range(3):
        for sign in (-1, 1):
            shift = np.zeros(3)
            shift[axis] = sign * options['perturbation_fraction']
            shifted_cells, shifted_groups = _grid(points, origin, sizes, options, shift)
            appearances = defaultdict(int)
            affected = set()
            for group in shifted_groups:
                ids = [i for cell in group for i in shifted_cells[cell]]
                baseline_labels = set(map(int, labels[ids]))
                for label in baseline_labels:
                    appearances[label] += 1
                if len(baseline_labels) > 1:
                    affected.update(baseline_labels)
            affected.update(label for label, count in appearances.items() if count != 1)
            for label in affected:
                reasons[label].add('grid_origin_membership_sensitive')
            probes.append({'offset_fraction_uvd': shift.tolist(), 'candidate_count': len(shifted_groups),
                           'occupied_cell_count': len(shifted_cells),
                           'changed_target_count': len(affected), 'partition_unchanged': not affected})

    for summary, why in zip(summaries, reasons):
        summary['blocking_reasons'] = sorted(why)
        summary['usable'] = not why
    summaries.sort(key=lambda s: (s['bounds_uvd'][0], s['target_id']))
    usable = [s for s in summaries if s['usable']]
    auto = summaries[0]['target_id'] if len(summaries) == 1 and len(usable) == 1 else None
    geometry_sha = canonical_sha256(points)
    fingerprint = hashlib.sha256(json.dumps(
        {'algorithm': 'section_voxel_targets_v1', 'geometry': geometry_sha, 'parameters': options,
         'origin_uvd': origin.tolist()}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    public = {
        'type': 'section_target_evidence', 'version': '0.15.4', 'state': 'inferred_candidate',
        'status': 'ready' if auto else 'selection_required' if usable else 'blocked',
        'source_point_count': len(points), 'source_geometry_sha256': geometry_sha,
        'analysis_fingerprint': fingerprint, 'parameters': options, 'grid_origin_uvd': origin.tolist(),
        'coordinate_precision_floor_uvd': floors.tolist(), 'occupied_cell_count': len(cells),
        'occupied_voxel_volume': volume, 'candidate_target_count': len(summaries),
        'candidate_targets': summaries, 'auto_selected_target_id': auto,
        'point_accounting': {'assigned_point_count': len(points), 'unassigned_point_count': 0,
                             'unsupported_or_ambiguous_point_count': sum(s['source_point_count'] for s in summaries if not s['usable'])},
        'perturbation_probes': probes, 'ambiguity_pair_count': len(pair_evidence),
        'ambiguity_pair_preview': pair_evidence[:16], 'ambiguity_pair_preview_truncated': len(pair_evidence) > 16,
        'warnings': sorted(set().union(*reasons)),
        'raw_points_returned': False, 'scene_mutations_requested': False,
        'manufacturing_intent_confirmed': False, 'user_accepted': False,
        'assumptions': ['complete supplied snapshot, not independent acquisition proof',
                        'half-open anisotropic cells anchored at sample minima; 6-neighbor connectivity',
                        'six declared +/- origin probes and one UV erosion are diagnostics, never repairs',
                        'all articulation cells are conservatively treated as marginal bridges/appendages',
                        'subcell contact, unsampled connections and coincident surfaces cannot be ruled out',
                        'depth_cell_size groups spatial evidence, not physical layers; accepted layer checks still required',
                        'nearest-other separation is a bounding-box lower bound, not exact surface clearance'],
    }
    result = SectionTargetAnalysis(public, points, memberships)
    refresh_candidate_fingerprints(result)
    return result


def select_section_target(analysis: SectionTargetAnalysis, *, target_id: str | None = None,
                          expected_target_fingerprint: str | None = None) -> np.ndarray | None:
    candidates = {s['target_id']: s for s in analysis.public['candidate_targets']}
    if target_id is not None:
        if target_id not in candidates:
            raise SectionTargetError('Unknown target_id for this exact analysis')
        if expected_target_fingerprint != candidates[target_id]['candidate_fingerprint']:
            raise SectionTargetError('Explicit selection requires the current expected_target_fingerprint')
    elif expected_target_fingerprint is not None:
        raise SectionTargetError('expected_target_fingerprint requires an explicit target_id')
    chosen = target_id or analysis.public['auto_selected_target_id']
    if chosen is None or not candidates[chosen]['usable']:
        return None
    return analysis.target_source_indices[chosen].copy()
