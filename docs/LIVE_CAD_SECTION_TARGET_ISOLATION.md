# 0.15.4 bounded section-target isolation

Status: internally tested, **UNMERGED; real Windows/CloudCompare acceptance pending**.
Python 0.15.4; qMCPBridge remains 0.12.0 / workflow revision 8. No DLL rebuild.
See AGENTS.md for exact checkpoints and the [focused Windows procedure](WINDOWS_SECTION_TARGET_ACCEPTANCE.md).

## Purpose and scope

A complete slab can contain many disconnected pieces before depth layers are even
meaningful. This stage reports explicit coarse spatial targets before calling the
accepted [0.15.3 layer solver](LIVE_CAD_SECTION_LAYER_ISOLATION.md). A supported
selected target then enters the unchanged 0.15.2 occupancy, 0.15.1 topology and
primitive-fitting pipeline. It does not raise the accepted layer-component limit,
identify physical parts, infer manufacturing intent or require the real fan to fit.

The four read-only tools are `analyze_section_target_regions`,
`analyze_live_section_target_regions`, `reconstruct_section_target_profile` and
`reconstruct_live_section_target_profile`. Analysis does not reconstruct. The two
reconstruction tools first analyze targets, then select a supported target, then
invoke the accepted downstream stages. No raw point arrays are returned. All acquired
points remain server-side and assigned to reported candidates, including clutter.

Capabilities are discovered at `python_section_layers.section_targets`, version
0.15.4. The parent layer capability remains 0.15.3; profile capability remains 0.15.2.
The existing layer registry delegates target registration without changing server.py
or the accepted layer/boundary/topology/fitting implementations.

## Explicit numerical contract

`target_parameters` requires `uv_cell_size`, `depth_cell_size` and
`perturbation_fraction`. Distances are native coordinate units, not presumed mm.
The fraction is dimensionless and must be in (0, 0.25]. Voxel origin is the minimum
of each acquired section-coordinate axis. Cells are half-open, using floor with
no epsilon snapping. Connectivity uses the six face neighbors in anisotropic
(u,v,signed_depth) space. Cell membership is not a physical separation proof.

Optional defaults and bounds:

| Parameter | Default | Bounds |
|---|---:|---:|
| min_cell_points | 3 | 1..20000 unique positions per voxel |
| min_target_cells | 4 | 3..20000 |
| max_points | 20000 | 3..20000 complete input points |
| max_cells | 20000 | 3..20000 occupied voxels per analysis/probe |
| max_targets | 32 | 1..64 components per analysis/probe |

Duplicate records remain in point accounting but cannot manufacture unique-point
support. Component IDs and geometry hashes are invariant to input permutation.
Summaries include point counts, unique support statistics, occupied/UV cells,
UV/depth bounds, extent, depth median, connectivity, source geometry hashes,
nearest-other bounding-box distance lower bound, ambiguity and candidate tokens.
The reported distance is not exact surface clearance. Pair detail is a bounded
16-pair preview; the full pair count and per-target flags remain authoritative.

Diagnostics never replace the baseline membership:

* Every articulation voxel is conservatively flagged as a bridge or appendage.
  Tarjan traversal is iterative; no graph-recursion limit hides long chains.
* One four-neighbor UV-cell erosion must leave exactly one component. Empty or
  split erosion is a thin/neck-sensitive refusal, not permission to remove cells.
* Distinct targets with shared projected UV cells or diagonal-only voxel contact
  are both ambiguous. Contact is reported, not joined; overlap is not resolved by
  choosing one depth sign.
* Six fixed grid-origin probes (+/- the declared fraction along each of U, V and
  depth) compare exact point partitions. Any split/merge affecting a target blocks
  that target. Probe budget overflow refuses the analysis; it never drops targets.

These tests are deliberately conservative and resolution-dependent. Small harmless
appendages may block. Wide necks, subcell contacts, unsampled connections, coincident
surfaces, other grid origins and changes of cell size are not exhaustively ruled out.
No adaptive resolution, seed growth or parameter search is implemented. A caller
must declare a physically defensible scale before inspecting results, not search
until topology becomes convenient. `depth_cell_size` groups spatial evidence, not
physical layers; coarse targets can and should still contain multiple depth layers.
A finer depth cell that separates UV-overlapping targets can correctly refuse them.

## Acquisition, provenance and selection

