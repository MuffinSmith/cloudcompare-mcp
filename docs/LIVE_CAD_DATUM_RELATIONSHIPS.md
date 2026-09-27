# 0.14 first increment: CAD datum frames and feature relationships

Branch: `feature/live-cad-datum-relationships`, based on accepted main
`e39949759c6386e5cd0387983c43a74f26e6a58e`. Python 0.14.0; qMCPBridge remains
0.12.0 / workflow revision 8. **Development only: pending real Windows acceptance
and explicit merge approval.** No native source, dependency, or DLL change.

CloudCompare remains the scan interpretation/metrology layer, not a CAD kernel.
This increment supplies two read-only MCP tools and a pure Python numerical module:

- `analyze_feature_relationships`: bounded relationships among existing geometry.
- `build_live_datum_frame`: an explicit right-handed orthonormal coordinate frame.

Both tools are snapshot-only and require **no host connection**. The datum tool's
`live` name means its inputs can come from existing live fitting tools; it does
not acquire a fresh sample, validate source existence, or establish scene freshness.
Existing specific relationship, fitting, discovery, and overlay tools remain intact.
`get_live_workflow_capabilities` adds `python_cad_datums` without changing native
version claims or older capability sections.

## Input contract and evidence boundary

Supply `features`, `frame_id`, and explicit positive `distance_tolerance` in native
units. Each feature is an object with a unique caller-assigned `id`, an `observation`
object, and optional compact `provenance`. IDs are nonempty strings of at most 128
characters. The tools accept at most 16 features; analysis returns at most 120
unordered pairs, sorted by feature ID. Reordering input does not change output.

For real work, put the complete JSON result of `fit_live_plane`, `fit_live_line`,
`fit_live_circle`, `fit_live_cylinder`, or an applicable `fit_live_region_*` call in
`observation`. Required geometry fields are:

| Type | Anchor | Direction | Other |
| --- | --- | --- | --- |
| `plane` | `centroid` | `normal` | |
| `line` | `centroid` | `direction` | |
| `circle` | `center` | `normal` | positive `radius` |
| `cylinder` | `axis_point` | `axis_direction` | positive `radius` |
| `point` | `position_global` | none | |

Every observation must explicitly state `coordinate_space: "global"` and
`units: "native"`. No local/global conversion is performed. A region fit may retain
a `region_coordinate_space` of `native_local` as selector provenance while its
actual fitted geometry is global. This is not a contradiction or a conversion by
these tools. A separately supplied observation `frame_id`, when present, must
match the call. The common `frame_id` is a **caller assertion**, not proof that
unrelated scan coordinate systems have been registered.

A source cloud ID, source pick records with entity IDs, or explicit provenance is
required. For a discovery candidate or derived direction, construct the envelope
explicitly, preserving its actual global frame, source discovery/candidate IDs,
fit quality, and derivation in provenance. Do not relabel native-local values as
global. Do not present an inferred direction as a measured one. A supplied `state`
is retained as `supplied_interpretation_state`; geometry is labelled
`supplied_geometry`, never independently verified measurement. An input's supplied
state does not accept the output relationship or datum on the user's behalf.

Known top-level `global_shift` and `global_scale` are preserved unchanged; attach
additional source bookkeeping in `provenance` when it was not returned by the fit.
Absent bookkeeping is not filled with an assumed zero shift or unit scale. Native
units are never renamed millimetres. No metadata is applied a second time.

The full observation is finite JSON, limited to 65,536 bytes, and fingerprinted
with SHA-256 of sorted, compact JSON. Preserve the upstream snapshot with that
fingerprint for later reconstruction graphs. Results echo compact normalized
geometry, selected source metadata, supplied residuals, source pick entity IDs and
counts, and the caller's provenance (maximum 4096 bytes). Pick positions are not
echoed. Raw `points` arrays are rejected. Provenance is not an authenticated scene
fingerprint; stale snapshots cannot be detected here. Numerical conditioning
checks are not a calibrated uncertainty model.

## Relationship analysis

`angular_tolerance_degrees` is required, between 0 and 45 inclusive. Angle and
length thresholds are inclusive with an eight-ULP floating-point boundary guard;
this does not add an absolute native-unit tolerance. All geometry is validated
before computation, and the tools never issue native I/O, even on errors.

**Planes.** Report acute normal angle, parallel/perpendicular candidates, and the
signed offset of B's reference point from A's plane, relative to A's explicitly
reported canonical normal. `parallel_spacing` is available only for numerically
parallel ideal planes, not merely for a user-tolerance parallel match. For tilted
planes, `reference_normal_spacing` is location-dependent and constant spacing is
undefined. A separated, near-parallel pair may be a `thickness_candidate`, but
bounded face overlap and opposing material sides remain explicitly unverified.
Opposite fitted normal signs alone do not establish opposing material faces.

**Axes.** Lines, cylinder axes and circle normal axes can be compared for acute
angle, perpendicular/parallel candidates and infinite-axis shortest distance.
Coaxial candidates require angular agreement **and both supplied anchors' distances
to the other axis** to pass. Two almost-parallel lines intersecting far away are
not coaxial merely because their shortest distance is zero. Skew axes within the
distance tolerance retain distinct closest points; their midpoint is labelled
closest approach, not silently promoted to an exact intersection.

