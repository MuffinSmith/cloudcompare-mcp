# Camera guard recovery — integrated Python 0.16.1 / native 0.13.1

Resume EXISTING feature/live-agent-visual-inspection and stacked draft PR #22.
PR #21 base: c35916d4badf5bdac815417d88cdffba56b537b7.
Accepted main: 2b385820ecfcb84d79aaf59ad5965e748f961466.
Neither PR may be merged without separate explicit authorization.

## Read first

- docs/CAMERA_GUARD_RECOVERY.md is the current guard/capture/restoration contract.
- docs/WINDOWS_CAMERA_GUARD_RETEST.md is the focused next gate, not the old full marathon.
- docs/WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md preserves actual user-reported Windows status.
- docs/LIVE_AGENT_VISUAL_INSPECTION.md remains the broader 0.16.0 workflow contract;
  camera ownership/equality portions are superseded by CAMERA_GUARD_RECOVERY.md.
- Keep docs/RETAINED_0_15_7_CHECKPOINT.md and all earlier acceptance/review evidence.

## Recovery sequence and observed internal evidence

Started from 5559f099670b0e1d86de6df793fca12ffa4ac53e. Preserved the Windows report
at 3b27fc7a940a6d0884f0cf88d12f01904b165480. Native-first commit
156c6952993f7f0cc2be03300288066d12f00b11 passed push CI 36391019292, including
35 production-helper Qt CTests and actual CloudCompare v2.13.2 plugin compilation.
Current integrated source adds Python 0.16.1 guard choice/error propagation/schema
compatibility and 47 new regressions. It requires a NEW exact-head push AND PR CI
check, recorded in PR #22 after completion; do not infer final CI from native-first.

Local noneditable Python 3.13.5 full suite: 1440 passed, zero skips, 106.32 s.
Combined focused suite: 229 passed, zero skips, 10.31 s (retained 182 plus new 47).
All 34 installed Python source module hashes match. Compileall and full local
baseline-tree whitespace checks pass. Actual installed MCP stdio + event-aware
TCP replay: 40 native requests, five geometry reads, three capture attempts (two
replay PNGs plus one refused). Scripted unsure answer is not human acceptance.
Retained legacy stdio cycle still passes 44 requests / six reads / two replay PNGs.
Qt development headers are unavailable locally; Qt CTests run in CI, not locally.
Full source/remote-archive verification and final PR summary must be retained before
handoff. Remote file blob SHAs were checked against local bytes after writing.

## Preserved Windows result and unresolved diagnosis

At 5559f099, reported Windows checks passed: 1393/182 tests, 34 module hashes, nine
fixtures, 36 reviewed actual viewport PNGs, native rebuild and synthetic semantic
lifecycle. Fan camera/capture refused on two hosts; actual human confirmation is
PENDING. Raw report/packet live only in the Windows acceptance directory named in
WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md and were not read in this development container.
Do not relabel old blocked/unrun manual or fan cases as passes.

The earlier full-fingerprint explanation is a HYPOTHESIS about the fan, not proven
root cause. Derived zNear/zFar and computed matrices were already outside the old
full fingerprint. The new design fixes style-versus-navigation conflation and gives
field-level diagnostics. Genuine pose/projection/identity drift must still refuse.
No Windows 0.16.1 DLL/image/fan acceptance has been performed here.

## Current narrow contract

Python 0.16.1; public native ping/capabilities 0.13.1 / workflow revision 9.
cc-camera-v1 and its full parameter fingerprint remain unchanged. Additive
cc-camera-guard-v1 removes ONLY point/line size and redundant view/up directions;
all pose, projection, explicit clipping, mode, display scale, session, window,
viewport size and future parameter fields remain exactly guarded. Modern restores
preserve current style and report restored_guard_equal separately from restored_equal.
Legacy full guards stay strict. Dual/malformed guards and response downgrades refuse.
Capture compares guard around one redraw/event turn and full state across the grab.
No refresh/retry loops or tolerance widening. Diagnostics carry phase and snapshots;
32-state diagnostic history is not authorization and cannot evict saved camera tokens.

Existing server.py, numerical fitting/discovery/section/ROI/target/layer solvers,
fixture generator and qMCPFusionWorkflow.cpp remain byte-unchanged. Public capabilities
are enriched at qMCPBridge dispatch. The public capture_live_view tool stays no-argument;
explicit expected-guard captures are available through the installed Python helper and
internally in inspect_live_part. Do not call a direct bridge probe MCP stdio evidence.

## Windows next gate and boundaries

Install BOTH Python and a rebuilt compatible isolated Windows DLL. Verify hashes,
public contracts and process/port identity; preserve normal runtime/unsaved work.
Run automated regression/Qt CTests and only a small visible disposable-fixture guard
probe, then a bounded camera-only fan preflight. If it refuses, retain exact field
values and phases, do not force or tune away protected state. Once it passes, one
bounded inspection, actual PNG review and understandable questions with actual human
answers. Keep the same MCP process alive for evidence IDs. Restore/release owned state
only. Preserve all earlier successful synthetic coverage instead of repeating 36 PNGs.

Authorized fan SHA256:
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Retained count 406276; rediscover IDs/frame. Existing threshold 0.15 GLOBAL native units
only with same verified frame; physical units are unknown. No success-driven numerical
search, source mutation, fan ROI/reconstruction, broad CAD IR, Fusion or merge.
Vision is context, geometry dimensional evidence, human answer semantic intent.
Sampled/non-atomic freshness is NOT full-cloud coordinates/attributes equality.

## Disconnect discipline

Recover actual refs, commits, PRs/issues, CI and this file first. Preserve unexpected
work. Never reset, clean, force-push, recreate branches or invent retry/recovery names.
Commit coherent increments and verify returned SHA AND actual remote ref. No temporary
transport/dependency helper workflow recreation. Local source/dependency archives are
reused because GitHub/PyPI DNS is unavailable. Local install is noneditable but reuses
some preinstalled dependencies, not pristine isolation; CI uses fresh dependencies.
Keep unit/replay, installed MCP stdio, Qt tests, actual native build and visible Windows
acceptance separate. All final result claims must name the exact tested checkpoint.
