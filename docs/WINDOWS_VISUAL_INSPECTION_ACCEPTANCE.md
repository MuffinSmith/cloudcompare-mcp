# Focused Windows acceptance: agent visual inspection 0.16.0

Status: NOT RUN. This procedure is not an acceptance result. Keep PR #21 and stacked
draft PR #22 unmerged. Do not repeat the passed `safe` precise-pick interaction or
relabel the remaining old manual cases as passed.

Read `AGENTS.md`, `LIVE_AGENT_VISUAL_INSPECTION.md`, and
`VISUAL_INSPECTION_REVIEW.md`. Recover the actual visual branch and exact-head CI
before testing; do not substitute an earlier native-only checkpoint. The runtime
checkpoint is `bef9f0135e7a7c1b15cdba0d140624fb975c8418`; subsequent documentation
commits are acceptable only after verifying the runtime diff and exact tested HEAD.

## 1. Isolate and identify the installed runtime

Preserve existing worktrees, ignored evidence, GUI work, picks, selection and
unrelated overlays. Never reset, clean, force-push, recreate retained branches or
merge either PR. Use a clean isolated worktree at the verified visual branch HEAD
rather than switching a conflicting checkout. Record SHA, base SHA, package path,
interpreter/dependencies, and module hashes. Install Python 0.16.0 noneditably into
a dedicated environment. Verify all 34 installed source module hashes.

Run the complete installed suite, `python -m compileall -q src scripts tests`,
working and complete-parent `git diff --check`, and inspect the full native diff.
The runtime checkpoint has 1393 passing tests; the focused five modules have 182:
`test_native_camera_policy.py`, `test_inspection_camera.py`,
`test_live_inspection.py`, `test_inspection_tools.py`, and
`test_visual_inspection_fixtures.py`. Configure MSVC and rerun compiler-gated tests;
skips are not passes. Distinguish compiled policy tests from a full plugin build.

**A native rebuild is required:** qMCPBridge 0.13.0 / workflow revision 9. Follow
`cloudcompare-plugin/qMCPBridge/README.md`: CloudCompare v2.13.2 source, compatible
Qt 5.15.2 msvc2019_64 and MSVC Release/x64, target `QMCP_BRIDGE_PLUGIN`. Use an
isolated plugin directory and preferably a separate visible acceptance host on an
unused loopback port. Do not overwrite a loaded DLL, normal MCP configuration,
unsaved GUI work, or the installed CloudCompare core libraries. Record the actual
DLL hash, host executable/version/PID, bridge version/capabilities and port owner.
The successful Linux build is not Windows ABI or GUI acceptance.

Use the exact installed Python MCP stdio process for the visible tests. Keep it
alive through inspect/propose/confirm/validate/release: process restart invalidates
inspection IDs. Counted TCP replay from regression is not independent native-host
query accounting. Report native counts only at the level actually measured.

## 2. Small deterministic visible fixtures first

Generate outside Git with the installed interpreter:

```text
python scripts/generate_visual_inspection_fixtures.py <new-evidence-directory>
```

Verify all nine PLY SHA256 values against the generated manifest before use. Cases:
plane, parallel_planes, ring, cylinder, shifted_plane, scaled_plane, rotated_plane,
noisy_plane, clutter_plane. Fixture files store global double coordinates; they do
not encode CloudCompare global shift/scale metadata. Establish and verify the
actual host frame for shifted/scaled cases, rather than treating replay conversion
as visible-host coverage. Fixture threshold 0.02 is not a fan calibration.

For each declared camera exercise record baseline camera, session/window,
viewport dimensions, scene/selection/overlay metadata and source evidence before
moving. Exercise get/save, move/get, capture/move/restore/compare; all six declared
axis views and isometric; positive/negative orbit; pan; zoom in/out; source focus;
global center plus width; global bounded-region focus; large global coordinates and
nonunit source global scale. Confirm the retained standard-view tool still works.
Use the latest camera guard after every move. Inspect actual returned PNGs to verify
orientation, framing and plausible navigation; numerical replay alone cannot do so.