**Axis/plane.** Report angle to the plane (0 parallel; 90 perpendicular), signed
anchor offset, and the unique ideal intersection when well conditioned. Parallel
axes have no unique intersection; `axis_in_plane_candidate` describes the offset
check rather than a unique point. Circle/plane analysis refers to the circle's
normal axis, not the circle's entire rim.

**Circular sizes and centers.** Circle/cylinder pairs report diameter differences
and axis relationships. Circle/circle concentricity requires center proximity
and aligned normal axes; axially separated circles may be coaxial but not
concentric. Point/circle centers have `center_distance`. Other feature pairs have
`reference_point_distance`: fitted centroids and axis anchors are not automatically
physical part centers. Point/plane signed distance is also available.

Directions use a largest-absolute-component-positive canonical sign. Signed plane
offsets refer to that reporting direction, not an outward material normal.
Coincident observations remain separately traceable; they are not counted as
independent evidence, automatically merged, or labelled a symmetry feature.

Numerical parallelism uses sine <= 64 float64 machine epsilons. Point constructions
with inverse-angle amplification above 1e8 are withheld as ill-conditioned.
Distances use anchor differences rather than subtracting large global plane
constants. Requested distance tolerance must cover at least eight ULPs of supplied
and constructed global point coordinates; unresolved precision or arithmetic
overflow is an error, not a fabricated high-precision result. This check cannot
recover precision already lost when a scanner/host stored its coordinates.

## Datum construction

Required IDs are `primary_plane_id` and `secondary_feature_id`, referring to distinct
supplied features. The primary must be a plane. Z is its normalized normal. X is
either the intersection direction with a secondary plane or the projection of a
secondary line/circle/cylinder axis onto the primary plane. Y = Z cross X, and X is
recomputed as Y cross Z. Degenerate definitions fail rather than selecting an
arbitrary fallback direction. `minimum_datum_angle_degrees` defaults to 1 degree
and may be explicitly set between 0.0001 and 45; the boundary is inclusive.

Optional `z_direction_hint` and `x_direction_hint` resolve axis **signs**, not their
geometric directions. A perpendicular/ambiguous hint fails. Without hints, the
canonical global sign is deterministic but physically ambiguous; changing the
world orientation across a canonical-sign boundary can flip axes. Rotate explicit
hints along with geometry when consistent physical signs must be maintained.

The default origin is the primary fitted centroid, explicitly not an inferred
manufacturing origin. Optional `origin_feature_id` may select:

- A point or circle center within `distance_tolerance` of the primary plane. It is
  explicitly projected; input position and signed projection distance are returned.
- A line or cylinder axis with a well-conditioned unique primary-plane intersection.

A plane cannot be an origin feature in this increment. Parallel origin axes, remote
point origins, duplicate IDs and nearly degenerate secondary directions are errors.

Results include `origin_global`, `x_axis`, `y_axis`, `z_axis`, right-handedness,
determinant, orthogonality error, source IDs, normalization explanation, angular
projection residual, origin residual, ambiguity messages and provenance. Conversion
is explicitly `datum = rotation_rows @ (global - origin_global)`, not a silently
applied scene transformation. No scan entity or native coordinate metadata changes.

### Small synthetic example

The following values are synthetic native units, not dimensions of the user's fan.
For real use, replace observations with complete fit results rather than guessing
geometry. Use this body with `build_live_datum_frame`:

```json
{
  "frame_id": "synthetic-example-global",
  "distance_tolerance": 0.01,
  "primary_plane_id": "mounting-face",
  "secondary_feature_id": "side-face",
  "origin_feature_id": "bore",
  "z_direction_hint": [0, 0, 1],
  "x_direction_hint": [1, 0, 0],
  "features": [
    {"id": "mounting-face", "observation": {
      "type": "plane", "coordinate_space": "global", "units": "native",
      "source_cloud_id": 42, "centroid": [0, 0, 0], "normal": [0, 0, 1]}},
    {"id": "side-face", "observation": {
      "type": "plane", "coordinate_space": "global", "units": "native",
      "source_cloud_id": 43, "centroid": [0, 0, 0], "normal": [0, 1, 0]}},
    {"id": "bore", "observation": {
      "type": "cylinder", "coordinate_space": "global", "units": "native",
      "source_cloud_id": 44, "axis_point": [3, 4, 5],
      "axis_direction": [0, 0, 1], "radius": 2}}
  ]
}
```

Expected origin is `[3,4,0]`; axes are +X,+Y,+Z and determinant +1. To analyze these
features, pass only `features`, `frame_id`, `distance_tolerance`, and
`angular_tolerance_degrees: 0.5` to `analyze_feature_relationships`.

`scripts/make_datum_fixtures.py` creates separate primary-plane, secondary-plane,
and cylindrical point clouds, both untransformed and arbitrarily rotated with a
large translation, plus expected geometry in a manifest. Generated fixtures and
acceptance evidence belong outside Git. See the Windows acceptance procedure.

## Deliberately deferred

No persistent datum/feature graph, acceptance/rejection store, general symmetry
detector, 2D profile reconstruction, topology/material confirmation, automatic
whole-assembly recognition, Fusion connection, STEP export, or CAD creation is
included. The snapshot fingerprints, explicit reference IDs, state separation,
residuals and provenance are intended to feed a later reconstruction graph without
turning an inference into a measured fact.
