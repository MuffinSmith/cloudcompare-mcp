# Agent visual inspection: recovery checkpoint

Branch: `feature/live-agent-visual-inspection`.
Stacked base: `feature/live-section-roi-from-picks`, draft PR #21,
SHA `c35916d4badf5bdac815417d88cdffba56b537b7`.
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.

## Current state

Python 0.16.0, native qMCPBridge 0.13.0 / workflow revision 9.
Native camera/capture checkpoint 4b84b3a61a856bef312b73728820c2276c2a11ed passed CI
36376174049, including actual Linux CloudCompare 2.13.2 plugin compilation (job
108782362426). Python registration and active-window source-focus guard were
integrated at e5070fdaf0fc87a24e0f04750d1e750e264a6287. All new tests/generator are
now persisted. The temporary Actions source helper AND its workflow are removed.
Do not recreate a transport/recovery branch or helper merely because chat restarted.

Local installed complete regression: 1393 passed, zero skips in 135.75 s.
Focused new suite: 182 passed (31 compiled C++ camera policy, 59 Python camera/PNG,
65 bounded workflow/semantic/freshness, 17 real MCP schema/dispatch/installed stdio,
10 fixture checks). Nine deterministic PLY files are generated outside Git and
hash-verified before numerical use. Actual installed MCP subprocess is exercised
against a counted TCP replay: 44 native calls, six region reads, two replay PNGs.
This is not a real-host native-call measurement or real viewport-image acceptance.
compileall and local git diff --check passed. Source modules' Git blob hashes matched
local bytes. Full source/parent diff review, final docs/PR and final exact-head CI
still need completion. Do not claim final CI from earlier native checkpoints.

## Contracts

get_live_camera(save=true) stores an exact native ccViewportParameters copy.
set_live_camera supports look/orbit/pan/zoom/focus/restore/release with session,
window and expected-camera guards. Eight tokens, no eviction. Restore requires the
same session/window/viewport size and compares the resulting fingerprint. Supports
object-centered ortho/perspective; refuses stereo/bubble/viewer-centered/nonunit
display scale. Camera center is a CloudCompare host-render parameter, NOT a global
world-eye point. Global focus converts through the declared cloud's shift/scale;
pending transforms, invisible/disabled sources and another display window refuse.
No source geometry, selection, unrelated overlay or mouse-simulation writes.

inspect_live_part uses a declared whole-source query and 24..2048 sample points
(source <=5 million); reuses existing plane/circle/cylinder discovery once each.
Limits: four captures, five navigation moves plus one restore, two geometry queries,
three discovery calls, six initial candidates, 128 KiB metadata, 8 MiB per PNG and
16 MiB total PNGs. Required threshold is fixed before fitting. Default restoration
is ownership-guarded; concurrent human movement/ambiguous transport returns recovery
state instead of overwriting it. Explicit retain-view keeps a releasable save token.

The calling agent reviews actual returned PNGs, then propose_live_semantic_feature
binds candidate IDs/fingerprints, inspected capture indexes, observations and a
concise question. Draft auto-proposals cannot be confirmed before review.
confirm_live_semantic_feature requires the issued proposal fingerprint, explicit
yes/no/unsure and exact reported human answer text. validate_live_semantic_confirmation
rechecks the same observed acquisition + scene/selection/overlay metadata + endpoint
+ native session/window. Changes permanently stale evidence; latest answer supersedes
previous answers. Overlapping different affirmative roles require review. Camera
motion alone does not stale frozen capture evidence. release_live_inspection removes
only its process-local evidence. Sixteen cached inspections, twelve proposals each;
restart/release invalidates IDs. PNG blobs are not retained in semantic objects.

## Limits / preserved evidence

Vision is context, geometry is dimensional evidence, human response is semantic
intent. None authorizes reconstruction or bypasses existing numerical refusal.
No ROI/scale/layer/target/reconstruction quality searches, broad CAD IR or Fusion.
Freshness is metadata plus deterministic sample/native query summary, NOT whole-cloud
geometry/attributes equality. Reads are non-atomic; unobserved change-and-change-back
cannot be detected. Session/endpoint and caller-reported answers are not authenticated
host/human identities. Real image interpretation is NOT performed by the Python
service. Existing unrelated overlays are fingerprinted/preserved; no new overlay is
created because current group-wide clearing would affect unrelated diagnostics.

Read docs/RETAINED_0_15_7_CHECKPOINT.md and prior spatial-intent/Windows reports.
PR #21 and the new stacked PR MUST stay draft/unmerged. Do not repeat passed safe
picks or pretend old blocked/unrun GUI cases passed. No fan ROI/reconstruction call.
Authorized fan SHA256: 79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0;
retained source count 406276; rediscover entity IDs. Fan semantic inspection only
after internal CI and synthetic visible camera gates. A full CAD model is not this
gate's objective. No visible Windows native build/viewport/semantic acceptance yet.

## Next / recovery discipline

Finish docs, full parent/native diff review, draft PR against the fallback branch,
and final exact-head CI. Then provide a focused Windows/CloudCompare prompt requiring
native rebuild and semantic questions, not tiny-vertex clicking.

Recover actual refs, commits, PRs/issues, CI and AGENTS first. Preserve unexpected
work. Never reset, clean, force-push, delete/recreate retained branches or invent
retry/recovery/numbered branches. Commit coherent increments and verify actual remote
SHA persistence before continuing. Keep local unit/compiled policy, replay, actual
MCP stdio, GitHub CI/native build and visible Windows evidence distinct.

Local environment is Python 3.13.5 with a noneditable project install and some reused
preinstalled third-party dependencies (not pristine isolation). Exact source comes
from CI archives; local GitHub/PyPI DNS is unavailable. GitHub CI uses a fresh Python
3.12 install and a separate actual CloudCompare 2.13.2 native build.
