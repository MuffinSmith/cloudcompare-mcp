# Repository work and interruption recovery

## Active lane: Python 0.15.7 picked section ROI intent

Branch `feature/live-section-roi-from-picks`, draft PR #21, accepted-main parent
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Do not recreate this lane or merge it.
No newer lane or open PR/issue existed at initial recovery. Accepted main CI
`36366822554` succeeded. No accepted-main or native modifications have been made.

Runtime/test checkpoint `8b8e37f65d84b419004b95d4cf60ac6a691fc6ff` passed complete
installed Linux regression: **1204 passed, zero skips**, Python3.13.5; all31 installed
modules matched checkout bytes. Exact-head push CI `36368858950` succeeded. Its
source artifact was recovered and the complete Git tree verified as
`1ad3d032ea4e8af4bd41c121e015807093778835`. Accepted native and numerical solver diffs
are empty. This is not Windows/visible CloudCompare acceptance.

**Current increment after that checkpoint:** bind configured bridge host/port into
live intent, and refuse endpoint changes during acquisition. Secrets are not echoed
or hashed into provenance. This closes identical-data/different-endpoint ambiguity;
it does NOT supply a native process/scene epoch. Six new context tests were added;
130 focused numerical/workflow/exact-file/context tests pass after this change.
The prior 10 MCP/schema/installed-stdio tests passed before this endpoint addition.
Next run complete installed regression again (expected total1210), verify exact-head
CI and source bytes, then finish documentation/Windows handoff. Do not label the
post-endpoint full regression complete until it has actually run.

## Contract and evidence

Six tools in `section_spatial_intent_tools.KINDS` separate snapshot/live derivation,
analysis and reconstruction. Full names are authoritative in that map. Package0.15.7;
accepted ROI remains0.15.6, target0.15.4, layer0.15.3, profile0.15.2. No solver forks.
Explicit declared frame, 2..32 distinct captured boundary anchors, explicit finite
nonnegative margin. No frame-from-picks solver, automatic ROI search, hidden padding,
quality-driven adjustment, manufacturing acceptance, preview or CAD model graph.
Live origin/normal uses accepted canonical section basis; snapshot requires explicit
right-handed orthonormal basis. Raw U/V spans must be positive above numerical
precision before margin. All anchor depths are reported, never used to crop ROI.

Live: stopped picks; N current anchor point-info reads; ONE complete slab query;
pick-status reads before/after, and configured-endpoint bookends. A valid N-anchor
call requests N+3 read-only native calls. No source mutation is requested. Derivation
runs no target analysis. Every downstream call recomputes intent, rejects stale
expected intent, and adds its fingerprint to accepted ROI context so target/layer
fingerprints inherit it. Intent/report/foreign tokens cannot bypass selection or
ROI truncation guards. Multiple targets and unsafe layers remain explicit/refused.

Freshness covers observed complete slab and selected anchors, not whole-cloud
geometry/attributes. Native has no picking/scene epoch or atomic multi-call snapshot;
identical unobserved ABA changes remain undetectable. Keep the host quiescent during
calls. Configured endpoint is not authenticated host/process identity. Snapshot/frame
provenance is caller asserted. Snapshot/live contexts are fingerprint-separated.
Keep numerical, mocked-native/TCP replay, installed MCP stdio, CI and real GUI claims
separate. Never promote proxy quantization or requested query counts to host proof.

Eighteen deterministic exact PLY fixtures (including actual source anchor vertices)
are generated OUTSIDE Git by `scripts/make_section_spatial_intent_fixtures.py`.
Four focused modules originally supplied134 tests; context module adds6. Read the
actual tests for exact-file/replay/stdio scope. The accepted0.15.6 stdio test changes
only its root installed-package version assertion; its ROI expectations remain intact.

## Accepted 0.15.6 and fan boundaries

Read `docs/WINDOWS_0_15_6_ACCEPTED.md` and `docs/LIVE_CAD_SECTION_TARGET_ROI.md`.
PR20 merge `04a21fc32261fe7a071fd9ab46ee353afd33016c`; accepted-main checkpoint above.
Windows feature `3a1d49550e3e1a90d4915fb197ad51688a3e836d`; runtime
`5d618c0de30c90a4573d4c8be52174a3aed58eee`; final pre-merge docs
`f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`; pre-0.15.6main
`809c522550274316fa0a14d2e86d90a4921bfc03`. Accepted1054+16MSVC=1070;
28 module hashes,22 PLY hashes,180 focused tests,20 visible fixtures passed.
qMCPBridge **unchanged0.12.0/revision8**. Do not rebuild or repeat that Windows gate.
Retain no real-host nonunit scale, independent host query count or whole-cloud equality
proof; host quantization can alter hashes. See accepted report for exact host evidence.

Authorized fan SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
Rediscovered406276-point source. No0.15.6 fan ROI call occurred; no prior deliberate
frame/intent. Retained0.15.5 fan diagnostic remains BLOCKED. Future gate: verify hash,
rediscover source, deliberately declare frame, obtain human boundary anchors, freeze
picks/frame/bounds, THEN analyze. No diagnostic-derived ROI, resizing/search, padding
optimization, higher target/layer budgets, chosen depth sign or convenient clutter
removal. Trustworthy intent with refused geometry is useful. Do not tune fixtures to
this fan. After acceptance, the next architecture is a CAD feature/model IR, not broad
Fusion automation bundled here.

## Recoverability

Inspect actual main/branches/commits/PRs/issues/CI and this file before resuming.
Preserve unexpected work. Commit coherent increments, verify returned SHA AND remote
ref, update this file at milestones, then continue. Save before long tests. Never
reset, clean, force-push, delete retained branches or add retry/recovery/numbered lanes.
A failed ChatGPT stream does not imply lost Git work. Do not merge0.15.7.

Sandbox DNS cannot resolve GitHub/PyPI. Use connector workflow source artifacts for
exact recovery. Public dependency wheels were recovered through temporary bootstrap
CI36367435852; that bootstrap workflow is removed. Local project is noneditable,
with some preinstalled third-party dependencies reused (not pristine dependency
isolation). Local exact shallow commits/trees were SHA-verified without resetting or
cleaning. Regular tests workflow includes this branch and noneditable installation.
