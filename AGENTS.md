# Repository work and interruption recovery

## Active 0.15.6 lane; not Windows-ready yet

Resume `feature/live-cad-section-target-roi`; do not recreate it.
Accepted-main parent: `809c522550274316fa0a14d2e86d90a4921bfc03`.
Workflow checkpoint `f252e753ea4633594ec15d0f61f9fb17427a7479` is persisted.
Core checkpoint `7bf0fadc4c8b047f85a9dd24aededbd98e9d0f1e` passed CI36362582288.
This checkpoint exposes all four read-only MCP ROI tools and additive capabilities,
and bumps the Python package to0.15.6. Native and accepted solvers remain unchanged.
Local numerical/workflow tests:116 passed; new schema/dispatch tests:11 passed.
Installed full regression is being checked separately; do not infer completion here.

Source, whole slab (including outside geometry), index mapping, exact ROI bounds,
frame/acquisition/bookkeeping and target parameters bind the selection context.
ROI report fingerprints are NOT candidate authorization. Every selected candidate
must independently clear the inclusive one-cell truncation guard. No bounds search,
no depth crop and no solver or accepted-limit weakening.

NEXT: generated exact external fixtures A-N; transformed/large-coordinate, overlap
and actual stdio/TCP replay tests; full installed regression, compileall/diff review
and CI; draft PR and focused Windows instructions. Do not merge or request Windows
acceptance yet. Disable unrelated sandbox pytest plugin autoload during local tests
and use bounded file logging rather than a long blocking tool call. Reinstall the
local wheel after every runtime change; source PYTHONPATH tests are a separate claim.
Accepted boundary input-order index hashes can legitimately change on permutation;
ROI/candidate/layer fingerprints and geometric summaries must stay invariant.

## Accepted baseline is complete

Read README, docs/WINDOWS_0_15_5_ACCEPTED.md and accepted target diagnostics/isolation,
layer, boundary, topology and fitting contracts. Historical pending wording in old
docs is superseded by acceptance records, not a request to repeat Windows gates.
PR#19 merged at `50ff06cb383cd662ddee2a1d0e7d0445f9143719`; retained0.15.5 HEAD
`f6e2fc8a19b97da7d367abd259bed50c02a7e382`; runtime/test checkpoint
`c3dac92069bf530e41fa66a6d08794e31f0d9076`: CI890 passed, zero skips.
Windows874 plus16 MSVC tests accepted. Preserve issue#13 and0.15 through0.15.5.
Native qMCPBridge remains0.12.0/revision8. Do not rebuild the DLL for Python changes.

Fan remains legitimately BLOCKED/inconclusive: complete5605 points, baseline19
blocked targets, UV-coarser10 blocked; other probes refused at max_targets32.
No target/layer/profile selected. Do not raise budgets, pick a depth sign, discard
clutter, choose a diagnostic scale or tune an ROI to get a convenient reconstruction.
A later fan ROI must come from explicit spatial intent declared before inspecting fits.
Whole-source integrity was metadata-only; no full-cloud equality, real-host nonunit
scale or independently measured host native query count. Real transformed host used
shift[-100000000,199999000,-299999000], scale1; host quantization changed hashes and
bounds. Replay scale2.5 and exact slab/file hashes do not establish stronger GUI claims.

## Sandbox and recovery

Direct network cloning/installing is unavailable. Main's exact CI source artifact
10945467790 supplied tree77e6588ba7a5e4f306129c1be3c8f8e4dcaf0740; its main commit
was reconstituted byte-identically as a local shallow baseline. GitHub connector
writes are verified against local trees and expected parents, then remote branch HEAD.
Temporary public-wheel bootstrap succeeded at36362213680/artifact10945423819 and
its workflow was removed. Local venv uses downloaded MCP dependencies plus the
sandbox's preinstalled scientific/test packages. Noneditable wheel installs work;
editable installation lacked an editables wheel. Reinstall after source changes.
Never archive credentials, private scan data or generated fixture files in Git.

Commit small coherent changes before long tests. Verify SHA/parent/tree and remote
persistence, update this file at milestones, then continue. After a tool/stream failure
inspect actual remote HEAD, recent commits, AGENTS and CI; UI failure does not prove
GitHub work was lost. Never reset, clean, force-push, delete retained branches, or
create retry/recovery/numbered duplicates. Preserve unexpected work. Avoid giant logs
and rapid polling. Distinguish numerical tests, replay, actual MCP stdio, CI and GUI.
