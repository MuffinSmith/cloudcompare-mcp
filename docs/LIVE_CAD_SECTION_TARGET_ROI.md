# Explicit section-target ROI isolation — Python 0.15.6

The caller declares a numerical rectangle in the section frame **before** target
analysis. This is spatial intent, not a claim about parts or manufacturing intent.
The tool does not discover, rank, resize or optimize ROIs. qMCPBridge remains
0.12.0 / workflow revision 8; no native code or DLL rebuild is involved.

Pipeline: complete slab acquisition → section `(u,v,signed_depth)` → explicit UV
ROI → unchanged 0.15.4 targets → unchanged 0.15.3 layers → unchanged 0.15.2 occupancy
boundary → unchanged 0.15.1 topology → accepted primitive fitting.

## MCP surface

| Tool | Contract |
|---|---|
| `analyze_section_target_roi` | Complete caller-asserted snapshot; no native I/O |
| `analyze_live_section_target_roi` | One complete global-coordinate slab query |
| `reconstruct_section_target_roi_profile` | Snapshot ROI/target/layer selection and accepted reconstruction |
| `reconstruct_live_section_target_roi_profile` | Same reconstruction, using one newly acquired complete slab per call |

Capabilities are additive under
`python_section_layers.section_targets.roi_isolation`. Accepted version fields,
including 0.15.5 fixed-scale diagnostics, remain unchanged. All four tools are
read-only, return compact evidence, and leave original clouds untouched.

## Numerical contract

Every request requires exactly these four finite native-unit bounds:

```json
{"roi":{"u_min":-3,"u_max":11,"v_min":-3,"v_max":9}}
```

Membership is exactly `[u_min,u_max) × [v_min,v_max)` using the acquired float64 UV
values, without epsilon snapping. Lower boundaries are included; upper boundaries
are excluded. Bounds must have strictly positive finite spans. Booleans, strings,
nonfinite values, missing/extra keys and degenerate/inverted bounds are rejected.
Every point whose UV is inside retains **all** of its signed-depth evidence. There
is no ROI depth interval and no hidden filtering of unfavorable depths or clutter.

Snapshot `section` uses the accepted `section_uv_depth`, `native`,
`acquisition_complete:true`, `samples_uvd`, optional frame/source/provenance contract.
ROI snapshot tools additionally accept optional `source_point_indices`: unique
uint32-range integers in sample order, with exactly one per sample. Omit this field
when real source indices are unknown; do not invent original-cloud provenance.

Live requests use accepted `cloud_id`, `origin`, `normal`, `half_thickness`,
`target_parameters`, and optional query timeout. Complete acquisition is verified
before ROI narrowing: matched/returned counts agree, every record has a unique
source index, coordinates are global and finite, and `truncated:false`. An
incomplete/reservoir-truncated slab cannot establish ROI/target topology. The full
slab must satisfy the existing 20,000-point hard bound before ROI classification;
small ROIs do not authorize truncated acquisition of a larger slab.

The acquisition refactor separates the accepted verifier from target partitioning.
It does not change the target solver. Outside points therefore do not spend the
in-ROI target-count budget, but remain hashed, summarized and explicitly accounted
for. Target/cell limits and every accepted support/ambiguity check remain unchanged.

## One-cell truncation guard

Guard width is exactly the declared `target_parameters.uv_cell_size`. An in-ROI
sample at distance **less than or equal to** one cell from any ROI side touches the
guard. This inclusive inner threshold is deliberately conservative. No separate
searchable tolerance, guard-width setting or automatic growth is provided.

The report includes union and per-side point/cell counts, each candidate's minimum
sample distance from every side, and whether that candidate contains guard points.
Per-side counts can overlap at corners; union counts do not double-count points.
A candidate touching any guard is ineligible for downstream reconstruction even
when it is otherwise a usable accepted target and the caller supplies its explicit
ID and current fingerprint. The tool does not repair the clipping by resizing.

Outside support comes from one-cell outward strips along each half-open edge
extent, using the same complete slab and all depths. Per-candidate support records
outside samples in tangential grid cells also occupied by that candidate's guard
samples. These are projected adjacency observations, **not proof of a physical
connection**. Diagonally exterior corners remain in total outside accounting even
when they are not in an edge strip. Absence of outside support never overrides
inward guard contact. Guard clearance is evidence about supplied samples, not proof
that unobserved geometry cannot cross the rectangle.

Empty/fewer-than-three-point ROIs, or rectangles with no interior clear of the
fixed guard, return bounded `roi_evidence` refusals. Unsupported/ambiguous target
states, target-budget failures, layer uncertainty and downstream boundary/topology
failures retain their own refusal stages. No explicit selection overrides them.

