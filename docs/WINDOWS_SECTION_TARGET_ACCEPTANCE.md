# Focused real Windows/CloudCompare acceptance: 0.15.4

Testing/reporting only. Do not implement fixes, rebuild qMCPBridge, merge, or request
merge authorization. Accepted 0.15.3 GUI acceptance is already complete; this gate
covers the new target stage and its downstream integration, not a repeated old gate.
Read AGENTS.md and LIVE_CAD_SECTION_TARGET_ISOLATION.md first. Keep logs, JSON evidence,
manifest and generated PLYs outside Git. Use short bounded calls/checkpoints.

## Exact source and runtime

Use the supplied final branch HEAD, or reconcile a later deliberate commit rather
than resetting. Branch: `feature/live-cad-section-target-isolation`.
Accepted-main parent: `0201cdd46381e0c79c05b33ee9de48851a18b877`.
Complete runtime/test checkpoint: `f2ba2eb5b09c6cc267cd2eaf33dbfde268e59080`;
CI run `36356259255`: 765 passed, no skips, compileall and diff check passed.
Later documentation-only commits do not invalidate this runtime coverage.

Inspect remote heads, current worktree/branch, tracked and ignored work, existing
Python environment and live GUI identity. Preserve unrelated checkouts. Reuse a
correct isolated worktree; otherwise create a new detached testing worktree at the
exact supplied SHA without switching or resetting an unrelated checkout. A different
active development branch is not by itself a reason to overwrite it or stop testing
when a safe isolated worktree can be used. Do not delete retained branches/caches.

Install `.[test]` into an isolated environment associated with that worktree. Record
Python executable, package version 0.15.4 and imported source path. Use that executable
for tests and the temporary MCP stdio server, not whichever old server is configured
in the desktop app. Preserve normal user configuration. Identify the visible
CloudCompare version and native qMCPBridge 0.12.0 / revision 8.

Verify `git diff --exit-code 0201cdd46381e0c79c05b33ee9de48851a18b877 HEAD -- cloudcompare-plugin`
has no differences. No DLL build is authorized. Run full pytest, compileall and both
working/staged diff checks plus the accepted-main diff check. Expected installed
suite is 765 tests: an ordinary Windows shell may show 749 passed/16 compiler skips;
run those 16 policy tests under available configured MSVC separately and report the
split. This compiles the policy test only, not the plugin. Report unavailable tools
as BLOCKED, never as successful native/GUI validation.

## Exact files and actual MCP exposure

Run `scripts/make_section_target_fixtures.py` into a fresh directory outside Git.
Verify all 14 hashes/counts in manifest.json and test these exact files through the
new product path. Run the five target test modules (139 tests total); their actual
stdio/TCP replay tests do not count as real GUI acceptance. Independently list the
actual temporary stdio server's four target tools and validate capability version
at `python_section_layers.section_targets`, with accepted parent versions intact.

Use manifest request parameters unchanged. Prove snapshot analysis/reconstruction
works without native access, including transformed_single. Save compact results;
do not paste raw arrays or full stdio transcripts into chat.

## Visible CloudCompare target gate

Load disposable generated fixtures into identified temporary scene groups; do not
reuse ambiguous historical IDs. Resolve the actual newly loaded cloud for each case.
Record native source metadata before and after, including count, bounds, shift,
scale and available attributes. Query already-global positions without reapplying
shift/scale. Use each manifest origin/normal/half-thickness and target parameters.

Exercise the following cases through actual MCP stdio and the visible GUI bridge:

* `single`, `parallel`, `transformed_single`, `transformed_parallel`: one supported
  spatial target. Parallel cases must retain both depth layers, require an explicit
  downstream layer choice, and retain unselected-layer counts. Verify clean and
  transformed single-target handoff through occupancy/topology/primitive fitting.
* `coherent_clutter`, `two_targets`, `dominant`, `nested_choices`: explicit target
  choice required regardless of size. Fixture identity/spatial location supplies
  the intended choice; never choose by best reconstruction. Retain clutter and all
  target/layer unselected counts. Nested choice yields N=3600,T=2400,L=1200.