Snapshot input uses the accepted `section` schema: `coordinate_space` is
`section_uv_depth`, `units` is `native`, `acquisition_complete` is literally true,
and `samples_uvd` contains complete finite rows. Optional frame/source/provenance
follow the accepted bounded, right-handed-frame rules. The completeness flag is a
caller assertion, not independent proof. Process snapshot arrays locally/server-side
rather than dumping them into a chat transcript.

Live input instead supplies `cloud_id`, `origin`, `normal`, `half_thickness` and
optional `query_timeout_seconds` (default 30, maximum 120). The only native method is
`cloud.region_query` in global coordinates, once per tool call. Counts must match
all returned records, `truncated` must be false, indices must be unique and points
must lie in the requested slab. Too many points, malformed/nonfinite input or
unrepresentable precision refuses before a topology result. Tolerances and declared
perturbations must exceed source-global precision floors. Global shift/scale are
preserved as metadata and **never applied to already-global coordinates again**.

A target-analysis `ready` result requires exactly one candidate and no blocking
reason. Multiple candidates always require an explicit choice, even when just one
is large or usable. Distant unsupported clutter remains reported: a separate usable
target can be explicitly chosen while all clutter counts/reasons remain unselected.
An ambiguous target itself cannot be overridden by selecting its ID.

For explicit target selection, supply both `target_id` and its
`candidate_fingerprint` as `expected_target_fingerprint`. Tokens bind the target and
whole acquired geometry, target parameters, frame, source and acquisition context.
Live context includes point-index mapping and native bookkeeping. Snapshot and live
tokens are intentionally different. Changed file-provenance hashes also change
bound tokens, even when only file order changes; geometry-only permutation invariance
requires the same provenance. These hashes cover acquired slab geometry, not an
independently verified revision of the entire source cloud or its attributes.

Reconstruction additionally requires `layer_parameters` and `profile_parameters`
using the unchanged accepted schemas. When the selected target contains several
layers, inspect `layer_result.layer_analysis`, then provide both `layer_id` and that
analysis's `analysis_fingerprint` as `expected_layer_fingerprint`. The downstream
fingerprint also binds upstream target selection; standalone 0.15.3 layer tokens
cannot be substituted. No token confirms manufacturing intent or user acceptance.

A live request shape (resolve `cloud_id` from the current scene first):

```json
{
  "cloud_id": 123,
  "origin": [0, 0, 0],
  "normal": [0, 0, 1],
  "half_thickness": 0.5,
  "target_parameters": {
    "uv_cell_size": 2.0,
    "depth_cell_size": 1.0,
    "perturbation_fraction": 0.1,
    "min_cell_points": 3,
    "min_target_cells": 4,
    "max_points": 20000,
    "max_cells": 20000,
    "max_targets": 32
  }
}
```

Those numbers are a declared coarse-evidence example, not universal defaults or a
promise of useful candidates. The required size/fraction values have no implicit
runtime defaults. A failed budget returns a structured MCP error, not a partial
candidate list. An unsupported target returns evidence with `status=blocked` or an
unusable candidate. Reconstruction retains `blocked_stage`, target evidence and,
when available, accepted layer/boundary diagnostics.

For N acquired points, T selected-target points and L selected-layer points, the
reconstruction reports N-T unselected outside the target, T-L inside the target,
and N-L total unselected. These are slab counts, not the full source-cloud size.
Each stage retains all evidence needed to explain a refusal; no filtering, point
mutation, morphology repair or synthetic boundary replacement occurs here.

## Reusable fixtures and validation

Generate fresh exact files outside Git:

```text
python scripts/make_section_target_fixtures.py <new-directory-outside-repository>
python -m pytest -q tests/test_section_targets.py tests/test_section_target_workflow.py tests/test_section_target_boundaries.py tests/test_section_target_fixtures.py tests/test_section_target_tools.py
```

The generator writes 14 ASCII-double PLY files plus SHA-256 manifest: clean single,
coherent target plus clutter, two targets, dominant plus other target, narrow bridge,
parallel depth layers, nested target/layer choices, sparse target, depth-separated
UV overlap, 20-patch fan-like slab, permuted two-target file, and rotated/large-
translated single/two/parallel cases. It refuses repository paths and overwrites.
No geometry or parameter was derived from the user's real fan.

Tests consume the exact files through product projection and workflows, including
native-result replay. Actual MCP stdio tests use a generated transformed snapshot
without a bridge and generated nested choices through a read-only TCP replay peer.
Replay is NOT real CloudCompare. No real nonunit-global-scale or full-cloud integrity
claim follows from replay. Real acceptance remains a separate gate.
