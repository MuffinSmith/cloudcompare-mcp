# Focused Windows post-release continuation — Python 0.16.3 / native 0.13.2

This is the narrow successor to the 0.16.2 Windows run. Do not repeat already-passed
broad synthetic or automatic-pivot acceptance unless a regression appears.

Expected branch: `feature/live-agent-visual-inspection`. Read current AGENTS/PR first
and use the actual exact HEAD after CI.

Required runtime:
- Python **0.16.3**, noneditable isolated install;
- qMCPBridge **0.13.2 / workflow revision 9**. Native code is unchanged from the
  already-tested 0.16.2 DLL, so the verified DLL may be reused if its SHA256 is
  `88D0B067D535BAFE026525D0A1CEC61836F7B91D50E870F455B2F537E2D2A154`; otherwise
  rebuild with the documented CloudCompare 2.13.2-compatible Qt/MSVC toolchain.

## 1. Automated checks

Verify exact branch SHA, installed Python hashes, DLL hash, host PID/port ownership,
ping/capabilities and CI. Run the complete installed Python suite and focused camera/
inspection set. The prior Windows focused command correctly counted **236**, not 237,
plus two target-ROI stdio tests run separately. Run compileall. Native 37/37 Qt tests
need not be repeated if the DLL is byte-identical to the already-tested 0.13.2 DLL;
if rebuilt, rerun them.

## 2. Minimal post-release control fixture

Use one disposable fixture. Through actual installed MCP stdio, perform baseline get ->
save with `suspend_auto_pivot=true` -> focus -> one look -> at most one capture ->
guarded restore -> release. Verify:

- the guarded restore matches baseline exactly while the token still owns suspension;
- recovery reports `restored_while_owned=true`;
- release restores the original automatic-pivot control;
- if release changes the navigation guard, the call still succeeds and records
  `post_release_navigation_changed=true`, the exact `release_camera_difference`, and
  `post_release_change_scope=host_or_human_after_release`;
- no second restore, refreshed-guard retry, sleep, or tolerance is used.

The prior external UI re-enable probe is optional because Windows UI automation could
not reliably target the isolated host. Its deterministic/native negative coverage is
already retained; inability to perform that UI probe alone is not a blocker.

## 3. Authorized fan camera-only preflight

Verify fan SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.

Rediscover the visible 406276-point source and verify shift/scale/frame. Keep one MCP
stdio process alive. Perform exactly baseline get -> save with suspension -> focus ->
one look -> up to two captures -> exact guarded restore -> release.

The preflight PASSES if all owned operations and the exact pre-release restore pass,
the token releases, and original automatic-pivot control is restored/reported. A
post-release guard change is evidence, not a failure, and must be reported exactly.

Any refusal before release remains BLOCKED. Never refresh/retry a stale guard or force
a second restore after release.

## 4. One fan inspection after preflight

Use explicit rediscovered `cloud_id`, distance threshold `0.15` global native units
only if the frame is unchanged, `sample_limit=1024`, views `top`, `front`,
`isometric`, kinds `plane`, `cylinder`, and `restore_camera=true`. Do not tune these
values for success.

Review actual returned PNGs and numerical candidates. Ask only supported, concise
semantic questions. Bind only the user's actual yes/no/unsure answer and exact text
to the issued proposal fingerprint, then validate freshness. No answer means pending.

No precise point clicking, fan ROI/profile reconstruction, clutter removal, parameter
search, CAD IR, Fusion work, source mutation, or merge belongs to this gate.
