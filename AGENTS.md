# Repository work and interruption recovery

## 0.15.6 explicit ROI increment: internally green, Windows pending

Resume `feature/live-cad-section-target-roi`; do not recreate it.
Draft PR #20 is open and unmerged. Do not merge or enable auto-merge.
Accepted-main parent: `809c522550274316fa0a14d2e86d90a4921bfc03`.
Runtime/test checkpoint: `5d618c0de30c90a4573d4c8be52174a3aed58eee`.
This documentation checkpoint changes no runtime, tests, fixtures or native source.
Read actual remote HEAD/PR and its CI on recovery; do not infer final status from
an older run. Keep the accepted branches and every deliberate ROI checkpoint.

Verified at the runtime/test checkpoint:
- GitHub Actions run 36363760167 / job 108745962764: 1070 passed, zero skips,
  Python 3.12.14, 100.59 seconds. compileall and diff checks also passed.
- Installed noneditable sandbox Python 3.13.5 package: 1070 passed, zero skips,
  212.55 seconds. Every installed runtime module matched checkout bytes. No tests
  excluded; unrelated sandbox pytest plugin autoload was disabled.
- 180 added tests: acquisition 5; numerical ROI 62; workflow 49; schema/dispatch 11;
  exact-file fixtures 46; actual installed MCP stdio 2; extra safety 5.
- 22 exact generated PLY files exercised through product code, outside Git.
- Full accepted-main diff reviewed. qMCPBridge and all accepted numerical solvers
  unchanged; only acquisition/workflow composition and additive MCP references vary.

The next gate is documented in `docs/WINDOWS_SECTION_TARGET_ROI_ACCEPTANCE.md`.
Read the numerical contract in `docs/LIVE_CAD_SECTION_TARGET_ROI.md` and README.
No real CloudCompare GUI validation of 0.15.6 has occurred in this sandbox. Actual
stdio and counted TCP native replay are separate coverage, not GUI acceptance.
Do not repeat the already completed 0.15.5 Windows gate or request a DLL rebuild.

## Implemented contract and non-negotiable refusals

Four read-only snapshot/live ROI analysis/reconstruction tools use complete slab
acquisition, explicit half-open UV bounds, all-depth inside/outside accounting and
an inclusive one-declared-UV-cell edge guard BEFORE unchanged accepted target,
layer, occupancy, topology and fitting. No ROI discovery/search or scale tuning.

Source, whole slab (including outside geometry), source-index mapping, exact ROI,
frame/acquisition/bookkeeping and target parameters bind selection. ROI/diagnostic
report fingerprints are NOT candidate authorization. Every selected candidate must
clear the edge guard; explicit IDs cannot override truncation or unsafe target/layer
states. Multiple targets still require explicit choice, even if only one clears the
guard. Outside support is projected evidence, not proof of physical connection.

Layer evidence must match target-selection mode: switching automatic to explicit
selection requires a fresh layer fingerprint. Accepted boundary input-order index
hashes can legitimately differ on permutation; ROI/candidate/layer fingerprints and
geometric summaries remain invariant when geometry, mapping and context are equal.
Host quantization may change exact geometry hashes. Do not manufacture equality.

## Accepted baseline and retained fan limitations

Read `docs/WINDOWS_0_15_5_ACCEPTED.md` and accepted diagnostics/target/layer/boundary/
topology/profile contracts. Historical pending wording in older feature docs is
superseded by acceptance records, not a request to repeat completed host gates.
PR #19 merged at `50ff06cb383cd662ddee2a1d0e7d0445f9143719`; retained 0.15.5 HEAD
`f6e2fc8a19b97da7d367abd259bed50c02a7e382`; runtime/test checkpoint
`c3dac92069bf530e41fa66a6d08794e31f0d9076`: CI 890 passed, zero skips.
Windows 874 plus 16 MSVC policy tests accepted. Preserve issue #13 and 0.15–0.15.5.
Native qMCPBridge remains 0.12.0 / revision 8. Python work does not justify a DLL build.

Fan remains legitimately BLOCKED/inconclusive: complete 5605 points, baseline 19
blocked targets, UV-coarser 10 blocked; other probes refused at max_targets=32.
No target/layer/profile selected. Do not raise budgets, pick a depth sign, discard
clutter, choose a diagnostic scale or tune ROI sizes to obtain a convenient outline.
A later fan ROI requires explicit spatial intent declared before inspecting fits.
Whole-source integrity was metadata-only; no full-cloud geometry/attribute equality,
real-host nonunit scale or independently measured host native query count. The real
transformed host used shift [-100000000,199999000,-299999000], scale 1; quantization
changed hashes/bounds. Replay scale 2.5 and slab/file hashes do not strengthen this.

## Sandbox and interruption recovery

Direct container GitHub/PyPI networking was unavailable. Main's exact CI source
artifact 10945467790 supplied tree 77e6588ba7a5e4f306129c1be3c8f8e4dcaf0740; its
main commit was reconstituted byte-identically as a local shallow baseline. GitHub
connector writes were checked against local trees, expected parents and remote HEAD.
Temporary public-wheel bootstrap succeeded at run 36362213680/artifact 10945423819;
its workflow was removed. No credentials or private scan data were archived.

Local venv uses downloaded MCP dependencies and preinstalled scientific/test packages.
Noneditable wheel installs work; editable installation lacked an editables wheel.
Reinstall after runtime changes. Earlier long blocking test attempts were incomplete;
the final bounded installed run completed with the results recorded above.

Commit coherent small changes before long tests. Verify SHA/parent/tree and remote
persistence, update this file at milestones, then continue. After tool/stream failure,
inspect actual HEAD, recent commits, AGENTS and CI: UI failure does not prove work
was lost. Never reset, clean, force-push, delete retained branches, or create retry,
recovery or numbered duplicate branches. Preserve unexpected work. Avoid giant logs
and rapid polling. Keep numerical, replay, actual stdio, CI and GUI claims separate.
