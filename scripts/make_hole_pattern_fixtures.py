#!/usr/bin/env python3
"""Write small deterministic circular-candidate fixtures outside the checkout.

These are sampled circles, not manufactured holes or hole-topology ground truth.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np


def write_fixtures(outdir: Path) -> dict:
    outdir = outdir.resolve()
    repo = Path(__file__).resolve().parents[1]
    if outdir == repo or repo in outdir.parents:
        raise ValueError("Fixture output must be outside the repository")
    outdir.mkdir(parents=True, exist_ok=True)
    centers = {
        "square": [(-10,-10),(10,-10),(10,10),(-10,10)],
        "row": [(-10,0),(0,0),(10,0)],
        "irregular": [(-10,-10),(10,-10),(8,7),(-10,10)],
        "bolt6": [(10*math.cos(i*math.pi/3),10*math.sin(i*math.pi/3)) for i in range(6)],
    }
    result = {}
    for name, xy in centers.items():
        path = outdir / f"{name}.ply"
        # Exclusive mode prevents accidental replacement of even disposable input.
        with path.open("x", encoding="ascii", newline="\n") as out:
            out.write("ply\nformat ascii 1.0\n" + f"element vertex {120*len(xy)}\n" +
                      "property double x\nproperty double y\nproperty double z\nend_header\n")
            for x,y in xy:
                for angle in np.linspace(0,2*math.pi,120,endpoint=False):
                    out.write(f"{x+2*math.cos(angle):.15g} {y+2*math.sin(angle):.15g} 0\n")
        result[name] = {"path":str(path),"circle_centers_global":[[x,y,0] for x,y in xy],
                        "circle_radius":2,"point_count":len(xy)*120,"physical_holes":False}
    with (outdir / "fixtures.json").open("x",encoding="utf-8") as out:
        json.dump(result,out,indent=2,allow_nan=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_fixtures(args.outdir),indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
