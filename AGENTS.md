# Repository work and interruption recovery

## Active development lane

Continue `feature/live-feature-candidates-overlays` for the 0.12 candidate-discovery
and visible-overlay work. Do not create a new branch merely because a chat, tool
session, or execution environment restarted.

The recovery point preceding this instruction was
`22a4b2a8fd62d231d1a0618594c3a9399ed0b3d2` (circle-refinement hardening).
Resolve the current remote head before continuing; do not reset to this historical
checkpoint. `main` already contains the accepted 0.11.0 retest at
`c2dfc46c3e445efa6a50afa5997297567f2d80ab`.

The older `feature/live-auto-feature-overlays` and `feature/live-candidate-overlays`
branches came from interrupted attempts. Leave them intact. Inspect their diffs
before deliberately porting anything useful; do not automatically merge divergent
implementations or create another replacement branch.

## Resume procedure

1. Read this file and `docs/LIVE_FEATURE_CANDIDATES.md`.
2. Inspect local status, remote branch heads, recent commits, and open issues.
3. Preserve unexpected local work. Never reset, clean, force-push, or discard it
   without explicit authorization.
4. Continue the existing active branch with small reviewable commits. Verify each
   returned commit SHA before claiming that a change was saved.
5. Keep `main` at its accepted state until the complete next acceptance passes.

## Testing boundary

Use the development container for every available numerical, unit, protocol,
CLI, static, and build check before requesting another Windows run. Test the
actual source, not a hand-written reference implementation presented as product
validation. Clearly distinguish exact-source tests, mocked boundaries, reference
calculations, native compilation, and real live-GUI checks.

An unavailable dependency, network failure, or missing CloudCompare build is a
validation limitation, not a passing test. Preserve the failure evidence locally.
Never claim a full suite, native build, or fan-project run that was not executed.

The Windows machine is for testing and reporting, not implementing fixes. Give its
assistant one copyable test prompt with the exact branch/head and minimal retest
scope. New defects belong in GitHub Issues; close them only after the required
retest passes.

## User workflow and data safety

- Keep CloudCompare visible for the user, but prefer structured geometry calls.
  Do not routinely capture viewport images or include point arrays in model context.
- The CloudCompare instance is a test system and may be closed/reopened without
  saving. This does not authorize deleting unrelated files or repository changes.
- `fan_project.bin` is an authorized disposable test dataset. Resolve its real path
  and use a working copy; do not assume it is in the repository or container.
- Discovery must preserve source geometry and attributes. Overlay operations may
  change only their explicitly managed objects. Never identify deletable user
  geometry by display name alone.
- Keep reports, raw logs, screenshots, fixtures, exported geometry, and test-run
  scripts/evidence outside Git. Reusable product tests and developer instructions
  belong in the repository; acceptance reports do not.

## Focused Windows recovery retest

After the Windows partial acceptance recorded on issue #7, use
`docs/WINDOWS_CANDIDATE_RECOVERY.md` for the remaining same-cloud move-out /
retry-clear check. Do not repeat the full fan acceptance or rebuild an unchanged
DLL merely because the chat restarted. This reduced scope applies only while all
product/runtime sources remain identical to the Windows-tested `fc51824` commit.
Keep the gate blocked until that live recovery check passes; policy tests with
test scene nodes do not substitute for it.
