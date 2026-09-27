# Repository work and interruption recovery

## Active UNMERGED 0.15.5: core, workflow and MCP persisted

Branch `feature/live-cad-section-target-diagnostics`.
Accepted-main parent `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
Initial lane7f29148d71a4e94fc0d902648227325aa5abb8d7;
core47c84d4fab4143733da5f01530230ccd6e185878;
workflow40746c1ae8aa8bf6aeb9c45cc81a01285e251a50.
This commit adds two MCP tools, registry/capability integration and9 MCP tests.
Local core44+workflow47 =91 passed in5.20s. Local compileall/diff passed for MCP;
MCP dependencies are absent locally, so actual schema/stdio/full-suite evidence
must come from installed CI, not a falsely claimed local run.

Tools: diagnose_section_target_stability, diagnose_live_section_target_stability.
Capabilities: python_section_layers.section_targets.scale_diagnostics (0.15.5).
Parent accepted versions remain layer0.15.3,target0.15.4,profile0.15.2. Only target
registry delegates new tools; accepted solvers, workflow acquisition and server.py
are unchanged. Native qMCPBridge remains0.12.0/revision8; no DLL rebuild.

NEXT: inspect current CI, add exact generated diagnostic files/tests including
split/merge/budget cases plus existing14 fixtures, complete regression, final docs,
source/native diff verification and focusedWindows handoff. Do not merge0.15.5.
The older progress document describes the preceding workflow-only checkpoint;
this AGENTS supersedes its MCP TODO. Resume persisted work, never recreate the lane.

## Contract

Five fixed settings: baseline,UV*0.75,UV*1.25,depth*0.75,depth*1.25. Identical support,
point/cell/target budgets and origin perturbations; accepted0.15.4 solver reused.
Exact source-record intersections detect splits/merges, even at equal counts.
Blocking-reason comparison only for identical one-to-one memberships; other points
explicitly uncompared. Every point accounted, including refused probes and bounded
spatial previews (8 candidates/16 relations), never quality-ranked. No accepted
selection tokens, recommendation, adaptive search, target selection or profile.
Baseline must complete (all-blocked is allowed); failed probe gives inconclusive
without retry/raised budget. No-change is sampled evidence, not universal stability,
physical topology, whole-source integrity or manufacturing intent.

The thin workflow uses strict accepted analysis-only validation before I/O. Exactly
one complete native slab at most; invalid/truncated records are never dropped or
reacquired. Fingerprints bind source/mapping/geometry/frame/provenance/parameters.
Diagnostic tokens cannot authorize accepted selection. Smaller probes retain global
precision guards and acquired global coordinates are not shifted/scaled twice.

## Accepted history is not an outstanding gate

0.15.4 PR18 merged045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03 after user approval.
Retained feature/live-cad-section-target-isolation at tested
4b5dfe7026f8166c0102d763a9b60e9048686996. TestedCI36356915539 success;
post-merge main942c56e CI36358516660 success. User report: Windows749+16 MSVC,
target139; all14 exact PLY/actualstdio/visibleGUI and safety/handoff gates PASS.
Full detailed report mentioned but not attached; do not invent its evidence links.
See docs/WINDOWS_0_15_4_ACCEPTED.md. Complete5605 fan slab returned19 candidates,
all blocked, all points accounted, no selection/profile. Legitimate BLOCKED, no defect.
Integrity remains metadata-only; no full-cloud equality or real nonunit-scale test.
Actual shift[-100000000,199999000,-299999000],scale1, no double application. Host
quantization removed one bridge flag but erosion refused. Do not repeat accepted
0.15.4/0.15.3 gates due to a new chat or tune thresholds to make the fan pass.
Original historical AGENTS: docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md.

## Recovery

Commit coherent work and verify returned SHA,parent/tree and remote HEAD before
next substantial work. Keep AGENTS current and save before long tests. After a
failed stream inspect actual HEAD/commits/AGENTS/CI, not assumptions about lost work.
Never reset, clean, force-push, delete retained branches or create retry/recovery/-2
lanes. Preserve unexpected work. Avoid giant logs/rapid polling; show progress.
Container Git DNS unavailable. Accepted main source artifact10944489842 SHA256
641f9608146dbae57b0e4bec90d35973aa4d58fd4e0eda5a4d92b49837dfd796 matched942c56e and
tree1be000e5c7e29818b1f772d7b522f01c087cd0f8. Local mirror IDs are not remote IDs.
Distinguish local dependency-available checks, installed CI/actualstdio, native replay
and realGUI. Before Windows handoff require full installed tests, compileall/diff,
exact files/schema/stdio/replay, final native/accepted-main comparison, green finalCI
and current checkpoint. No source-integrity inflation; replay is not realGUI.
