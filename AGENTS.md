# Recovery checkpoint: agent visual inspection

Branch: `feature/live-agent-visual-inspection`.
Stacked parent: `c35916d4badf5bdac815417d88cdffba56b537b7` on
`feature/live-section-roi-from-picks` (draft PR #21).
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.

## Current state

Native integration is pending the narrow checkpoint helper.
Native camera dispatcher and shared policy are persisted. Policy checkpoint
c2e04e0fbd5825a2cb574b76fe365c64a6a12c8e passed all 31 compiled local C++ policy tests.
This is NOT a Qt/plugin build or GUI result. Python remains 0.15.7; the 0.16.0
inspection/semantic workflow is still being implemented, not yet persisted.

Read docs/VISUAL_INSPECTION_PROGRESS.md and actual subsequent commits. The temporary
branch-specific Actions helper applies exact guarded edits to existing large native
files, then deletes itself and creates a normal source commit. It uses non-force
push and refuses a changed remote head. Inspect actual branch state before resuming;
a failed stream never means the work was lost. Do not recreate this branch.

## Implemented native design, awaiting validation

view.camera: get/save/look/orbit/pan/zoom/focus/restore/release. Save tokens are
native-session scoped, capped at eight without eviction. Moves and restore require
current session, active window and camera fingerprint. Full ccViewportParameters
copies are restored only to the same window and viewport size. Recompute and compare
camera fingerprint after restore. Derived clipping distances/framebuffer/LOD and
unrelated GUI or source state are not exact-restoration claims. Object-centered
orthographic/perspective supported; stereo, bubble, viewer-centered and nonunit
display scale refused. Camera center is a CloudCompare host-render parameter, NOT a
global world-eye coordinate. Focus takes a point-cloud source frame and converts
explicit global center/region through its shift/scale; pending transforms refused.
Source geometry, selection and overlays are never edited by this contract.

## Direction and preserved evidence

Agent inspects images plus structured geometry and asks simple semantic questions.
Vision is contextual, geometry dimensional; explicit human answers bind exact issued
evidence and cannot override numerical refusal. No automatic ROI/scale/fit-quality
search, fan reconstruction, broad CAD IR or Fusion backend. Existing overlays are
read-only context initially because clear-all would affect unrelated overlays.

Read docs/RETAINED_0_15_7_CHECKPOINT.md and the three spatial-intent/Windows docs.
PR #21 stays draft/unmerged. Do not merge this branch either. Do not repeat the passed
safe human-pick fixture or claim old blocked/unrun GUI cases passed. No fan ROI call
has occurred. Authorized fan SHA256 is
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0;
retained count 406276, rediscover current source rather than reusing entity IDs.

## Recovery and testing discipline

Inspect current main, relevant refs/commits/PRs/issues/CI and this file. Preserve
unexpected work. Never reset, clean, force push, delete retained branches, or invent
retry/recovery/numbered branches. Commit coherent increments; verify returned SHA and
actual remote branch persistence before continuing. Update this checkpoint at each
milestone. Save before long tests. Keep unit/numerical, compiled policy, TCP replay,
actual installed MCP stdio, GitHub CI, real plugin build and visible Windows claims
separate. Old numerical reconstruction solvers must remain unchanged.

Sandbox recovered exact parent source from successful Actions run 36373820422,
artifact 10949957563, verified tracked tree 4521f1df9d4fa6ef389428efbf1600df0faa6529.
Offline wheels: run 36367435852 artifact 10946969592. Local Python 3.13.5 environment
uses a noneditable project install and some preinstalled dependencies; not pristine
isolation. GitHub/PyPI DNS is unavailable locally; use connector/source artifacts.
