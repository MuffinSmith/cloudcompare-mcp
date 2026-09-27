"""Create disposable datum acceptance fixtures outside the repository; no overwrite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def create_fixtures(output_dir: Path) -> dict:
    output_dir = Path(output_dir).resolve()
    repository = Path(__file__).resolve().parents[1]
    if output_dir == repository or repository in output_dir.parents:
        raise ValueError("Generated fixtures must be outside the repository")
    output_dir.mkdir(parents=True, exist_ok=False)
    grid = np.linspace(-10, 10, 41)
    primary = np.array([[x, y, 0] for x in grid for y in grid])
    secondary = np.array([[x, 0, z] for x in grid for z in np.linspace(-2, 8, 25)])
    bore = np.array([[3 + 2*np.cos(t), 4 + 2*np.sin(t), z]
                     for z in np.linspace(1, 9, 17) for t in np.linspace(0, 2*np.pi, 96, endpoint=False)])
    axis = np.array([1., 2., 3.]); axis /= np.linalg.norm(axis)
    x, y, z = axis
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    angle = np.deg2rad(37)
    rotated = np.eye(3) + np.sin(angle)*cross + (1-np.cos(angle))*(cross @ cross)
    manifest = {"units": "native", "physical_units_confirmed": False, "variants": {}}
    for name, rotation, translation in (("original", np.eye(3), np.zeros(3)),
                                        ("rotated_translated", rotated, np.array([1e8, -2e8, 3e8]))):
        folder = output_dir / name; folder.mkdir()
        files = {}
        for label, points in (("primary", primary), ("secondary", secondary), ("bore", bore)):
            path = folder / f"{label}.xyz"
            values = points @ rotation.T + translation
            np.savetxt(path, values, fmt="%.17g")
            files[label] = {"path": str(path), "point_count": len(points),
                            "bounds_global": [values.min(axis=0).tolist(), values.max(axis=0).tolist()]}
        manifest["variants"][name] = {
            "files": files, "rotation": rotation.tolist(), "translation": translation.tolist(),
            "expected_origin_global": (rotation @ [3, 4, 0] + translation).tolist(),
            "expected_x_axis": rotation[:, 0].tolist(), "expected_z_axis": rotation[:, 2].tolist(),
            "expected_radius": 2, "expected_axis_primary_plane_angle_degrees": 90,
        }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory outside the checkout")
    args = parser.parse_args()
    create_fixtures(args.output_dir)
    print(args.output_dir.resolve() / "manifest.json")


if __name__ == "__main__":
    main()
