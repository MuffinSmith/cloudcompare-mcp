# Repository work and interruption recovery

## Python 0.15.7: first Windows interaction partially passed; capture continuation pending

Branch: `feature/live-section-roi-from-picks`. Draft PR: **#21, do not merge**.
Accepted-main parent: `2b385820ecfcb84d79aaf59ad5965e748f961466`.
Previously tested Windows HEAD: `8438ba311c6d31de5a775d3ec3f17a5bca214ce6`;
its exact-head CI **36370032133 succeeded**. The first Windows gate is preserved in
`docs/WINDOWS_0_15_7_PARTIAL_ACCEPTANCE.md`: internal checks passed and the real
human two-anchor `safe` interaction passed, but the gate remained BLOCKED when
repeated events on one `three_anchors` vertex exhausted `max_picks=3`. No fan ROI
call occurred. Do not rewrite the unrun GUI cases as passes.

The continuation procedure in `docs/WINDOWS_SECTION_SPATIAL_INTENT_ACCEPTANCE.md`
now overprovisions a fixed native event budget and explicitly selects distinct
predeclared source-point indexes. Extra duplicate click records remain bound in raw
pick-state provenance. A capture can be retried before any ROI/reconstruction-quality
inspection while its declared source/frame/anchor IDs/parameters/margin stay fixed.
This is acquisition recovery, not ROI tuning, and requires **no qMCPBridge change**.

One additional regression test proves an unselected duplicate event cannot consume
a logical anchor while still affecting the frozen session fingerprint. Previous
runtime checkpoint `604cc5d21c38a138aea0dff367cd2af888565830` passed 1210 tests;
the new expected total is 1211 / focused 141, but do not claim those new totals until
the new exact HEAD has green CI. Resolve actual branch HEAD before resuming. Do not
repeat completed 0.15.6 Windows acceptance, start the CAD-model IR, or merge merely
because CI is green.

## Exact internal evidence

At the runtime checkpoint, a noneditable installed Python 3.13.5 package passed
**1210 tests, zero skips**, including all accepted regressions and 140 new tests.
All **31 installed Python modules** matched checkout bytes. Compileall and working /
accepted-main diff checks passed. Native source and the accepted ROI, target, layer,
boundary, topology and profile solvers have no changes. The old ROI stdio test changes
only the root package-version assertion to 0.15.7, not its nested ROI expectations.

New focused modules and counts:
- `test_section_spatial_intent.py`: 49 numerical / malformed-input tests.
- `test_section_spatial_intent_workflow.py`: 36 freshness / downstream / mocked-native tests.
- `test_section_spatial_intent_fixtures.py`: 39 exact-file / transformed / quantization-proxy tests.
- `test_section_spatial_intent_tools.py`: 10 actual schema / dispatch / installed-stdio tests.
- `test_section_spatial_intent_context.py`: 6 transport / source-context tests.

The installed-stdio tests run real MCP subprocesses: snapshots with an unavailable
bridge, and live calls against a counted read-only TCP replay. Neither is visible
GUI validation. The deterministic generator writes **18 hashed PLY fixtures outside
Git**, including actual source anchor vertices. Exact bytes are exercised through
product projection and workflows. A float32-local host proxy is not real-host
nonunit-scale or quantization acceptance. Requested call counts are not independent
host execution instrumentation.

## Implemented contract

Six additive tools, with exact names in `section_spatial_intent_tools.KINDS`:
`derive_section_roi_from_picks`, `derive_live_section_roi_from_picks`,
`analyze_picked_section_target_roi`, `analyze_live_picked_section_target_roi`,
`reconstruct_picked_section_target_roi_profile`, and
`reconstruct_live_picked_section_target_roi_profile`.

Require an explicit declared frame/provenance, 2..32 distinct captured boundary
anchors, and explicit finite nonnegative native-unit margin. Live origin/normal uses
the existing canonical section basis, not an inferred datum X/Y rotation. Snapshot
requires an explicit right-handed orthonormal frame and source bookkeeping. Raw U/V
spans must clear numerical precision before margin; padding cannot repair degeneracy.
Bounds are exact half-open projected min/max plus margin. Anchor depths are reported,
never used to select a depth sign or crop the already-declared complete slab.

Live derivation and downstream calls require stopped picks, reread each selected
source point, acquire ONE complete slab, and bracket with pick-status reads plus
configured host/port checks. A valid N-anchor call requests N+3 read-only native
calls. Credentials are not included in provenance. No source mutation is requested.
Derivation runs no target analysis. Every downstream call recomputes intent and
rejects stale expected intent before the unchanged ROI solver. Intent binding flows
through ROI context into target and layer evidence, not merely four detached bounds.
Intent/report/foreign candidate tokens cannot bypass selection or truncation guards.

