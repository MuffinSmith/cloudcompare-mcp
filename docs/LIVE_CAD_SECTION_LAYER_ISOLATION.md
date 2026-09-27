# 0.15.3: depth-aware section layer isolation

Branch: `feature/live-cad-section-layer-isolation`.
Accepted-main parent: `cb1ee9eab9c64ff4806036a6317606938faa22e6`.
PR #16 merged accepted 0.15.2 at `8f2e0317f9eeff14547db1d83c100549c65fb18c`.
This increment completed focused real Windows/CloudCompare acceptance at exact HEAD
`2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`. Fixture, live-GUI, handoff and safety
gates passed; the bounded fan remained correctly BLOCKED by excessive component
complexity rather than a product defect. The branch is not merged and still requires
explicit user merge authorization. See AGENTS.md for exact acceptance attribution.
Python is 0.15.3. Native qMCPBridge remains unchanged 0.12.0 / workflow revision 8.
No DLL rebuild, new native method, or Fusion 360 integration is introduced.


## Windows acceptance summary

The focused Windows gate used a clean isolated worktree at the exact tested HEAD.
The local suite reported 610 passed plus 16 compiler-gated native policy skips; those
16 subsequently passed under configured MSVC. compileall and diff checks passed.
The final CI run at the same source, `36352480651`, also passed.

All 12 freshly generated PLY files matched manifest hashes and point counts. Actual
MCP stdio exposed all four 0.15.3 tools. Real CloudCompare fixture acquisitions were
complete, point accounting was exact, and unsafe crossing/thick/sparse cases refused
continuation. Original/transformed single-layer fixtures passed through the accepted
0.15.2/0.15.1 reconstruction path. Parallel fixtures required explicit current
fingerprint selection, and stale or snapshot-to-live fingerprints were rejected.

The transformed GUI sources used global shift
`[-100000000, 199999000, -299999000]` and scale 1 without double application.
Integrity coverage was before/after metadata only; full-cloud geometry/attribute
equality was not independently proved, and real native nonunit scale remains untested.

The bounded fan source 359 (`Assembly | Fan - scan 1`) returned a complete
5,605 / 5,605 slab with depth approximately -0.499512 to +0.499924. The declared
analysis exceeded the 16-component limit, produced no candidate fingerprint, and
correctly blocked before reconstruction. This result must not be converted into a
pass by threshold search, sign selection, or simply raising the component budget.

## Why retain depth before projection?

The accepted 0.15.2 fan refusal involved a complete slab with substantial samples
through both sides of its depth range. Flattening it into one UV occupancy field
cannot establish which surface a sample came from. This increment retains complete
`[u, v, signed_depth]` evidence, constructs explicit coherent component candidates,
and only then allows a safe selected component into accepted occupancy/topology.
It never selects a depth sign or whichever candidate produces the nicest outline.

CloudCompare owns read-only acquisition and source coordinate provenance. Python
owns depth observations, continuity, ambiguity, selection and the existing boundary,
topology and primitive reconstruction. A layer candidate is inferred evidence, not
a physical part, a confirmed cross-section, or manufacturing intent.

## Numerical model and exact thresholds

The independent `section_layers.py` core uses a caller-visible native-unit UV cell
size. Half-open cells are anchored at the supplied sample minima after local
coordinate subtraction. Within each cell, sorted depth samples are split only when
an adjacent gap is **strictly greater than** `depth_separation`. Equality does not
split. A resulting local observation is supported only when it has at least
`min_cell_points` distinct XYZ-in-section-frame samples and depth span no greater
than `max_layer_thickness`. Exact duplicates do not manufacture additional support.
Thickness must be strictly less than separation.

Observations in four-neighbor UV cells connect when their median-depth difference
is **less than or equal to** `max_neighbor_depth_step`. A one-to-many neighbor
correspondence is ambiguous. A connected component containing two depth observations
from the same UV cell is merging/crossing evidence. Such evidence is retained but
cannot be selected. Components also require `min_layer_cells` connected UV cells
and genuinely two-dimensional sample support.

All points belong to reported components, including sparse/thick/ambiguous ones.
Nothing is silently dropped. Any unusable component blocks continuation for the
whole acquisition, even if another component appears usable and is explicitly chosen.
This deliberately conservative rule prevents an explicit choice from hiding
unresolved geometry. Reduce/isolate the source acquisition instead.

Local thickness is not the global depth span: a supported gently sloped layer may
span more depth overall while satisfying the per-cell bound. The reported RMS is
residual about local cell medians, not a plane-fit error or a sensor uncertainty.

## Tools and request contracts

