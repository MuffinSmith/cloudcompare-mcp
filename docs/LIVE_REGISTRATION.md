# Live ICP registration

Version 0.5.0 introduces the first live registration operation for the already-open
CloudCompare scene.

## Tool

`register_live_icp` performs rigid point-cloud-to-point-cloud ICP using temporary
copies of both source entities.

Inputs:

- `data_id`: the point cloud to be aligned.
- `model_id`: the fixed reference point cloud.
- `overlap_percent`: expected final overlap, 1-100, default 100.
- `max_iterations`: bounded ICP iteration count, default 20.
- `random_sampling_limit`: maximum point count used internally by ICP, default 50000.
- `filter_out_farthest_points`: optional CloudCompare ICP farthest-point filtering.
- `preview_only`: default true.
- optional `name` and `destination_group_id` when creating an aligned result.

## Safety model

The operation never runs ICP directly on the live source clouds. It clones both
data and model into temporary in-memory working copies first. Registration distance
scalar fields, octrees, and other transient ICP state therefore cannot alter the
original scene entities.

Current registration is rigid only: scale adjustment is disabled.

Both clouds must currently have identical CloudCompare global shift and global
scale metadata. Mismatched frames are rejected instead of silently applying a
local-coordinate transform to incompatible frames.

## Preview mode

The default `preview_only=true` computes registration and returns:

- final RMS in native coordinate units
- point count used for the final RMS
- ICP result code
- 4x4 transformation matrix in OpenGL column-major order
- scale (currently always 1 for rigid registration)
- source-preservation flags

No live geometry is created.

## Applied result

With `preview_only=false`, a successful non-identity registration creates a fresh
clone of the original data cloud, applies the estimated rigid transform to that
clone, and adds it to the requested working group (or DB root when no destination
is supplied).

The model and original data cloud remain unchanged. If ICP reports that no
transformation is necessary, no duplicate result is created.

## Initial scope

This first revision supports standalone point-cloud to standalone point-cloud ICP.
Mesh reference registration, scalar-field weighting, normals matching,
transformation-axis constraints, frame conversion, and point-pair initialization
are intentionally left for later registration revisions.


## Acceptance targets

Before merging this branch, live Windows acceptance should verify at minimum:

- a synthetic data cloud with a known rigid transform converges back onto its model
- preview mode returns a plausible inverse transform and adds no scene entities
- applied mode creates exactly one aligned clone under the requested working group
- original data/model coordinates, attributes, names, parents, and shift/scale remain unchanged
- returned RMS and point count match the native ICP result
- invalid IDs, same data/model ID, incompatible global frames, invalid overlap/iteration/sampling values,
  empty names, and invalid destination groups are transactional failures
- the aligned result preserves the original data cloud's RGB, normals, scalar fields, global shift, and scale


## MCP error signaling

Native bridge validation failures are returned as MCP tool failures with
`CallToolResult.isError=true`. The JSON error text remains in the content so an
assistant can read the validation message and correct its next call. A rejected
native request must not be represented as a successful tool result containing an
`{"error": ...}` payload.
