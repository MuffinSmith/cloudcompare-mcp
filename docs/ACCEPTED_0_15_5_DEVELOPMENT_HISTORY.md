# Repository work and interruption recovery

## Active 0.15.5: internally complete, UNMERGED, Windows next

Branch: `feature/live-cad-section-target-diagnostics`.
Accepted-main parent: `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
Complete runtime/test HEAD: `c3dac92069bf530e41fa66a6d08794e31f0d9076`.
CI run `36359440529`, job `108733546296`: **890 passed, zero skips, 83.57 s**.
Installed Python 0.15.5, compileall and diff checks passed. Later finalization commits
change documentation only; inspect current remote HEAD and its CI before the gate.

Local dependency-available regression: **666 passed in 40.14 s**, zero skips.
Nineteen MCP-dependent modules were excluded after import failure; the complete
installed suite and actual stdio evidence are CI results, NOT a full local run.
New coverage: **125 tests** (44 numerical, 47 workflow/replay, 9 MCP schema/dispatch/
actual stdio, 25 exact-file/handoff). Twenty fresh hashed PLY files were exercised
through product projection, snapshot and replay. No real 0.15.5 GUI validation yet.

NEXT: focused Windows acceptance using the final supplied SHA and
`docs/WINDOWS_SECTION_TARGET_DIAGNOSTIC_ACCEPTANCE.md`. Read
`docs/LIVE_CAD_SECTION_TARGET_DIAGNOSTICS.md` for the contract and limitations.
Testing/reporting only, not more implementation. Do NOT merge 0.15.5, enable
auto-merge, or request merge authorization merely because development tests pass.
Do not repeat accepted 0.15.4 or 0.15.3 acceptance because a chat restarted.

## Implementation and boundaries

Tools: `diagnose_section_target_stability`, `diagnose_live_section_target_stability`.
Capabilities: `python_section_layers.section_targets.scale_diagnostics` version0.15.5.
Fixed panels: baseline, UV*0.75, UV*1.25, depth*0.75, depth*1.25. Same source records,
accepted target solver, support thresholds, budgets and origin probes. No adaptive
search, recommendation, selection token, target choice, profile or scene mutation.
One complete live acquisition at most. Baseline must complete (blocked is allowed);
refused probe yields inconclusive with every record explicitly unclassified there.

Exact source-record intersections detect splits/merges even at equal target counts.
Reasons compare only identical one-to-one memberships. Other records are explicitly
uncompared for reasons. Eight spatial candidate and sixteen relation previews retain
all omitted counts/point totals. No largest-match or preferred-result shortcut.
No-change is sampled evidence, NOT physical topology, universal stability, source
integrity or manufacturing intent. A diagnostic fingerprint cannot authorize accepted
selection. Native global coordinates are never shifted/scaled twice.

Accepted solvers, acquisition workflows and server.py are unchanged; only the target
tool registry delegates the additions. Python0.15.5; qMCPBridge unchanged0.12.0 /
workflow revision8. No DLL rebuild. Parent target/layer/profile capability versions
remain0.15.4/0.15.3/0.15.2. New runtime lives in the three section_target_diagnostic*
modules; generator and four new test modules are separate.

Twenty generated files include fourteen accepted-case shapes plus split/merge,
cell/target-budget refusal and rotated/large-translated split/merge cases. The new
shuffle has its own hashes. Snapshot/live normalization can change exact projected
hashes: the transformed audit found identical discrete evidence and at most1.11e-16
bounds difference against about5.33e-7 source precision. Never require cross-context
hash equality or retune parameters to hide host quantization effects.

## Accepted 0.15.4 history

PR18 merged at `045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03` after user authorization.
Retained feature/live-cad-section-target-isolation tested HEAD:
`4b5dfe7026f8166c0102d763a9b60e9048686996`. Tested CI36356915539 passed;
post-merge main942c56e CI36358516660 passed. User Windows report:749 passes plus16
MSVC policy passes; target139; all14 exact PLY/actualstdio/visibleGUI and safety/
handoff gates PASS. No defect. See docs/WINDOWS_0_15_4_ACCEPTED.md. Full detailed
report was mentioned but not attached in this continuation; no invented evidence.

Fan: complete5605 points,19 candidates, allblocked/allaccounted, no target/profile.
This remains legitimate BLOCKED, not a defect. The new fan gate is one diagnostic,
not permission to raise limits, choose a depth sign, drop clutter or try better fits.
Integrity stays metadata-only; no full-cloud equality or real-host nonunit-scale test.
Actual shift[-100000000,199999000,-299999000],scale1; no double application. Host
quantization removed one bridge flag but erosion still refused. Old pending wording
in retained procedures/history is superseded by this checkpoint and acceptance record.
Original pre-acceptance AGENTS is docs/ACCEPTED_0_15_4_DEVELOPMENT_HISTORY.md.
The intermediate SECTION_TARGET_DIAGNOSTICS_PROGRESS.md is historical, not new TODOs.

## Persistence and exact-source verification

Verified remote increments: initial7f29148d71a4e94fc0d902648227325aa5abb8d7;
core47c84d4fab4143733da5f01530230ccd6e185878;
workflow40746c1ae8aa8bf6aeb9c45cc81a01285e251a50;
MCP1e60917d2b32e272a178990cf21cfc11203ba789; files/runtime c3dac920 above.

Git DNS failed in the container; connector writes and CI source artifacts were used.
Runtime artifact10945730616 ZIP SHA256:
`b5dd7debd172a617ca4807f6030a12d38dba2763d2431ae3a674bf803a3eab9d`.
Archive commit matched c3dac920 and all runtime/test bytes matched local work.
Reconstructed tree: `7946dcfb421e9187901aa44fa6c9d8161d597004`.
Accepted-main tree: `1be000e5c7e29818b1f772d7b522f01c087cd0f8`.
Local mirror commit IDs are NOT remote IDs. Native diff and full accepted-main range
whitespace check passed. Generated files/logs remain outside Git. A local test-call
transport timeout did not lose work: recovered exit0/log666 passes without rerunning.

Commit coherent work, verify returned SHA/parent/tree and remote HEAD before the next
substantial change. Keep this file current and save before long tests. On a failed
stream inspect HEAD/commits/AGENTS/CI; do not infer lost writes. Never reset, clean,
force-push, delete retained branches or create retry/recovery/-2 lanes. Preserve
unexpected work. Avoid giant logs/rapid polling; keep progress visible. Distinguish
numerical, replay, installed CI/stdio and real GUI. No integrity-coverage inflation.
