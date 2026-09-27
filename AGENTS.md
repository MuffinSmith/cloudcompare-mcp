# Repository work and interruption recovery

## Active UNMERGED 0.15.5: numerical core persisted

Branch: `feature/live-cad-section-target-diagnostics`.
Accepted-main parent: `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
Initial lane checkpoint: `7f29148d71a4e94fc0d902648227325aa5abb8d7`.
This commit adds the pure numerical core and44 deterministic tests. Local targeted
run:44 passed in2.46s. Workflow/acquisition integration, MCP tools, exact-file tests,
complete installed regression, final documentation and Windows handoff remain TODO.
Resume here rather than recreating a branch or reimplementing the core.

Core: `src/cloudcompare_mcp/section_target_diagnostics.py`.
Tests: `tests/test_section_target_diagnostics.py`.
Fixed schedule: baseline, UV*0.75, UV*1.25, depth*0.75, depth*1.25. Reuses the
accepted0.15.4 target solver with all support/point/cell/target budgets and origin
perturbations unchanged. Exact source-record intersections detect splits/merges,
even if candidate counts agree. Blocking-reason comparisons only cover identical
one-to-one memberships; changed memberships are explicitly uncompared for reasons.
All points are counted, including refused probes and bounded preview omissions.
Eight candidate and16 relation previews are spatial/deterministic, not quality ranked.
No selection authorization, accepted selection tokens, recommended scale or profile.

Baseline must complete (it may be fully blocked). Failed probe gives an inconclusive
report without retry or raised budget. No-change means only sampled partition and
blocking-reason agreement across five settings, not physical topology or universal
stability. Changes to numeric support values alone do not mean membership changed.
Source precision must remain valid for each smaller probe. Native coordinate data
must not be shifted/scaled twice. No accepted solver/acquisition file has changed.

Next: reuse accepted snapshot/live target analysis to obtain the baseline, then call
`diagnose_target_analysis`. Add two read-only tools, schema/capabilities/actual stdio,
workflow replay tests, exact generated fixtures, transformed provenance/fingerprint
coverage and accepted-regression tests. Test refusal/no I/O for unknown/selection/
profile/schedule arguments. Report fingerprint is diagnostic-only. Do not reconstruct
from probes or parameter-search to make the fan fit. Keep qMCPBridge unchanged.

## Accepted history, not an outstanding gate

PR18 merged0.15.4 at `045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03`.
Retained tested branch `feature/live-cad-section-target-isolation` HEAD
`4b5dfe7026f8166c0102d763a9b60e9048686996`. CI36356915539 passed.
Post-merge documentation main942c56e CI36358516660 passed.
Read `docs/WINDOWS_0_15_4_ACCEPTED.md`: Windows749+16 MSVC passes, target139,
all14 exact PLY/actualstdio/visibleGUI and safety/handoff gates PASS. No defect.
Complete5605-point fan slab:19 candidates, all blocked, all points accounted, no
selection or profile. Metadata-only integrity; no independent full-cloud equality
or real-host nonunit-scale test. Actual shift[-100000000,199999000,-299999000],scale1,
no double application; quantization removed one bridge flag but erosion still blocked.
Earlier pending wording is superseded. Do not repeat accepted0.15.4 or0.15.3 gates
because a chat restarts. Original prior AGENTS is preserved verbatim in
`docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md`; earlier accepted contracts remain valid.
qMCPBridge stays0.12.0/workflow revision8; do not rebuild the DLL or merge0.15.5.

## Persistence and validation

Commit coherent changes; verify returned SHA,parent,tree and remote HEAD before
substantial next work. Update this file at milestones and save before long tests.
On disconnect inspect HEAD/commits/AGENTS/CI and resume actual persisted work. Never
reset, clean, force-push, delete retained branches or create retry/recovery/-2 lanes.
Preserve unexpected work. Avoid giant logs/rapid polling. Keep progress visible.

Direct container Git DNS failed; use connector writes and source artifacts. Accepted
main source artifact10944489842 SHA256
`641f9608146dbae57b0e4bec90d35973aa4d58fd4e0eda5a4d92b49837dfd796` matched archive
comment942c56e and tree`1be000e5c7e29818b1f772d7b522f01c087cd0f8`. Local mirror commit
IDs are not remote IDs. The container lacks mcp/laspy/plyfile/hatchling; distinguish
local available tests from full installed CI and actual stdio, and realGUI tests.
Before Windows handoff require full installed regression, compileall/full diff check,
native/accepted-solver comparison, exact-file/schema/stdio/replay tests, green final
CI and current AGENTS. Do not label replay realGUI or inflate source-integrity claims.
