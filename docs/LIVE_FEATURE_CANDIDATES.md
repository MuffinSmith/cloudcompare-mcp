# Automatic circle/cylinder candidates and visible fit overlays

Version 0.12.0 extends the accepted image-free discovery workflow with robust
circle/cylinder candidate search and temporary visible CloudCompare overlays.

The goal is to let the assistant discover and inspect likely mechanical features
numerically while the user can still watch CloudCompare, without sending viewport
screenshots into model context.

## Versions

- cloudcompare-mcp: 0.12.0
- qMCPBridge: 0.12.0
- workflow revision: 8

This release contains native qMCPBridge changes and therefore requires a native
Windows rebuild/acceptance run.

## Compact scene inventory

`summarize_live_scene` is the intended first call for large real CloudCompare
projects such as `fan_project.bin`. It flattens the recursive DB tree into a
small geometry-only list by default, keeps hierarchy paths and essential bounds /
frame metadata, and orders point clouds by size so the primary scan is normally
visible immediately.

This avoids spending model context on every hierarchy/group object before the
assistant even knows which cloud to analyze.

## Circle candidate discovery

`discover_live_circles` works inside any structured live region accepted by the
0.10 region-query layer.

The algorithm is deterministic:

1. qMCPBridge returns a bounded deterministic sample from the requested region.
2. Python RANSAC repeatedly chooses three non-collinear 3D samples.
3. Each triplet defines a 3D circle candidate.
4. All sample points are scored by orthogonal circle distance: combined
   out-of-plane and radial error.
5. Candidates must satisfy the requested distance threshold, minimum support,
   minimum support fraction, optional radius limits, and minimum angular coverage.
6. The strongest candidate is refined with the already accepted geometric
   `fit_circle_3d` fitter.
7. Final support is recomputed after refinement.
8. Inliers are removed and the process repeats for additional circles.

Each result includes:

- support count
- support fraction of the complete fitting sample
- center, normal, radius and diameter
- angular coverage
- radial / planar / combined fit diagnostics
- final orthogonal discovery residual statistics
- inlier bounds
- region/sample provenance

No raw inlier list or raw fitting sample is returned to the model.

Radius constraints are especially useful for mechanical searches such as:
"find likely 4-8 mm mounting holes on this face."

## Cylinder candidate discovery

`discover_live_cylinders` searches for dominant circular-cylinder surfaces in a
bounded region.

A general minimal cylinder RANSAC solver is deliberately avoided in this first
version. Instead the discovery layer uses deterministic multi-start robust fitting:

1. build one broad seed from a deterministic sample;
2. build additional seeds from small deterministic pseudorandom subsets (six
   points by default) so useful hypotheses can still be generated when the
   surrounding region contains unrelated geometry;
3. fit each seed with the accepted `fit_cylinder_3d` solver;
4. score every seed against the complete bounded sample by radial error;
5. keep the candidate with the strongest threshold support;
6. iteratively refit its inliers;
7. recompute final support after refinement;
8. enforce support-fraction, angular-coverage and optional radius constraints;
9. remove accepted inliers before searching for another dominant cylinder.

The result reports:

- axis point / direction
- radius / diameter
- radial residuals
- angular coverage
- axial span and span endpoints
- support count and support fraction
- inlier bounds
- region/sample provenance

When no explicit maximum radius is supplied, discovery rejects candidates larger
than twice the sampled-region diagonal. This suppresses huge-radius "cylinders"
that are effectively just flat patches.

The small seed size makes the candidate stage substantially more tolerant of
outliers than fitting large random subsets. Candidate hypotheses are always
scored against the complete bounded sample before acceptance.

This is still intended for reasonably localized candidate regions rather than blind
classification of an entire building-sized scan. The normal workflow is:
structured grid -> numerical zoom -> candidate search.

## Temporary visible overlays

qMCPBridge adds:

- `fit.overlay.create`
- `fit.overlay.status`
- `fit.overlay.clear`

The MCP layer exposes:

- `show_live_plane_overlay`
- `show_live_circle_overlay`
- `show_live_cylinder_overlay`
- `show_live_axis_overlay`
- `get_live_fit_overlays`
- `clear_live_fit_overlays`

Overlays are stored under a dedicated top-level group:

`MCP Fit Overlays`

They are intentionally separate from source scan geometry.

Fixed display colors:

- plane: cyan wireframe
- circle: yellow
- cylinder: magenta wireframe
- axis: green

Overlay coordinates are supplied in CloudCompare global coordinates. qMCPBridge
uses the selected source cloud only as a coordinate-frame/display reference:

- global center/endpoints are converted into that source cloud's local frame
- lengths/radii are converted with the source global scale
- the overlay inherits source shift/scale metadata
- source geometry itself is never modified

Cylinder overlays also show the fitted axis by default.

`clear_live_fit_overlays` removes the complete managed overlay group and leaves
source entities untouched.

Overlay creation validates all requested geometry before creating the managed
group, so invalid requests are intended to be transactional.

## Intended user interaction

The assistant can now do:

1. inspect the fan numerically;
2. identify a likely mounting face;
3. discover circular-hole candidates;
4. show the strongest few circles in CloudCompare;
5. ask the user only whether the visible overlays correspond to the intended
   holes;
6. continue numerically from the accepted candidates.

The user sees the overlays directly on their monitor. The model receives only
structured fit/overlay IDs, not a screenshot.

The same pattern applies to hub/bore cylinders.

## fan_project.bin

The user's disposable copy of the real CloudCompare fan project is intended as
the primary real-world acceptance fixture for this branch.

Testing should freely load and manipulate the copy, but source scan geometry must
remain unchanged by candidate discovery. Overlay operations are expected to add
only the managed `MCP Fit Overlays` group, and clearing overlays must restore the
pre-overlay scene exactly.

## Safety boundary

Candidate discovery is read-only.

Visible overlays are the only intentional scene mutation added by 0.12.0.
They:

- live under one dedicated managed group
- never become children of source scan entities
- inherit coordinate-frame metadata rather than modifying it
- are explicitly removable in one operation

The source scan/project should compare exactly before and after a complete
create/status/clear overlay lifecycle.

## Next likely layer

After real fan-project acceptance, likely next work is higher-level feature intent:

- "find likely mounting holes on this plane"
- candidate clustering / repeated-hole patterns
- concentricity and center-spacing sets
- feature coordinate-system construction
- export of accepted reference geometry for CAD
