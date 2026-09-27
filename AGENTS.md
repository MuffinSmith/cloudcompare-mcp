# Repository work and interruption recovery

## Accepted 0.15.4; next lane is separate

PR #18 merged after explicit user authorization at
`045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03`.
Exact Windows-tested and retained feature HEAD:
`4b5dfe7026f8166c0102d763a9b60e9048686996` on
`feature/live-cad-section-target-isolation`.
Pre-merge main: `0201cdd46381e0c79c05b33ee9de48851a18b877`.
Tested-head CI `36356915539` independently rechecked: success.
Python 0.15.4; qMCPBridge unchanged 0.12.0 / workflow revision 8. No DLL rebuild.

Read `docs/WINDOWS_0_15_4_ACCEPTED.md`. The user reported PASS for all 14 exact
fixtures, actual MCP stdio, visible GUI and safety/handoff gates. Windows749 passed
plus16 MSVC policy tests passed; target modules139 passed. No reproducible defect.
The complete5605-point fan slab returned19 candidates, all blocked and all points
accounted for; no target selected or profile attempted. BLOCKED is legitimate.
Integrity remains metadata-only; no independent full-cloud geometry/attributes or
real-host nonunit-scale test. Actual shift[-100000000,199999000,-299999000], scale1;
no double application. Quantization removed one bridge flag but erosion still refused.

0.15.4 acceptance is COMPLETE: do not repeat it because a chat restarts. Historical
pending/do-not-merge wording in the retained procedure/development documents is
superseded by this checkpoint and the acceptance record. Original prior AGENTS is
preserved verbatim in `docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md`; earlier accepted
histories and profile/layer/target contracts remain relevant.

## Next deliberate increment: bounded target-scale diagnostics

First inspect remote branches, HEAD, recent commits, PRs/issues and CI. Resume a
legitimate existing next-stage lane rather than creating another. Otherwise create
exactly `feature/live-cad-section-target-diagnostics` from current accepted main.
Suggested Python version0.15.5. Do NOT modify the accepted0.15.4 branch.

Implement a small Python-only diagnostic around caller-declared target cell sizes.
Use one complete slab acquisition and the unchanged accepted target solver at a
bounded predeclared set of scales. Report partition/support/refusal changes and
point accounting. Never rank/recommend a scale, optimize until a profile works,
return diagnostic tokens as selection authorization, or reconstruct from probes.
A diagnostic agreement is not proof of physical topology or manufacturing intent.
Keep native bridge, accepted solver limits and accepted reconstruction behavior
unchanged. The real fan is design evidence, not a requirement to fit.

Separate pure numerical comparison, workflow/acquisition and MCP schema/stdio tests.
Cover exact generated files, permutation, arbitrary orientation/large translation,
scale-sensitive splits/merges, sparse/bridge/overlap refusal, budgets, malformed and
nonfinite inputs, no source mutation, compact output and complete live acquisition.
Do not call replay real GUI validation. Do not merge0.15.5 without later acceptance.

## Stream-disconnect policy

Commit coherent increments; verify returned SHAs, parents/trees and remote branch
persistence before substantial next work. Update this file at each milestone; save
before long tests. A failed stream does not imply lost GitHub writes. Read actual
remote HEAD/commits/AGENTS/CI and continue. Never reset, clean, force-push, delete
retained branches or create retry/recovery/-2 branches. Preserve unexpected work.
Avoid giant CI-log dumps and rapid polling loops. Keep progress updates visible.

Direct container Git DNS failed in this session. Source came from tested-head CI
artifact10943579845, SHA256
`4200724cd16465dd9820364c681b7593e37940d6e9f2ff576225729f921f343a`.
Reconstructed local Git tree matched remote
`26869e9438224265c49c09ad0fcefc2c15d5fb2b`. Local mirror commit IDs are not remote IDs.
No full local or real-GUI rerun is implied by that source verification.
