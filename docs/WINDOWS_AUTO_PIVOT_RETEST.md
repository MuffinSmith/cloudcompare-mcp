# Focused Windows automatic-pivot fan continuation — 0.16.2

This is the narrow successor to `WINDOWS_CAMERA_GUARD_RETEST.md`. Do not repeat
already-passed broad synthetic acceptance unless a regression appears.

Expected branch: `feature/live-agent-visual-inspection`.
Exact HEAD must be taken from the current PR/AGENTS after CI, not guessed from this
pre-CI draft.

Required runtime:
- Python 0.16.2, noneditable isolated install;
- qMCPBridge 0.13.2 / workflow revision 9 rebuilt Release/x64 against the documented
  CloudCompare 2.13.2-compatible Qt/MSVC toolchain;
- capabilities must advertise `cc-camera-auto-pivot-v1` and that saved camera tokens
  can suspend automatic pivot.

## 1. Automated gates

Verify exact branch SHA, installed package/version/hash set, rebuilt DLL hash, host
PID/port ownership and current PR/CI state. Run the complete installed Python suite,
the focused camera/inspection modules, compileall, whitespace/native diff checks and
the separate production Qt helper CTests. Qt helper expected count is 37 for this
checkpoint. Skips are not passes.

## 2. One disposable visible control test

Use one small hash-verified fixture. Through actual installed MCP stdio:

1. Read baseline camera; record `auto_pick_pivot_at_center`.
2. Save with `save=true, suspend_auto_pivot=true`.
3. Confirm the returned state reports automatic pivot FALSE and the token-owned
   suspension while camera pose/full fingerprint remains otherwise coherent.
4. Focus and perform one declared look; capture at most two PNGs.
5. Restore using the current navigation guard.
6. Release the token; confirm the original auto-pivot mode is restored and inspect
   the returned post-release camera state.
7. If original auto-pivot was TRUE, the post-release navigation guard should match
   the original baseline. Record control-field difference separately from pose.

On the disposable fixture only, explicitly model an external auto-pivot re-enable
while the token owns FALSE. The next guarded movement/capture must refuse without
performing the requested move. Release must preserve/report the external override.
Do not use this conflict probe on the fan.

## 3. Authorized fan camera-only preflight

Verify fan SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.

Rediscover the visible 406276-point source and verify shift/scale/frame. Historical
entity IDs, process IDs and ports are not reusable identities. Physical units remain
unknown.

Keep one installed MCP stdio process alive. Perform exactly:

1. baseline get;
2. save with `suspend_auto_pivot=true`;
3. focus the explicit fan cloud;
4. one declared look;
5. up to two guarded viewport captures;
6. guarded restore;
7. release and verify the returned post-release camera state.

Do not change styling, introduce sleeps, refresh a failed guard, loop until stable or
loosen equality. If any step refuses, stop and preserve request, native stage,
reference/current snapshots, parameter/control field deltas and release state.

## 4. One fan inspection only after camera preflight passes

Use explicit rediscovered `cloud_id`, distance threshold 0.15 global native units,
`sample_limit=1024`, views `top`, `front`, `isometric`, kinds `plane`, `cylinder`, and
`restore_camera=true`. Do not tune those values to improve the result.

Review the actual returned PNGs and numerical candidates. If evidence supports it,
issue a small number of reviewed semantic proposals and ask the human understandable
questions. Bind only the human's actual explicit yes/no/unsure answer text to the
issued proposal fingerprint and validate freshness. No answer means confirmation
pending, not inferred yes.

No precise point clicking, fan ROI/profile reconstruction, clutter removal, success-
driven threshold/scale/target/layer search, CAD IR, Fusion work or merge is part of
this gate.
