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

## Scan-boundary drift and low-confidence fringe trimming

`edge_drift.py` adds a separate pass for curled acquisition boundaries, including
coherent strips that are too large or dense for the small-wisp detector.

```powershell
python edge_drift.py accepted-wrap.ply accepted-top.ply accepted-bottom.ply --output drift-run --tolerance 0.18 --band 4
python -m unittest discover -s . -p "test_*.py"
```

Keep the scans separate and aligned. Normals must consistently identify the same
side of a surface across scans. Two independent scans suffice where one has good
interior coverage of the other's edge; duplicate files are rejected. Independent
acquisition provenance remains the caller's responsibility.

1. Infer boundaries from angular gaps in each scan's local tangent neighborhoods,
   agreeing at two radii. This uses the [angle-based boundary-estimation
   principle](https://pointclouds.org/documentation/classpcl_1_1_boundary_estimation.html),
   with our own implementation and conservative overlap checks.
2. Mark a band up to four local point spacings from a compatible boundary. Lock
   reference interiors beyond six spacings before considering any deletion.
   Removable bands and reference interiors are disjoint throughout the pass.
3. Fit robust quadratic reference patches at two scales using only another scan's
   locked interior. Require same-side normals, low scatter, well-conditioned fits,
   surrounding angular coverage, and nearby actual samples. Do not extrapolate
   through missing overlap or across a hole. Curved patches can represent local
   curvature instead of treating it as departure from a plane.
4. Seed drift where every available reference agrees on signed departure exceeding
   the tolerance or four times patch scatter. Reliable supporting references veto
   deletion. No usable reference means keep the point.
5. Trim a bounded fringe within two spacings of those seeds only if it also departs
   by at least half the tolerance or three times patch scatter and has agreeing
   reference evidence. There is no recursive erosion or arbitrary removal of all
   boundary points. Confident replacement samples stay locked in the output.

The output includes exact retained/removed PLY records, a review PLY containing
all remaining boundary-band points (not all are defects), and per-point boundary,
spacing, reference coverage, drift-seed and fringe-trim labels. Reference residual
and scatter arrays map through `query_indices` to input rows, with columns in
input order excluding the current scan; NaN means unknown. The manifest records
input/source hashes, parameters and environment. Source files remain unchanged.

Here "confidence" is geometric support, not a scanner-provided confidence value
or calibrated probability. Without acquisition poses or per-frame range images,
scan-footprint edges are inferred: physical edges, occlusion boundaries and old
cleanup boundaries can also be detected. Overlap checks reduce that ambiguity;
they do not prove the scanner's error mechanism. Large registration errors,
consistently biased interiors, close parallel surfaces, bad normals and unobserved
regions remain limitations. Choose tolerance above alignment uncertainty in native
units. Inspect each new copy; do not repeatedly feed the result back into this pass.

Eight added tests cover a curled edge plus fringe, retained replacement interiors,
clean quadratic curvature, missing overlap, small registration offset, opposite
thin faces, contradictory references, intact hole rims and no fitting across holes.
