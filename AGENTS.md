# Repository work and interruption recovery

## Accepted 0.15.1 profile topology increment (merge authorized)

The exact Windows-tested feature HEAD is
`e0043eab698e407cdb5df05ea4e827b6f05b1802`, based on accepted main
`efd2e7aff2e2c9a68fde83373b804450f20ebbe2`. Python is 0.15.1.
qMCPBridge remains accepted 0.12.0 / workflow revision 8; no native source or DLL
change is part of this increment.

Real Windows/CloudCompare acceptance completed successfully at that exact feature
HEAD. Applicable gates passed: checkout/runtime identity, complete regression,
snapshot multi-loop topology, original live topology fixture, rotated/large-translated
live fixture, truncation/assertion safety, coordinate bookkeeping, and source-integrity
checks. Windows regression was 455 passed with 16 compiler-gated native policy tests
initially skipped; all 16 then passed under the installed MSVC environment.
`compileall` and `git diff --check` also passed. No product defect was found.

Both snapshot and real-host topology fixtures recovered
`outer -> hole -> island` at nesting depths `0 -> 1 -> 2`, with source counts
210 / 64 / 32. Snapshot original measurements were outer area 272.0, hole radius
2.5, island radius 0.8. Snapshot transformed measurements were outer area
272.0000000083869, hole radius 2.500000001589996, island radius
0.8000000002119626. Real original measurements were 306 matched / 306 sampled,
outer area 272.0, hole radius 2.4999999992653312, island radius
0.799999993578975. Real transformed measurements were 306 matched / 306 sampled,
outer area 272.0000130808068, hole radius 2.5000003152777674, island radius
0.7999993434446816.

For the transformed real fixture, the mathematical translation was
`[100000000,-200000000,300000000]`, CloudCompare source global shift was
`[-100000000,199999000,-299999000]`, and global scale was 1. The MCP result
preserved that bookkeeping without applying it twice. Native nonunit-scale behavior
remains untested.

The bounded fan exercise was correctly BLOCKED by acquisition, not failed. The
retained `fan_project.bin` working copy produced cloud ID 359 with 406,276 points;
the selected slab contained 5,605 matched / 5,605 sampled points, 196 nonempty
section-grid cells, and signed offset span approximately -0.49951171875 to
0.4999237060546875. It was an ordinary filled/mixed scan slab, so the tester
correctly refused to assert `boundary_samples_only=true`. Do not repeat the 0.15.1
topology acceptance solely to force this fan subtest through. This is direct evidence
for the next filled-section boundary-extraction stage.

The user explicitly authorized merging this accepted increment. Preserve
`feature/live-cad-profile-topology` after merge. After merge, record the exact PR
and merge commit here, then start the next runtime lane from current main rather than
continuing development on this accepted branch.

## Accepted 0.15 first profile-reconstruction increment

The user explicitly approved merging the accepted first 0.15 increment. PR #14 merged
`feature/live-cad-profile-reconstruction` into `main` at
`6044907781593221170f2fdaaffd5fa207bf73b3`.

Python is 0.15.0. qMCPBridge remains accepted 0.12.0 / workflow revision 8 and did
not change. The accepted increment adds the pure-Python profile reconstruction core,
snapshot `reconstruct_section_profile`, live `reconstruct_live_section_profile`,
line/arc/circle fitting, bounded circle/rectangle/slot candidates, explicit ordering
assumptions, compact live acquisition, and source shift/scale provenance retention.

Real Windows acceptance initially exposed issue #13: dense committed slot fixtures
fragmented into extra two-point line slivers at tangent joins and across a cyclic cut.
The bounded Python fix at `ebec95d64df08231881d1b5451d1c7da918784b7` added
regression coverage for the exact generated fixtures. Focused real-Windows retest at
`e2caa93ecc4ec983344f936416eceeb45f2a510a` passed: snapshot, original PLY and
rotated/large-translated PLY all returned exactly two lines plus two arcs and a
`slot_candidate` within the original acceptance bounds. Issue #13 is closed.

The final accepted feature-branch documentation checkpoint was
`58b4d866032d80c7e654afb33b36eddac841ca44`; its CI passed. Do not repeat the
full 0.15 first-increment acceptance, issue #13 retest, or fan exercise merely because
a chat restarted or documentation changed.

Retain the fan profile result as a coverage limitation, not a defect: the first
increment deliberately supports only one sufficiently simple closed loop under
`polar_closed_loop`. The real fan section contained topology that did not justify
that assumption. Later 0.15 work should address explicit boundary/loop extraction,
multiple loops/holes/islands, and non-star-shaped sections instead of weakening that
safety boundary.

Future profile-topology work must branch deliberately from current accepted main and
preserve the distinction between measured section samples, inferred loop topology,
fitted CAD primitives, and accepted manufacturing intent.

## Accepted 0.14 baseline

The user explicitly approved merging the accepted 0.14 increment. PR #12 merged
`feature/live-cad-datum-relationships` into `main` at
`e0e1b96e4f8b5a28e465303059ae3fbbbe767647`.

The accepted 0.14 runtime/product checkpoint is
`477403785b0693e431227db79d1954326dbc081a`. Later commits on the feature branch
were documentation/acceptance guidance only. Real Windows acceptance ran at
`0a5ca860d8a2f425b7e8a83659f524ecf1ac6a9c`: all executed product checks passed.
The final pre-merge branch head `099f861760793cf27cf9fb07017ceb303fc04e73`
recorded the acceptance outcome and coverage limits. Python is 0.14.0. Native
qMCPBridge remains accepted 0.12.0 / workflow revision 8 and did not change.

Retain the fan datum result as a coverage limitation, not a defect: bounded
acquisition on the selected bearing-cap component found two strong planes only
0.05599773824 degrees apart, below the intentional 1-degree datum minimum, and no
robust nonparallel secondary observation was acquired. Do not repeat the full 0.14
Windows gate merely to force a successful fan datum. The selected 460,198-point
bearing-cap cloud received full exported XYZ/normals equality coverage; other fan
entities and the fixture clouds retain narrower metadata-only integrity coverage.
Real native nonunit global scale remains untested; loaded scales were 1, while
offline scale 2.5 covered bookkeeping only.

Do not reopen or repeat accepted 0.14 testing for documentation-only changes or
chat restarts. Future work should branch deliberately from current accepted main,
preserve this evidence attribution, and require a new targeted Windows gate only
for behavior actually changed by that later stage.



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
