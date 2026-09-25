# Experimental multi-scan wisp detection

This prototype finds small protrusions contradicted by other aligned scans.
It writes reversible PLY subsets and per-point evidence. It does not control a
CloudCompare process, change source files, move points, smooth geometry, or mesh.
Load the result into the live GUI to inspect it. It is not yet a production MCP tool.

## Run

Use the local development environment with `requirements.txt` installed:

```powershell
python detect_wisps.py wrap.ply top.ply bottom.ply --output new-run --tolerance 0.15
python test_detect_wisps.py
python evaluate_labels.py new-run reviewed-labels.json
```

Inputs must be distinct, already aligned point-only PLYs with finite XYZ and
nonzero normals. Normals should have consistent orientation between scans.
Tolerance is in native coordinate units, not assumed millimeters. Select it above
registration error. Output must be a new directory; previous runs are not overwritten.

## Method

1. Estimate local spacing, neighborhood shape, and spacing relative to neighbors.
2. For each independent scan, examine reference patches at six and ten local
   spacings. Group normals rather than mixing opposite faces or using the suspect
   point's own normal to select the surface.
3. Require at least ten similarly oriented observations and low robust scatter.
   A point must depart from a coherent patch at both scales. A supported face
   vetoes that reference's rejection. Uncovered regions remain unknown.
4. Require all reference scans with evidence to agree on the departure.
5. Group suspect points spatially. Only small groups containing a sparse seed
   with a strong residual and evidence from two scans (one if only two inputs)
   enter the proposed removal mask. Larger or unseeded groups remain review-only.

The geometry code contains no bearing-cap coordinates, hole radii, or manually
selected point indices. PCA linearity and roughness are saved for inspection,
but do not independently justify deletion of potentially legitimate thin features.

## Outputs and benchmark discipline

Each input produces `after.ply`, `removed.ply`, `review.ply`, and `labels.npz`.
The archive records decisions, evidence votes, coverage, residual severity,
density ratio, component IDs and neighborhood measurements at original indices.
The manifest records source hashes, parameters and environment, and the detector
source is snapshotted. Retained point records are round-trip checked exactly.
Source PLY metadata comments are not copied; all per-vertex properties are retained.

Keep human labels separate from predictions. `evaluate_labels.py` requires the
source hash, so labels cannot silently be applied to a different or filtered cloud.
Unlabeled points are unknown, not presumed clean. Example:

```json
{"input_sha256":"sha256-of-original-ply", "positive":[12,42], "negative":[90,91]}
```

For a useful benchmark, label complete protrusion clusters, their attachment
regions, valid hole walls, rims, smooth curved surfaces, and areas with only one
scan. Split review examples from a held-out scan/part before tuning. A six-point
known-wisp check is a regression test, not a general precision or recall estimate.

## Current limitations

Tangential fringes lying on a supported plane can survive. Broad ghost surfaces,
dense wisps, missing overlap, and sharp curvature remain difficult. Registration
errors or normal errors can create false candidates; the density/group checks
reduce that risk without eliminating it. No guarantee of watertightness or removal
of every wisp is made. Use the proposed mask as a reviewable experiment.

Synthetic tests cover a strand, clean boundaries, missing overlap, thin opposite
faces, a cylinder, and uniform registration offset. These checks do not establish
that the full real scan is undamaged.

## Optional fine edge pass

After reviewing the primary detector output, `fine_edges.py` can process accepted
copies. It requires at least three independent scans and consistently **outward**
normals; inward or inconsistent normals invalidate the signed exterior test.

```powershell
python fine_edges.py accepted-wrap.ply accepted-top.ply accepted-bottom.ply --output fine-run --tolerance 0.10
python test_fine_edges.py
```

This pass handles a point that aligns with a top face but protrudes beyond its
side wall. Both independent reference scans must place it outside locally coherent
patches at two neighborhood sizes. Only small candidate groups (40 points or fewer)
qualify, and every removed point must have lower local sampling density than its
neighbors. A sparse seed never causes removal of an entire surrounding group.

It writes before-indexed evidence, removed/review subsets, exact retained records,
source snapshots and a manifest. It preserves the input copies. Avoid blindly
repeating the pass: iterative erosion can create damage even if each pass is small.
Four additional synthetic tests cover fine side-wall strays despite top-plane
support, intact thin slabs, convex/concave cylinder surfaces, and missing overlap.
The 0.10 default is in native units and is not a guaranteed safe tolerance for all
registration errors or scanners. Fine residuals close to registration uncertainty
and inadequately observed boundaries remain unresolved.
