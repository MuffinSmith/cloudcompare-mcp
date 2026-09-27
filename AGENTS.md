# Repository work and interruption recovery

## Active development lane

The user approved the 0.12 merge and the next development stage. PR #8 merged
`feature/live-feature-candidates-overlays` into `main` at
`38f92c1dd62fdba92a4fc51959289287ae6eaaed`.

Continue **`feature/live-hole-patterns`** for the 0.13 Python-only mounting-hole
candidate grouping and spacing increment. This branch was deliberately created
from the accepted merge; do not create another merely because a chat or container
restarted. Resolve the current remote head and preserve any unexpected local work.
Read `docs/LIVE_HOLE_PATTERNS.md` on the active branch.

Keep the accepted 0.12 branch intact. Its accepted checkout was
`b62f9b4d238e7f169e76c36e630b2060320d261a`, with native/runtime baseline
`fc51824d9edf7328614653c57bf3644c1db02769`. The 0.13 increment changes Python only;
its new tools require targeted Windows acceptance, NOT reopening 0.12 or rebuilding
an unchanged DLL. Use `docs/WINDOWS_HOLE_PATTERN_ACCEPTANCE.md` on the active branch.
This approval covers merging 0.12 and starting 0.13, not automatically merging the
new unaccepted stage.

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
5. Require both completed acceptance and explicit user approval before merging
   into `main`. Passing tests alone is not automatic merge authorization.

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

## Completed Windows recovery gate

The final same-cloud move-out / retry-clear retest passed and issue #7 is closed.
The authoritative completion comment is:
https://github.com/MuffinSmith/cloudcompare-mcp/issues/7#issuecomment-5852167082

Treat `docs/WINDOWS_CANDIDATE_RECOVERY.md` as a retained test procedure, not an
outstanding task. Do not reopen the completed gate, repeat the full fan acceptance,
or rebuild an unchanged DLL merely because a chat restarted or documentation
changed. Compare current product/runtime sources against `fc51824` before relying
on the unchanged-runtime acceptance; assess targeted retests for future changes.

The recovery used a manual GUI drag. Automated dragging did not succeed and must
not be described as accepted. Previous broad synthetic/fan results retain their
original report/runtime attribution and coverage limitations. This checkpoint is
restart guidance; detailed reports and raw evidence remain outside Git.

## 0.13 empty-region follow-up

Continue `feature/live-hole-patterns` for issue #11. The targeted Windows report
for `2c3338e8ab45624feeaf56dc3b88f0bcf1ae6750` passed the executed nonempty pattern,
offline, transformed-coordinate and bounded fan checks, but empty native regions
returned errors. Use `docs/WINDOWS_EMPTY_REGION_RETEST.md` for the focused follow-up;
do not require another full fan run or rebuild the unchanged accepted DLL.

The fix adapts only the new live hole tool's selector-specific no-match responses.
Legacy region tools and native sources remain unchanged. Keep #11 and acceptance
issue #9 open until the required Windows retest passes; keep draft PR #10 unmerged.
A passing replay test uses real Python/MCP/TCP with a test peer, not a native host.
Preserve the original broad report's exact coverage and test-run attribution.
