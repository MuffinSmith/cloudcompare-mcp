# Live cylinder, line, and picked cross-section fitting

Version 0.9.0 extends the Python feature-fitting layer on top of the already
accepted qMCPBridge 0.7.0 metrology API.

This release remains Python-only. The native CloudCompare plugin stays at
qMCPBridge 0.7.0 / workflow revision 5.

## Line fitting

`fit_live_line` fits an orthogonal least-squares 3D line to captured global picks.

The result includes:

- centroid
- deterministic direction
- residual statistics
- principal variances and linearity
- axial range/span
- span endpoints

The direction sign is deterministic: its largest-magnitude component is forced
positive.

## Cylinder / bore / shaft fitting

`fit_live_cylinder` fits an infinite circular cylinder to sampled surface picks.

At least six distinct samples are required.

The solver:

1. centers the sampled points;
2. uses covariance eigenvectors plus deterministic mixed directions as axis seeds;
3. projects each candidate onto its perpendicular cross-section plane;
4. geometrically fits a circle in that projection;
5. selects the best radial-RMS candidate;
6. locally refines the axis direction with a deterministic tangent-space pattern search.

The result includes:

- a point on the fitted axis near the sample centroid
- deterministic axis direction
- radius and diameter
- radial RMS/P95/max residual diagnostics
- angular circumference coverage
- sampled axial range/span
- span endpoints
- normalized radial RMS
- warnings for low circumferential coverage or very short axial coverage

Low coverage is important. A narrow visible strip of a cylindrical surface can fit
many nearby axes/radii with similar residuals, so a low residual alone is not
sufficient evidence of a reliable diameter.

## Line/axis relationships

`compare_live_picked_lines` fits two lines and returns:

- acute axis angle
- shortest distance between the infinite lines
- closest point on each line
- parallel flags

A fitted cylinder can use the same numerical relationship helper because its axis
has the same point+direction representation.

`compare_live_line_to_plane` fits a line and plane and returns:

- line-to-plane angle
- distance from the line's representative point to the plane
- whether the line is parallel to the plane
- whether it is perpendicular within one degree
- intersection point when one exists

These are intended for shaft-to-face perpendicularity, centerline offsets, slot
directions, and related CAD measurements.

## Picked cross-section projection

`project_live_picks_to_section` fits a section plane from one pick set, then
projects a profile pick set into a stable 2D U/V coordinate frame.

It can optionally reject profile picks farther than a specified half-thickness from
the section plane.

The result reports:

- fitted section plane
- 2D U/V profile coordinates
- projected 3D points
- signed offsets from the section plane
- 2D projected bounds/extents
- exact source pick indexes retained by the slab filter

This is intentionally a **picked-profile** cross-section in 0.9.0. Arbitrary
full-cloud slab extraction is not yet exposed because efficiently streaming a
large live cloud through the bridge deserves its own native/transport design.

## Safety

All 0.9.0 fitting operations are read-only calculations over captured
`position_global` values.

They do not:

- modify source geometry
- add labels or primitives
- create scalar fields
- alter CloudCompare hierarchy
- change global shift/scale metadata

Visible fitted primitives and full-cloud arbitrary section extraction remain
separate future native layers.

## Numerical testing focus

Tests cover:

- exact and noisy rotated cylinders
- partial circumference coverage
- native-coordinate scale changes
- exact/skew/parallel line relationships
- line-plane intersection and parallel cases
- section projection and slab filtering
- duplicate/insufficient sample rejection
- live MCP handler contracts

The next intended work after acceptance is full-cloud arbitrary slab extraction,
visible fit overlays, and higher-level feature relationships such as
concentricity and hole/axis spacing.