## Selection and fingerprints

A single accepted usable target can continue automatically only when the accepted
automatic-selection rule allows it and its ROI guard is clear. Multiple candidates
still require explicit selection, even if only one is guard-clear. No largest,
closest-to-center or best-fit preference is introduced.

Analysis exposes `target_analysis.candidate_targets`. Use a candidate's `target_id`
and **candidate_fingerprint** as `expected_target_fingerprint`. The separate
`roi_fingerprint` is a report/context fingerprint, not an authorization token.
Plain target, plain analysis and 0.15.5 diagnostic report fingerprints cannot be
substituted for a bound ROI candidate fingerprint.

The domain-separated ROI context binds the full slab geometry (including outside
points), source identity, source-index mapping when available, section frame,
complete acquisition metadata, global-coordinate bookkeeping, exact bounds,
normalized target parameters and ROI algorithm contract. Any change invalidates
prior target selection. Snapshot and live contexts are intentionally distinct.

Layer selection uses `layer_id` and the returned layer analysis fingerprint as
`expected_layer_fingerprint`. Obtain that layer evidence with the **same target
selection mode** intended for the next request. Switching from automatic target
selection to explicit target selection changes upstream context and invalidates
an old layer fingerprint. Changing ROI bounds likewise invalidates layer selection.

Exact geometry/token invariance under permutation assumes the same source context
and index-to-point mapping. Raw file byte hashes and accepted boundary input-order
index hashes may legitimately differ. Host import quantization may also change
geometry and exact hashes; do not demand impossible snapshot/live bit equality.

## Accounting and coordinate bookkeeping

Analysis always reports input, inside, outside and zero unclassified ROI points.
It separately reports target-classified and target-unclassified inside points, so a
target-budget refusal cannot look like a successful classification. Analysis itself
selects zero points. Geometry summaries and index hashes replace raw arrays.

Reconstruction's root accounting retains `outside_roi_point_count`, selected target
and layer counts, unselected inside-ROI points, and unselected within-target points.
Its total unselected count plus selected-layer count equals the original complete
slab count, including on refusal. The nested accepted result has its own narrower
in-ROI input scope; it does not erase the root outside count. To avoid duplication,
accepted target analysis appears once under `roi_analysis.target_analysis`.

Live global XYZ is projected once. Source global shift and scale are preserved as
bookkeeping and are **not reapplied** to already-global geometry. The accepted
global-coordinate precision checks remain in force. Replay scale 2.5 is bookkeeping
coverage, not evidence of a real CloudCompare nonunit-scale import. No whole-source
geometry/attribute integrity or independently measured host query count is claimed
without an actual corresponding host measurement.

## Reusable fixtures and validation

Run `python scripts/make_section_target_roi_fixtures.py /absolute/new/output`.
The generator refuses repository-local output and overwriting. It creates 22 exact
ASCII-double PLY files plus a SHA256 manifest, outside Git. Cases cover safe targets,
outside clutter, two targets, all four clipped sides, half-open/nextafter samples,
clear margins, an exiting narrow bridge, sparse/empty/tiny evidence, two depth
layers, projected overlap, alternating-thick refusal, permutation, generic fan-like
clutter and arbitrary rotation with approximately `[1e8,-2e8,3e8]` translation.

File tests read and verify those exact bytes before using product projection and
snapshot/one-query native replay. Actual installed MCP stdio tests exercise both
snapshot tools without a bridge and both live tools against a TCP replay peer.
None of these tests is real GUI validation. See
[WINDOWS_SECTION_TARGET_ROI_ACCEPTANCE.md](WINDOWS_SECTION_TARGET_ROI_ACCEPTANCE.md)
for the separate focused host gate. The retained real fan may remain BLOCKED.

## Verified internal checkpoint

Runtime/test commit `5d618c0de30c90a4573d4c8be52174a3aed58eee` passed the complete
installed suite: **1070 passed, zero skips** in both the Python 3.13.5 sandbox
(212.55 seconds) and Python 3.12.14 GitHub CI (100.59 seconds, run 36363760167,
job 108745962764). compileall, diff checks and native/accepted-core immutability
checks passed. The 180 added tests include 46 exact-file tests over 22 fixtures
and two actual installed MCP stdio tests. Draft PR #20 remains unmerged.

Later documentation-only checkpoints do not change that runtime; still verify their
exact HEAD and CI. Real Windows/CloudCompare 0.15.6 acceptance remains pending.
