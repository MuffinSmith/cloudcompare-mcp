# Camera guard recovery checkpoint

Resume `feature/live-agent-visual-inspection`, existing stacked draft PR #22.
Base is draft PR #21 at c35916d4badf5bdac815417d88cdffba56b537b7.
Accepted main is 2b385820ecfcb84d79aaf59ad5965e748f961466.
Neither PR is authorized to merge. Recover actual refs/CI before writing.

## Preserved Windows evidence

Read docs/WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md. At 5559f099670b0e1d86de6df793fca12ffa4ac53e
Python 0.16.0 / native 0.13.0 passed the reported Windows installed and synthetic
camera/semantic gates: 1393 tests, 182 focused, 34 module hashes, nine fixtures,
36 reviewed PNGs. The fan camera gate refused on two hosts. No actual fan semantic
confirmation exists. Raw Windows files were NOT read by the development container.
The previous explanation about viewport drift is a hypothesis, not proven root cause.
Derived zNear/zFar were already outside the full fingerprint. Do not hide this limit.

## Current native checkpoint

Native qMCPBridge 0.13.1 / workflow revision 9 adds cc-camera-guard-v1 and
cc-camera-diagnostics-v1. Full cc-camera-v1 fingerprints and legacy strict guards
remain available. New guards exclude only point/line style and redundant view/up
directions; exact pose, projection, explicit clipping, mode, display scale, session,
window, viewport size and unknown future parameter fields remain guarded.
Modern restore preserves CURRENT point/line sizes; restored_guard_equal is separate
from restored_equal (full equality). Capture checks the guard around event processing,
then full state across the framebuffer grab. No retries or tolerance widening.
A 32-state diagnostic history does not authorize movement and cannot evict save tokens.
Native refusal details include phase, available reference/current snapshots and field
differences. qMCPBridge enriches outgoing capability metadata; the legacy numerical
qMCPFusionWorkflow.cpp implementation is unchanged.

This coherent commit is native-first. The retained Python package is still 0.16.0
and exercises legacy guards. Python 0.16.1 integration and new event-aware replay
regressions are the NEXT checkpoint; do not mistake this for final acceptance.
CI now runs 35 standalone Qt CTests against the production guard helper, then the
actual CloudCompare v2.13.2 native plugin build. Check their observed result; no local
Qt execution or visible Windows acceptance of the patch has been claimed.

## Boundaries / continuation

Finish Python guard selection, strict legacy schemas, capture provenance and refusal
diagnostic propagation; add regressions for style drift versus real navigation,
framebuffer instability, dual/malformed guards, restore preservation and actual
installed MCP stdio. Run full installed regression and exact-head push/PR CI, update
contract documentation, then provide a focused Windows guard/fan prompt.

Preserve prior successful synthetic coverage. No precise-click repeats, fan ROI or
reconstruction, threshold/ROI/target/layer success search, source/selection/overlay
mutation, broad CAD IR or Fusion. Authorized fan SHA256:
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Retained count 406276; previous threshold 0.15 global native units; rediscover IDs.
Actual human yes/no/unsure and exact text are still required for reviewed proposals.

Read docs/LIVE_AGENT_VISUAL_INSPECTION.md, docs/VISUAL_INSPECTION_REVIEW.md,
docs/VISUAL_INSPECTION_CI_CHECKOUT.md and docs/RETAINED_0_15_7_CHECKPOINT.md.
Freshness remains observed samples/query summaries plus metadata, not full-cloud
coordinate/attribute equality. Never overwrite genuine concurrent human navigation.

No reset, clean, force-push, branch recreation or new retry/recovery branch. Commit
coherent work, verify returned SHA AND actual remote ref. Do not recreate temporary
transport workflows. The container reuses existing source/dependency archives because
GitHub/PyPI DNS is unavailable. Local project is noneditable but third-party packages
may be reused; CI uses fresh dependencies. Distinguish replay, installed MCP, Qt tests,
actual native compilation and visible-host evidence.
