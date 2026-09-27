# Repository work and interruption recovery

## Active UNMERGED 0.15.5: target-scale diagnostics

Branch: `feature/live-cad-section-target-diagnostics`.
Accepted-main parent: `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
This is the deliberate next lane, NOT a retry of accepted0.15.4. Initial checkpoint
only: numerical core, workflow, MCP tools and tests are still to be implemented.
Python version is reserved as0.15.5 and push CI is enabled for this branch.
Do not merge this lane without later focused acceptance.

Fixed diagnostic schedule: baseline, UV*0.75, UV*1.25, depth*0.75, depth*1.25.
Use one complete acquisition and the unchanged accepted0.15.4 target solver.
All support/point/cell/target budgets and origin-perturbation fractions stay fixed.
No adaptive scales, best-scale ranking, seed growth, target selection or profile
reconstruction. Baseline analysis must complete (it may be fully blocked); a refused
probe makes the diagnostic inconclusive and is never silently skipped or retried.
Partition correspondence must use exact source-record intersections, not nearest
bounds, a dominant match or candidate-count coincidence. All points are accounted
for including refused panels and omitted summary-preview candidates. Diagnostic
identifiers/fingerprints must not be usable as target-selection authorization.
Agreement only describes sampled partitions and blocking-reason sets, not physical
topology, source integrity, manufacturing intent or universal stability.

Keep numerical comparison independent from MCP plumbing. Reuse accepted snapshot
and live acquisition without changing accepted solvers/reconstruction. Preserve
source/frame/acquisition/shift-scale provenance. Compact deterministic previews
must expose omitted counts; raw geometry and membership arrays remain server-side.
Tests must cover scale-sensitive splits/merges/refusal changes, sparse/overlap/bridge
support, budgets, malformed/nonfinite input, permutation, arbitrary orientation and
large translation, no mutation, exact generated files, live replay, schema and
actual stdio. All five panels must be predeclared; no fan-driven parameter search.

## Accepted history, not an outstanding gate

PR18 merged0.15.4 at `045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03`.
Retained tested branch `feature/live-cad-section-target-isolation` HEAD
`4b5dfe7026f8166c0102d763a9b60e9048686996`. CI36356915539 passed.
Read `docs/WINDOWS_0_15_4_ACCEPTED.md`: Windows749+16 MSVC passes, target139,
all14 exact PLY/stdin-stdout/visibleGUI and safety/handoff gates PASS. No defect.
Complete5605-point fan slab:19 candidates, all blocked, all points accounted, no
selection or profile. Metadata-only integrity; no independent full-cloud equality
or real-host nonunit-scale test. Actual shift[-100000000,199999000,-299999000],scale1,
no double application; quantization removed one bridge flag but erosion still blocked.
Earlier pending wording is superseded. Do not repeat accepted0.15.4 or0.15.3 gates
because a chat restarts. Original prior AGENTS is preserved verbatim in
`docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md`; earlier accepted contracts remain valid.
qMCPBridge stays0.12.0/workflow revision8; do not rebuild the DLL.

## Persistence

Commit coherent changes and verify returned SHAs, parents/trees and remote HEAD.
Update this file at milestones; save before long tests. On disconnect inspect branch
HEAD, commits, AGENTS and CI and resume actual persisted work. Never reset, clean,
force-push, delete retained branches or recreate retry/recovery/-2 lanes. Preserve
unexpected work. Avoid giant logs and rapid polling. Keep progress updates visible.

Direct container Git DNS failed. The accepted runtime source was retrieved from CI
artifact10943579845 with verified SHA256
`4200724cd16465dd9820364c681b7593e37940d6e9f2ff576225729f921f343a`, matching tree
`26869e9438224265c49c09ad0fcefc2c15d5fb2b`. Local mirror commits are not remote IDs.
The container lacks mcp/laspy/plyfile/hatchling; distinguish dependency-available local
tests from the complete installed CI suite and actual stdio, and from realGUI tests.
Before Windows handoff require full installed regression, compileall, full diff
check, native/accepted-solver comparison, exact-file/schema/stdio/replay coverage,
green final-head CI and a current checkpoint. Never label replay realGUI validation.
