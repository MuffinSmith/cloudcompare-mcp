# Post-release camera ownership — Python 0.16.3 / native 0.13.2

Resume existing `feature/live-agent-visual-inspection` and stacked draft PR #22.
PR #21 base remains `c35916d4badf5bdac815417d88cdffba56b537b7`; accepted main remains
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Neither PR may be merged without
separate explicit authorization. Never reset/clean/force-push/recreate retained branches.

## Preserved Windows evidence

Read `docs/WINDOWS_0_16_1_PARTIAL_ACCEPTANCE.md` and
`docs/WINDOWS_0_16_2_PARTIAL_ACCEPTANCE.md`. The 0.16.2 Windows retest at exact HEAD
`728e37214c591187d9cb06af573f091011f940ed` passed Python/native installation,
1,447 complete Python tests, 37/37 Qt tests and the normal disposable automatic-pivot
cycle. The external UI re-enable probe was not executable because Windows UI
automation could not target the isolated host; this alone is not a product failure.

On the authorized fan, save/focus/look/capture and guarded restore reached an exact
baseline match while the token still owned automatic-pivot suspension. No native
request refused. Release restored CloudCompare automatic pivot to ON, after which
the host moved camera-center Z and pivot Z by about 0.000185967 host units. The old
0.16.2 Python policy incorrectly treated that post-release motion as a failed restore,
so the tester correctly stopped before fan inspection/human confirmation.

The focused Windows command contained **236**, not the earlier estimated 237, passing
tests; two target-ROI stdio tests passed separately. The tested native 0.13.2 DLL
SHA256 is `88D0B067D535BAFE026525D0A1CEC61836F7B91D50E870F455B2F537E2D2A154`.

## 0.16.3 contract correction

Native qMCPBridge 0.13.2 remains unchanged. Python 0.16.3 moves the semantic ownership
boundary to the successful exact guarded restore *before* release. Release deliberately
returns CloudCompare's original host control mode; subsequent host automatic-pivot or
human motion is not agent-owned and must not trigger a second overwrite.

Bounded inspection still requires exact ownership through save/focus/look/capture and
exact guarded restore. Only after that succeeds may release occur. Release evidence is
retained even when its final navigation guard differs:
- `restored_while_owned=true`;
- `release_camera_difference`;
- `post_release_navigation_changed`;
- `post_release_change_scope=host_or_human_after_release` when changed;
- original auto-pivot restoration / external-override fields.

There is NO tolerance, sleep/stabilization loop, refreshed-guard retry or second
restore after release. A stale/failed restore before release remains a hard refusal.
The final post-release pose is not claimed equal to baseline when it is not.

Read `docs/AUTO_PIVOT_RECOVERY.md` and `docs/WINDOWS_AUTO_PIVOT_RETEST.md`.

## Exact internally green checkpoint

Runtime checkpoint: `ae03248065feea07e80f8f956cfd36ce6f4ac8f6`.

Observed exact-head validation:
- push CI `36415703006`: SUCCESS;
- PR integration CI `36415706720`: SUCCESS;
- fresh Python install/full suite: **1449 passed, zero skips**, 130.06 s;
- compileall and `git diff --check`: PASS;
- production Qt camera-guard helper: **37/37 passed**;
- actual qMCPBridge build against CloudCompare v2.13.2: PASS;
- qMCPBridge source is unchanged from the Windows-tested 0.13.2 DLL;
- the seven focused modules now contain **238 tests** by source count (the 0.16.2
  Windows command had 236; two new 0.16.3 release-boundary regressions were added).

The first 0.16.3 CI attempt at `b987204e...` failed one new assertion because the
successful recovery summary omitted its raw release object. That evidence object was
then retained additively at `ae032480...`; no ownership rule was weakened.

CI/replay are not visible Windows fan acceptance.

## Focused Windows continuation

Install Python 0.16.3. Reuse the already-tested qMCPBridge 0.13.2 DLL only if its exact
SHA256 matches the value above; otherwise rebuild. Do one minimal disposable release
boundary fixture, then repeat the bounded fan camera preflight. Post-release motion is
reported evidence rather than failure only after exact owned restore succeeded.

If fan preflight passes, run ONE bounded inspection with explicit rediscovered cloud,
threshold 0.15 GLOBAL native units only if frame unchanged, sample_limit 1024, views
top/front/isometric, kinds plane/cylinder. Review real PNGs/candidates and ask only
supported semantic questions. Bind only actual explicit human yes/no/unsure text.

Authorized fan SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`; retained
count 406276. Rediscover IDs/PIDs/ports/frame; physical units remain unknown.

No fan ROI/profile reconstruction, success-driven numerical tuning, clutter removal,
CAD IR, Fusion work, source mutation or merge is authorized in this gate.
