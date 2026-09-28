# Agent visual inspection: recovered implementation checkpoint

Branch: `feature/live-agent-visual-inspection`; existing stacked draft PR #22.
Base: `feature/live-section-roi-from-picks`, draft PR #21,
`c35916d4badf5bdac815417d88cdffba56b537b7`.
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.
Both PRs MUST remain draft/unmerged without separate explicit merge authorization.

## Current state

Python 0.16.0; native qMCPBridge 0.13.0 / workflow revision 9. Native rebuild is
required for Windows acceptance. Runtime/tests persisted at
`bef9f0135e7a7c1b15cdba0d140624fb975c8418` before the chat failed. Its push CI
36378023620 and PR CI 36378197862 succeeded, including the actual Linux plugin build
against CloudCompare v2.13.2. The recovered PR #22 must not be recreated.

Recovery repeated complete noneditable installed regression: 1393 passed, zero
skips in 101.13 s; focused new suite: 182 passed in 8.31 s. All 34 installed source
module hashes match. The exact recovered Git tree and complete parent diff were
verified; source/native changes reviewed; compileall and parent whitespace checks
passed. Read docs/VISUAL_INSPECTION_REVIEW.md for exact evidence and test categories.

Camera/semantic contract and focused Windows handoff are complete in:
- docs/LIVE_AGENT_VISUAL_INSPECTION.md
- docs/WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md
- docs/VISUAL_INSPECTION_REVIEW.md

Read actual latest HEAD and its CI before continuing. Documentation after the
runtime checkpoint is not a new behavioral validation claim. PR #22 records the
final documentation-head SHA and CI run/result once checked. Do not substitute an
earlier native-only run or infer CI success from this file. No visible Windows,
actual viewport interpretation, or real human semantic acceptance has run here.

## Implemented contracts

get_live_camera(save=true) stores an exact ccViewportParameters copy.
set_live_camera supports look/orbit/pan/zoom/focus/restore/release, guarded by the
native session, active window and expected-current camera fingerprint. Eight saved
tokens, no eviction. Restore requires same session/window/viewport dimensions and
compares camera fingerprints, not framebuffer pixels or the whole GUI. Current
object-centered ortho/perspective mode is preserved; stereo, bubble, viewer-centered
mode and nonunit display scale refuse. Source global scale is separate and supported.
Camera center is a host-render parameter, NOT a global world-eye coordinate. Focus
requires a visible cloud in the active display, its declared global shift/scale and
no pending source/ancestor transform. No mouse simulation or source/selection writes.

inspect_live_part uses a whole-source query with a fixed caller-declared threshold,
24..2048 sampled points and source <=5 million. Multiple eligible sources require
an explicit cloud ID; never choose the largest silently. Existing plane/circle/
cylinder discovery runs once per requested kind, with no success-driven retries.
Limits: four captures, five navigation moves plus one restore, two geometric
acquisitions, three discovery calls, six initial candidates, twelve proposals per
inspection, sixteen cached inspections, 128 KiB metadata, 8 MiB per PNG, 16 MiB total.
Default restoration is ownership-guarded. Concurrent user movement or ambiguous
transport returns recovery information rather than overwriting that state. Retain
view leaves an explicit baseline token for later restore/release.

The calling agent reviews actual returned PNGs, then propose_live_semantic_feature
binds issued candidate/capture evidence, explicit observations and a concise question.
Unreviewed automatic drafts cannot be confirmed. Candidate A/B/C labels are metadata,
not new viewport labels. Semantic vocabulary is not a complete bolt-pattern or
through-feature detector. Existing hole-pattern/datum/section tools remain separate.
confirm_live_semantic_feature requires the issued proposal fingerprint, explicit
yes/no/unsure and exact reported human answer text. Never infer a human yes.
validate_live_semantic_confirmation rechecks observed source acquisition plus
scene/selection/overlay metadata, endpoint and native session/window. Detected changes
or read failure permanently stale evidence; later answers supersede old answers.
Different affirmative roles sharing candidate IDs require review. This is not
arbitrary spatial-overlap detection. Camera motion alone does not stale frozen
captures. Inspection release/restart invalidates its process-local evidence IDs;
release does not remove camera tokens or unrelated overlays. PNG blobs are not
retained in semantic objects. Keep issued packets before releasing evidence.

## Refusal / evidence boundaries

Vision is context, geometry dimensional evidence, human response semantic intent.
None authorizes reconstruction or bypasses numerical refusal. No ROI/padding/scale/
layer/target/reconstruction-quality search, clutter removal, CAD IR or Fusion.
Freshness is metadata plus deterministic sample/native query summary, NOT whole-cloud
geometry/attributes equality. Reads are non-atomic; unobserved change-and-change-back
may be undetectable. Session/endpoint and caller-reported answers are not authenticated
host/human identities. Python performs no automatic image interpretation. Existing
overlays are fingerprinted/preserved; no new ones are created because group-wide
clearing lacks per-inspection ownership. Do not clear unrelated diagnostics.

Read docs/RETAINED_0_15_7_CHECKPOINT.md and prior spatial-intent/Windows reports.
Do not repeat passed safe picks or pretend unfinished manual cases passed. No fan
ROI/reconstruction call. Authorized fan SHA256:
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0;
retained source count 406276; rediscover entity IDs. Fan inspection is only after
internal exact-head CI and visible synthetic camera gates. A full CAD model is not
this gate's objective. Fewer supported semantic questions or refusal are valid.

## Next / recovery discipline

After exact-head CI, execute docs/WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md on the
visible Windows host: native rebuild, synthetic camera/source-safety gates, then
bounded fan inspection and understandable semantic questions, not vertex clicking.

Recover actual refs, recent commits, PRs/issues, CI and AGENTS first. Preserve
unexpected work. Never reset, clean, force-push, delete/recreate retained branches or
invent retry/recovery/numbered branches. Commit coherent increments and verify the
returned SHA and actual remote branch persistence before continuing. Temporary
transport/dependency helper workflows were removed; do not recreate them merely
because chat restarted. Keep local unit/compiled policy, replay, actual MCP stdio,
GitHub CI/native build and visible Windows evidence distinct.

Local recovery used Python 3.13.5, noneditable project installation and some reused
preinstalled third-party dependencies, not pristine isolation. Exact source came
from existing CI archives because container GitHub/PyPI DNS was unavailable. CI uses
a fresh Python 3.12 install and separate actual CloudCompare 2.13.2 native compilation.
