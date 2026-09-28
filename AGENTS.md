# Repository work and interruption recovery

## Active lane: Python 0.15.7 pick-to-section ROI intent

Branch: `feature/live-section-roi-from-picks`, from accepted main
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Do not recreate it or merge it.
Recovery found no newer lane or open PR/issue; main CI `36366822554` succeeded.
Core/workflow checkpoint: `eba1d516dad6299f9691c37bcb7b95a19ff687ef`.

Implemented `section_spatial_intent.py` and `section_spatial_intent_workflow.py`:
explicit frame and 2..32 deliberate boundary-anchor picks, stopped pick state,
strict coordinates/source identity, no automatic frame fitting, exact half-open
projected min/max plus explicit nonnegative margin. Degenerate spans cannot be
repaired with margin. Live wrappers recheck selected point-info and bracket one
complete slab query with stopped pick-status reads. No source mutation is requested.

The wrapper recomputes intent on every call and binds the intent fingerprint into
accepted ROI context before unchanged 0.15.6 analysis/reconstruction. The binding
flows into target and layer evidence; an intent fingerprint is not authorization
for target/layer selection. Numerical 0.15.6 tools remain unchanged.

Validation so far: 49 focused numerical tests passed locally, including malformed
inputs, duplicates, source mismatches, stopped state, no hidden padding or frame
solver, no target analysis during derivation and no snapshot native I/O. These are
NOT installed full regression, actual stdio or visible GUI acceptance yet.
MCP registration, version bump, downstream/staleness/live replay, exact fixtures,
full installed regression and acceptance documentation remain to be completed.

The sandbox cannot resolve GitHub/PyPI. Accepted source was recovered from main's
successful CI artifact and verified against Git tree
`06105cff75a49ad196257c1247f9034d2f86a6bb`. The exact shallow main commit was
reconstructed locally and SHA-verified. A temporary dependency bootstrap succeeded
in run `36367435852`; its wheels were recovered, and the temporary workflow is now
removed. The regular tests workflow now includes this branch and uses noneditable
package installation. Use successful/failed source artifacts for exact recovery
when direct cloning is unavailable. Never infer lost Git work from a stream error.

## Contract and next work

Require explicit frame provenance. Live origin/normal uses the accepted canonical
section basis; snapshot frames are explicit right-handed orthonormal frames. Picks
are boundary intent, not target evidence or inferred manufacturing datums. Do not
add an ordered three-pick frame solver or a CAD model graph in this increment.

Native 0.12.0 has no scene/pick generation counter or atomic multi-call snapshot.
Do not invent those guarantees. Bind observed complete slab plus anchor geometry,
not unobserved whole-cloud geometry. Snapshot freshness is caller asserted and
fingerprints are domain-separated from live. Identical unobserved ABA changes
cannot be detected without a native epoch. No native change is currently needed.

Next: add MCP schemas/dispatch and actual stdio, live counted TCP replay, transformed
and quantization cases, changed pick/source/frame/margin tests, and downstream
0.15.6 guard/target/layer safety tests. Generate deterministic exact PLY files outside
Git and run those bytes through product code. Require complete installed regression,
compileall, diff review, unchanged native source and green exact-head CI before a
focused Windows interaction gate. Open a draft PR; do not merge or ask to merge.

## Accepted main: 0.15.6

PR #20 merged at `04a21fc32261fe7a071fd9ab46ee353afd33016c`; post-merge main
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Windows-tested feature HEAD:
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

Accepted ROI retains complete all-depth slab evidence, explicit half-open UV bounds,
inside/outside accounting and the inclusive one-cell truncation guard before the
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

For a future fan exercise verify the file hash, rediscover the source, deliberately
declare the frame, obtain human boundary-anchor picks, freeze intent, and only then
inspect reconstruction evidence. Never derive bounds from convenient diagnostic
panels, search ROI sizes, raise target/layer budgets, choose a depth sign, discard
clutter, or select whichever reconstruction looks best. A valid intent with blocked
reconstruction is useful success. Do not tune synthetic fixtures to this fan.

After acceptance, the next architecture is a CAD feature/model IR for datums,
sketches, fitted features, dimensions, dependencies, provenance and unresolved/refused
evidence. Do not bundle that graph or broad Fusion automation here.

## Recovery policy

Before resumed work inspect actual main/remote branches/recent commits/open PRs,
issues, CI and this file. Preserve unexpected work. After each coherent increment
commit, verify the returned SHA and remote persistence, update this file at milestones,
then proceed. Save before long tests. A stream timeout does not mean Git work was lost.
Never reset, clean, force-push, delete retained branches, recreate this branch, or add
retry/recovery/numbered duplicates. Keep numerical, replay, actual MCP stdio, CI and
visible GUI evidence separate; do not silently promote integrity or query counts.
