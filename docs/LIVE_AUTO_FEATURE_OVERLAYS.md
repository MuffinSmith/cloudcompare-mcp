# Automatic feature candidates and visible fit overlays

Version 0.12.0 extends the image-free discovery workflow with automatic circle and
cylinder candidate search plus temporary wireframe overlays in the visible
CloudCompare scene.

The goal is to let an assistant discover and verify mechanical features on a real
scan without repeatedly sending viewport images into model context.

## Automatic circle discovery

`discover_live_circles` searches a sphere/box/slab region using a deterministic
bounded point sample from qMCPBridge.

The Python discovery layer performs deterministic RANSAC over four-point circle
seeds, scores each candidate by 3D orthogonal distance to the circle, refines the
best inlier set with the accepted geometric circle fitter, removes that feature,
and continues searching.

Each candidate reports:

- support count
- support fraction of the complete fitting sample
- 3D surface residual RMS/mean/median/P95/max
- global inlier bounds
- refined circle center, normal, radius/diameter, arc coverage and fit diagnostics

Optional minimum/maximum radius constraints prevent implausibly large or small
solutions from competing with the intended mechanical feature.

The raw region sample and inlier-index list are not returned to the model.

## Automatic cylinder discovery

`discover_live_cylinders` performs deterministic random-subset cylinder fitting
inside a requested live-cloud region.

For each candidate:

1. a small deterministic point subset seeds the accepted cylinder fitter;
2. the candidate is scored against all sampled region points by radial surface
   distance;
3. the strongest inlier set is refit using all candidate inliers;
4. the inlier set is recalculated and refined;
5. accepted inliers are removed before searching for another cylinder.

Results report:

- support count and support fraction
- radial surface residuals
- axis point/direction
- radius and diameter
- circumference coverage
- sampled axial range/span
- global inlier bounds

Radius limits, fit threshold, candidate subset size, iteration count and minimum
support are caller-controllable.

Cylinder discovery is intentionally more expensive than plane/circle discovery.
The default live-region fitting sample is therefore 3,000 points instead of
20,000.

## Visible overlays without image context

qMCPBridge 0.12.0 / workflow revision 8 adds:

- `overlay.create`
- `overlay.clear`

The MCP-facing tool `show_live_fit_overlay` accepts one of the normal fit result
objects returned by:

- plane fitting/discovery
- circle fitting/discovery
- cylinder fitting/discovery
- line fitting

and converts it into a temporary wireframe overlay.

Overlay types:

- plane: fitted rectangle outline plus yellow normal
- circle: fitted circular polyline
- cylinder: top/bottom circles, four generators and yellow center axis
- line: fitted axis segment

All overlay coordinates are supplied in CloudCompare global coordinates, converted
back into the source cloud's native-local frame by qMCPBridge, and assigned the
same global shift/scale metadata. This keeps overlays aligned even for shifted and
scaled projects.

Overlays live under a dedicated root group named:

`MCP Fit Overlays`

The group and every fit subgroup are tagged with qMCPBridge metadata. The safe
`clear_live_fit_overlays` operation only removes that tagged group and refuses to
treat an arbitrary user group as an overlay group.

Overlay creation is transactional with respect to validation: invalid fit geometry
is rejected before the overlay group is inserted into the DB tree.

Source clouds are never modified.

## Intended real-scan workflow

A typical fan reverse-engineering workflow can now be:

1. load the fan project;
2. list live entities and inspect bounds;
3. use `describe_live_region_grid` to map the object numerically;
4. use `discover_live_planes` to identify a mounting face;
5. use region/section tools around that face;
6. discover circle candidates for mounting holes;
7. discover cylinder candidates for the hub/bore;
8. call `show_live_fit_overlay` for the strongest candidates;
9. the user visually confirms the overlays on their own CloudCompare screen;
10. continue measuring accepted features without sending a screenshot back to the
    model.

A viewport capture remains available if something is genuinely ambiguous, but the
normal path is geometry-first.

## Version boundary

Version 0.12.0 contains native changes:

- cloudcompare-mcp: 0.12.0
- qMCPBridge: 0.12.0
- workflow revision: 8

A Windows native build and live acceptance run is required before merging the
branch.