| Tool | Acquisition | Result |
| --- | --- | --- |
| `analyze_section_layers` | Caller-supplied complete U/V/depth snapshot; no live I/O | Compact layer evidence |
| `analyze_live_section_layers` | One complete read-only native slab query | Compact evidence plus live provenance |
| `reconstruct_section_layer_profile` | Snapshot | Selection gate, then accepted 0.15.2 boundary/topology/fitting |
| `reconstruct_live_section_layer_profile` | Reacquires the live slab | Same selection gate and composite path |

All four tools are read-only. The snapshot tools work with no bridge connection.
Their schemas are exposed through actual MCP `tools/list`. Workflow capabilities
add `python_section_layers.version=0.15.3`; accepted `python_cad_profiles` remains
0.15.2. Live availability reflects the existing native region-query capability.

### Explicit layer parameters

Every request requires a nested `layer_parameters` object. Example fixture settings:

```json
{
  "uv_cell_size": 0.5,
  "depth_separation": 0.2,
  "max_layer_thickness": 0.09,
  "max_neighbor_depth_step": 0.12,
  "min_cell_points": 1,
  "min_layer_cells": 4,
  "max_points": 20000,
  "max_cells": 20000,
  "max_components": 16
}
```

The first four parameters have no hidden defaults and must be finite positive
numbers. All lengths use native units, not assumed millimetres. `min_cell_points=1`
above deliberately permits singly sampled edge cells in generated fixtures; it is
not the default or a universal real-scan recommendation.

Defaults/hard bounds: `min_cell_points=3` (1..20,000), `min_layer_cells=4`
(3..20,000), `max_points=20,000` (3..20,000), `max_cells=20,000` (3..20,000), and
`max_components=16` (1..64). At most 16 local depth modes per UV cell are supported.
Exceeding any budget fails explicitly; it never truncates evidence or keeps only
the largest components. Overlap pair previews contain at most 16 entries and report
whether the preview is truncated; the actual layer analysis is not truncated.

### Snapshot envelope

`analyze_section_layers` receives:

```text
{
  "section": {
    "coordinate_space": "section_uv_depth",
    "units": "native",
    "acquisition_complete": true,
    "samples_uvd": [[u, v, signed_depth], ...]
  },
  "layer_parameters": { ...explicit settings above... }
}
```

The sample placeholder represents actual finite numeric rows, not literal text.
The complete assertion is caller-supplied snapshot provenance, not independent
verification of the original source. Optional `section.frame` may contain a compact
`frame_id`, or all of `origin_global`, `basis_u`, `basis_v`, and `normal`. A geometric
frame must be orthonormal and right-handed. Optional `section.source` retains
`cloud_id`, `cloud_name`, `global_shift`, and positive `global_scale` without
reapplying them to already projected UV/depth coordinates. Optional `provenance`
is a finite JSON object of at most 4,096 UTF-8 bytes. Unknown contract keys fail.

### Live envelope and completeness

Example structure for `analyze_live_section_layers`:

```text
{
  "cloud_id": <resolved actual entity ID>,
  "origin": [0, 0, 0],
  "normal": [0, 0, 1],
  "half_thickness": 1.0,
  "layer_parameters": { ...explicit settings above... },
  "query_timeout_seconds": 30
}
```

The only native call is `cloud.region_query` with global coordinates and the same
explicit slab. The point budget comes from `layer_parameters.max_points`.
The optional query timeout is positive, at most 120 seconds, default 30.
The wrapper verifies all of:

- requested cloud identity and explicit global coordinate space;
- valid equal matched/returned counts, no truncation, and exact returned record count;
- unique native source point indices and finite coordinates;
- source cloud name, actual global shift and positive global scale;
- every returned point lies in the requested slab within representational precision.

It does not silently filter out bad records. Deterministic reservoir sampling is not
proof of layer topology. Large sections must be isolated before use. Source-global
precision floors reject subprecision layer thresholds and composite fit/grid lengths.
The existing section projection canonicalizes the normal orientation; its returned
normal/bases and orientation policy are authoritative for signed depth.

### Compact evidence and selection

Analysis returns point/cell/observation counts, depth quantiles, local sparse/thick
and correspondence diagnostics, candidate layers, overlap, thresholds, grid origin,
precision floors and fingerprints. Each candidate reports source support, UV extent
and coverage, depth range/median, maximum local thickness, local RMS residual,
continuity edges, overlap and blocking reasons. Raw samples/indices remain private.
Live candidates additionally carry source-index and source-global-geometry hashes.

`status` is `ready` only for exactly one wholly supported unambiguous component;
`auto_selected_layer_id` then identifies it. Multiple credible components return
`selection_required`, never automatic collapse. Any unusable component gives
`blocked`. Malformed, incomplete, subprecision or over-budget requests are structured
MCP errors rather than successful analyses with missing data.

