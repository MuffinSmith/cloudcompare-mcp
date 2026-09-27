# 0.15.5 fixed target-scale diagnostics

Status: internally complete and CI-green; **unmerged, real Windows/CloudCompare
0.15.5 acceptance pending**. Accepted 0.15.4 was merged through PR #18; its Windows
summary is in [WINDOWS_0_15_4_ACCEPTED.md](WINDOWS_0_15_4_ACCEPTED.md). Earlier pending
wording in historical target documents is superseded by that record.

Python is 0.15.5. Native qMCPBridge remains 0.12.0 / workflow revision 8. No DLL
rebuild. Read AGENTS.md for exact source/CI identities and interruption recovery.

## Purpose and non-goals

A blocked target analysis can reflect spatial clutter, marginal support, bridges,
or sensitivity to its declared occupancy scale. This increment compares evidence
at a fixed, bounded set of cell sizes. It does not choose a cell size, isolate a new
target, infer manufacturing intent, or make the retained fan reconstruct.

The independent numerical core is `section_target_diagnostics.py`; the thin workflow
reuses the accepted target acquisition/validation and solver implementations without
changing them. Native geometry remains read-only, with every source record retained.
No adaptive or multiresolution *search*, morphological repair, fit-based ranking,
ROI growth, Fusion integration, ellipse or spline work is included.

## MCP contract

`diagnose_section_target_stability` accepts exactly the accepted target-analysis
snapshot arguments: `section` and `target_parameters`. The section requires
`coordinate_space="section_uv_depth"`, `units="native"`, literal
`acquisition_complete=true`, and finite `[u,v,signed_depth]` samples. Optional source,
frame and provenance follow the accepted strict contract. It performs no native I/O.
Snapshot completeness is a caller assertion, not independent verification.

`diagnose_live_section_target_stability` accepts `cloud_id`, global `origin`,
`normal`, `half_thickness`, and `target_parameters`, with optional
`query_timeout_seconds` (default 30, maximum 120). That timeout bounds the native
query, not the complete Python analysis. Exactly one `cloud.region_query` is issued
for a valid live acquisition request. It must return all matches, unique source
indices, finite global coordinates, and valid source shift/scale. Truncation, malformed
records, outside-slab records, or over-budget baseline evidence refuse the call.
Records are never dropped, reacquired or reservoir-sampled as topology proof.

The target parameters remain explicit native-unit `uv_cell_size`, `depth_cell_size`
and `perturbation_fraction` in (0,0.25], plus accepted bounded support/cell/point/target
options. Defaults are min_cell_points=3, min_target_cells=4, max_points=20000,
max_cells=20000, max_targets=32; the hard max_targets is 64. These limits are not
raised by this tool. Selection tokens, target/layer IDs, reconstruction parameters,
custom scales, schedules and stop-on-success arguments are rejected before native I/O.

Capabilities are advertised at
`python_section_layers.section_targets.scale_diagnostics`, version 0.15.5. Parent
capability versions remain target 0.15.4, layer 0.15.3 and profile 0.15.2. Both tools
are read-only/idempotent; only the live tool advertises external-world access.

## Fixed evidence experiment

The schedule is always declared in the response and never changes with outcomes:

| Panel | UV cell size | Depth cell size |
|---|---:|---:|
| baseline | declared size | declared size |
| uv_finer | 0.75 x declared | declared size |
| uv_coarser | 1.25 x declared | declared size |
| depth_finer | declared size | 0.75 x declared |
| depth_coarser | declared size | 1.25 x declared |

Only the named cell-size axis changes. All support thresholds, budgets and the
accepted six grid-origin probes retain their original settings. Each panel uses the
same acquired source records and accepted six-face occupancy connectivity. Finer and
coarser describe cell size, not evidence quality. There are at most five target
analyses, with up to 35 occupancy constructions including accepted origin probes.
This is a count bound, not a wall-time guarantee.

Baseline must finish successfully as an analysis, but all of its candidates may be
blocked. A baseline limit/error stops the whole call; it is not retried at another
size. A later probe refusal is a completed *diagnostic observation*: the panel reports
its reason, zero classified records and all N records unclassified. Other fixed
panels still run; no probe is quietly omitted or retried. Smaller settings must also
respect the acquired source's global-coordinate precision floor.

## Comparing membership without guessing correspondences

Baseline and probe memberships are compared by exact source-record intersections.
For each baseline candidate and each probe candidate the core counts their common
records. A baseline candidate intersecting several probe candidates is a split; a
probe candidate intersecting several baseline candidates is a merge. Equal candidate
counts do not imply equal partitions, and a largest overlap is not accepted as a match.

