# Repository work and interruption recovery

## Active UNMERGED 0.15.5: implementation and exact fixtures complete

Branch `feature/live-cad-section-target-diagnostics`.
Accepted-main parent `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
Initial lane7f29148d71a4e94fc0d902648227325aa5abb8d7;
core47c84d4fab4143733da5f01530230ccd6e185878;
workflow40746c1ae8aa8bf6aeb9c45cc81a01285e251a50;
MCP1e60917d2b32e272a178990cf21cfc11203ba789.
MCP checkpoint CI36359232798/job108732946770 SUCCESS including full installed pytest,
compileall and diff; exact count has not yet been independently read from logs.
This commit adds20 fresh hashed PLY fixtures and25 exact-file tests. Local file suite
25 passed in15.28s; prior core44+workflow47=91 passed in5.20s. Total new coverage125:
44core+47workflow/replay+9MCP(schema/dispatch/actualstdio)+25file. No actual0.15.5GUI.

NEXT: inspect this commit CI, verify source tree against local working files, run
available local regression and complete installed CI, final docs/Windows prompt and
final native/accepted-main diff. Keep0.15.5 unmerged. Resume this existing lane.

Tools diagnose_section_target_stability / diagnose_live_section_target_stability.
Capabilities python_section_layers.section_targets.scale_diagnostics0.15.5.
New pure core/workflow/tools; only existing target registry delegates. Accepted
solver/acquisition/server.py files unchanged. Native qMCPBridge0.12.0/rev8 unchanged.
No DLL rebuild. Existing target0.15.4/layer0.15.3/profile0.15.2 versions preserved.

## Contract and evidence boundaries

Five fixed panels: baseline,UV*0.75,UV*1.25,depth*0.75,depth*1.25; no custom schedule,
selection/profile arguments, adaptive search or recommended scale. One complete
native acquisition at most; no dropped/reacquired records. Accepted target solver
and all other thresholds/budgets unchanged. Baseline must complete (blocked allowed);
failed probe is inconclusive, not skipped/retried. Exact source-record intersections
show splits/merges even at equal counts. Reasons compare only identical one-to-one
membership; changed points explicitly uncompared. All points accounted including
refused panels and preview omissions (8candidates/16relations). No diagnostic token
can authorize accepted selection. No-change is not physical topology, universal
stability, whole-source integrity or manufacturing intent.

Generator scripts/make_section_target_diagnostic_fixtures.py writes20 PLY files plus
manifest outside Git. Existing14 cases plus depth split/merge, cell/target-budget
refusal and arbitrary-rotated/large-translated split/merge. Files tested by product
projection/snapshot/replay; permutation invariant; native metadata preserved.
Snapshot/live normal normalization can change exact projected geometry SHA values:
transformed audit found only hashes and at most1.11e-16 bounds difference (source
floor approximately5.33e-7). Tests compare exact discrete evidence and bounds within
source precision, not cross-context hash equality. No accepted normal code changed.

## Accepted history, not a pending gate

PR18 merged0.15.4 at045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03 after user authorization.
Retained feature/live-cad-section-target-isolation WindowsHEAD
4b5dfe7026f8166c0102d763a9b60e9048686996. TestedCI36356915539 and post-merge main942c56e
CI36358516660 succeeded. User report Windows749+16MSVC; target139; all14 exactPLY,
actualstdio, visibleGUI and safety/handoff PASS. Full detailed report mentioned but
not attached; never invent its contents. docs/WINDOWS_0_15_4_ACCEPTED.md is authoritative.
Fan complete5605points/19candidates, allblocked/allaccounted, no target/profile.
Legitimate BLOCKED, not defect or permission to retune. Integrity metadata-only;
no full-cloud equality or real-host nonunit scale. Actual shift[-100000000,199999000,
-299999000],scale1,no double application; quantization lost onebridge flag but erosion
still refused. Do not repeat accepted0.15.4/0.15.3 due to a new chat. Historical old
AGENTS retained in docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md; older pending wording
and docs/SECTION_TARGET_DIAGNOSTICS_PROGRESS.md TODOs are superseded by this file.

## Recovery

Commit coherent increments and verify returned SHA,parent/tree,remoteHEAD before next
substantial work. Save before long tests and update AGENTS. After failed stream read
HEAD/commits/AGENTS/CI; never assume writes lost. Never reset/clean/force-push/delete
retained branches or create retry/recovery/-2 lanes. Preserve unexpected work. Avoid
huge logs/rapid polling; show progress. Container Git DNS unavailable; use connector.
Local mirror commits are NOT remoteIDs. Distinguish local available tests, installed
CI/actualstdio, replay and realGUI. NoWindows handoff without installed fulltests,
compileall/full diff,schema/stdio/replay/files, final source/nativecomparison, green
finalCI and current checkpoint. No native rebuild or0.15.5 merge without later gate.