The composite tools additionally require nested `profile_parameters`, for example:

```json
{
  "cell_size": 0.5,
  "max_edge_length": 1.1,
  "fit_tolerance": 0.35,
  "angular_tolerance_degrees": 2.0,
  "require_grid_stability": true
}
```

Accepted occupancy controls such as `min_cell_support`, `min_component_cells`,
`max_cells`, `max_boundary_points`, `minimum_loop_points`, `max_loops`,
`max_segments_per_loop`, and `minimum_arc_angle_degrees` remain caller-visible in
this object. Layer UV cell size and boundary occupancy cell size are separate
settings; neither is optimized automatically.

For explicit selection, copy `layer_id` from an analysis candidate and supply its
exact `analysis_fingerprint` as `expected_analysis_fingerprint` alongside the same
acquisition and layer parameters. The fingerprint binds canonical geometry, layer
parameters, frame, source identity/bookkeeping, and acquisition provenance. Live
composites reacquire rather than caching source data. Changed evidence, source
mapping, metadata or frame invalidates the old choice. Layer IDs/hashes are stable
under point permutation, not under unrelated coordinate transforms or reimported
source identity. Never reuse a snapshot fingerprint for a live source.

When selection is unavailable, the composite returns candidates and
`status=blocked`, `blocked_stage=layer_selection`. It never attempts all candidates
and picks whichever fits. A selected component is passed unchanged into accepted
0.15.2 occupancy, 0.15.1 loop topology and primitive fitting. Successful output has
`status=candidate`, explicit selected/unselected point counts, and nested `profile`.
A legitimate boundary/topology refusal retains the layer evidence, reason, and
available occupancy diagnostics with `blocked_stage=boundary_or_topology`.

## Coordinate and integrity claims

Global positions are transformed to section-relative coordinates once. CloudCompare
shift/scale is retained as bookkeeping, never applied again. Source-point mapping
hashes cover only the complete bounded acquisition, not every point in the source
cloud. The tool does not independently export/hash the full source before and after;
its live acquisition explicitly reports that integrity coverage is not independently
measured. External Windows acceptance must report its actual integrity coverage.

Every layer/boundary/topology/primitive remains `inferred_candidate`;
`manufacturing_intent_confirmed` and `user_accepted` remain false.

## Fixtures and development validation

Generate a new directory outside Git:

```text
python scripts/make_section_layer_fixtures.py <new-absolute-directory-outside-repository>
```

The generator refuses repository paths and existing output directories. Twelve
ASCII-double PLY files plus a hashed manifest cover single/parallel/three layers,
partial overlap, slope, crossing, bounded noise, excessive thickness, sparse support,
a generic fan-like two-sided slab, and arbitrary 3D rotation with approximately
`[100000000,-200000000,300000000]` translation for single and parallel layers.
Tests read the actual files, verify hashes and project their coordinates before
running production workflow code. They do not substitute generator helper arrays.

Tests include numerical thresholds, permutation determinism, malformed/nonfinite
inputs, budgets, no source mutation, compact responses, stale selection, accepted
profile handoff, schemas, real MCP stdio snapshots, and live MCP stdio over a replay
TCP peer. The replay peer is NOT a real CloudCompare instance. See AGENTS.md for
exact final local/CI results and the remaining real-host gate.

## Deliberate limitations

The first implementation is a fixed-grid local-depth connectivity model, not general
surface segmentation or a physical-layer proof. Grid origin, orientation, density,
slope and thresholds may alter component evidence. No rotation-invariance guarantee
is claimed beyond tested fixtures. Subthreshold layers and crossings between
unsampled locations cannot be ruled out. Local depth span includes within-cell slope
as well as noise; excessive slope may correctly refuse under the chosen bounds.

Disconnected coplanar regions are separate candidates and are never automatically
joined; one connected candidate is not necessarily the whole desired part. The
accepted outer/hole/island solver remains intact, but this stage does not infer that
separate layer patches belong to one manufacturing profile. No adaptive occupancy,
morphological repair, gap filling, spline inference, or parameter sweep is added.
Native nonunit global-scale behavior still needs real-host coverage. Snapshot/replay
scale 2.5 tests are bookkeeping coverage only. The real fan may remain BLOCKED;
success means explaining its depth structure accurately, not forcing an outline.

See [focused Windows procedure](WINDOWS_SECTION_LAYER_ACCEPTANCE.md). Do not reopen
completed 0.15.2 acceptance or weaken its boundary safety checks for this increment.