No automatic ROI/padding/scale search, manufacturing-frame-from-picks solver,
quality-driven repositioning, preview helper, CAD-model graph or Fusion backend was
added. Old numerical 0.15.6 tools remain valid but do not claim picked provenance.
Multiple targets require explicit choice; layers require fresh matching selection
context; unsafe targets, touched guards and unsupported layers remain refused.

## Honest freshness boundaries

Freshness binds observed complete slab, selected anchors, captured pick state,
source/index mapping, frame/provenance, margin, parameters and configured endpoint.
It does not prove unobserved whole-cloud geometry/attribute equality. Native
qMCPBridge **0.12.0 / workflow revision 8 remains unchanged**; it has no scene/picking
epoch or atomic multi-call snapshot. Keep the host quiescent. Unobserved identical
change-and-change-back events or same-endpoint process replacement may be
indistinguishable. Endpoint identity is not authenticated host/process identity.
Snapshot and frame provenance are caller asserted and separated from live context.
Do not silently promote these guarantees or rebuild the DLL without a proven need.

## Accepted 0.15.6 and retained fan state

Read `docs/WINDOWS_0_15_6_ACCEPTED.md` and `docs/LIVE_CAD_SECTION_TARGET_ROI.md`.
PR #20 merge: `04a21fc32261fe7a071fd9ab46ee353afd33016c`.
Windows feature HEAD: `3a1d49550e3e1a90d4915fb197ad51688a3e836d`.
Runtime checkpoint: `5d618c0de30c90a4573d4c8be52174a3aed58eee`.
Final pre-merge documentation: `f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`.
Pre-0.15.6 main: `809c522550274316fa0a14d2e86d90a4921bfc03`.
Accepted Windows results: 1054 ordinary + 16 MSVC = 1070; 28 module hashes,
22 PLY hashes, 180 focused tests and 20 visible fixtures passed. All-depth accounting,
ROI guards, explicit multiple-target choice and matching layer evidence were retained.
37 preexisting scene roots and empty selection were restored. Host was CloudCompare
2.13.2 / PID 14312 / port 8765; rediscover current identity rather than reusing it.

Retain the absence of real-host nonunit-scale, independent host native-query-count,
or whole-cloud geometry/attribute equality proof. Accepted transformed host shift
was [-100000000,199999000,-299999000], scale 1; maximum observed file/host global-bound
difference about 2.73e-5. Host quantization can legitimately alter exact hashes.

Authorized fan / working-copy SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
Retained rediscovered source: 406276 points. No 0.15.6 fan ROI call occurred because
no defensible spatial intent/frame was declared beforehand. The 0.15.5 fan diagnostic
remains BLOCKED/inconclusive. Do not rewrite it as a pass.

Next Windows gate must test real human interaction: verify file hash, rediscover
source, deliberately declare frame and fixed parameters, capture actual human
boundary anchors, freeze picks/frame/bounds, THEN inspect ROI/reconstruction quality.
Do not derive convenient rectangles from diagnostics, search sizes/padding, increase
budgets, choose depth signs, remove clutter or choose the best reconstruction.
A trustworthy intent with blocked reconstruction is a useful interaction success,
not a reconstructed-fan success. Preserve preexisting picking sessions and scene work.
After this bridge is accepted, the next milestone is a CAD feature/model IR.

## Recovery discipline and environment notes

Before resumed work inspect actual main/branches/recent commits/open PRs/issues/CI
and this file. Preserve unexpected work. Commit coherent increments, verify returned
SHA AND actual remote ref, update this file at milestones, then continue. Save before
long tests. Never reset, clean, force-push, delete retained branches, recreate this
lane or invent retry/recovery/numbered lanes. Stream failure does not imply lost Git.
Keep numerical, mocked-native/TCP replay, installed MCP stdio, CI and GUI claims separate.

Sandbox DNS could not resolve GitHub/PyPI. Accepted source and a successful runtime
source archive were recovered through GitHub Actions artifacts and Git tree hashes
verified. Temporary public-wheel bootstrap CI 36367435852 succeeded; that workflow
was removed. The regular tests workflow includes this branch and uses noneditable
installation. Local project installation reused some preinstalled third-party packages;
do not call it pristine dependency isolation. Exact local shallow commits/trees were
SHA-verified without reset/clean. For another sandbox recovery, use persisted source
artifacts rather than assuming the remote work was lost.
