"""Generate disposable 0.15.2 filled-section boundary fixtures outside the repository."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def _inside_concave_outer(x: float, y: float) -> bool:
    return (
        -10.0 <= x <= 10.0
        and -8.0 <= y <= 8.0
        and not (-4.0 < x < 4.0 and 2.0 < y <= 8.0)
    )


def _filled_profile(spacing: float = 0.2) -> np.ndarray:
    xs = np.arange(-10.0, 10.0 + spacing * 0.25, spacing)
    ys = np.arange(-8.0, 8.0 + spacing * 0.25, spacing)
    output: list[tuple[float, float]] = []
    for y in ys:
        for x in xs:
            if not _inside_concave_outer(float(x), float(y)):
                continue
            radius = math.hypot(float(x), float(y) + 2.0)
            # Material outer region, circular empty region, and nested material island.
            if radius < 2.5 and radius > 0.8:
                continue
            output.append((float(x), float(y)))
    return np.asarray(output, dtype=np.float64)


def _nonuniform_profile() -> np.ndarray:
    points = _filled_profile(0.2)
    keep = np.ones(points.shape[0], dtype=bool)
    candidates = np.flatnonzero(points[:, 0] > 1.0)
    keep[candidates[::3]] = False
    return points[keep]


def _narrow_feature_profile(spacing: float = 0.2) -> np.ndarray:
    xs = np.arange(-8.0, 8.0 + spacing * 0.25, spacing)
    ys = np.arange(-6.0, 6.0 + spacing * 0.25, spacing)
    output: list[tuple[float, float]] = []
    for y in ys:
        for x in xs:
            inside = -8.0 <= x <= 8.0 and -6.0 <= y <= 6.0
            # Open notch only 1.5 native units wide (three 0.5-unit cells).
            in_notch = -0.75 < x < 0.75 and 2.0 < y <= 6.0
            if inside and not in_notch:
                output.append((float(x), float(y)))
    return np.asarray(output, dtype=np.float64)


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


def _variant(
    output_dir: Path,
    *,
    name: str,
    uv: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    z_offsets: np.ndarray | None = None,
) -> dict:
    if z_offsets is None:
        z_offsets = np.zeros(uv.shape[0], dtype=np.float64)
    local = np.column_stack((uv, z_offsets))
    xyz = local @ rotation.T + translation
    filename = f"filled_section_{name}.ply"
    _write_ply(output_dir / filename, xyz)
    return {
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


def generate(output_dir: Path) -> dict:
    repository_root = Path(__file__).resolve().parents[1]
    resolved = output_dir.resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ValueError("Filled-section fixtures must be generated outside the repository")

    output_dir.mkdir(parents=True, exist_ok=False)

    base = _filled_profile()
    rng = np.random.default_rng(15801)
    base = base[rng.permutation(base.shape[0])]

    rotation = _rotation(np.array([1.0, 2.0, 3.0]), 41.0)
    translation = np.array([1.0e8, -2.0e8, 3.0e8], dtype=np.float64)

    variants = [
        _variant(
            output_dir,
            name="original",
            uv=base,
            rotation=np.eye(3),
            translation=np.zeros(3),
        ),
        _variant(
            output_dir,
            name="rotated_translated",
            uv=base,
            rotation=rotation,
            translation=translation,
        ),
    ]

    nonuniform = _nonuniform_profile()
    nonuniform = nonuniform[
        np.random.default_rng(15802).permutation(nonuniform.shape[0])
    ]
    variants.append(
        _variant(
            output_dir,
            name="nonuniform_density",
            uv=nonuniform,
            rotation=np.eye(3),
            translation=np.zeros(3),
        )
    )

    narrow = _narrow_feature_profile()
    narrow = narrow[np.random.default_rng(15803).permutation(narrow.shape[0])]
    variants.append(
        _variant(
            output_dir,
            name="narrow_feature",
            uv=narrow,
            rotation=np.eye(3),
            translation=np.zeros(3),
        )
    )

    # Duplicate the same projected material samples onto two separated planes.
    # The live wrapper should report this as unsupported projected-layer ambiguity.
    layered_uv = np.repeat(base, 2, axis=0)
    layered_z = np.tile(np.asarray([-0.45, 0.45], dtype=np.float64), base.shape[0])
    layered_perm = np.random.default_rng(15804).permutation(layered_uv.shape[0])
    variants.append(
        _variant(
            output_dir,
            name="overlapping_layers",
            uv=layered_uv[layered_perm],
            rotation=np.eye(3),
            translation=np.zeros(3),
            z_offsets=layered_z[layered_perm],
        )
    )

    manifest = {
        "type": "cloudcompare_mcp_filled_section_boundary_fixture",
        "version": 1,
        "units": "native",
        "shape": "filled_concave_outer_with_hole_and_island",
        "expected": {
            "base_loop_count": 3,
            "base_roles": ["outer", "hole", "island"],
            "base_material_component_count": 2,
            "narrow_feature_contour_count": 1,
            "overlapping_layers_live_result": "reject_as_ambiguous",
        },
        "recommended": {
            "half_thickness": 0.05,
            "cell_size": 0.5,
            "min_cell_support": 1,
            "min_component_cells": 2,
            "max_cells": 20000,
            "max_boundary_points": 2048,
            "max_edge_length": 1.25,
            "fit_tolerance": 0.35,
            "angular_tolerance_degrees": 2.0,
            "minimum_loop_points": 6,
            "max_loops": 8,
            "sample_limit": 20000,
            "require_grid_stability": True,
        },
        "overlapping_layers_half_thickness": 0.5,
        "transform": {
            "rotated_axis": [1.0, 2.0, 3.0],
            "rotated_angle_degrees": 41.0,
            "rotated_translation": translation.astype(float).tolist(),
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