* `narrow_bridge`, `sparse`, `overlap`: visible blocking evidence; explicit target
  choice must not override it. `fan_like_many` reports 20 targets with complete
  accounting, not a required profile or a promise all targets are usable.
* `permuted_two` and `transformed_two`: same target geometry/count semantics as the
  originals, with context-appropriate fingerprints. Different loaded cloud IDs or
  source/file provenance legitimately change bound tokens.

Test a stale target token after changing a declared target parameter; test a stale
layer token after changing upstream target selection/context. Show snapshot/live
selection tokens cannot be interchanged. For truncation refusal, use a disposable
fixture with max_points=10 and do not treat its reservoir sample as topology proof.
Exercise a supported target with deliberately unsupported accepted layer evidence
(the deterministic alternating-thick case in test_section_target_workflow.py),
confirming target selection cannot bypass the layer refusal. Keep source untouched.

Large translated imports may use a real global shift. Record the actual shift/scale,
verify global slab coordinates and approximate expected extents/selected counts, and
check there is no double application. A replayed scale of 2.5 is not a real-host
nonunit-scale test. If import quantization changes a threshold classification, save
exact measured evidence and report the limitation; do not tune thresholds silently.

## One declared, bounded real-fan diagnostic

Only after synthetic gates pass, resolve the authorized `fan_project.bin` and use a
working copy. Identify current source by scene metadata; historical ID359, name
`Assembly | Fan - scan 1`, count406276 are clues, not authority. Record actual identity.
Use the retained slab origin [40,0,135], normal [0,0,1], half-thickness0.5.
Predeclare target parameters once: uv_cell_size2.0, depth_cell_size1.0,
perturbation_fraction0.1, min_cell_points3, min_target_cells4, max_points20000,
max_cells20000, max_targets32, query_timeout_seconds30. These specify coarse
spatial evidence in native units, not manufacturing intent or a promised result.

Require complete acquisition and report compact target counts, bounds, support,
bridge/overlap/probe ambiguity and candidate fingerprints when available. The old
5605-point/16-layer-component refusal remains accepted history. Do not rerun or
raise its layer limit to force success; do not raise target budgets after refusal,
choose depth sign, delete small targets or search parameters for a nice profile.

If multiple targets remain without an already justified explicit spatial choice,
report them and stop: BLOCKED is legitimate. If exactly one supported target (or an
already authorized spatial selection) exists, continue once through the accepted
layer stage. Keep max_components16. Predeclare accepted layer values uv_cell_size0.5,
depth_separation0.2, max_layer_thickness0.09, max_neighbor_depth_step0.12,
min_cell_points3, min_layer_cells4; profile cell_size0.5, max_edge_length1.1,
fit_tolerance0.35, angular_tolerance_degrees2, require_grid_stability=true.
Multiple layers still require justified explicit selection; do not choose by sign
or fit quality. Downstream refusal is useful evidence, not a mandatory defect.

## Evidence and report

Return PASS/FAIL/BLOCKED per subtest with exact source/runtime, CI attribution,
actual GUI/bridge identity, generated manifest hashes, analysis/selection counts,
stale/truncation/unsupported refusal results, transformed bookkeeping and bounded
fan outcome. Distinguish numerical, replay, actual MCP and real GUI coverage.

Source-integrity coverage must be labeled metadata-only, sampled or independently
full-cloud geometry/attributes, according to what was actually measured. A source
file hash or acquisition fingerprint is not a full live-cloud integrity proof.
Do not promote inherited 0.15.3 coverage: it was metadata-only and lacked a real
nonunit-scale source. Report whether the new gate materially adds either coverage.

On a reproducible product defect, record a minimal case and evidence outside Git,
open a focused issue if authorized, and stop the affected gate. Do not fix code or
rebuild the DLL during acceptance. No merge, even when all checks pass.
