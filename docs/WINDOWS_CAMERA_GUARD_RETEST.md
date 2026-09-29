# Focused Windows guard and fan continuation — 0.16.1

Resume `feature/live-agent-visual-inspection`, stacked draft PR #22, without
reset/clean/force-push/recreating branches or merging #21/#22. Recover actual refs,
AGENTS.md and exact-head push/PR CI. Reconcile newer legitimate work, not backwards.
Base remains c35916d4badf5bdac815417d88cdffba56b537b7; accepted main remains
2b385820ecfcb84d79aaf59ad5965e748f961466. Read CAMERA_GUARD_RECOVERY.md and
WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md before the historical full procedure.

## Preserve and diagnose the prior result

Read actual raw files under
`C:/Users/Admin/Documents/CloudCompare/mcp-live-test/acceptance-0160-5559f09-20260927/`
(ACCEPTANCE_REPORT.md, fan-feature-intent.json and linked evidence). Record the
original failing request, exact error, camera snapshots and phase where available.
The previous style-drift explanation was a hypothesis, not established root cause.
The previous full fingerprints excluded derived zNear/zFar already.

Preserve the passed 1393/182 tests, nine fixtures and 36 reviewed PNGs as historical
0.16.0 evidence. Do not repeat all manual fixtures or precise vertex picking as a
prerequisite. Original unsaved work, selection, picks and unrelated overlays stay
untouched. Keep new evidence in a separate directory outside Git.

## Exact installation and automated checks

Use an isolated worktree/noneditable environment, without switching a conflicting
checkout or changing normal MCP configuration. Install Python 0.16.1. Rebuild
qMCPBridge 0.13.1 against the documented CloudCompare 2.13.2-compatible Qt/MSVC
Release/x64 toolchain. Do not overwrite loaded DLLs or installed core libraries.
Use an isolated visible host and unused loopback port; rediscover PID/port ownership.

Verify all 34 Python source hashes and the rebuilt DLL hash. Verify actual public
ping/capabilities both report native 0.13.1, revision 9, camera guard contract
cc-camera-guard-v1 and diagnostics contract cc-camera-diagnostics-v1. Verify the
installed MCP tool schema advertises the new exclusive expected guard field.

Run full installed pytest (baseline 1441, zero skips), compileall and complete-parent
whitespace/native diff checks. Run the seven focused modules (230 total):
test_camera_guard_legacy_transport, test_camera_guard_recovery, test_inspection_camera,
test_inspection_tools, test_live_inspection, test_native_camera_policy,
test_visual_inspection_fixtures. Configure MSVC for compiler-gated tests; skipped is
not passed. The added legacy-transport test checks the old native capture allowlist.

Also run the 35 standalone Qt CTests using the compatible Qt prefix/PATH:

    cmake -S tests/native/camera_guard -B <isolated-guard-build> -DCMAKE_PREFIX_PATH=<compatible-Qt-prefix>
    cmake --build <isolated-guard-build> --config Release
    ctest --test-dir <isolated-guard-build> -C Release --output-on-failure

These are production-helper tests, separate from Python counts and visible GUI tests.
Keep the same installed MCP stdio process alive across inspection, review, actual
human answers, validation and release. Never reuse evidence IDs after restart.

## Small visible synthetic gate (one disposable fixture, at most six PNGs)

Verify one unchanged deterministic fixture's hash/count, frame and initial state.
Exercise get/save, one deliberate move, two stable captures and guarded restore.
Use current returned guards after each deliberate move; compare both restoration
flags and record actual parameter differences, not only hash strings.

On this disposable fixture only, change global default point/line styling through
the visible host without navigating. This is NOT source-entity editing. Verify
full fingerprint changes, navigation guard stays equal, guarded capture succeeds
with actual new style, and modern restore preserves that style with guard equality
true/full equality false. The legacy full guard must refuse the same drift.
No new mutation tool or source change is needed to induce this probe.

Use actual MCP stdio for camera tools, capture_live_view({}) and bounded inspection.
For explicit expected-guard capture use the installed Python/native helper described
in CAMERA_GUARD_RECOVERY.md; report it separately, not as MCP stdio. The public
no-argument capture tool does not forward arbitrary expected-guard arguments.

Induce one independent camera move on the disposable fixture, then try the old
move/restore guard. Both must refuse without overwriting the intervening pose, with
field-level diagnostics. End that session after retaining evidence and release its
token; do not silently refresh the guard and retry the refused restore. Any explicit
fixture cleanup is a separate declared operation, never a concurrency-pass claim.
Verify source metadata/sample, selection and unrelated overlays remain preserved.

## Fan camera preflight, then semantic inspection

Only after internal and synthetic gates pass, verify fan_project.bin SHA256:
79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Rediscover the visible 406276-point cloud and frame (previous shift zero/scale1).
Old ID355/PID9364/port8766 are historical, not current identifiers. Physical units
remain unknown. Keep 0.15 GLOBAL native units as the fixed threshold only for the
same verified coordinate frame; do not silently assume millimetres or tune it.

Predeclare a short camera-only preflight: baseline/save, focus, one declared look,
up to two captures, then guarded restore/release. Store returned states after every
operation. Do not change style on the fan, try arbitrary delays, loop until stable,
remove fields from the guard, widen equality tolerance or force restoration.

On any unexpected refusal, STOP this preflight and record its exact request,
expected/current full and guard fingerprints, phase, changed field names AND values.
Retain native error_details and Python recovery/failure_diagnostics. Read current
state once for safe cleanup; release owned tokens but do not overwrite lost camera
ownership. Mark the fan continuation BLOCKED. Do not claim this patch fixed a
protected-field drift or reopen fitting with different parameters to manufacture PASS.

When preflight passes, perform one bounded inspect_live_part through installed MCP:
explicit cloud_id, distance_threshold 0.15, sample_limit 1024, views top/front/isometric,
kinds plane/cylinder, restore_camera true. Retain all reported discovery refusals.
Do not search thresholds, sample limits, ROIs, depth signs, targets or layers.
Document fit attempts separately from returned usable fits: discovery precedes the
inspection camera moves. No packet does not necessarily mean no solver was called.

Actually review returned fan PNGs and numerical candidates. Ask a few supported,
understandable semantic questions (3–6 only when justified; fewer is valid), not
precise clicks. No on-screen A/B/C labels are claimed: identify candidates clearly
using the image, reported geometry and concise descriptions. Issue reviewed proposals
before asking, bind the user's exact actual yes/no/unsure answer to the issued
fingerprint, and validate. Scripted answers are not human acceptance; without an
actual answer report confirmation pending and preserve the live inspection session.

Save the feature-intent packet and question/answer evidence outside Git before
release. Restore only owned state, report navigation/full equality separately and
release only owned resources. Verify source count/frame, observed sample coverage,
selection and overlays; do not claim full-cloud equality from sampled checks.
No fan ROI/reconstruction, clutter removal, CAD IR, Fusion or merge is authorized.

## Return

PASS/FAIL/BLOCKED per gate; exact branch HEAD, base, installed versions/hashes and CI;
Python/Qt counts; actual MCP versus direct Python/native versus replay versus visible
image evidence; original/new refusal phases and precise field deltas; restoration
flags; source/selection/overlay coverage; actual questions/answers/confirmation state;
raw evidence paths. Reproducible additional defects stay on this existing branch in
small verified commits with affected tests and exact-head CI, never weakened guards.
