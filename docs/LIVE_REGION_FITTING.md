# Structured live regions and direct feature fitting

Version 0.10.0 adds a native point-cloud region query to qMCPBridge and uses it
from the Python MCP layer to avoid image-heavy/manual picking for routine geometry
work.

The primary design goal is to let an assistant operate on CloudCompare geometry
numerically while the user can still watch the visible GUI. Viewport screenshots
remain available for ambiguous visual checks, but they are no longer required for
ordinary plane/circle/cylinder fitting or section extraction.

## Native region query

qMCPBridge 0.10.0 / workflow revision 6 adds:

`cloud.region_query`

It operates on a standalone live point cloud and supports four region types:

- `sphere`: center + radius
- `box`: axis-aligned min/max bounds
- `slab`: origin + normal + half-thickness
- `nearest`: closest point to a supplied center, with optional max distance

Regions can be interpreted in CloudCompare global coordinates or the source
cloud's native-local coordinates.

The native query always scans the actual source cloud and computes exact summary
information over every matched point:

- matched point count
- centroid in the query coordinate space
- bounding box in the query coordinate space
- source frame metadata

Returned point payloads are explicitly bounded. At most 20,000 point records are
returned. When the match count exceeds that limit, qMCPBridge uses a deterministic
reservoir sample while preserving exact count/centroid/bounds summaries.

The source cloud is read only.

## Compact region inspection

`query_live_region` exposes the native query in a model-friendly form.

By default it returns only a small structured point preview along with exact
region count/bounds/centroid. It does not return a viewport image.

Typical use:

1. inspect scene/entity bounds;
2. identify an approximate 3D location from a prior fit, pick, or known geometry;
3. query a sphere/box/slab numerically;
4. refine the region or fit a primitive directly.

The `nearest` selector is useful for snapping an approximate coordinate to a real
scan point without mouse interaction.

## Direct region fitting

The Python layer adds:

- `fit_live_region_plane`
- `fit_live_region_circle`
- `fit_live_region_cylinder`

Each tool asks qMCPBridge for a bounded deterministic sample from the requested
live-cloud region and then feeds those global point coordinates into the already
accepted feature-fitting core.

Only the compact fit result is returned through MCP. The potentially thousands of
sample coordinates stay internal to the local MCP request path and do not need to
be included in model-visible output.

Fit results include region provenance:

- source cloud ID
- region selector
- region coordinate space
- exact match count
- sample count
- whether the sample was truncated
- exact region bounds/centroid summary

This makes it clear when a fit used every matching point versus a representative
bounded sample.

## Full-cloud slab section

`extract_live_section` defines a global plane and half-thickness, asks the native
bridge for all matching slab statistics plus a bounded sample, projects that sample
into a deterministic 2D U/V frame, and returns compact profile statistics.

The result includes:

- exact matched count
- sampled count and truncation state
- section origin/normal/U/V basis
- projected U/V bounds
- signed offset statistics
- a small profile preview only

It intentionally does not return all profile points to the model.

A later layer can add direct line/circle/profile analysis over the internal section
sample without exposing the raw profile through model context.

## Sampling and interpretation

A direct fit is exact with respect to the sampled points but may be based on a
deterministic reservoir sample when more than `sample_limit` points match.

For precision-sensitive work:

- inspect `region_match_count`
- inspect `region_sample_count`
- check `region_sample_truncated`
- increase `sample_limit` up to 20,000 when useful
- compare residual diagnostics and feature coverage

Exact count/centroid/bounds are always computed over all matched points even when
the returned fitting sample is bounded.

## Safety

Region operations:

- do not create CloudCompare entities
- do not alter source coordinates or attributes
- do not change visibility, selection, hierarchy, or global shift/scale
- do not require viewport screenshots

The native operation is synchronous and currently performs a full source-cloud scan
for each query. This favors implementation simplicity and correctness for the first
version; octree-accelerated spatial queries can be added after native acceptance if
performance warrants it.

## Version boundary

Version 0.10.0 contains native qMCPBridge changes:

- qMCPBridge: 0.10.0
- workflow revision: 6
- cloudcompare-mcp: 0.10.0

A native Windows rebuild and acceptance run is required before merging this branch.
