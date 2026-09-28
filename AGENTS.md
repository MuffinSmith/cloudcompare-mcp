# Agent visual inspection: recovery checkpoint

Branch: `feature/live-agent-visual-inspection`.
Stacked base: `feature/live-section-roi-from-picks`, draft PR #21,
SHA `c35916d4badf5bdac815417d88cdffba56b537b7`.
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.

## Current milestone

Python integration pending the one-shot source helper.

Persisted Python modules implement strict camera/PNG evidence, bounded inspection,
and seven MCP schemas/handlers with explicit semantic proposal and answer binding.
Local focused tests: 182 passed (31 compiled camera policy, 59 Python camera,
65 workflow/freshness, 17 actual schema/dispatch/installed stdio, 10 exact-fixture
checks). The six new test/support files and fixture generator are not yet persisted
at this checkpoint; persist them next. Full installed regression is running locally;
no final result claimed yet. Python modules' Git blob hashes matched local bytes.

Native checkpoint `4b84b3a61a856bef312b73728820c2276c2a11ed` CI run 36376174049
PASSED both installed Python and actual Linux CloudCompare 2.13.2 qMCPBridge build.
Native job 108782362426 compiled the real plugin, not only a policy harness.
That checkpoint's local full regression: 1242 passed, zero skips.
No Windows native build, actual viewport-image interpretation or visible-host
acceptance has occurred for this increment. Native is 0.13.0 / workflow revision 9.

## New workflow

get_live_camera(save=true) stores an exact native ccViewportParameters copy.
set_live_camera supports look/orbit/pan/zoom/focus/restore/release with session,
window and expected-camera guards. Eight save tokens, no eviction. Native restore
requires the same session/window/viewport size; comparison is explicit. Object-
centered ortho/perspective only, no stereo/bubble/viewer-centered/nonunit display
scale. Camera center is a host-render parameter, NOT a global world-eye position.
Focus converts global point/region via the declared cloud's shift/scale; no pending
transforms, invisible/disabled sources, or another display window. No GUI mouse
simulation, source/selection changes or overlay writes.

inspect_live_part uses one explicit whole-source query recipe (24..2048 sampled
points, source <=5 million), existing plane/circle/cylinder discovery once each,
up to four declared views, at most five navigation moves plus one restore, two
geometry acquisitions, six initial geometric/draft semantic candidates. Required
threshold is fixed before fitting; no quality-driven retries. PNGs have native
camera provenance, verified SHA256/chunk CRCs and byte/pixel budgets, and are
returned as images separately from compact retained evidence. Default camera
restoration is ownership-guarded; a concurrent human move/ambiguous response yields
an explicit recoverable error rather than overwriting it. Retain-view is explicit.

The agent must actually review returned PNGs before issuing a semantic proposal;
Python does not interpret images or invent human answers. Proposals bind issued
candidate IDs, code/evidence fingerprints, captured views, explicit observations,
and a concise question. Answers require exact proposal fingerprint and explicit
yes/no/unsure plus exact reported human text. Freshness rechecks the same source,
scene/selection/overlay metadata, sampled coordinates/query summary, endpoint and
native session/window. Changed evidence becomes permanently stale; latest answer
supersedes previous answers; overlapping different affirmative roles require review.
Camera pose changes alone do not stale frozen evidence. Cache is process-local,
16 inspections/12 proposals each; restart/release invalidates IDs. No PNGs in cache.

## Refusal/provenance limits

Images/semantic intent never authorize CAD construction or bypass accepted numerical
refusals. No reconstruction/ROI/layer/target scale tuning, broad CAD IR or Fusion.
Freshness is observed deterministic sample + native full-query summary + metadata,
NOT whole-cloud geometry/attributes equality. Reads are not atomic; unobserved
change-and-change-back cannot be ruled out. Session/endpoint are context, not
cryptographic host/human authentication. No independent real-host native call count.
Replay PNGs are test transport, not real viewport visual acceptance. Existing
unrelated overlays are fingerprinted/preserved; this increment creates none.

## Preserve prior work / next steps

Read docs/RETAINED_0_15_7_CHECKPOINT.md and the spatial-intent/Windows reports.
PR #21 and this branch must remain draft/unmerged. Do not repeat passed safe picks
or claim old blocked GUI cases passed. No fan ROI/reconstruction call occurred.
Authorized fan SHA256: 79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Retained fan source count 406276; rediscover IDs. Fan semantic inspection only AFTER
internal exact-head CI and synthetic visible camera gates; no full model required.

Next persist new tests/generator, inspect full installed regression, review complete
parent/native diff, remove transport workflow through connector, write contract and
focused Windows gate, open stacked draft PR, require final exact-head green CI.

Recover actual remote heads/commits/PRs/issues/CI before resuming. Preserve unexpected
work; never reset, clean, force-push, delete or recreate retained branches. No retry,
recovery or numbered branches. Commit coherent increments and verify actual remote
SHA persistence. Temporary Actions helper is branch-scoped, non-force, guards exact
remote HEAD, and applies only explicit source edits. GitHub Actions tokens cannot
edit workflows; use the connector for workflow changes/removal.

Local environment: Python 3.13.5 noneditable project install; some preinstalled third-
party packages reused, not pristine isolation. Exact source via CI artifact;
GitHub/PyPI DNS unavailable locally. Keep unit/policy, replay, actual MCP stdio,
GitHub CI/native build, and visible Windows results separate.
