"""Deterministic occupancy-grid boundary evidence for filled 2D scan sections.

This layer does not treat interior samples as contour samples. It bins projected
section samples into an explicit native-unit grid, traces exposed occupied-cell
edges, associates those edges with original source samples, and returns compact
evidence suitable for the accepted 0.15.1 topology solver.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import math
from typing import Any, Iterable, Sequence

import numpy as np

from .profile_topology import (
    MAX_TOPOLOGY_LOOPS,
    MAX_TOPOLOGY_POINTS,
    ProfileTopologyError,
    reconstruct_profile_topology_2d,
)


class SectionBoundaryError(ProfileTopologyError):
    """Raised when filled-section boundary evidence is unsupported or ambiguous."""


MAX_FILLED_SECTION_POINTS = 20_000
MAX_OCCUPIED_CELLS = 100_000
MAX_BOUNDARY_CONTOURS = MAX_TOPOLOGY_LOOPS


@dataclass
class SectionBoundaryEvidence:
    public: dict[str, Any]
    boundary_points_uv: np.ndarray
    boundary_source_indices: list[int]


def _points2d(points: Iterable[Sequence[float]]) -> np.ndarray:
    try:
        array = np.asarray(list(points), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SectionBoundaryError(
            "points_uv must be an array of 2D numeric section samples"
        ) from exc
    if array.ndim != 2 or array.shape[1:] != (2,):
        raise SectionBoundaryError("points_uv must be an array of [u, v] points")
    if array.shape[0] < 8:
        raise SectionBoundaryError("Filled-section extraction requires at least 8 points")
    if array.shape[0] > MAX_FILLED_SECTION_POINTS:
        raise SectionBoundaryError(
            f"Filled-section extraction supports at most {MAX_FILLED_SECTION_POINTS} points"
        )
    if not np.isfinite(array).all():
        raise SectionBoundaryError("points_uv coordinates must all be finite")
    return array


def _float64_sha256(points: np.ndarray) -> str:
    return hashlib.sha256(
        np.asarray(points, dtype="<f8").tobytes(order="C")
    ).hexdigest()


def _index_sha256(indices: Sequence[int]) -> str:
    return hashlib.sha256(
        np.asarray(indices, dtype="<i8").tobytes(order="C")
    ).hexdigest()


def _precision_floor(points: np.ndarray) -> float:
    spacing = np.abs(np.spacing(np.abs(points)))
    finite = spacing[np.isfinite(spacing)]
    floor = float(np.max(finite)) if finite.size else 0.0
    scale = max(
        float(np.max(np.abs(points))),
        float(np.ptp(points, axis=0).max()),
        1.0,
    )
    return 8.0 * max(floor, np.finfo(np.float64).eps * scale)


def _validate_positive_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise SectionBoundaryError(f"{label} must be finite and positive")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise SectionBoundaryError(f"{label} must be finite and positive") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise SectionBoundaryError(f"{label} must be finite and positive")
    return numeric


def _validate_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SectionBoundaryError(
            f"{label} must be an integer between {minimum} and {maximum}"
        )
    if not minimum <= value <= maximum:
        raise SectionBoundaryError(
            f"{label} must be an integer between {minimum} and {maximum}"
        )
    return value


def _grid_indices(
    points: np.ndarray,
    origin: np.ndarray,
    cell_size: float,
) -> np.ndarray:
    relative = points - origin
    if not np.isfinite(relative).all():
        raise SectionBoundaryError(
            "Section coordinate differences overflow float64; shift coordinates before analysis"
        )
    scaled = relative / cell_size
    if not np.isfinite(scaled).all():
        raise SectionBoundaryError("Grid indexing overflowed float64")
    return np.floor(scaled).astype(np.int64)


def _occupancy(
    points: np.ndarray,
    *,
    origin: np.ndarray,
    cell_size: float,
    min_cell_support: int,
    max_cells: int,
) -> tuple[dict[tuple[int, int], list[int]], int]:
    indices = _grid_indices(points, origin, cell_size)
    raw: dict[tuple[int, int], list[int]] = defaultdict(list)
    for source_index, pair in enumerate(indices):
        raw[(int(pair[0]), int(pair[1]))].append(source_index)
    supported = {
        cell: source_indices
        for cell, source_indices in raw.items()
        if len(source_indices) >= min_cell_support
    }
    if len(supported) < 4:
        raise SectionBoundaryError(
            "Too few supported occupied cells for boundary extraction; "
            "reduce min_cell_support, use a larger cell_size, or acquire denser samples"
        )
    if len(supported) > max_cells:
        raise SectionBoundaryError(
            f"Occupied-cell count {len(supported)} exceeds max_cells={max_cells}"
        )
    return supported, len(raw)


def _material_components(
    occupied: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start in sorted(occupied):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[tuple[int, int]] = []
        while stack:
            current = stack.pop()
            component.append(current)
            i, j = current
            for neighbor in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if neighbor in occupied and neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def _diagonal_ambiguities(
    occupied: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    squares: set[tuple[int, int]] = set()
    for i, j in occupied:
        squares.update(((i, j), (i - 1, j), (i, j - 1), (i - 1, j - 1)))
    ambiguous: list[tuple[int, int]] = []
    for i, j in sorted(squares):
        a = (i, j) in occupied
        b = (i + 1, j) in occupied
        c = (i, j + 1) in occupied
        d = (i + 1, j + 1) in occupied
        if (a and d and not b and not c) or (b and c and not a and not d):
            ambiguous.append((i, j))
    return ambiguous


def _edge_records(
    occupied: set[tuple[int, int]],
) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    """Return oriented grid-lattice edges with occupied material on the left."""
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = []
    for i, j in sorted(occupied):
        if (i, j - 1) not in occupied:
            edges.append(((i, j), (i + 1, j), (i, j)))
        if (i + 1, j) not in occupied:
            edges.append(((i + 1, j), (i + 1, j + 1), (i, j)))
        if (i, j + 1) not in occupied:
            edges.append(((i + 1, j + 1), (i, j + 1), (i, j)))
        if (i - 1, j) not in occupied:
            edges.append(((i, j + 1), (i, j), (i, j)))
    return edges


def _trace_edges(
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]],
) -> list[list[int]]:
    outgoing: dict[tuple[int, int], list[int]] = defaultdict(list)
    incoming: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (start, end, _cell) in enumerate(edges):
        outgoing[start].append(index)
        incoming[end].append(index)

    for vertex in sorted(set(outgoing) | set(incoming)):
        if len(outgoing[vertex]) != 1 or len(incoming[vertex]) != 1:
            raise SectionBoundaryError(
                "Exposed grid edges do not form unambiguous closed contours; "
                "diagonal contacts, gaps, or non-manifold occupancy are present"
            )

    loops: list[list[int]] = []
    seen: set[int] = set()
    for start_edge in range(len(edges)):
        if start_edge in seen:
            continue
        current = start_edge
        loop: list[int] = []
        while current not in seen:
            seen.add(current)
            loop.append(current)
            end = edges[current][1]
            current = outgoing[end][0]
        if current != start_edge:
            raise SectionBoundaryError(
                "Boundary edge trace entered another contour instead of closing"
            )
        if len(loop) < 4:
            raise SectionBoundaryError("Boundary contour contains fewer than four grid edges")
        loops.append(loop)
    return loops


def _signed_grid_area(
    loop: list[int],
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]],
    cell_size: float,
) -> float:
    vertices = np.asarray([edges[index][0] for index in loop], dtype=np.float64)
    relative = vertices - vertices[0]
    x = relative[:, 0]
    y = relative[:, 1]
    area_cells = 0.5 * float(
        np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))
    )
    return area_cells * cell_size * cell_size


def _bounds_for_loop(
    loop: list[int],
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]],
    origin: np.ndarray,
    cell_size: float,
) -> dict[str, list[float]]:
    vertices = np.asarray([edges[index][0] for index in loop], dtype=np.float64)
    uv = origin + vertices * cell_size
    return {
        "u": [float(np.min(uv[:, 0])), float(np.max(uv[:, 0]))],
        "v": [float(np.min(uv[:, 1])), float(np.max(uv[:, 1]))],
    }


def _representative_source_indices(
    points: np.ndarray,
    loop: list[int],
    edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]],
    occupied: dict[tuple[int, int], list[int]],
    origin: np.ndarray,
    cell_size: float,
) -> list[int]:
    # A corner boundary cell can own two exposed edges. Feeding one source sample
    # per edge into the accepted radius-graph topology solver creates local clusters
    # and shortcut edges. Instead retain one original representative per boundary
    # cell, targeted at the mean midpoint of that cell's exposed contour edges.
    # Adjacent representatives then follow the cell chain without synthesizing grid
    # vertices or modifying the accepted topology algorithm.
    cell_order: list[tuple[int, int]] = []
    midpoints_by_cell: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    for edge_index in loop:
        start, end, cell = edges[edge_index]
        if cell not in midpoints_by_cell:
            cell_order.append(cell)
        midpoint_lattice = np.asarray(
            [
                (start[0] + end[0]) * 0.5,
                (start[1] + end[1]) * 0.5,
            ],
            dtype=np.float64,
        )
        midpoints_by_cell[cell].append(
            origin + midpoint_lattice * cell_size
        )

    selected: list[int] = []
    for cell in cell_order:
        target = np.mean(np.vstack(midpoints_by_cell[cell]), axis=0)
        chosen = min(
            occupied[cell],
            key=lambda index: (
                float(np.linalg.norm(points[index] - target)),
                index,
            ),
        )
        selected.append(int(chosen))

    if len(selected) < 6:
        raise SectionBoundaryError(
            "A traced contour has fewer than six distinct boundary cells with "
            "associated source samples; use a finer supported cell_size or denser acquisition"
        )
    return selected


def _support_statistics(
    occupied: dict[tuple[int, int], list[int]],
) -> tuple[dict[str, Any], list[str]]:
    counts = np.asarray([len(value) for value in occupied.values()], dtype=np.float64)
    mean = float(np.mean(counts))
    std = float(np.std(counts))
    stats = {
        "min": int(np.min(counts)),
        "median": float(np.median(counts)),
        "p90": float(np.percentile(counts, 90)),
        "max": int(np.max(counts)),
        "mean": mean,
        "coefficient_of_variation": 0.0 if mean == 0 else std / mean,
        "single_sample_cell_fraction": float(np.mean(counts == 1)),
    }
    warnings: list[str] = []
    if stats["coefficient_of_variation"] > 1.5:
        warnings.append(
            "Occupied-cell support is strongly nonuniform; occupancy boundaries may depend on sampling density."
        )
    if stats["single_sample_cell_fraction"] > 0.5:
        warnings.append(
            "More than half of occupied cells contain only one source sample; boundary evidence is weakly supported."
        )
    return stats, warnings


def _topology_signature(
    points: np.ndarray,
    *,
    origin: np.ndarray,
    cell_size: float,
    min_cell_support: int,
    max_cells: int,
) -> dict[str, Any]:
    try:
        occupied_map, _raw_count = _occupancy(
            points,
            origin=origin,
            cell_size=cell_size,
            min_cell_support=min_cell_support,
            max_cells=max_cells,
        )
        occupied = set(occupied_map)
        if _diagonal_ambiguities(occupied):
            return {"valid": False, "issue": "diagonal_only_connection"}
        components = _material_components(occupied)
        edges = _edge_records(occupied)
        loops = _trace_edges(edges)
        return {
            "valid": True,
            "occupied_cell_count": len(occupied),
            "material_component_count": len(components),
            "contour_count": len(loops),
        }
    except SectionBoundaryError as exc:
        return {"valid": False, "issue": str(exc)}


def _occupied_topology_signature(
    occupied: set[tuple[int, int]],
) -> dict[str, Any]:
    if not occupied:
        return {"valid": False, "issue": "occupancy_empty"}
    diagonal = _diagonal_ambiguities(occupied)
    if diagonal:
        return {
            "valid": False,
            "issue": "diagonal_only_connection",
            "diagonal_only_connection_count": len(diagonal),
        }
    try:
        components = _material_components(occupied)
        edges = _edge_records(occupied)
        loops = _trace_edges(edges)
    except SectionBoundaryError as exc:
        return {"valid": False, "issue": str(exc)}
    return {
        "valid": True,
        "occupied_cell_count": len(occupied),
        "material_component_count": len(components),
        "contour_count": len(loops),
    }


def _one_cell_perturbation_diagnostic(
    occupied: set[tuple[int, int]],
) -> dict[str, Any]:
    neighbors = ((-1, 0), (1, 0), (0, -1), (0, 1))
    dilated = set(occupied)
    for i, j in occupied:
        for di, dj in neighbors:
            dilated.add((i + di, j + dj))

    eroded = {
        (i, j)
        for i, j in occupied
        if all((i + di, j + dj) in occupied for di, dj in neighbors)
    }

    base = _occupied_topology_signature(occupied)
    erosion = _occupied_topology_signature(eroded)
    dilation = _occupied_topology_signature(dilated)

    stable = bool(base.get("valid"))
    for perturbed in (erosion, dilation):
        if (
            not perturbed.get("valid")
            or perturbed.get("material_component_count")
            != base.get("material_component_count")
            or perturbed.get("contour_count") != base.get("contour_count")
        ):
            stable = False

    return {
        "applied_to_reconstruction": False,
        "policy": (
            "single diagnostic 4-neighbor erosion and dilation only; "
            "perturbed occupancy never replaces measured occupancy"
        ),
        "base": base,
        "one_cell_erosion": erosion,
        "one_cell_dilation": dilation,
        "topology_stable": stable,
    }


def extract_section_boundary_evidence_2d(
    points_uv: Iterable[Sequence[float]],
    *,
    cell_size: float,
    min_cell_support: int = 1,
    min_component_cells: int = 2,
    max_cells: int = 100_000,
    max_boundary_points: int = MAX_TOPOLOGY_POINTS,
    check_grid_origin_sensitivity: bool = True,
) -> SectionBoundaryEvidence:
    points = _points2d(points_uv)
    cell = _validate_positive_float(cell_size, "cell_size")
    min_support = _validate_int(min_cell_support, "min_cell_support", 1, 1_000_000)
    min_component = _validate_int(
        min_component_cells, "min_component_cells", 1, MAX_OCCUPIED_CELLS
    )
    cell_budget = _validate_int(max_cells, "max_cells", 4, MAX_OCCUPIED_CELLS)
    boundary_budget = _validate_int(
        max_boundary_points, "max_boundary_points", 6, MAX_TOPOLOGY_POINTS
    )

    precision_floor = _precision_floor(points)
    if cell < precision_floor:
        raise SectionBoundaryError(
            f"cell_size {cell:.17g} is below the representable coordinate precision floor "
            f"{precision_floor:.17g}"
        )

    origin = np.min(points, axis=0)
    occupied_map, raw_cell_count = _occupancy(
        points,
        origin=origin,
        cell_size=cell,
        min_cell_support=min_support,
        max_cells=cell_budget,
    )
    occupied = set(occupied_map)

    diagonal = _diagonal_ambiguities(occupied)
    if diagonal:
        preview = diagonal[:8]
        raise SectionBoundaryError(
            "Occupancy contains ambiguous diagonal-only cell connections at "
            f"{preview}; choose a better-supported cell_size rather than guessing connectivity"
        )

    components = _material_components(occupied)
    tiny = [len(component) for component in components if len(component) < min_component]
    if tiny:
        raise SectionBoundaryError(
            "Occupancy contains disconnected components smaller than "
            f"min_component_cells={min_component}: {tiny[:8]}; noise is not discarded silently"
        )

    edges = _edge_records(occupied)
    loops = _trace_edges(edges)
    if len(loops) > MAX_BOUNDARY_CONTOURS:
        raise SectionBoundaryError(
            f"Boundary extraction found {len(loops)} contours, exceeding "
            f"{MAX_BOUNDARY_CONTOURS}"
        )

    support_stats, warnings = _support_statistics(occupied_map)
    perturbation = _one_cell_perturbation_diagnostic(occupied)
    if not perturbation["topology_stable"]:
        warnings.append(
            "Material-component or contour count changes under a single one-cell "
            "erosion/dilation diagnostic; narrow or weakly supported topology is "
            "resolution-sensitive. The perturbed occupancy is not used for reconstruction."
        )
    rejected_cells = raw_cell_count - len(occupied_map)
    if rejected_cells:
        warnings.append(
            f"{rejected_cells} raw occupied cells were below min_cell_support={min_support}; "
            "they were excluded explicitly, not repaired."
        )

    contour_records: list[dict[str, Any]] = []
    boundary_source_indices: list[int] = []
    boundary_cells: set[tuple[int, int]] = set()
    for contour_index, loop in enumerate(loops):
        source_indices = _representative_source_indices(
            points,
            loop,
            edges,
            occupied_map,
            origin,
            cell,
        )
        boundary_source_indices.extend(source_indices)
        for edge_index in loop:
            boundary_cells.add(edges[edge_index][2])
        source_points = points[source_indices]
        signed_area = _signed_grid_area(loop, edges, cell)
        preview = (
            source_indices[:8]
            if len(source_indices) <= 16
            else source_indices[:8] + source_indices[-8:]
        )
        contour_records.append(
            {
                "contour_id": f"contour-{contour_index}",
                "state": "inferred_candidate",
                "edge_count": len(loop),
                "closed": True,
                "orientation": "ccw" if signed_area > 0 else "cw",
                "facing_candidate": (
                    "material_exterior" if signed_area > 0 else "enclosed_empty_region"
                ),
                "signed_grid_area": float(signed_area),
                "bounds_uv": _bounds_for_loop(loop, edges, origin, cell),
                "associated_source_point_count": len(source_indices),
                "associated_source_indices_sha256_int64_le": _index_sha256(source_indices),
                "associated_source_index_preview": list(map(int, preview)),
                "associated_source_points_sha256_float64_le": _float64_sha256(source_points),
            }
        )

    if len(boundary_source_indices) > boundary_budget:
        raise SectionBoundaryError(
            f"Boundary evidence requires {len(boundary_source_indices)} distinct source "
            f"samples, exceeding max_boundary_points={boundary_budget}; use a larger "
            "cell_size or isolate a smaller section instead of silently thinning evidence"
        )

    sensitivity: list[dict[str, Any]] = []
    stable = True
    if check_grid_origin_sensitivity:
        base_signature = {
            "valid": True,
            "occupied_cell_count": len(occupied),
            "material_component_count": len(components),
            "contour_count": len(loops),
        }
        for du, dv in ((0.5, 0.0), (0.0, 0.5), (0.5, 0.5)):
            shifted_origin = origin + np.asarray([du * cell, dv * cell])
            signature = _topology_signature(
                points,
                origin=shifted_origin,
                cell_size=cell,
                min_cell_support=min_support,
                max_cells=cell_budget,
            )
            signature["origin_shift_cells"] = [du, dv]
            sensitivity.append(signature)
            if (
                not signature.get("valid")
                or signature.get("material_component_count")
                != base_signature["material_component_count"]
                or signature.get("contour_count") != base_signature["contour_count"]
            ):
                stable = False
        if not stable:
            warnings.append(
                "Material-component or contour count changes under half-cell grid-origin "
                "shifts; reconstruction from this cell_size is grid-sensitive."
            )

    selected = points[boundary_source_indices]
    grid_i = [cell_key[0] for cell_key in occupied]
    grid_j = [cell_key[1] for cell_key in occupied]
    public = {
        "type": "section_boundary_evidence",
        "version": "0.15.2",
        "coordinate_space": "section_uv",
        "units": "native",
        "state": "inferred_candidate",
        "source_geometry_preserved": True,
        "input_point_count": int(points.shape[0]),
        "input_points_sha256_float64_le": _float64_sha256(points),
        "raw_points_returned": False,
        "cell_size": cell,
        "coordinate_precision_floor": precision_floor,
        "grid_origin_uv": [float(origin[0]), float(origin[1])],
        "grid_index_bounds": {
            "i": [int(min(grid_i)), int(max(grid_i))],
            "j": [int(min(grid_j)), int(max(grid_j))],
        },
        "min_cell_support": min_support,
        "raw_occupied_cell_count": raw_cell_count,
        "occupied_cell_count": len(occupied),
        "rejected_low_support_cell_count": rejected_cells,
        "material_component_count": len(components),
        "boundary_cell_count": len(boundary_cells),
        "boundary_edge_count": len(edges),
        "connected_contour_count": len(loops),
        "support_statistics": support_stats,
        "source_boundary_evidence": {
            "point_count": len(boundary_source_indices),
            "source_indices_sha256_int64_le": _index_sha256(boundary_source_indices),
            "source_points_sha256_float64_le": _float64_sha256(selected),
            "raw_points_returned": False,
        },
        "contours": contour_records,
        "ambiguity": {
            "diagonal_only_connection_count": 0,
            "grid_origin_sensitivity_checked": bool(check_grid_origin_sensitivity),
            "topology_stable_under_half_cell_origin_shifts": stable,
            "origin_shift_results": sensitivity,
            "one_cell_perturbation": perturbation,
            "warnings": warnings,
        },
        "assumptions": [
            "occupied grid cells represent material support in the projected section",
            "empty neighboring cells represent absence of material at the selected cell_size",
            "section_uv snapshots cannot distinguish multiple 3D surfaces that project onto the same cells",
            "no morphological repair is applied; one-step erosion/dilation is diagnostic only and never replaces measured occupancy",
        ],
    }
    return SectionBoundaryEvidence(
        public=public,
        boundary_points_uv=selected.copy(),
        boundary_source_indices=list(map(int, boundary_source_indices)),
    )


def _minimum_two_neighbor_radius(points: np.ndarray) -> float:
    if points.shape[0] < 3:
        raise SectionBoundaryError(
            "Boundary evidence has too few points for two-neighbor topology"
        )
    delta = points[:, None, :] - points[None, :, :]
    distances = np.sqrt(np.sum(delta * delta, axis=2))
    np.fill_diagonal(distances, np.inf)
    second_nearest = np.partition(distances, 1, axis=1)[:, 1]
    required = float(np.max(second_nearest))
    if not math.isfinite(required):
        raise SectionBoundaryError(
            "Boundary evidence cannot establish two finite local neighbors per sample"
        )
    return required


def reconstruct_filled_section_profile_2d(
    points_uv: Iterable[Sequence[float]],
    *,
    cell_size: float,
    max_edge_length: float,
    fit_tolerance: float,
    min_cell_support: int = 1,
    min_component_cells: int = 2,
    max_cells: int = 100_000,
    max_boundary_points: int = MAX_TOPOLOGY_POINTS,
    angular_tolerance_degrees: float = 1.0,
    minimum_loop_points: int = 6,
    max_loops: int = 16,
    minimum_arc_angle_degrees: float = 12.0,
    max_segments_per_loop: int = 64,
    require_grid_stability: bool = True,
) -> dict[str, Any]:
    evidence = extract_section_boundary_evidence_2d(
        points_uv,
        cell_size=cell_size,
        min_cell_support=min_cell_support,
        min_component_cells=min_component_cells,
        max_cells=max_cells,
        max_boundary_points=max_boundary_points,
        check_grid_origin_sensitivity=True,
    )
    stable = evidence.public["ambiguity"][
        "topology_stable_under_half_cell_origin_shifts"
    ]
    if require_grid_stability and not stable:
        raise SectionBoundaryError(
            "Filled-section reconstruction is grid-sensitive at the requested cell_size; "
            "inspect extract_section_boundary_evidence diagnostics and choose a better-supported "
            "resolution instead of fabricating stable topology"
        )

    edge_limit = _validate_positive_float(max_edge_length, "max_edge_length")
    required_two_neighbor_radius = _minimum_two_neighbor_radius(
        evidence.boundary_points_uv
    )
    if edge_limit < required_two_neighbor_radius:
        raise SectionBoundaryError(
            f"max_edge_length {edge_limit:.17g} is too small for extracted boundary "
            f"evidence; at least {required_two_neighbor_radius:.17g} is required "
            "for every selected source sample to have two local neighbors"
        )

    topology = reconstruct_profile_topology_2d(
        evidence.boundary_points_uv,
        max_edge_length=max_edge_length,
        fit_tolerance=fit_tolerance,
        angular_tolerance_degrees=angular_tolerance_degrees,
        minimum_loop_points=minimum_loop_points,
        max_loops=max_loops,
        minimum_arc_angle_degrees=minimum_arc_angle_degrees,
        max_segments_per_loop=max_segments_per_loop,
    )
    if topology["loop_count"] != evidence.public["connected_contour_count"]:
        raise SectionBoundaryError(
            "Boundary evidence and accepted topology solver disagree on loop count; "
            "the reconstruction is ambiguous at the requested thresholds"
        )

    candidates: list[dict[str, Any]] = []
    for loop in topology["loops"]:
        profile = loop.get("profile", {})
        for candidate in profile.get("profile_candidates", []):
            candidates.append(
                {
                    "loop_id": loop.get("loop_id"),
                    "role_candidate": loop.get("role_candidate"),
                    "candidate": candidate,
                }
            )

    return {
        "type": "cad_filled_section_profile",
        "version": "0.15.2",
        "coordinate_space": "section_uv",
        "units": "native",
        "state": "inferred_candidate",
        "topology_confirmed": False,
        "manufacturing_intent_confirmed": False,
        "user_accepted": False,
        "source_geometry_preserved": True,
        "raw_points_returned": False,
        "extraction": evidence.public,
        "topology": topology,
        "topology_handoff_diagnostics": {
            "max_edge_length": edge_limit,
            "minimum_two_neighbor_radius": required_two_neighbor_radius,
            "margin": edge_limit - required_two_neighbor_radius,
        },
        "profile_candidates": candidates,
        "provenance": {
            "boundary_evidence_source_point_count": len(
                evidence.boundary_source_indices
            ),
            "boundary_evidence_source_indices_sha256_int64_le": _index_sha256(
                evidence.boundary_source_indices
            ),
        },
        "quality_warnings": list(evidence.public["ambiguity"]["warnings"]),
    }
