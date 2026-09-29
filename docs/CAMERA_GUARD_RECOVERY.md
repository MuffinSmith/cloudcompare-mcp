# Camera guard recovery — Python 0.16.1 / qMCPBridge 0.13.1

This additive contract supersedes the camera-guard and restoration portions of
LIVE_AGENT_VISUAL_INSPECTION.md. Workflow revision remains 9. Install BOTH the
Python package and the rebuilt native plugin. Old full guards remain supported.

## Evidence boundary

Windows 0.16.0 synthetic acceptance passed at 5559f099; fan semantic acceptance
was blocked by a reproducible camera refusal. See
[the preserved report](WINDOWS_0_16_0_PARTIAL_ACCEPTANCE.md). The raw Windows files
have not been read in this development container. The summary does not identify
the changed field. This patch repairs a demonstrated design issue (display style
being conflated with navigation ownership) and exposes diagnostics; it does NOT
establish or claim to have resolved the fan's exact root cause.

Derived zNear/zFar and computed matrices were already outside the old fingerprint.
Removing them would not explain the old refusal. No tolerance or stabilization
retry has been introduced, and no actual camera movement is presumed harmless.

## Two fingerprints, explicit semantics

`camera_fingerprint` retains the exact original Qt JSON hashing of cc-camera-v1
identity, viewport size and all reported parameters, including point/line size.
Its bytes/meaning have not been redefined. It is full PARAMETER equality, not
framebuffer equality or an inventory of every GUI/render setting.

`camera_guard_contract: cc-camera-guard-v1` and `camera_guard_fingerprint` add a
separate domain. The guard includes the native session/window, viewport width and
height and every parameter EXCEPT `point_size`, `line_width`, `view_direction_host`
and `up_direction_host`. The last two are redundant with the guarded rotation.
Rotation, pivot, camera center, focal distance, projection, FOV/aspect, explicit
clipping, modes and display scale remain EXACTLY guarded. Unknown future parameter
fields remain guarded by default. No numerical rounding or equality tolerance.

`set_live_camera` accepts exactly one of `expected_camera_guard_fingerprint` or
legacy `expected_camera_fingerprint`, plus native_session/window_id. Both together
are invalid; a legacy digest is never silently interpreted as a navigation digest.
Use the returned current state after each deliberate move, not the baseline hash.
Python selects the new guard only when a valid new contract/digest pair is present.
Malformed pairs or a downgraded response refuse, rather than falling back silently.
Legacy 0.13.0 responses still use the old strict full guard. Legacy capture sends
ONLY expected_camera_fingerprint: the old native capture allowlist does not accept
session/window arguments. A dedicated regression checks this exact wire format.

Modern `restore` preserves CURRENT default point/line sizes, restoring only the
owned navigation state. It reports `restored_guard_equal` independently from
`restored_equal` (the unchanged full-parameter equality flag). `restoration_scope`
and `restored_full_reference_fingerprint` make the distinction explicit. A changed
style may therefore produce true/false respectively; that is NOT a full restore
pass. Legacy restore retains its strict full-parameter behavior. Tokens retain
actual native viewport copies, same-session/window/size checks and explicit release.

## Capture and refusal diagnostics

The native capture checks its precondition, redraws/processes one event turn,
reacquires the active window, and checks ownership again. Modern/default capture
can tolerate style settling before the grab; explicit legacy full-guard capture
cannot. Full parameter equality is required across the framebuffer grab itself,
even for modern capture. No automatic refresh/retry, extra geometry query or loop.
The returned PNG is bound to the actual post-redraw camera parameters and SHA256.
Native capture also returns `camera_before_redraw` and `redraw_difference`.

Refusal phases: `movement.precondition`, `capture.precondition`,
`capture.after_redraw`, `capture.after_grab`. Structured native `error_details`
use `cc-camera-diagnostics-v1`, with reference/current snapshots when available,
changed identity/parameter field names and `authorizes_retry: false`. A 32-state
bounded history supplies diagnostics only; it does not authorize anything or evict
the separately owned eight save tokens. Missing old references are reported, not
invented. Some non-guard validation/mode errors remain ordinary textual errors.

Python freezes finite diagnostic JSON up to 16 KiB. Inspection errors preserve the
original phase alongside restoration outcome, last-owned/current state and field
differences. Actual owned-field comparisons supplement the reported guard hash.
Neither diagnostics nor a newly read guard authorizes repeating a refused mutation.

`capture_live_view` remains the existing no-argument MCP tool: it returns actual
camera_state/PNG provenance, with native diagnostics preserved in error text.
For an explicit expected-guard capture probe use installed
`inspection_camera.capture(live.request, state)`; identify this as a direct installed
Python/native bridge probe, NOT MCP stdio. `inspect_live_part` internally performs
explicit guarded capture and retains transition metadata in its MCP evidence packet.

## Validation and preserved behavior

Local noneditable installed Python 3.13.5: 1441 passed, zero skips (105.18 s).
Combined focused suite: 230 passed (10.39 s), including all retained 182 and 48 new
cases. All 34 installed Python source module SHA256 hashes match. Compileall and
complete local baseline-tree whitespace checks pass. Some third-party dependencies
are reused; this is not pristine isolation. CI installs fresh dependencies.

New actual installed MCP stdio + event-aware counted TCP replay: 40 requests,
five geometry acquisitions, three capture attempts (two replay PNGs plus one refused
capture), scripted unsure answer, safe evidence release and conflict recovery.
The retained stdio cycle remains 44 requests, six acquisitions and two replay PNGs.
Neither is real-host query accounting, visual interpretation or human acceptance.

CI additionally compiles/runs 35 Qt CTests against the exact production guard helper,
then builds the actual plugin against CloudCompare v2.13.2. These Qt tests are NOT
included in the 1441 Python count. Local Qt development files are unavailable; no
local Qt pass is claimed. The native-first checkpoint 156c6952993f7f0cc2be03300288066d12f00b11
passed push CI 36391019292, including Qt tests and actual native build. Final exact
Python-integrated HEAD push AND PR runs must be checked separately in PR #22.

Existing fitting, discovery, datum, section, ROI, target, layer and reconstruction
solvers, deterministic fixture generator and native qMCPFusionWorkflow.cpp are
byte-unchanged. qMCPBridge enriches public ping/capabilities with 0.13.1 and guard
contracts. Existing server.py remains unchanged; its existing handlers delegate to
the updated components. Retained stdio test edits only adjust version assertions.

Hard inspection budgets, source/selection/overlay preservation, sampled/non-atomic
freshness limits, genuine concurrent-movement refusal and explicit actual-human
semantic intent remain unchanged. No new overlays, fan reconstruction or CAD IR.
Next: [focused Windows retest](WINDOWS_CAMERA_GUARD_RETEST.md). Both PRs stay draft.