Verify PNG bytes, dimensions, reported content hash and camera/capture fingerprints.
Restored camera equality is required within its documented scope, not identical
framebuffer pixels. Preserve baseline tokens until their exercise is finished.
Where practical on these small fixtures, compare all source coordinates before and
after, independently of the service's preservation flag. Record attributes checked;
do not upgrade coordinate equality into whole-cloud attribute equality.

Negative probes must cover booleans as numbers, nonfinite/huge inputs, zero direction,
nearly parallel direction/up, stale expected-camera fingerprints, wrong session,
window and tokens, unsupported camera mode/display scale, and a source associated
with another display. Test viewport resize/window changes where available. A refusal
must not move the camera or mutate source/selection/unrelated overlays. After an
owned-operation error verify restore; after a deliberate concurrent human move,
verify that automatic restore refuses rather than overwrites that move. Report
unsupported or unavailable host scenarios BLOCKED, not passed by replay.

## 3. Bounded inspection and semantic lifecycle

Through actual installed MCP stdio, run the fixed fixture thresholds/kinds/views
and verify limits, geometry candidates, real PNG return and camera restoration.
Keep geometric refusals; do not change ROI, threshold, scale, limits or clutter to
manufacture success. No new inspection overlays or drawn A/B/C labels are promised.
Never clear an unrelated overlay group to make the screenshots cleaner.

Review actual returned images, issue a reviewed proposal, then exercise explicit
yes/no/unsure, wrong fingerprints, latest-answer supersession and conflicting
roles. Scripted fixture answers are synthetic test inputs, not human acceptance.
On disposable fixtures only, change observed geometry or selection/overlay context
and verify permanent staleness, including after reversal. Camera movement alone
must not invalidate otherwise fresh frozen capture evidence. Keep reports and
fingerprints before releasing process-local inspections and owned camera tokens.

## 4. Fan semantic demonstration, only after preceding gates

Verify authorized `fan_project.bin` SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
Retained source count is 406276; rediscover the actual source ID and frame.
Do not immediately reconstruct the fan or modify the source.

Declare a distance threshold from independent coordinate/noise information before
looking at fit results. Record unknown units explicitly; a native-coordinate
inspection is not a calibrated dimensional model. Do not search thresholds or
reuse 0.02 merely because it worked for synthetic fixtures.

The agent stores baseline camera, summarizes the source, requests a bounded set of
views and geometric candidates, and actually reviews the returned PNGs. Ask a small
number of understandable semantic questions, up to roughly 3-6 when evidence
supports them: for example, whether a supported plane is the mounting face or a
supported cylinder is the hub. Fewer supported questions or a geometric refusal
are legitimate outcomes; never invent candidates to meet a quota. Metadata labels
must be tied to a clearly described captured feature, not presented as if a label
was already drawn in the viewport. Do not claim complete hole-pattern or through
feature detection from the semantic vocabulary alone.

Obtain the human's actual answer. Bind the explicit yes/no/unsure and exact answer
text to the issued reviewed proposal fingerprint, then validate. If the human has
not answered, report confirmation pending; never infer it. Save the feature-intent
packet with numerical, capture, proposal and confirmation provenance. Restore the
baseline only while ownership is established; otherwise report the retained token
and conflict without overwriting user navigation. Release only owned resources.

A full fan CAD model is not required. No fan ROI/profile reconstruction call,
result-driven fitting search, CAD IR, Fusion construction, tiny-vertex click test,
or merge is authorized by this gate. Sampled freshness is not full fan equality.

## 5. Required result

Report PASS / FAIL / BLOCKED per gate, exact HEAD/base and installed paths/versions,
DLL/module/fixture hashes, full and focused test counts including skips, actual
stdio versus replay versus visible-host evidence, source/selection/overlay checks,
camera restore comparisons, observed images and questions, actual answers and
fingerprint/staleness results, and residual limitations. Preserve evidence outside
Git unless intentionally committing a compact report. A host or environment block
is not automatically a product defect. Fix only a reproducible defect in a small
verified commit on the existing visual branch; rerun affected tests and exact-head
CI before using that new runtime. Do not merge either PR.
