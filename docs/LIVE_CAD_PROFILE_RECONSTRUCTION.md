# 0.15 first increment: CAD section-profile reconstruction

Branch: `feature/live-cad-profile-reconstruction`, based on accepted-main checkpoint
`b462fb2733a7c57b590a283d1ed03dfdfc3df0bc`. Python 0.15.0; qMCPBridge remains
0.12.0 / workflow revision 8. **Development only until real Windows acceptance and
explicit merge approval.**

The purpose of this stage is to turn already-extracted 2D scan sections into compact
sketch-like geometry that a later CAD reconstruction graph and Fusion handoff can use.
CloudCompare remains the scan interpretation/acquisition layer; this is not a CAD
kernel and it does not create a Fusion sketch.

## MCP surface

### `reconstruct_section_profile`

Snapshot-only. It accepts a caller-supplied section envelope with:

- `coordinate_space: "section_uv"`
- `units: "native"`
- `points_uv` (2–4096 finite points)
- optional frame/provenance such as `frame_id`, `origin_global`, `basis_u`,
  `basis_v`, `normal`, source cloud ID, and known global shift/scale

The call also requires `closed` and an explicit positive `fit_tolerance`. Optional
controls include angular tolerance, minimum useful arc angle and a maximum primitive
count. It never contacts CloudCompare. The input points are fingerprinted but are
not echoed in the result.

### `reconstruct_live_section_profile`

Live read-only wrapper. It accepts a cloud ID, explicit global section origin/normal,
slab half-thickness, closed/open policy, fit tolerance and bounded sample limit.
It reuses the already accepted native `cloud.region_query` slab selector, projects
the bounded sample into a stable U/V frame in Python, reconstructs the profile, and
returns only compact geometry/diagnostics. Raw sampled points remain server-side.
No new native method or DLL rebuild is required.

Malformed tolerances, ordering modes, frame vectors and sample limits are rejected
before bridge I/O where practical. Source entities are never transformed, renamed,
created, deleted or annotated by these tools.

## Ordering is explicit

Topology cannot be recovered safely from an arbitrary point permutation without
assumptions, so this increment refuses to hide the ordering policy:

- `input`: caller states that points already follow a boundary traversal.
- `polar_closed_loop`: deterministic angle sort around the sample centroid. This is
  only appropriate for one closed loop that is sufficiently star-shaped around that
  center. It is useful for simple isolated circles, rectangles and slots, but is not
  a general contour solver.
- `principal_open`: deterministic ordering along the dominant PCA direction. This
  assumes an open profile is single-valued enough along that direction.

The selected assumptions and ordering diagnostics are returned. A future 0.15
increment should replace these bounded assumptions with explicit boundary graph /
loop extraction for complex sections rather than silently extending polar sorting.

## Primitive reconstruction

The numerical core is pure NumPy and unit-neutral. It recursively splits an ordered
profile until each span is representable within `fit_tolerance`, then deterministically
merges adjacent spans when the combined primitive still meets the threshold.

Initial primitive types:

- `line`: orthogonal least-squares 2D line with fitted endpoints, direction, length
  and residual statistics.
- `arc`: geometric least-squares circle over an ordered span, with center, radius,
  signed sweep, arc length, monotonic angular-progress diagnostic and residuals.
- `circle`: full closed-loop circle when radial residual and angular coverage support
  it directly.

Every primitive is an `inferred_candidate`, carries source count/endpoints in the
ordered input, and reports RMS/P95/max fitting residuals. `fit_tolerance` is a
numerical threshold in native units, **not calibrated measurement uncertainty**.
The threshold is inclusive; tolerances below resolvable float64 coordinate precision
are rejected instead of fabricating sub-precision accuracy.

Adjacent primitives report endpoint gap and tangent-deviation measurements plus
candidate flags. Adjacent lines additionally report parallel/perpendicular candidate
relationships. These are geometric tests, not semantic constraints accepted on the
user's behalf.

## Bounded higher-level candidates

The first increment recognizes only strongly structured cases:

- one full fitted circle -> `circle_profile_candidate`
- four line segments with opposite parallel / adjacent perpendicular evidence ->
  `rectangle_candidate`
- two parallel lines alternating with two near-semicircular equal-radius tangent arcs
  -> `slot_candidate`

Slot results include radius, width, centerline length, overall length and axis
direction. Rectangle results include center and paired side lengths. These labels are
candidate geometry. They do not prove that a scanned feature was designed as a slot
or rectangle, that corners are manufactured exactly, or that dimensions should be
rounded to nominal values.

## Coordinate/provenance policy

Section U/V values remain in `native` units. No millimetre assumption is introduced.
Snapshot frame metadata and caller provenance are copied, not reapplied. The live
wrapper reports its global section frame, source cloud ID, exact/all-match count when
available, returned sample count, truncation and sampling strategy. A truncated live
sample adds an explicit warning.

Large global translation is handled by projecting relative to the supplied section
origin before 2D fitting. Precision already lost in upstream storage cannot be
recovered. The snapshot tool fingerprints input float64 U/V bytes; that fingerprint
is evidence identity, not a live scene-freshness guarantee.

## Synthetic slot fixture

`scripts/make_profile_fixtures.py --output-dir <new-directory>` generates two
separate PLY outlines plus `manifest.json` outside Git when the chosen output path is
outside the repository:

- an axis-aligned slot
- the same slot rotated 37 degrees about normalized `[1,2,3]` and translated by
  `[100000000,-200000000,300000000]`

Expected native geometry is radius 5, width 10, centerline length 20 and overall
length 30, represented by two lines and two semicircular arcs. The transformed
fixture exists to exercise projection, host global-shift bookkeeping and large
coordinate values rather than only XYZ-aligned examples.

## Deliberately deferred within 0.15

This first increment does **not** yet implement:

- ellipse fitting
- rounded-rectangle classification
- arbitrary non-star-shaped or multiple-loop boundary ordering
- holes/islands within a profile
- robust self-intersection/topology repair
- automatic symmetry constraints
- tangent/parallel constraint solving across nonadjacent primitives
- spline fallback
- persistent CAD reconstruction graph or acceptance states
- Fusion sketch creation

Spline fallback should only be introduced after normal CAD primitives have been
systematically attempted and the residual evidence shows that a freeform segment is
actually necessary. Complex topology should get an explicit loop/graph layer rather
than increasingly fragile sorting heuristics.
