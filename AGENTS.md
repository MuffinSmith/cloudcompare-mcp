# Automatic-pivot recovery — Python 0.16.2 / native 0.13.2

Resume the existing `feature/live-agent-visual-inspection` branch and stacked draft
PR #22. PR #21 base remains
`c35916d4badf5bdac815417d88cdffba56b537b7`; accepted main remains
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Neither PR may be merged without
separate explicit authorization.

## Preserved Windows evidence and root cause

Read `docs/WINDOWS_0_16_1_PARTIAL_ACCEPTANCE.md` first. The Windows 0.16.1 run at
`0be16cf8709b77f562744c19d26895717466a57c` passed installation, 1441 complete
Python tests, 230 focused tests, 35/35 Qt CTests, the visible synthetic guard gate,
and real synthetic PNG review. The authorized fan preflight then BLOCKED after a
successful focus because protected camera state changed before the next look. No fan
inspection, proposal, human question/answer or confirmation occurred.

The diagnostic transition translated pivot and camera together while focal distance
was effectively preserved. CloudCompare v2.13.2 source explains this exactly:
`ccGLWindowInterface` defaults `m_autoPickPivotAtCenter` to true and the render path
can call `setPivotPoint(pivot, true, false)`, where `autoUpdateCameraPos=true` moves
the camera with the newly selected center-screen pivot. This is a host interaction
behavior, not a guard-tolerance problem. Do not weaken pose guards or refresh/retry a
stale guard.

The report was persisted first at commit
`cb162edf8e3d6f8324c2601b40aa4ef634b9fb4e` before implementing the recovery.
Raw Windows evidence remains outside Git under the path recorded in that report.

## Current 0.16.2 / 0.13.2 recovery contract

Read `docs/AUTO_PIVOT_RECOVERY.md` and `docs/WINDOWS_AUTO_PIVOT_RETEST.md`. They
supersede the automatic-pivot portions of the older 0.16.1 guard handoff while
preserving all earlier acceptance/history documents.

`view.camera save` now accepts optional `suspend_auto_pivot=true`. Only a save token
created with that flag owns a temporary FALSE value for CloudCompare's center-screen
automatic pivot on the active window. Ordinary save tokens do not touch it. At most
one suspension owner exists per window.

Snapshots add `cc-camera-auto-pivot-v1` metadata and the current auto-pivot state,
without rewriting the legacy full camera fingerprint or weakening
`cc-camera-guard-v1`. Camera movements complete one host event turn before success,
so any delayed protected mutation is attributed immediately as
`movement.after_redraw`. If auto-pivot becomes TRUE while a token owns FALSE,
movement/capture refuses as an ownership conflict.

Restore occurs while auto-pivot is still suspended. Release then restores the
original host auto-pivot mode and returns the post-release camera state. Re-enabling
CloudCompare auto-pivot can itself schedule a redraw, so bounded inspection verifies
that final navigation state against the saved baseline. An externally re-enabled
auto-pivot value is preserved/reported instead of silently overwritten.

There is no guard refresh-and-retry loop, sleep/stabilization search, equality
widening or acceptance of pivot/camera translation as harmless. Styling remains
outside navigation ownership exactly as in 0.16.1; pose/projection/clipping/window/
session/viewport guards remain exact.

Python package is 0.16.2. Public native ping/capabilities are qMCPBridge 0.13.2 /
workflow revision 9 and advertise `cc-camera-auto-pivot-v1`. Both Python and the DLL
must be replaced for Windows acceptance.

## Internal validation and exact implementation checkpoint

The interrupted local patch was recovered from an exact Git tree matching
0.16.1 head tree `c2e56866ea3ef73ec6c3292832fabc4757467a5e`; it was not recreated from memory.
The deterministic replay reproduces the fan failure shape when auto-pivot is not
suspended, and proves save-with-suspension -> focus -> look -> capture -> restore ->
release succeeds while restoring the original host mode. It also verifies an external
re-enable refuses without moving the requested camera and is preserved at release.

Exact implementation checkpoint:
`42dfe3ad922d624e6e4553e98504ca4ed93ce39c`.

Observed validation at that exact SHA:
- exact-head push CI 36407285042: SUCCESS;
- PR integration CI 36407289691: SUCCESS;
- fresh CI Python install: **1447 passed**, zero skips, 94.14 s;
- production Qt camera-guard helper: **37/37 passed**;
- actual qMCPBridge build against CloudCompare v2.13.2: PASS;
- local focused camera/inspection core: 194 passed;
- local native-camera-policy + picked-intent modules: 41 passed;
- local installed stdio target ROI module: 2 passed separately;
- complete focused seven-module set contains 237 tests;
- 34/34 locally installed Python source hashes matched the candidate source;
- compileall and whitespace checks passed.

The existing deterministic numerical solvers, CAD section/ROI/target/layer/profile
math, fixture generator and qMCPFusionWorkflow behavior are unchanged by this
recovery. CI is authoritative for fresh dependency installation, the 37 Qt CTests
and actual native compilation; replay/CI are not visible Windows fan acceptance.

## Next visible Windows gate

After exact-head CI is green, follow `docs/WINDOWS_AUTO_PIVOT_RETEST.md`: install
Python 0.16.2 plus rebuilt qMCPBridge 0.13.2; verify hashes/capabilities; run automated
gates; run ONE small disposable auto-pivot ownership fixture; then run a bounded
camera-only fan preflight. Do not repeat the broad 36-PNG 0.16.0 exercise or precise
point clicking unless a regression appears.

Only after the fan camera preflight passes, run ONE bounded fan inspection using the
same independently fixed 0.15 GLOBAL native-unit threshold if the source frame is
verified unchanged, `sample_limit=1024`, views top/front/isometric, kinds plane and
cylinder. Review actual PNGs and candidates, ask only supported understandable
questions, and bind only the user's actual explicit yes/no/unsure answer text. No
answer means confirmation pending.

Authorized fan SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
Retained point count is 406276; IDs/PIDs/ports must be rediscovered. Physical units
remain unknown.

No fan ROI/profile reconstruction, threshold/ROI/target/layer/depth success search,
clutter removal, CAD IR, Fusion work, source mutation or merge is authorized at this
gate. Vision is context; structured geometry is dimensional evidence; human answers
are semantic intent. None overrides numerical refusal or authorizes reconstruction.

## Disconnect recovery

Recover actual refs, commits, PRs/issues, CI and this file before writing. Preserve
unexpected work. Never reset, clean, force-push, delete/recreate retained branches or
invent retry/recovery/numbered branches. Commit coherent increments, verify returned
SHA AND actual remote ref, then continue. Keep source/selection/overlay/camera evidence
honest and distinguish replay, installed MCP stdio, native Qt compilation, visible
CloudCompare behavior and real human semantic confirmation.
