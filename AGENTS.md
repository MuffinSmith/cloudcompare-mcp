# Repository work and interruption recovery

## Active lane: Python 0.15.7 pick-to-section ROI intent

Branch: `feature/live-section-roi-from-picks`, created from accepted main
`2b385820ecfcb84d79aaf59ad5965e748f961466`. No newer lane, open PR or open issue
existed at recovery. Main CI `36366822554` succeeded. Do not recreate this branch.
Do not merge this increment without a later explicit user instruction.

Initial recovery checkpoint: source recovered from the successful main CI artifact;
its complete Git tree verified as `06105cff75a49ad196257c1247f9034d2f86a6bb`.
The local sandbox cannot resolve GitHub or PyPI. A temporary branch-only workflow
exports public Python dependency wheels for offline installed regression. Remove
that bootstrap workflow after recovering the dependencies. No product code has
changed at this checkpoint. Continue with the design below, then tests and docs.

First contract: explicit caller-declared origin/normal/frame provenance using the
accepted deterministic section projection basis; deliberate boundary-anchor picks,
not target samples or an inferred manufacturing frame. No ordered frame solver.
Bounds are exact projected min/max plus explicit nonnegative margin, all depths
retained. No padding search, automatic ROI discovery or quality-driven adjustment.

Use an additive wrapper around accepted `analyze_roi_input`/`reconstruct_roi`.
Recompute current pick/source/frame intent before downstream analysis; bind its
fingerprint into ROI context so target and layer fingerprints inherit it. An intent
fingerprint is never target/layer selection permission. Keep old 0.15.6 tools and
numerical solvers unchanged. Derivation must not run target analysis.

Live scope: require stopped captured standalone-cloud picks, one source ID, and
explicit pick indexes. Revalidate selected source points through existing point-info
calls and acquire one complete slab. Bracket acquisition with pick-status checks.
Native 0.12.0 has no scene/picking generation counter or atomic multi-call snapshot;
do not invent those guarantees. Bind observed complete slab plus anchor geometry,
not unobserved whole-cloud geometry. Source mutation is never requested.
Snapshot evidence is caller asserted and domain-separated from live evidence.

Required remaining work: numerical/core and provenance tests; live replay/accounting;
MCP schemas/dispatch and actual stdio; exact generated files outside Git; arbitrary
rotation/large coordinates/quantization; downstream guard/target/layer safety; full
installed regression, compileall, diff review and exact-head green CI. Then provide
a focused Windows interaction acceptance prompt. No visible GUI tests have run here.

## Accepted main: 0.15.6

PR #20 merged at `04a21fc32261fe7a071fd9ab46ee353afd33016c`; post-merge main
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Accepted Windows-tested feature HEAD:
`3a1d49550e3e1a90d4915fb197ad51688a3e836d`; runtime/test checkpoint:
`5d618c0de30c90a4573d4c8be52174a3aed58eee`; final pre-merge documentation HEAD:
`f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`; pre-0.15.6 accepted main:
`809c522550274316fa0a14d2e86d90a4921bfc03`.

Read `docs/WINDOWS_0_15_6_ACCEPTED.md` and `docs/LIVE_CAD_SECTION_TARGET_ROI.md`.
Acceptance is complete; do not repeat it merely because a chat restarted. Python
0.15.6 had 1054 ordinary installed passes plus all 16 MSVC-gated tests: effective
1070. All 28 installed modules matched checkout, 22 PLY hashes verified, seven
focused modules 180/180, actual stdio and counted TCP replay passed, and 20 visible
CloudCompare fixtures passed. Native qMCPBridge is unchanged 0.12.0 / revision 8.
Do not rebuild it unless a demonstrated capability gap requires native work.

Accepted ROI uses complete all-depth slab evidence, explicit half-open UV bounds,
inside/outside accounting and an inclusive one-cell truncation guard. It precedes
unchanged accepted target/layer/boundary/topology/profile solvers. Multiple targets
require explicit choice; changed target-selection mode requires fresh layer evidence.
Explicit IDs cannot override unsafe target/layer evidence or a touched ROI guard.

Retained limits: no real-host nonunit scale test, independent real-host native query
count or whole-cloud geometry/attribute equality. Host quantization can change exact
cross-context hashes. Observed transformed host shift was
[-100000000,199999000,-299999000], scale 1; maximum file/host global-bound difference
about 2.73e-5. The 37 preexisting roots and empty selection were restored.

## Fan and future architecture

Authorized fan/working-copy SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
The source was rediscovered as 406276 points. No 0.15.6 fan ROI call was made:
no defensible picked spatial intent and section frame were declared in advance.
The retained 0.15.5 fan diagnostic remains BLOCKED/inconclusive.

For a future fan exercise, verify the file hash, rediscover the source, deliberately
declare the frame, obtain human boundary-anchor picks, freeze intent, and only then
inspect reconstruction evidence. Never derive bounds from convenient diagnostic
panels, search ROI sizes, raise target/layer budgets, choose a depth sign, discard
clutter, or select whichever reconstruction looks best. A valid intent with blocked
reconstruction is useful success. Do not tune synthetic fixtures to this fan.

After acceptance of this bridge, the next architecture is a CAD feature/model IR
for datums, sketches, fitted features, dimensions, dependencies, provenance and
unresolved/refused evidence. Do not bundle that graph or broad Fusion automation here.

## Recovery policy

Before any resumed work inspect actual main/remote branches/recent commits/open
PRs/issues/CI and this file. Preserve unexpected work. After each coherent increment
commit, verify the returned SHA and remote branch persistence, update this file at
milestones, then proceed. Save before long tests. A stream timeout does not mean Git
work was lost. Never reset, clean, force-push, delete retained branches, recreate this
branch, or add retry/recovery/numbered duplicate branches after a disconnect.

Keep numerical, mocked-native/replay, actual MCP stdio, CI and visible GUI evidence
separate. Do not silently promote source-integrity or query-count claims.
