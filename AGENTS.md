# Agent visual inspection: recovered implementation and CI checkpoint

Branch: `feature/live-agent-visual-inspection`; existing stacked draft PR #22.
Base: `feature/live-section-roi-from-picks`, draft PR #21,
`c35916d4badf5bdac815417d88cdffba56b537b7`.
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.
Both PRs MUST remain draft/unmerged without separate explicit merge authorization.

## Current state and exact evidence

Python 0.16.0; native qMCPBridge 0.13.0 / workflow revision 9. Windows needs a native
DLL rebuild. Runtime/tests persisted at `bef9f0135e7a7c1b15cdba0d140624fb975c8418`
before the failed chat. Recovery resumed that existing branch/PR, repeated tests,
reviewed the full parent/native diff and completed the documentation.

Recovery installed regression: 1393 passed, zero skips in 101.13 s. Focused new
suite: 182 passed in 8.31 s (31 compiled C++ camera policy, 59 Python camera/PNG,
65 workflow/semantic/freshness, 17 actual MCP schema/dispatch/installed stdio,
10 fixture checks). All 34 installed Python module hashes match. Nine generated
PLY hashes and vertex counts were independently verified. Actual installed MCP
stdio uses counted TCP replay: 44 native requests, six region reads, two replay
PNGs. This is not real-host query-count or viewport-image acceptance.

Runtime push 36378023620 and PR 36378197862 passed. Documentation head
`77879285f7fd6b62521a2358d51afb30656d0c7b` passed exact-head push 36379584524,
including full Python checks and actual Linux CloudCompare v2.13.2 plugin build.
Its source artifact reconstructs exact tree 2d1d3d8c193fb24729f6e09127e5b8f39ab0ee9d;
complete-parent whitespace checks passed; product/runtime/tests were unchanged.

IMPORTANT: companion PR run 36379587715 then failed before native compilation while
fetching an unrelated optional plugin from an external GitLab server. Python passed.
See docs/VISUAL_INSPECTION_CI_CHECKOUT.md. The subsequent narrow CI correction fetches
only the required CCCoreLib gitlink, verifies its exact commit, and bounds checkout
timeouts. It does NOT skip the real native build or suppress errors. Product code,
numerical solvers, generator and tests remain unchanged. Verify NEW exact-head push
and PR CI after this correction; do not infer success from the previous green run.
PR #22 records the final SHA/results after they are checked. No visible Windows,
actual image interpretation or real human semantic acceptance is claimed here.

## Contracts and documentation

Read docs/LIVE_AGENT_VISUAL_INSPECTION.md for the complete camera, inspection,
provenance, semantic confirmation/staleness and refusal contracts;
docs/VISUAL_INSPECTION_REVIEW.md for internal source/test evidence;
docs/WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md for the next visible-host gate;
cloudcompare-plugin/qMCPBridge/README.md for the required native build.

Seven tools: get_live_camera, set_live_camera, inspect_live_part,
propose_live_semantic_feature, confirm_live_semantic_feature,
validate_live_semantic_confirmation, release_live_inspection.
Existing set_live_view remains; capture_live_view gains camera/content provenance.
Native camera snapshots store actual ccViewportParameters copies, eight tokens,
no eviction. Look/orbit/pan/zoom and source-frame focus require current session,
window and camera-fingerprint guards. Restore requires same viewport dimensions
and checks camera equality, not framebuffer/full-GUI equality. Camera-center values
are host-render parameters, not a global eye pose. Current object-centered
ortho/perspective mode is preserved. Global source scale may be nonunit; unsupported
camera display modes/scales, pending source transforms or another display refuse.
Never overwrite concurrent human navigation during automatic recovery.

Inspection fixes the threshold before fitting, uses 24..2048 sampled points from
<=5 million source points, at most four captures, five navigation moves plus restore,
two acquisitions, three existing discovery calls and six initial candidates. No
largest-source guess, fit-quality retry, or whole-part autonomous unbounded loop.
Twelve proposals/inspection, sixteen cached inspections, 128 KiB metadata, 8 MiB
per PNG and 16 MiB total. Release only owned tokens/evidence; no automatic eviction.

The calling agent must review actual returned PNGs before issuing reviewed semantic
proposals. Automatic drafts cannot be confirmed. Require issued proposal fingerprint,
explicit human yes/no/unsure and exact reported answer text; never infer yes.
Detected acquisition/scene/selection/overlay/session/endpoint changes permanently
stale evidence; latest answers supersede prior ones. Different affirmative roles
sharing candidate IDs require review, not a general spatial-overlap check. Camera
movement alone does not stale frozen captures. Restart/release invalidates
process-local IDs; inspection release does not release camera tokens or overlays.
Keep issued packets before release. No PNG blobs remain in semantic objects.

## Limits, preserved work and next gate

Vision is context, geometry dimensional evidence, human response semantic intent.
None authorizes CAD reconstruction or overrides numerical refusal. No ROI/padding/
scale/target/layer/threshold success search, clutter removal, fan reconstruction,
CAD IR or Fusion work. Freshness is sample + native query summary + metadata, NOT
whole-cloud coordinates/attributes equality. Reads are non-atomic; unobserved
change-and-change-back may be undetectable. Session/endpoint and reported human
answers are not authenticated identities. Python does not interpret images.
No new inspection overlays/onscreen A/B/C labels; labels are packet metadata.
Existing unrelated overlays are preserved. Role names are not full bolt-pattern or
through-feature detectors; existing hole-pattern/datum/section tools remain separate.

Preserve docs/RETAINED_0_15_7_CHECKPOINT.md and prior spatial-intent/Windows reports.
Do not repeat passed safe picks or pretend unfinished manual cases passed. Authorized
fan SHA256: 79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0;
retained count 406276; rediscover source IDs. No fan ROI/reconstruction call. After
new exact-head CI, run the focused Windows DLL/synthetic camera/safety gate, then
bounded fan inspection and understandable questions with actual human answers.
Fewer supported questions or geometric refusal are valid; no full CAD model required.

## Recovery discipline

Recover actual refs, commits, PRs/issues, CI and AGENTS first. Preserve unexpected
work. Never reset, clean, force-push, delete/recreate retained branches or invent
retry/recovery/numbered branches. Commit coherent work and verify returned SHA AND
actual remote ref before continuing. Removed transport/dependency helper workflows
must not be recreated merely because chat restarted. Distinguish unit/compiled
policy, replay, actual MCP stdio, native compilation and visible Windows evidence.
Local noneditable Python 3.13.5 used some preinstalled third-party dependencies, not
pristine isolation. Existing CI archives supplied exact source because container
GitHub/PyPI DNS was unavailable. CI installs fresh Python 3.12 dependencies.
