# 0.15.1 development: explicit section boundary topology

Branch: `feature/live-cad-profile-topology`, based on accepted main
`efd2e7aff2e2c9a68fde83373b804450f20ebbe2`. Python becomes 0.15.1.
qMCPBridge remains accepted 0.12.0 / workflow revision 8 and is unchanged.

This increment addresses the largest limitation retained from the accepted first
0.15 profile stage: a section can contain more than one closed loop and a useful
profile can be concave or non-star-shaped. It adds an explicit topology layer
between section samples and the existing line/arc/circle primitive fitter.

This is still a bounded reconstruction tool, not a generic contour-from-surface
algorithm.

## New MCP surface

### `reconstruct_section_topology`

Snapshot-only. The caller supplies a `section_uv` / `native` point envelope and
must explicitly set:

- `boundary_samples_only: true`
- `max_edge_length`
- `fit_tolerance`

The input points may be arbitrarily ordered and may represent several disjoint or
nested closed boundary loops.

The tool:

1. builds a local radius-neighbor graph using the caller-selected
   `max_edge_length`;
2. separates disconnected components;
3. traces each component deterministically by nearest unvisited local continuation,
   using turn only as a tie-break;
4. rejects open/dead-ended/ambiguous/self-intersecting/touching topology;
5. determines loop containment;
6. orients outer/material boundaries counter-clockwise and holes clockwise;
7. labels nesting candidates as `outer`, `hole`, or `island`;
8. feeds each ordered loop into the already accepted 0.15 line/arc/circle fitter.

Raw U/V point arrays are fingerprinted but not returned. Each loop carries compact
source-index evidence, signed area, sampled perimeter, edge-length diagnostics,
nesting depth and a nested profile reconstruction.

### `reconstruct_live_section_topology`

Read-only live wrapper. It uses the already accepted native
`cloud.region_query` slab acquisition and Python section projection.

The caller must explicitly assert `boundary_samples_only: true`. This assertion is
important: a normal dense scan slab can contain filled surfaces, multiple layers or
interior samples and is **not** automatically a boundary cloud.

The live wrapper also refuses truncated acquisition. If the slab contains more
matches than the bounded sample can return, the call fails and requires the caller
to increase `sample_limit` or isolate a smaller boundary cloud. Missing samples
cannot safely be treated as complete loop topology.

No native method or DLL change is required.

## Why `max_edge_length` is explicit

Recovering a curve graph from unordered coordinates requires a locality assumption.
This increment does not hide that assumption behind an undocumented auto-tuned
number.

`max_edge_length` must be:

- large enough that neighboring samples along every intended loop can connect;
- smaller than gaps to unrelated branches or separate loops that must remain
  disconnected.

The returned graph diagnostics include neighbor-count statistics and the trace
policy. If the threshold produces an open, merged or otherwise ambiguous graph, the
tool fails instead of silently choosing another threshold.

Future work can add evidence-driven threshold suggestions, but the numerical
assumption should remain observable.

## Nesting semantics

Loop nesting is inferred geometrically after validating that loops do not intersect
or touch.

- depth 0 -> `outer`
- odd depth -> `hole`
- positive even depth -> `island`

These labels describe candidate 2D material topology. They do not prove machining
intent, through-holes, extrusion direction or which later Fusion feature should
create the geometry.

Every output remains `inferred_candidate`; topology is not user-accepted merely
because a graph closes numerically.

## Determinism and provenance

Canonical loop orientation and start points make geometric loop order deterministic
for a fixed point set. Original section-input indices are retained only as compact
evidence:

- source point count
- SHA-256 of ordered int64 source indices
- bounded index preview
- primitive endpoint source indices remapped to the original section-input index
  space

Input U/V coordinates themselves are not echoed.

Live results preserve:

- source cloud ID/name
- global section origin/normal/U/V frame
- native global shift/scale bookkeeping
- query coordinate space
- exact sampled/matched counts
- sampling strategy

Shift/scale metadata is provenance only and is never reapplied to already-global
coordinates.

## Synthetic topology fixture

`scripts/make_profile_topology_fixtures.py` creates two shuffled multi-loop PLY
fixtures outside Git:

- axis-aligned
- rotated 41 degrees about normalized `[1,2,3]` and translated by
  `[100000000,-200000000,300000000]`

Each cloud contains:

- one concave notched outer loop
- one circular hole
- one smaller circular island inside the hole

The input point order is deliberately shuffled across all three loops.

Expected nesting is:

`outer -> hole -> island`

The transformed copy exercises arbitrary orientation, large global coordinates and
CloudCompare shift bookkeeping without changing the intended native dimensions.

## Deliberately unsupported in this increment

This increment does **not** infer boundary samples from:

- a filled planar section
- a thick surface slab
- overlapping front/back scan surfaces
- triangulated topology
- occupancy cells
- screenshots

It also does not repair:

- touching loops
- intersecting loops
- missing boundary spans
- severe undersampling
- non-manifold branches

Those cases fail explicitly.

The next useful 0.15 step after this topology layer is a bounded way to derive
boundary evidence from an ordinary scan section—likely from 2D occupancy / local
density / boundary-cell structure—before passing the result into this loop solver.

Ellipse fitting, rounded-rectangle classification, symmetry constraints and spline
fallback remain separate later profile-fitting work.
