# Focused Windows / CloudCompare 0.15.5 acceptance

Testing/reporting only. Do not implement fixes, rebuild the DLL, merge the new PR,
enable auto-merge, or request merge authorization just because tests pass.
Use the exact final SHA supplied in the handoff and read AGENTS.md first. Runtime/test
checkpoint is c3dac92069bf530e41fa66a6d08794e31f0d9076; later finalization commits are
documentation-only. Accepted-main parent:942c56e222eb5768ae2c60f7c1b6f153db070f68.

## 1. Identity and preservation

Inspect remote heads, recent commits/CI, existing worktrees/environments and the
visible CloudCompare instance. Reuse an exact isolated test worktree/environment,
or create a detached worktree at the supplied SHA. Preserve unrelated checkouts,
changes, caches, scene entities and desktop MCP configuration. Never reset/clean,
force-push, recreate branches, or create retry/recovery/-2 lanes. If state advanced,
reconcile it rather than resetting backward. Work in short steps and save logs and
raw evidence outside Git so a disconnected chat can resume without redoing work.

Python0.15.5; qMCPBridge unchanged0.12.0/workflow revision8. Verify imported package
path/version, Python executable, visible CloudCompare version and native capabilities.
Use the same isolated Python for tests and the temporary MCP stdio server. Native
source diff against the accepted-main parent must be empty. Do not rebuild the DLL.
0.15.4 and0.15.3 Windows acceptance are complete; this gate tests only the new
diagnostic and its limited integration checks, not their entire acceptance matrix.

## 2. Installed regression and source checks

Install .[test] in the isolated environment, then run:

```text
python -m pytest -q tests
python -m compileall -q src scripts tests
git diff --check
git diff --cached --check
git diff --check 942c56e222eb5768ae2c60f7c1b6f153db070f68 HEAD
git diff --exit-code 942c56e222eb5768ae2c60f7c1b6f153db070f68 HEAD -- cloudcompare-plugin
```

Expected installed suite:890 tests; an ordinary Windows shell may have874 passed
and16 compiler-gated skips. Run those16 policy tests separately under configured
MSVC, without building the plugin. Missing capability is BLOCKED, not a claimed pass.
The four diagnostic modules contain125 tests, included in the full suite.
CI at c3dac920 was890 passed with no skips; inspect final supplied SHA CI as well.

## 3. Exact fixtures and actual MCP stdio

Generate all20 PLY fixtures with scripts/make_section_target_diagnostic_fixtures.py
into a fresh outside-Git directory. Verify manifest SHA256/counts before product calls.
Use each record's target parameters/frame unchanged; do not adapt them to an outcome.
Exercise the exact files through the product snapshot path and run the four new test
modules. The new generator has its own deterministic shuffle/hashes.

Independently check actual temporary stdio tools/list and capability discovery:
- diagnose_section_target_stability
- diagnose_live_section_target_stability
- python_section_layers.section_targets.scale_diagnostics.version == 0.15.5

Accepted parent versions remain target0.15.4/layer0.15.3/profile0.15.2. With the bridge
unavailable, a transformed-file snapshot diagnostic must still work. Unknown custom
scales/schedules, target/layer IDs, selection tokens and profile parameters must
return structured errors; no native I/O is allowed for invalid arguments.
Run actual stdio tests, not only direct Python handlers. TCP replay is not real GUI.

## 4. Visible CloudCompare: new diagnostic only

Load the20 exact files into disposable labeled groups or reuse only a proved exact
matching fixture. Resolve current IDs. Record source count/bounds/global shift/scale
and available attributes before and after; do not alter source geometry. Call the
new live diagnostic once per file via the temporary stdio server, using manifest
origin/normal/slab/target parameters. It must acquire once, then report the fixed
five panels without extra native queries, raw arrays or profile generation. Where
transport instrumentation is available, record the cloud.region_query call count;
otherwise report that live call-count observation as unmeasured, not fabricated.

For completed panels require all N records classified, zero unclassified, and exact
preview-plus-omitted totals. Refused panels must have zero classified and N explicitly
unclassified. Root selected=0/unselected=N. Relations must account for every record.
Multiple/large/small/unsupported targets remain unselected. Candidate summaries are
bounded spatial previews, not quality-ranked choices; omitted counts must be visible.

Check baseline counts/status against manifest expectations. The specifically declared
new cases must expose depth_finer splitting at1.6 separation, depth_coarser merging
at2.1, uv_finer cell-budget refusal atmax_cells49, and uv_finer target-budget refusal
atmax_targets1. No budget change or retry is permitted. Refused probes yield
inconclusive. A blocked candidate remaining blocked across all settings is not a
failed diagnostic, and no_change_observed does not imply safe topology.

Verify original/permuted and transformed fixtures. Snapshot and live report tokens
are context-separated. Tiny projected-roundoff differences may legitimately alter
exact geometry hashes. Compare discrete evidence and measured bounds within source
precision; record real host quantization effects, never retune thresholds to conceal
them. Acquisition coordinates are already global: preserve shift/scale, do not apply
them again. No real nonunit-scale claim follows from replay metadata.

Test max_points10 on a dense file: incomplete acquisition must refuse before probes,
not return a successful comparison. Demonstrate report fingerprint changes after a
controlled snapshot geometry/frame/source/parameter change and rejects as an accepted
target-selection token. Do not mutate live originals to manufacture this test.

Limited downstream regression: on clean single and transformed parallel fixtures,
compare accepted target reconstruction before/after a diagnostic. It must be unchanged;
parallel still requires its justified layer choice. Also retain alternating-thick
layer refusal. Do not rerun the entire accepted0.15.4 gate or use a diagnostic panel
as a selected target. No probe profile or manufacturing inference is allowed.

## 5. Exactly one predeclared real-fan diagnostic

Only after synthetic gates pass, resolve the authorized fan_project.bin working copy
and current source identity. Historical cloud359/name "Assembly | Fan - scan 1"/
406276points are clues, not IDs to reuse without checking. Preserve the original.

Call diagnose_live_section_target_stability once with:

```json
{
  "cloud_id": 359,
  "origin": [40, 0, 135],
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
  },
  "query_timeout_seconds": 30
}
```

Replace only cloud_id with the resolved current ID. The five panels are the fixed
product experiment, not five choices from which to select a preferred outline.
The accepted run had complete5605points and19 entirely blocked targets. Report
current identity/counts, baseline evidence, all four probe results, splits/merges,
reason changes, refusals and total accounting. A refused baseline stops the call;
a refused probe makes it inconclusive. Record either as legitimate BLOCKED evidence
when consistent with the declared safety contract. A successful profile is not required.

Do not raise limits, choose depth signs, drop clutter, re-run alternative scales,
select a target/layer or attempt reconstruction from this experiment. Stop after
reporting the one diagnostic, even if a panel appears more usable.

## 6. Evidence and stop point

Return PASS/FAIL/BLOCKED by subtest, exact source/runtime/CI identities, actual GUI
identity, fixture hashes, panel/candidate/accounting summaries, refusal results,
shift/scale and transformed precision observations, and the one bounded fan result.
Separate numerical/unit, native replay, actual stdio and real GUI evidence.

Label integrity honestly: metadata-only, sampled, or independently full-cloud. File
hashes and slab fingerprints do not establish whole-live-cloud geometry/attribute
preservation. The inherited report is metadata-only and has no real-host nonunit-scale
test. Do not promote those claims. On a reproducible product defect, preserve a minimal
case, open a focused issue, stop the affected gate and do not implement a fix here.
Leave the0.15.5 branch/PR unmerged and retain all evidence outside Git.
