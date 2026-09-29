# CloudCompare automatic-pivot recovery

This document records the root cause and narrow recovery contract for the Windows fan
camera refusal observed on Python 0.16.1 / qMCPBridge 0.13.1.

## Observed Windows failure

The authorized fan preflight successfully saved the baseline camera and performed a
guarded focus. Before the next declared look, a fresh native state showed protected
pose changes with no user-approved navigation: camera-center Z moved from
628.4272923203682 to 693.8733201556884; pivot Y moved from -4.380668640136719 to
-5.092193828031531; pivot Z moved from 134.0451889038086 to 199.49121673912876.
Focal distance was effectively preserved. The exact guard therefore refused the look
at `movement.precondition`. That refusal was correct for the 0.16.1 contract.

No fan fitting, inspection packet, semantic proposal, human question/answer or
confirmation followed that refusal.

## CloudCompare v2.13.2 source cause

CloudCompare's `ccGLWindowInterface` initializes `m_autoPickPivotAtCenter` enabled.
During rendering, when automatic pivot is enabled, the mouse has not moved and a
center-screen candidate exists, the render path calls:

`setPivotPoint(pivot, true, false)`

The second argument is `autoUpdateCameraPos=true`. In
`ccGLWindowInterface::setPivotPoint`, CloudCompare computes a new camera center when
that flag is true. In orthographic mode it explicitly sets camera Z from the focal
distance plus the new pivot Z, preserving zoom while translating the pivot/camera.
This matches the measured fan transition.

`setAutoPickPivotAtCenter(true)` also requests a redraw so the automatic center pivot
can be updated. Therefore merely toggling the host behavior back on must itself be
part of restoration evidence.

Relevant upstream file at tag v2.13.2:
`libs/qCC_glWindow/src/ccGLWindowInterface.cpp`.

## Contract in 0.16.3 / native 0.13.2

The existing camera guard is not relaxed. Instead the host behavior is owned
explicitly and narrowly:

1. `view.camera save` accepts optional `suspend_auto_pivot=true`.
2. Only such a save token owns a temporary FALSE value for center-screen automatic
   pivot on that window.
3. Ordinary save tokens preserve prior behavior and do not touch automatic pivot.
4. Only one automatic-pivot suspension token may exist for a given window at once.
5. Camera snapshots report additive `cc-camera-auto-pivot-v1` metadata and the current
   auto-pivot boolean. Those additive fields do not rewrite the legacy full camera
   fingerprint or weaken `cc-camera-guard-v1`.
6. If the setting becomes TRUE while a suspension token owns FALSE, movement/capture
   refuses as an ownership conflict. Capture checks that ownership before redraw, after
   the redraw/event turn, and after framebuffer grab so a control-only override cannot
   slip through merely because the pose has not moved yet.
7. Every camera movement completes one event turn before success is returned. A
   delayed protected pose change becomes `movement.after_redraw` immediately rather
   than poisoning the next unrelated request.
8. Restore occurs with auto-pivot still suspended and retains the exact navigation
   guard checks.
9. Release restores the original auto-pivot mode. If enabling it makes CloudCompare
   request a redraw, that event turn is processed and the resulting camera state is
   returned. Bounded inspection requires the final navigation guard to match the
   saved baseline.
10. If an external user re-enabled the setting while the token owned FALSE, release
    preserves that external value and reports the override rather than silently
    overwriting it.

There is no guard refresh-and-retry loop, floating-point tolerance expansion, delay
search or acceptance of pivot/camera translations as harmless.

## Provenance boundaries

Automatic pivot is a host interaction control, not dimensional evidence. It is kept
outside the legacy full camera fingerprint for compatibility but is reported in every
new snapshot and in field-level diagnostics. Captured PNG bytes, full camera
parameters and source/scene evidence retain their existing provenance.

This fix does not authorize reconstruction, threshold changes, ROI search, target or
layer budget increases, clutter removal or semantic inference. The prior 0.15 global
native-unit threshold remains fixed only if the fan source frame is independently
verified unchanged.

## Post-release ownership boundary in 0.16.3

Windows 0.16.2 proved that the guarded restore can match the saved baseline exactly
while automatic pivot is still suspended, yet restoring CloudCompare's original
auto-pivot mode during release can immediately move the host camera. This is not a
reason to weaken the navigation guard or add a tolerance.

The authoritative safety gate is now the exact restore **before release**. Once that
restore succeeds, release relinquishes agent camera ownership while restoring the
original host control mode. Any returned post-release camera difference is retained
under `release_camera_difference`; `post_release_navigation_changed` states whether
the guard changed, and `post_release_change_scope` is
`host_or_human_after_release` when it did. The agent does not retry, restore again,
or claim final-pose equality.

A failed/stale guarded restore before release remains a hard refusal. Missing release
evidence, transport ambiguity, or source/context failures remain errors.
