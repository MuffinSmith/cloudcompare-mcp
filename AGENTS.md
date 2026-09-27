# Repository work and interruption recovery

## 0.14 Windows acceptance executed; awaiting explicit merge approval

Continue `feature/live-cad-datum-relationships`, based on accepted main
`e39949759c6386e5cd0387983c43a74f26e6a58e`. Inspect remote heads and local changes
before resuming; do not create a replacement branch or reset to historical SHAs.
Read `docs/LIVE_CAD_DATUM_RELATIONSHIPS.md` and
`docs/WINDOWS_DATUM_RELATIONSHIP_ACCEPTANCE.md` for the snapshot-only tools.
Python is 0.14.0; native remains accepted 0.12.0 / revision 8, with no native
source or build changes. Do not rebuild an unchanged DLL.

Real Windows acceptance ran at documentation checkpoint
`0a5ca860d8a2f425b7e8a83659f524ecf1ac6a9c`, whose runtime/product source is the
tested 0.14 checkpoint `477403785b0693e431227db79d1954326dbc081a`. All executed
product checks passed. The Windows suite produced 389 passes and 16 compiler-gated
skips; after configuring the installed MSVC environment those 16 native policy tests
also passed, for 405 distinct passing tests across the two runs. Synthetic MCP
dispatch, no-host stdio, bookkeeping, original fixture, rotated/large-translated
fixture, fan relationship analysis, and bounded source-integrity checks passed.

The fan datum subtest is a retained **coverage limitation, not a product defect**:
bounded acquisition found two strong fan planes only 0.05599773824 degrees apart,
below the intentional 1-degree minimum, and did not find a robust nonparallel
secondary observation. No direction was invented and no tolerance was loosened.
The selected 460,198-point bearing-cap cloud received full exported XYZ/normals
equality coverage; other fan entities and fixtures retain the report's narrower
metadata-only coverage. Real native nonunit global scale remains untested (loaded
scales were 1; offline scale 2.5 covered bookkeeping only).

Do not request another Windows run solely to turn that fan acquisition limitation
into a synthetic success. A future targeted fan-datum exercise is useful only if a
robust nonparallel measured feature can actually be acquired. No product defect issue
was opened. The branch is awaiting the user's explicit merge decision. Do not merge
automatically; CI/numerical/Windows passes are not merge authorization.


## Current accepted baseline

The user explicitly approved merging the accepted 0.13 increment. PR #10 merged
`feature/live-hole-patterns` into `main` at
`8c09f27dfde6c44ed38a63c9f8a1d6124ae4a52a`.
Acceptance issue #9 is closed as completed; defect #11 was already closed after
its focused real-Windows retest. Do not repeat or reopen these completed gates
merely because a chat or container restarted.

The merge result has the same complete tree as the CI-passing documentation
checkpoint `b0509dedcd0cfc72ae306a6d79dcb8af4c6bf1da`. The only merge conflict was
older AGENTS.md development guidance on main versus the completed-acceptance
checkpoint. Resolution commit `aa92f3b77a3286c777f489bedda94b2d18a5e544` retained
the latter without changing any file relative to that tested checkpoint.
This post-merge instruction update is documentation only, not a new runtime.

The accepted product commit is `45377b281e9df2445dd52a5e84887611387ac1bd`.
The original broad Windows report remains attributed to
`2c3338e8ab45624feeaf56dc3b88f0bcf1ae6750`; the focused #11 retest covers the later
empty-region adapter change. Python is 0.13.0. The native bridge remains the
accepted 0.12.0 / workflow revision 8 and requires no rebuild for this merge.

Retain `feature/live-hole-patterns` and the accepted 0.12 branch intact. The 0.12
PR #8 merge was `38f92c1dd62fdba92a4fc51959289287ae6eaaed`; its accepted checkout
was `b62f9b4d238e7f169e76c36e630b2060320d261a`, with native/runtime baseline
`fc51824d9edf7328614653c57bf3644c1db02769`.

No post-0.13 development branch was started as part of this merge. For future
requested work, inspect current remote heads before selecting an existing lane or
creating a deliberate next-stage branch. Do not create replacement branches just
because a session restarted. Do not reset to historical checkpoints.

The older `feature/live-auto-feature-overlays` and `feature/live-candidate-overlays`
branches came from interrupted attempts. Leave them intact. Inspect their diffs
before deliberately porting anything useful; do not automatically merge divergent
implementations or create another replacement branch.

## Resume procedure

1. Read this file and `docs/LIVE_HOLE_PATTERNS.md`.
2. Inspect local status, remote branch heads, recent commits, and open issues.
3. Preserve unexpected local work. Never reset, clean, force-push, or discard it
   without explicit authorization.
4. Continue the appropriate existing lane with small reviewable commits. Verify
   each returned commit SHA before claiming that a change was saved.
5. Require both completed acceptance and explicit user approval before future
   merges into `main`. Passing tests alone is not automatic merge authorization.

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

## Completed 0.13 acceptance and empty-region gate

Issue #11 is closed as completed after its focused real-Windows retest at
`45377b281e9df2445dd52a5e84887611387ac1bd`. The tester recorded the combined scoped
PASS on #9. After user merge approval, PR #10 was merged and #9 closed.
Authoritative acceptance records:

- Original broad report:
  https://github.com/MuffinSmith/cloudcompare-mcp/issues/9#issuecomment-5852430792
- Focused #11 completion:
  https://github.com/MuffinSmith/cloudcompare-mcp/issues/11#issuecomment-5852560616
- Combined acceptance and coverage limits:
  https://github.com/MuffinSmith/cloudcompare-mcp/issues/9#issuecomment-5852565296

Treat `docs/WINDOWS_HOLE_PATTERN_ACCEPTANCE.md` and
`docs/WINDOWS_EMPTY_REGION_RETEST.md` as retained procedures, not outstanding work.
Historical pre-acceptance wording in those documents does not reopen a completed
gate. Do not request another fan run, transformed-fixture run, manual-drag test,
reinstall or unchanged-DLL rebuild for a documentation-only change or chat restart.
Compare any later runtime change against the accepted product commit and assess
only the required targeted retests.

The empty adapter is confined to the new live hole tool. Selector-specific native
no-match responses become explicit empty results; invalid sources, malformed
requests and disconnected transport remain errors. Legacy region-tool and native
semantics remain unchanged. Real-host acceptance is distinct from replay-peer tests.

Retain coverage limits: fan point integrity covered the selected bearing-cap
XYZ/normals, not every fan cloud; other clouds received scene-metadata checks.
Nonempty duplicate mappings remain unit-test coverage. The transformed fixture
is not additional nonidentity global-shift bookkeeping coverage. Physical units
and physical-hole identity remain unconfirmed. Detailed reports and raw evidence
remain outside Git, with each run attributed to its actual checkout/runtime.
