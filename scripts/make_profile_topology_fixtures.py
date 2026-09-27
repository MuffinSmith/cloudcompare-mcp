"""Generate disposable 0.15.1 multi-loop topology fixtures outside the repository."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _sample_polygon(vertices: list[tuple[float, float]], spacing: float) -> np.ndarray:
    polygon = np.asarray(vertices, dtype=np.float64)
    output: list[np.ndarray] = []
    for index in range(len(polygon)):
        start = polygon[index]
        end = polygon[(index + 1) % len(polygon)]
        length = float(np.linalg.norm(end - start))
        count = max(1, int(math.ceil(length / spacing)))
        for t in np.linspace(0.0, 1.0, count, endpoint=False):
            output.append(start * (1.0 - t) + end * t)
    return np.asarray(output, dtype=np.float64)


def _circle(radius: float, count: int, center=(0.0, -2.0)) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    return np.column_stack(
        (
            center[0] + radius * np.cos(theta),
            center[1] + radius * np.sin(theta),
        )
    ).astype(np.float64)


def _rotation(axis: np.ndarray, angle_degrees: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    angle = math.radians(angle_degrees)
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    C = 1.0 - c
    return np.asarray(
        [
            [c + x*x*C, x*y*C - z*s, x*z*C + y*s],
            [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
            [z*x*C - y*s, z*y*C + x*s, c + z*z*C],
        ],
        dtype=np.float64,
    )


def _write_ply(path: Path, xyz: np.ndarray) -> None:
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {xyz.shape[0]}",
        "property double x",
        "property double y",
        "property double z",
        "end_header",
    ]
    lines.extend(f"{x:.17g} {y:.17g} {z:.17g}" for x, y, z in xyz)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _polygon_area(points: np.ndarray) -> float:
    relative = points - points[0]
    x = relative[:, 0]
    y = relative[:, 1]
    return 0.5 * abs(float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1))))


def generate(output_dir: Path) -> dict:
    repository_root = Path(__file__).resolve().parents[1]
    resolved = output_dir.resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ValueError("Topology fixtures must be generated outside the repository")

    output_dir.mkdir(parents=True, exist_ok=False)

    # Concave U/notched rectangle.  The circular hole and island sit in the
    # lower material region, away from the open notch.
    outer = _sample_polygon(
        [
            (-10.0, -8.0),
            (10.0, -8.0),
            (10.0, 8.0),
            (4.0, 8.0),
            (4.0, 2.0),
            (-4.0, 2.0),
            (-4.0, 8.0),
            (-10.0, 8.0),
        ],
        spacing=0.4,
    )
    hole = _circle(2.5, 64)
    island = _circle(0.8, 32)

    labelled = [
        ("outer", outer),
        ("hole", hole),
        ("island", island),
    ]
    uv = np.vstack([points for _, points in labelled])
    labels = np.concatenate(
        [
            np.full(points.shape[0], index, dtype=np.int64)
            for index, (_, points) in enumerate(labelled)
        ]
    )

    rng = np.random.default_rng(15501)
    permutation = rng.permutation(uv.shape[0])
    uv = uv[permutation]
    labels = labels[permutation]

    local = np.column_stack((uv, np.zeros(uv.shape[0], dtype=np.float64)))
    transformed_rotation = _rotation(np.array([1.0, 2.0, 3.0]), 41.0)
    transformed_translation = np.array([1.0e8, -2.0e8, 3.0e8], dtype=np.float64)

    variants = []
    for name, rotation, translation in (
        ("original", np.eye(3), np.zeros(3)),
        ("rotated_translated", transformed_rotation, transformed_translation),
    ):
        xyz = local @ rotation.T + translation
        filename = f"topology_{name}.ply"
        _write_ply(output_dir / filename, xyz)
        variants.append(
            {
                "name": name,
                "file": filename,
                "point_count": int(xyz.shape[0]),
                "origin_global": translation.astype(float).tolist(),
                "normal": (
                    rotation @ np.array([0.0, 0.0, 1.0])
                ).astype(float).tolist(),
                "basis_u": (
                    rotation @ np.array([1.0, 0.0, 0.0])
                ).astype(float).tolist(),
                "basis_v": (
                    rotation @ np.array([0.0, 1.0, 0.0])
                ).astype(float).tolist(),
                "bounds_global": {
                    "min": np.min(xyz, axis=0).astype(float).tolist(),
                    "max": np.max(xyz, axis=0).astype(float).tolist(),
                },
            }
        )

    counts = {
        name: int(np.count_nonzero(labels == index))
        for index, (name, _) in enumerate(labelled)
    }
    manifest = {
        "type": "cloudcompare_mcp_profile_topology_acceptance_fixture",
        "version": 1,
        "units": "native",
        "shape": "concave_outer_with_hole_and_island",
        "input_order": "deterministically shuffled across all loops",
        "expected": {
            "loop_count": 3,
            "roles": ["outer", "hole", "island"],
            "nesting_depths": [0, 1, 2],
            "source_point_counts": counts,
            "outer_area": _polygon_area(outer),
            "hole_radius": 2.5,
            "island_radius": 0.8,
        },
        "recommended": {
            "half_thickness": 0.001,
            "boundary_samples_only": True,
            "max_edge_length": 0.75,
            "fit_tolerance": 0.001,
            "angular_tolerance_degrees": 0.2,
            "minimum_loop_points": 12,
            "max_loops": 8,
            "sample_limit": 2048,
        },
        "transform": {
            "rotated_axis": [1.0, 2.0, 3.0],
            "rotated_angle_degrees": 41.0,
            "rotated_translation": transformed_translation.astype(float).tolist(),
        },
        "variants": variants,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