A candidate is an unchanged match only when that intersection is one-to-one with
identical membership. Blocking-reason sets are compared only for these exact matches.
All records in changed memberships are explicitly counted as uncompared for reasons.
No nearest-bounds matching, target preference, filtering or reconstructed-fit score
is used. Reordering the same records preserves the evidence and fingerprint within
the same coordinate/context representation; duplicate records remain fully counted,
while accepted unique-geometry support still prevents duplicate density inflation.

`status` has three meanings:

- `inconclusive`: at least one fixed probe refused. Successful-panel changes remain
  visible, but incomplete comparison is never relabeled stable.
- `sensitivity_observed`: all panels completed and at least one sampled partition or
  exact-match blocking-reason set changed.
- `no_change_observed`: all panels completed and neither comparison changed. This
  is not a claim that numerical support values are identical or that a target is safe.

In particular, five identically blocked panels can report no_change_observed. It is
never automatic permission to continue reconstruction or confirm a physical part.

## Compact reporting and accounting

Every completed panel reports effective parameters, accepted solver status, candidate
and occupied-cell counts, supported/unsupported point totals, blocking-reason totals,
and origin-probe changed-target counts. Blocking-reason point totals overlap and
must not be added as if mutually exclusive. Candidate summaries include source and
unique counts, UV/depth bounds, cell support statistics, articulation/erosion evidence,
and nearest-other *bounding-box distance lower bound*, not exact geometric distance.

Only the first eight candidates in deterministic spatial order and first sixteen
membership relations are previewed. These are not the largest or best candidates.
Explicit omitted candidate/relation counts and point counts retain total accounting;
preview truncation is not acquisition truncation. Detailed memberships and raw point
arrays remain server-side. Panel totals and relations account for all acquired points,
including unsupported and unclassified evidence. Root selection accounting is always
selected=0, unselected=N. No source mutation or profile reconstruction is attempted.

The `target-diagnostic-v1:` report fingerprint binds the accepted baseline's geometry,
source, frame, acquisition and parameters plus the fixed diagnostic schedule. Live
source-index mapping is included via accepted provenance. No accepted candidate or
analysis selection tokens are returned. Diagnostic region hashes identify sampled
geometry only; neither those nor the report fingerprint authorize target selection.
They are deliberately rejected by the accepted reconstruction selection API.

## Coordinate and integrity limits

Native acquisition already supplies global coordinates. Shift/scale are preserved
as provenance, never applied twice. A real nonunit-scale host has not been validated
here; replay with scale 2.5 is only bookkeeping coverage. No full-cloud geometry or
attribute equality is proved. Live integrity is reported as not independently measured
by this tool, and inherited 0.15.4 whole-source coverage stays metadata-only.

Snapshot and live normal normalization can produce sub-ULP differences in projected
coordinates and therefore different exact geometry hashes. Transformed development
files had identical discrete evidence with bounds differing by at most 1.11e-16;
the source precision floor was about 5.33e-7. Tests compare discrete evidence exactly
and bounds within declared source precision, not cross-context hashes. Actual host
quantization may change a guard; record it rather than retuning to hide it.

Five fixed scales and six origins do not cover every possible phase, grid size,
subcell connection, unsampled surface or wide bridge. Conservative accepted guards
can refuse harmless thin features. No manufacturing interpretation or topology proof
follows from finite diagnostic agreement.

## Fixtures and validation

Generate fresh files outside the repository:

```text
python scripts/make_section_target_diagnostic_fixtures.py <new-directory-outside-repository>
python -m pytest -q tests/test_section_target_diagnostics.py tests/test_section_target_diagnostic_workflow.py tests/test_section_target_diagnostic_tools.py tests/test_section_target_diagnostic_fixtures.py
```

The manifest covers 20 hashed ASCII-double PLY files: all 14 prior target-case shapes,
depth-split, depth-merge, cell-budget refusal, target-budget refusal, and arbitrary
rotated/approximately [100000000,-200000000,300000000]-translated split/merge cases.
The shuffle/manifest are reproducible. Files are consumed through product projection,
snapshot and native replay, not just compared to an in-memory generator. New hashes
are from this generator and need not equal the earlier 0.15.4 shuffle's hashes.

Development at runtime/test checkpoint c3dac92069bf530e41fa66a6d08794e31f0d9076:
installed CI 36359440529 / job108733546296: **890 passed, zero skips, 83.57 s**.
New coverage is125 tests:44 core,47 workflow/replay,9 MCP schema/dispatch/actualstdio,
25 exact-file and accepted-handoff tests. Local available subset:666 passed in40.14s;
19 modules could not import missing MCP dependencies locally and ran in installed CI.
This distinction must remain visible; replay/stdio is not real GUI acceptance.

See the [focused Windows procedure](WINDOWS_SECTION_TARGET_DIAGNOSTIC_ACCEPTANCE.md).
The real fan may remain blocked. The new gate diagnoses it once and never selects a
scale, target, layer or profile from probe outcomes.
