# Accepted 0.15.2: filled-section boundary evidence

Branch: `feature/live-cad-section-boundary-extraction`, created from accepted main
`2747bdd54cbe4260e3b37382f2afbadc2b677694`. Python is 0.15.2.
qMCPBridge remains the accepted 0.12.0 / workflow revision 8 and is unchanged.

Real Windows/CloudCompare acceptance completed at exact HEAD
`7610eceff68704132ff44086d8d070fbb10b5c38` (runtime checkpoint
`0fd59d19156f6d80087e1c43b2096482aa85715f`). Generated snapshot/live fixtures,
including rotated/large-translated outer/hole/island geometry, and safety checks
PASSed. Windows regression was 490 passed plus 16 initially skipped compiler-gated
policy tests, all 16 subsequently passing with MSVC configured. No DLL rebuild.
The bounded fan remained correctly BLOCKED by multiple/thick depth evidence and
diagonal occupancy ambiguity, not a product defect. Source integrity coverage was
metadata only; real-host nonunit scale remains untested. See AGENTS.md for exact
acceptance attribution, numerical checkpoints and merge recovery state. The retained
Windows procedure is not a request to repeat this completed gate.

This increment addresses the acquisition limitation retained from accepted 0.15.1:
ordinary scan sections usually contain material-interior samples, not an isolated
boundary-only cloud. The new layer derives explicit 2D boundary **evidence** from a
filled projected section, then reuses the accepted 0.15.1 topology solver and the
accepted line/arc/circle fitter.

The result is still inferred geometry. Occupancy is evidence at a caller-selected
resolution, not proof of manufacturing intent.

## Responsibility boundary

CloudCompare remains the acquisition/metrology layer. Existing
`cloud.region_query` slab acquisition supplies bounded live samples and source
coordinate bookkeeping.

Python is responsible for:

1. stable section projection;
2. explicit occupancy-grid construction;
3. exposed-cell boundary evidence;
4. source-sample association;
5. accepted 0.15.1 loop topology;
6. accepted primitive fitting;
7. provenance and ambiguity reporting.

No native bridge method or DLL change is required.

## New MCP surface

### `extract_section_boundary_evidence`

Snapshot-only. Input is a `section_uv` envelope whose unordered points may include
material-interior samples.

The caller must provide an explicit native-unit `cell_size`. Optional controls
include `min_cell_support`, `min_component_cells`, `max_cells`,
`max_boundary_points`, and grid-origin sensitivity checking.

The tool:

- bins samples into a half-open 2D occupancy grid;
- retains source indices and per-cell support;
- uses 4-neighbor material connectivity;
- identifies exposed cell edges;
- rejects diagonal-only/non-manifold connectivity instead of guessing;
- traces exposed edges into closed contour candidates;
- distinguishes material-exterior versus enclosed-empty-region facing from edge
  orientation;
- associates each exposed edge with a nearby original sample from its occupied cell;
- fingerprints source input and selected boundary evidence;
- reports cell support, component, boundary-edge, contour, and grid sensitivity
  diagnostics;
- returns no raw point array;
- runs one bounded one-cell erosion/dilation sensitivity diagnostic, but never uses
  the perturbed occupancy for reconstruction.

No erosion, dilation, closing, hole filling, or other morphology is applied as a
repair step. The single erosion/dilation pass exists only to flag topology that is
one-cell sensitive.

### `reconstruct_filled_section_profile`

Snapshot-only composite helper:

`filled samples -> boundary evidence -> accepted 0.15.1 topology -> accepted primitive fitter`

The occupancy stage remains visible in the response. The composite refuses a
grid-sensitive result by default when material-component or contour counts change
under half-cell origin shifts. `require_grid_stability=false` may be used only when
the caller deliberately wants to inspect the candidate despite that warning; it does
not make the result accepted.

The accepted topology solver still receives original section samples associated with
exposed occupancy edges rather than synthetic grid-corner geometry. This preserves a
direct evidence path back to the scan while the grid remains only the boundary
selection mechanism.

### `reconstruct_live_filled_section_profile`

Read-only live wrapper. It reuses the existing native slab query and stable Python
section projection.

For this first increment:

- `sample_limit` is bounded to 20,000;
- acquisition must be complete: matched count must equal sampled count and the native
  result must not be truncated;
- deterministic reservoir sampling is not treated as adequate occupancy evidence;
- sections larger than the limit must be reduced or isolated before reconstruction;
- raw live positions remain server-side;
- global shift/scale is retained as provenance and never reapplied to already-global
  coordinates.

The live wrapper also examines signed offsets through the slab. Strong support on
both sides across much of the slab depth is reported as possible multiple/thick
projected surfaces and is rejected rather than collapsed into a convenient 2D
outline.

## Numerical policy

All thresholds are in native units. No millimetre assumption is made.

Grid indexing first subtracts a nearby origin. Requests below a float64 coordinate
precision floor are rejected. The grid origin, index extents, cell size, source
support statistics, source fingerprints, and boundary-evidence fingerprints are
returned.

`cell_size` is deliberately not auto-hidden. A useful result must be interpreted
together with its resolution and sensitivity diagnostics.

Before calling the accepted 0.15.1 radius-graph topology solver, the composite also
reports the minimum radius required for every selected original boundary sample to
have two local neighbors. A caller-provided `max_edge_length` below that measured
lower bound is rejected with the exact required value; it is not auto-expanded.

## Safety and ambiguity boundaries

The implementation refuses or warns on evidence such as:

- truncated live acquisition;
- too few supported occupied cells;
- disconnected components below the explicit minimum component size;
- diagonal-only/non-manifold grid connectivity;
- boundary evidence exceeding the explicit point budget;
- representationally impossible grid resolution;
- strong half-cell origin sensitivity;
- material-component/contour changes under a single one-cell erosion/dilation
  diagnostic;
- strongly nonuniform or weak per-cell support;
- possible multiple/thick projected live surfaces.

It does not silently discard components, close gaps, fill holes, smooth narrow
features, repeatedly morph occupancy until topology looks useful, or infer feature
intent.

A BLOCKED result is preferred to an invented outline.

## Reusable fixtures

`scripts/make_filled_section_boundary_fixtures.py` creates disposable fixtures
outside Git:

- filled concave outer region with circular empty region and nested material island;
- arbitrary 3D rotation plus approximately
  `[100000000,-200000000,300000000]` translation;
- nonuniform-density copy;
- narrow-notch copy only a few occupancy cells wide;
- overlapping front/back-layer copy for live ambiguity testing.

Tests read the generated PLY files back from disk and run the real projection and
boundary/reconstruction code. Helper arrays alone are not the acceptance path.

## Provenance states remain separate

Do not collapse these states:

1. measured/projected scan samples;
2. inferred occupancy/boundary evidence;
3. inferred loop topology;
4. inferred CAD primitives/profile candidates;
5. user/manufacturing acceptance.

The new stage does not alter accepted 0.15/0.15.1 behavior or issue #13 semantics.

## Retained limitations

The first occupancy implementation is deliberately conservative. In particular:

- occupancy cannot by itself distinguish coincident 3D surfaces after projection;
- very nonuniform density can make empty cells ambiguous;
- a poor cell size can erase or split narrow geometry;
- no adaptive/multiresolution occupancy is claimed;
- no spline or manufacturing-intent inference is added;
- native nonunit global-scale behavior still lacks real-host coverage.

The accepted fan refusal motivates 0.15.3 depth-aware layer evidence before 2D
occupancy. That future stage must preserve this solver and may still return BLOCKED.
See `WINDOWS_SECTION_BOUNDARY_ACCEPTANCE.md` for the retained focused procedure.
