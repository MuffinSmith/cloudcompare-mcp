# Live feature fitting

Version 0.8.0 adds a unit-neutral Python feature-fitting layer on top of the
already-validated qMCPBridge 0.7.0 interactive metrology API.

This release intentionally keeps the numerical fitting core independent of the
CloudCompare GUI. qMCPBridge supplies exact captured global coordinates; the Python
layer performs the fits and returns quantitative diagnostics. No source entity is
modified and this release does not require a new native plugin build.

## Plane fitting

`fit_live_plane` uses captured metrology picks and computes an orthogonal
least-squares / PCA plane.

By default all currently captured picks are used. An explicit `pick_indices`
subset can be supplied.

The result includes:

- centroid
- deterministic unit normal
- two in-plane basis vectors
- plane equation
- RMS, mean-absolute, median-absolute, P95 and maximum residual
- principal variances and simple linearity/planarity/scattering metrics
- projected sample extents
- normalized RMS relative to fitted extent
- the exact captured picks used

All fitting is performed in CloudCompare global coordinates. Distances remain
reported in native coordinate units; the bridge does not invent physical units.

## Circle / hole fitting

`fit_live_circle` fits a 3D circle from captured picks.

The algorithm:

1. fits the best orthogonal plane to the 3D samples;
2. projects the samples to a stable 2D basis in that plane;
3. computes an algebraic circle seed;
4. refines center and radius with geometric least squares.

The result includes:

- 3D center
- plane normal
- radius and diameter
- radial residual statistics
- out-of-plane residual statistics
- combined orthogonal residual statistics
- sampled arc coverage in degrees
- normalized residuals relative to radius
- a warning when sampled arc coverage is below 120 degrees

Arc coverage matters because a small visible piece of a circle can mathematically
fit many different centers/radii while still having a small point residual.

## Derived measurements

`measure_live_pick_to_plane` fits a plane from one pick set and measures another
captured point to it. It returns signed/absolute distance and the projected point.

`compare_live_picked_planes` fits two planes and returns:

- acute angle
- centroid-to-centroid vector and distance
- normal-direction offsets measured from each plane
- a convenience flag for parallelism within one degree

These are intended as building blocks for mounting-face offsets, parallelism,
perpendicularity and feature-reference measurements.

## Safety and implementation boundary

Version 0.8.0 is Python-only:

- qMCPBridge remains version 0.7.0 and workflow revision 5
- no native CloudCompare source changes are required
- fitting consumes read-only pick records from `metrology.pick.status`
- no labels, primitives, scalar fields or hidden geometry are inserted into the DB tree
- source geometry and CloudCompare project state are untouched

Visible fitted primitives are deliberately deferred until the numerical layer has
been accepted. The next native layer can add optional working-group overlays that
represent the exact accepted fit result.

## Numerical testing

The fitting core lives in `cloudcompare_mcp.feature_fit` and does not require
CloudCompare. Its tests use deterministic exact/noisy planes and circles, partial
arcs, large shifted coordinates, degeneracy checks, known point-to-plane
measurements, known plane angles and randomized rotation-invariance cases.

The intended next features after acceptance are cylinder/shaft fitting and
cross-section extraction.
