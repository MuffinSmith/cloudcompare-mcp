"""Bounded, deterministic local-depth evidence; never flatten unresolved layers.

A candidate is one connected observation component, not a physical-part claim.
Every supplied point belongs to a reported component; unsupported observations are
retained and poison usability rather than being silently discarded.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from itertools import islice
import json
import math
from numbers import Real
from typing import Any, Iterable, Sequence

import numpy as np

MAX_LAYER_POINTS = 20_000
MAX_LAYER_CELLS = 20_000
MAX_LAYER_COMPONENTS = 64
MAX_MODES_PER_CELL = 16


class SectionLayerError(ValueError):
    """Malformed, unrepresentable or over-budget section-layer evidence."""


@dataclass
class SectionLayerAnalysis:
    public: dict[str, Any]
    samples_uvd: np.ndarray
    layer_source_indices: dict[str, np.ndarray]


def positive(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SectionLayerError(f"{label} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise SectionLayerError(f"{label} must be a finite positive number")
    return number


def integer(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise SectionLayerError(f"{label} must be an integer in [{low}, {high}]")
    return value


def samples_array(samples: Iterable[Sequence[float]], limit: int) -> np.ndarray:
    try:
        rows = list(islice(iter(samples), limit + 1))
        if not 3 <= len(rows) <= limit:
            raise SectionLayerError(f"samples_uvd requires 3 to {limit} complete samples")
        if any(len(row) != 3 or any(isinstance(x, bool) or not isinstance(x, Real)
                                    for x in row) for row in rows):
            raise SectionLayerError("samples_uvd must contain numeric [u, v, signed_depth] rows")
        points = np.asarray(rows, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SectionLayerError(f"Invalid samples_uvd: {exc}") from exc
    if points.shape != (len(rows), 3) or not np.isfinite(points).all():
        raise SectionLayerError("samples_uvd must contain finite 3D section-frame rows")
    # Own the data; normalizing signed zero must never mutate a caller's array.
    points = points.copy()
    points[points == 0] = 0.0
    return points


def canonical_sha256(points: np.ndarray) -> str:
    order = np.lexsort(tuple(points[:, i] for i in reversed(range(points.shape[1]))))
    return hashlib.sha256(np.asarray(points[order], dtype="<f8").tobytes()).hexdigest()


def precision_floor(points: np.ndarray) -> float:
    with np.errstate(over="raise", invalid="raise"):
        try:
            scale = max(1.0, float(np.abs(points).max()), float(np.ptp(points, axis=0).max()))
            return 8 * max(float(np.abs(np.spacing(np.abs(points))).max()),
                           np.finfo(np.float64).eps * scale)
        except FloatingPointError as exc:
            raise SectionLayerError("Coordinate span exceeds representable precision") from exc


def depth_summary(values: np.ndarray, *, percentiles: bool = False) -> dict[str, float]:
    """Rebase quantile arithmetic so finite large same-sign depths do not overflow."""
    base = float(values.min())
    relative = values - base
    result = {"min": base, "median": base + float(np.median(relative)),
              "max": float(values.max())}
    if percentiles:
        result.update(p10=base + float(np.percentile(relative, 10)),
                      p90=base + float(np.percentile(relative, 90)))
    return result



def validate_options(*, uv_cell_size: float, depth_separation: float,
                     max_layer_thickness: float, max_neighbor_depth_step: float,
                     min_cell_points: int = 3, min_layer_cells: int = 4,
                     max_points: int = MAX_LAYER_POINTS,
                     max_cells: int = MAX_LAYER_CELLS,
                     max_components: int = 16) -> dict[str, Any]:
    options = {key: positive(value, key) for key, value in {
        "uv_cell_size": uv_cell_size, "depth_separation": depth_separation,
        "max_layer_thickness": max_layer_thickness,
        "max_neighbor_depth_step": max_neighbor_depth_step}.items()}
    if options["max_layer_thickness"] >= options["depth_separation"]:
        raise SectionLayerError("max_layer_thickness must be less than depth_separation")
    for key, value, low, high in (
        ("min_cell_points", min_cell_points, 1, MAX_LAYER_POINTS),
        ("min_layer_cells", min_layer_cells, 3, MAX_LAYER_CELLS),
        ("max_points", max_points, 3, MAX_LAYER_POINTS),
        ("max_cells", max_cells, 3, MAX_LAYER_CELLS),
        ("max_components", max_components, 1, MAX_LAYER_COMPONENTS),
    ):
        options[key] = integer(value, key, low, high)
    return options


def analyze_section_layers_uvd(samples_uvd: Iterable[Sequence[float]], *,
                              uv_cell_size: float, depth_separation: float,
                              max_layer_thickness: float, max_neighbor_depth_step: float,
                              min_cell_points: int = 3, min_layer_cells: int = 4,
                              max_points: int = MAX_LAYER_POINTS,
                              max_cells: int = MAX_LAYER_CELLS,
                              max_components: int = 16) -> SectionLayerAnalysis:
    """Analyze the complete supplied snapshot; local thickness is NOT global depth span.

    Adjacent sorted depths split only at a gap strictly greater than separation.
    A local span equal to thickness, or neighbor median step equal to its bound,
    is allowed. A branching neighbor correspondence makes the component unusable.
    Half-open UV cells are anchored to the sample minima, not the world origin.
    """
    options = validate_options(
        uv_cell_size=uv_cell_size, depth_separation=depth_separation,
        max_layer_thickness=max_layer_thickness, max_neighbor_depth_step=max_neighbor_depth_step,
        min_cell_points=min_cell_points, min_layer_cells=min_layer_cells,
        max_points=max_points, max_cells=max_cells, max_components=max_components)
    points = samples_array(samples_uvd, max_points)
    uv_floor, depth_floor = precision_floor(points[:, :2]), precision_floor(points[:, 2:])
    if options["uv_cell_size"] < uv_floor:
        raise SectionLayerError(f"uv_cell_size is below coordinate precision floor {uv_floor:.17g}")
    for key in ("depth_separation", "max_layer_thickness", "max_neighbor_depth_step"):
        if options[key] < depth_floor:
            raise SectionLayerError(f"{key} is below depth precision floor {depth_floor:.17g}")
    origin = points[:, :2].min(axis=0)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            grid = np.floor((points[:, :2] - origin) / options["uv_cell_size"])
        except FloatingPointError as exc:
            raise SectionLayerError("UV grid exceeds representable index precision") from exc
    if not np.isfinite(grid).all() or np.abs(grid).max() >= 2**48:
        raise SectionLayerError("UV grid exceeds representable index precision")
    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in enumerate(grid.astype(np.int64)):
        cells[tuple(map(int, row))].append(index)
        if len(cells) > max_cells:
            raise SectionLayerError(f"UV occupied-cell budget exceeds max_cells={max_cells}")
    try:
        area = len(cells) * options["uv_cell_size"] ** 2
    except OverflowError as exc:
        raise SectionLayerError("UV cell area exceeds representable precision") from exc
    if not math.isfinite(area):
        raise SectionLayerError("UV cell area exceeds representable precision")

    nodes: list[dict[str, Any]] = []
    by_cell: dict[tuple[int, int], list[int]] = {}
    multimodal = sparse = thick = 0
    for cell in sorted(cells):
        # Tie-breaking on U/V makes every reduction independent of source order.
        ids = np.asarray(cells[cell], dtype=np.int64)
        p = points[ids]
        ids = ids[np.lexsort((p[:, 1], p[:, 0], p[:, 2]))]
        cuts = np.flatnonzero(np.diff(points[ids, 2]) > options["depth_separation"]) + 1
        bands = np.split(ids, cuts)
        if len(bands) > MAX_MODES_PER_CELL:
            raise SectionLayerError(f"Local depth-mode budget exceeds {MAX_MODES_PER_CELL} per cell")
        multimodal += int(len(bands) > 1)
        by_cell[cell] = []
        cell_sparse = cell_thick = False
        for band in bands:
            d = points[band, 2]
            span = float(d[-1] - d[0])
            unique = len(np.unique(points[band], axis=0))
            reasons = set()
            if unique < min_cell_points:
                reasons.add("sparse_local_support")
                cell_sparse = True
            if span > options["max_layer_thickness"]:
                reasons.add("local_thickness_exceeds_bound")
                cell_thick = True
            median = float(d[0] + np.median(d - d[0]))
            residual_scale = max(float(np.abs(d - median).max()), np.finfo(float).tiny)
            rms = residual_scale * float(np.sqrt(np.mean(((d - median) / residual_scale) ** 2)))
            by_cell[cell].append(len(nodes))
            nodes.append({"cell": cell, "indices": band, "median": median,
                          "span": span, "unique": unique, "reasons": reasons,
                          "rms": rms})
        sparse += int(cell_sparse)
        thick += int(cell_thick)

    parents = list(range(len(nodes)))

    def root(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    edges: list[tuple[int, int, float]] = []
    branch_pairs = 0
    for cell, left in by_cell.items():
        for offset in ((1, 0), (0, 1)):
            right = by_cell.get((cell[0] + offset[0], cell[1] + offset[1]), [])
            links = [(a, b, abs(nodes[a]["median"] - nodes[b]["median"]))
                     for a in left for b in right
                     if abs(nodes[a]["median"] - nodes[b]["median"]) <= options["max_neighbor_depth_step"]]
            degrees: dict[int, int] = defaultdict(int)
            for a, b, _ in links:
                degrees[a] += 1
                degrees[b] += 1
            branching = any(value > 1 for value in degrees.values())
            if branching:
                branch_pairs += 1
                for i in degrees:
                    nodes[i]["reasons"].add("ambiguous_neighbor_correspondence")
            # Retain ambiguous components as evidence; they can never be selected.
            for a, b, step in links:
                ra, rb = root(a), root(b)
                parents[max(ra, rb)] = min(ra, rb)
                edges.append((a, b, step))

    components: dict[int, list[int]] = defaultdict(list)
    for i in range(len(nodes)):
        components[root(i)].append(i)
    if len(components) > max_components:
        raise SectionLayerError(f"Layer component budget exceeds max_components={max_components}; "
                                "isolate a smaller acquisition, do not drop components")
    memberships: dict[str, np.ndarray] = {}
    summaries: list[dict[str, Any]] = []
    node_layers = {}
    for members in components.values():
        indices = np.concatenate([nodes[i]["indices"] for i in members])
        # Canonical order is used for every diagnostic reduction, not input indices.
        p = points[indices]
        p = p[np.lexsort((p[:, 2], p[:, 1], p[:, 0]))]
        footprint = {nodes[i]["cell"] for i in members}
        reasons = set().union(*(nodes[i]["reasons"] for i in members))
        if len(footprint) != len(members):
            reasons.add("merging_or_crossing_depth_modes")
        if len(footprint) < min_layer_cells:
            reasons.add("insufficient_connected_cells")
        relative = p[:, :2] - p[0, :2]
        scale = max(1.0, float(np.abs(relative).max()))
        singular = np.linalg.svd(relative / scale, compute_uv=False)
        rank = int(np.sum(singular > 8 * np.finfo(float).eps * max(relative.shape) * singular[0]))
        if rank < 2:
            reasons.add("insufficient_two_dimensional_support")
        fingerprint = canonical_sha256(p)
        layer_id = "layer_" + fingerprint[:24]
        memberships[layer_id] = np.sort(indices)
        for i in members:
            node_layers[i] = layer_id
        counts = [nodes[i]["unique"] for i in members]
        member_set = set(members)
        steps = [step for a, b, step in edges if a in member_set and b in member_set]
        rms_scale = max(max(nodes[i]["rms"] for i in members), np.finfo(float).tiny)
        rms = rms_scale * math.sqrt(sum(
            len(nodes[i]["indices"]) * (nodes[i]["rms"] / rms_scale) ** 2
            for i in members) / len(indices))
        summaries.append({
            "layer_id": layer_id, "state": "inferred_candidate", "usable": not reasons,
            "blocking_reasons": sorted(reasons), "source_point_count": len(indices),
            "source_geometry_sha256": fingerprint, "uv_cell_count": len(footprint),
            "uv_coverage_fraction": len(footprint) / len(cells),
            "uv_bounds": [p[:, :2].min(axis=0).tolist(), p[:, :2].max(axis=0).tolist()],
            "depth": depth_summary(p[:, 2]),
            "max_local_depth_span": max(nodes[i]["span"] for i in members),
            "rms_local_depth_residual": rms,
            "local_unique_support": {"min": min(counts), "median": float(np.median(counts)), "max": max(counts)},
            "continuity_edge_count": len(steps), "max_neighbor_median_step": max(steps, default=0.0),
            "disconnected_uv_regions": 1, "overlap_layer_count": 0, "overlap_uv_cell_count": 0,
        })
    summaries.sort(key=lambda s: (s["depth"]["median"], s["uv_bounds"][0], s["layer_id"]))
    overlap_pairs: dict[tuple[str, str], int] = defaultdict(int)
    overlap_cells: dict[str, int] = defaultdict(int)
    for local_nodes in by_cell.values():
        layers = sorted({node_layers[i] for i in local_nodes})
        if len(layers) > 1:
            for layer in layers:
                overlap_cells[layer] += 1
        for i, a in enumerate(layers):
            for b in layers[i + 1:]:
                overlap_pairs[a, b] += 1
    for summary in summaries:
        layer = summary["layer_id"]
        summary["overlap_uv_cell_count"] = overlap_cells[layer]
        summary["overlap_layer_count"] = sum(layer in pair for pair in overlap_pairs)
    unusable = [s for s in summaries if not s["usable"]]
    auto = summaries[0]["layer_id"] if len(summaries) == 1 and not unusable else None
    geometry_sha = canonical_sha256(points)
    fingerprint = hashlib.sha256(json.dumps(
        {"algorithm": "local_depth_components_v1", "geometry": geometry_sha,
         "options": options, "grid_origin_uv": origin.tolist()},
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    public = {
        "type": "section_layer_evidence", "version": "0.15.3", "state": "inferred_candidate",
        "status": "blocked" if unusable else "ready" if auto else "selection_required",
        "source_point_count": len(points), "source_geometry_sha256": geometry_sha,
        "analysis_fingerprint": fingerprint, "parameters": options,
        "grid_origin_uv": origin.tolist(), "uv_cell_count": len(cells), "uv_occupied_cell_area": area,
        "coordinate_precision_floor": {"uv": uv_floor, "depth": depth_floor},
        "depth": depth_summary(points[:, 2], percentiles=True),
        "local_observation_count": len(nodes), "multimodal_uv_cell_count": multimodal,
        "sparse_uv_cell_count": sparse, "thick_uv_cell_count": thick,
        "ambiguous_neighbor_pair_count": branch_pairs,
        "candidate_layer_count": len(summaries), "candidate_layers": summaries,
        "unusable_point_count": sum(s["source_point_count"] for s in unusable),
        "auto_selected_layer_id": auto, "overlap_pair_count": len(overlap_pairs),
        "overlap_preview": [{"layer_ids": list(pair), "uv_cell_count": count}
                            for pair, count in sorted(overlap_pairs.items())[:16]],
        "overlap_preview_truncated": len(overlap_pairs) > 16,
        "raw_points_returned": False, "source_geometry_preserved": True,
        "manufacturing_intent_confirmed": False, "user_accepted": False,
        "warnings": sorted(set(reason for s in summaries for reason in s["blocking_reasons"])),
        "assumptions": ["complete supplied snapshot; not independent live-acquisition proof",
                        "caller-selected half-open UV grid and local depth thresholds",
                        "4-neighbor connectivity; disconnected patches are not joined",
                        "subthreshold or unsampled crossings cannot be ruled out"],
    }
    return SectionLayerAnalysis(public, points, memberships)


def select_section_layer(analysis: SectionLayerAnalysis, *, layer_id: str | None = None,
                         expected_analysis_fingerprint: str | None = None) -> np.ndarray | None:
    """None means return candidates/BLOCKED. Explicit choice cannot bypass unsafe data."""
    public = analysis.public
    if layer_id is not None:
        if expected_analysis_fingerprint != public["analysis_fingerprint"]:
            raise SectionLayerError("Explicit selection requires the current expected_analysis_fingerprint")
        if layer_id not in analysis.layer_source_indices:
            raise SectionLayerError("Unknown layer_id for this exact analysis")
    elif expected_analysis_fingerprint is not None:
        raise SectionLayerError("expected_analysis_fingerprint requires an explicit layer_id")
    if public["status"] == "blocked":
        return None
    selected = layer_id or public["auto_selected_layer_id"]
    return None if selected is None else analysis.layer_source_indices[selected].copy()
