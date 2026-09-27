"""Generate disposable 0.15 CAD-profile acceptance fixtures outside the repository."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _slot_uv(centerline: float = 20.0, radius: float = 5.0) -> np.ndarray:
    half = centerline / 2.0
    line_count, arc_count = 41, 61
    points: list[list[float]] = []
    points.extend([[x, radius] for x in np.linspace(half, -half, line_count)])
    points.extend([
        [-half + radius * math.cos(a), radius * math.sin(a)]
        for a in np.linspace(math.pi / 2, 3 * math.pi / 2, arc_count)[1:]
    ])
    points.extend([[x, -radius] for x in np.linspace(-half, half, line_count)[1:]])
    points.extend([
        [half + radius * math.cos(a), radius * math.sin(a)]
        for a in np.linspace(3 * math.pi / 2, 5 * math.pi / 2, arc_count)[1:-1]
    ])
    return np.asarray(points, dtype=np.float64)


def _rotation(axis: np.ndarray, angle_degrees: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    angle = math.radians(angle_degrees)
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    C = 1.0 - c
    return np.asarray([
        [c + x*x*C, x*y*C - z*s, x*z*C + y*s],
        [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
        [z*x*C - y*s, z*y*C + x*s, c + z*z*C],
    ], dtype=np.float64)


def _write_ply(path: Path, xyz: np.ndarray) -> None:
    lines = [
        "ply", "format ascii 1.0", f"element vertex {xyz.shape[0]}",
        "property double x", "property double y", "property double z", "end_header",
    ]
    lines.extend(f"{x:.17g} {y:.17g} {z:.17g}" for x, y, z in xyz)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def generate(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    uv = _slot_uv()
    local = np.column_stack((uv, np.zeros(uv.shape[0])))

    original_rotation = np.eye(3)
    original_translation = np.zeros(3)
    transformed_rotation = _rotation(np.array([1.0, 2.0, 3.0]), 37.0)
    transformed_translation = np.array([1.0e8, -2.0e8, 3.0e8])

    variants = []
    for name, rotation, translation in (
        ("original", original_rotation, original_translation),
        ("rotated_translated", transformed_rotation, transformed_translation),
    ):
        xyz = local @ rotation.T + translation
        filename = f"slot_{name}.ply"
        _write_ply(output_dir / filename, xyz)
        variants.append({
            "name": name,
            "file": filename,
            "point_count": int(xyz.shape[0]),
            "origin_global": translation.astype(float).tolist(),
            "normal": (rotation @ np.array([0.0, 0.0, 1.0])).astype(float).tolist(),
            "basis_u": (rotation @ np.array([1.0, 0.0, 0.0])).astype(float).tolist(),
            "basis_v": (rotation @ np.array([0.0, 1.0, 0.0])).astype(float).tolist(),
            "bounds_global": {
                "min": np.min(xyz, axis=0).astype(float).tolist(),
                "max": np.max(xyz, axis=0).astype(float).tolist(),
            },
        })

    manifest = {
        "type": "cloudcompare_mcp_profile_acceptance_fixture",
        "version": 1,
        "units": "native",
        "shape": "synthetic_slot_candidate",
        "expected": {
            "radius": 5.0,
            "width": 10.0,
            "centerline_length": 20.0,
            "overall_length": 30.0,
            "primitive_types": ["line", "arc", "line", "arc"],
            "candidate_type": "slot_candidate",
        },
        "recommended": {
            "half_thickness": 0.001,
            "fit_tolerance": 0.001,
            "angular_tolerance_degrees": 0.2,
            "ordering_method": "polar_closed_loop",
            "closed": True,
            "sample_limit": 4096,
        },
        "transform": {
            "rotated_axis": [1.0, 2.0, 3.0],
            "rotated_angle_degrees": 37.0,
            "rotated_translation": transformed_translation.astype(float).tolist(),
        },
        "variants": variants,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = generate(args.output_dir)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
