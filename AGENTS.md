# Camera guard recovery — Python 0.16.1 / native 0.13.1

Resume existing feature/live-agent-visual-inspection and stacked draft PR #22.
PR #21 base: c35916d4badf5bdac815417d88cdffba56b537b7.
Accepted main: 2b385820ecfcb84d79aaf59ad5965e748f961466.
Neither PR may be merged without separate explicit authorization.

## Current contract and handoff

Read docs/CAMERA_GUARD_RECOVERY.md and docs/WINDOWS_CAMERA_GUARD_RETEST.md first.
They supersede the ownership/restoration parts of docs/LIVE_AGENT_VISUAL_INSPECTION.md
and the old full Windows procedure. Preserve docs/WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md,
docs/RETAINED_0_15_7_CHECKPOINT.md and all earlier reports; no old unrun case is a pass.

Python 0.16.1 / public native ping and capabilities 0.13.1 / workflow revision 9.
Full cc-camera-v1 parameter fingerprints remain byte/meaning compatible. Additive
cc-camera-guard-v1 excludes ONLY point/line style and redundant view/up directions;
all pose, projection, explicit clipping, mode, display scale, session/window/size
and unknown future parameters remain exactly guarded. No equality tolerance added.
Modern restore preserves current style, reporting restored_guard_equal separately
from restored_equal (full parameters). Legacy guards remain strict; dual/malformed
guards and silent response downgrades refuse. Legacy 0.13.0 capture accepts only the
old expected_camera_fingerprint; Python preserves that exact allowlist without extra
identity fields. The final compatibility regression is test_camera_guard_legacy_transport.

Capture compares ownership around one redraw/event turn, then full state across the
grab. No refreshed-guard retry or stabilization loop. cc-camera-diagnostics-v1 details
retain phases, reference/current snapshots and exact field deltas; bounded 32-state
history is not authorization and cannot evict the separate saved camera tokens.
The no-argument capture_live_view MCP tool remains unchanged; explicit expected-guard
captures use the installed Python helper and internally inspect_live_part. Do not
mislabel direct Python/native bridge probes as actual MCP stdio.

## Observed validation / exact checkpoint discipline

Started at 5559f099670b0e1d86de6df793fca12ffa4ac53e. Preserved Windows report at
3b27fc7a940a6d0884f0cf88d12f01904b165480. Native-first
156c6952993f7f0cc2be03300288066d12f00b11 passed push CI 36391019292 including
35 production-helper Qt CTests and actual CloudCompare v2.13.2 native compilation.
Python integration b8fa999d2620ebbfb46d58997cc4222acf661a45 had a local 1440-test pass.
Review then found the old native capture allowlist incompatibility; the current
correction adds one regression and retains modern identity guards without downgrading.

CURRENT local noneditable installed Python 3.13.5 suite: 1441 passed, zero skips,
105.18 s. Focused seven modules: 230 passed, zero skips, 10.39 s (182 retained + 48
new). All 34 installed source hashes match after reinstall. Compileall passes.
Verify the complete final tree/diff and final exact-head push AND PR CI separately;
PR #22 records actual SHA/results after verification. No earlier green run substitutes.

New actual installed MCP stdio + counted event-aware TCP replay: 40 requests,
five geometry reads, three capture attempts (two replay PNGs plus one refusal),
scripted unsure answer and safe release/recovery. Retained legacy stdio: 44 requests,
six reads, two replay PNGs. Neither is real-host image interpretation/query accounting
or actual human acceptance. Qt CTests are separate from Python totals and run in CI;
local Qt development files are unavailable. CI also builds the actual native plugin.

## Preserved Windows report / still unresolved fan diagnosis

At 5559f099 the user reported PASS for Windows installed runtime, native rebuild,
1393/182 tests, 34 hashes, nine fixtures, 36 actual reviewed PNGs and synthetic
semantic lifecycle. Fan camera/capture refused on two hosts; actual human fan
confirmation remains PENDING. Raw evidence is only in the Windows directory named
in the partial report; it was NOT read in this development container.

The style-drift explanation is a HYPOTHESIS about the fan, not proven root cause.
Derived zNear/zFar and computed matrices were already outside the old full hash.
This design correction plus diagnostics must not be sold as an observed fan fix.
No Windows 0.16.1 DLL, viewport or actual human semantic acceptance was run here.

## Retest / preserved boundaries

Install BOTH Python and a rebuilt compatible isolated Windows DLL. Verify hashes,
public contracts and PID/port identity; preserve normal runtime and unsaved work.
Run automated regression/Qt tests, one small visible disposable-fixture guard probe,
then bounded fan camera preflight. On unexpected refusal retain exact phases/fields,
release only owned tokens, never force or tune protected state. When preflight passes:
one bounded inspection, actual PNG review, understandable supported questions and
actual human answers bound to issued proposals. Keep the same MCP process alive.
Do not repeat the 36-PNG manual exercise or precise clicks as a prerequisite.

Authorized fan SHA256:
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Retained count 406276; rediscover IDs/frame. Existing threshold 0.15 GLOBAL native units
only with the same verified frame; physical units unknown. No success-driven threshold,
ROI/target/layer/depth search, source mutation, fan reconstruction, CAD IR, Fusion or merge.
Existing server.py, numerical solvers, fixture generator and qMCPFusionWorkflow.cpp
remain byte-unchanged; qMCPBridge enriches outgoing public native capability metadata.
Vision is context, geometry dimensional evidence, human answer semantic intent.
Sampled/non-atomic freshness is NOT whole-cloud coordinates/attributes equality.

## Disconnect recovery

Recover actual refs, commits, PRs/issues, CI and this file before writing. Preserve
unexpected work. No reset, clean, force-push, branch recreation or retry/recovery names.
Commit coherent increments and verify returned SHA AND actual remote ref. Do not
recreate temporary transport/dependency workflows. Local source/dependency archives
are reused due to unavailable GitHub/PyPI DNS. The project is installed noneditably
but some third-party dependencies are reused, not pristine isolation; CI installs
fresh dependencies. Distinguish unit/replay, installed MCP, Qt tests, actual native
compilation and visible Windows evidence. Name the exact tested checkpoint in claims.
