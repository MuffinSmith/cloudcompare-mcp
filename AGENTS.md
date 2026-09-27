# Repository work and interruption recovery

## 0.15.3 Windows acceptance complete — merge approval still required

Resume the EXISTING `feature/live-cad-section-layer-isolation` branch. Do not
recreate it after a disconnect. The exact real-Windows/CloudCompare tested HEAD is
`2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`, created from accepted main
`cb1ee9eab9c64ff4806036a6317606938faa22e6`. Python is 0.15.3.
qMCPBridge remains unchanged at accepted 0.12.0 / workflow revision 8; no DLL
rebuild occurred or is required.

Focused Windows acceptance completed successfully for the fixture, live-GUI,
handoff and safety gates. The bounded real fan analysis was legitimately BLOCKED;
no reproducible product defect was found, no GitHub issue was opened, no runtime
fix was made, and the branch was not merged. Detailed reports/raw evidence remain
outside Git.

Exact acceptance identity and regression:
- clean isolated Windows worktree at
  `2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`;
- accepted-main parent `cb1ee9eab9c64ff4806036a6317606938faa22e6`;
- isolated Python imports 0.15.3 from that worktree;
- visible CloudCompare 2.13.2, qMCPBridge 0.12.0;
- native source diff empty;
- Windows suite 610 passed with 16 compiler-gated native policy tests skipped in
  the ordinary shell, then all 16 passed separately under configured MSVC;
- compileall and both diff checks passed;
- final development CI run `36352480651` passed at the exact tested HEAD;
- the CI-installed suite at that source contained 626 tests.

All 12 freshly generated PLY fixtures matched manifest hashes and point counts.
Actual MCP stdio exposed:
- `analyze_section_layers`
- `analyze_live_section_layers`
- `reconstruct_section_layer_profile`
- `reconstruct_live_section_layer_profile`

Snapshot and real-GUI fixture behavior matched the contract. Single, sloped,
bounded-noise and transformed-single cases were ready. Parallel, three-layer,
partial-overlap, fan-like and transformed-parallel retained separate candidates.
Crossing, excessive-thickness and sparse cases blocked unsafe continuation. Every
live acquisition was complete and every acquired point was accounted for; compact
responses contained no raw point arrays.

Handoff/refusal checks passed. Original and transformed single cases selected
1,200 points with zero unselected points and produced one outer loop. Original and
transformed live parallel explicit choices selected 1,200 points and left 1,200
unselected; unchosen composites blocked. Stale fingerprints and snapshot-to-live
fingerprint reuse were rejected. Explicit selection did not bypass crossing, thick
or sparse evidence. A 100-point acquisition cap errored explicitly. A deliberately
too-small topology edge limit retained diagnostics while refusing topology.

The real live original-single primitive RMS residuals were, in fitted order:
`0, 0.074536, 0.022408, 0.048277, 0` for line, line, arc, line, line.
The transformed-single residuals were:
`0.046388, 0.059475, 0.186595, 0.048698, 0.0000103`.

Coordinate bookkeeping passed with limited integrity coverage. The transformed GUI
sources used CloudCompare global shift
`[-100000000, 199999000, -299999000]`, global scale 1, with no double application.
Before/after metadata matched for all 12 fixture entities and the fan source.
Full-cloud geometry/attribute equality was not independently proved, and no real
nonunit-scale source was tested. Preserve those limitations exactly.

Bounded fan acceptance is BLOCKED, not FAIL:
- source 359, `Assembly | Fan - scan 1`;
- complete 5,605 / 5,605 acquisition, no truncation;
- signed depth min approximately -0.499512, max +0.499924;
- 2,814 negative and 2,791 positive offsets;
- the single declared analysis exceeded the configured 16-component limit and
  refused before producing a candidate fingerprint;
- therefore there was no defensible selection and reconstruction was correctly not
  attempted.

Do not raise `max_components`, search thresholds, select by depth sign, or otherwise
retune solely to force this fan slab through. The BLOCKED result demonstrates that
the safety boundary is functioning. A smaller/better isolated acquisition can be a
future workflow improvement, but it is not required to accept 0.15.3.

This lane is now Windows-accepted but NOT merged. The user's previous explicit merge
authorization covered 0.15.2 only. Do not merge 0.15.3 until the user explicitly
authorizes this accepted increment. Documentation-only acceptance recording after the
tested SHA does not invalidate the tested runtime; verify its CI before merge.

## Accepted main: 0.15.2

The user explicitly authorized the 0.15.2 merge and then a separate 0.15.3
layer-isolation increment. PR #16 merged `feature/live-cad-section-boundary-extraction`
into main at `8f2e0317f9eeff14547db1d83c100549c65fb18c`.
The retained feature HEAD is `e4e53f7632e58843ea78780b88a2ab539cee1a94`.
Push CI `36350201179` and PR CI `36350227336` both completed successfully before
merge. The merge tree exactly matches that checked HEAD. The later main checkpoint
`cb1ee9eab9c64ff4806036a6317606938faa22e6` records this recovery state only.
Preserve the feature branch; do not merge it again.

Windows-tested HEAD: `7610eceff68704132ff44086d8d070fbb10b5c38`.
Runtime/product checkpoint: `0fd59d19156f6d80087e1c43b2096482aa85715f`.
Accepted Python: 0.15.2. qMCPBridge: unchanged accepted 0.12.0 / workflow revision 8.
No DLL rebuild is required. Generated snapshot/live fixtures and safety gates PASSed.
Windows regression: 490 passed plus 16 compiler-gated policy tests that subsequently
PASSed under configured MSVC. compileall and diff checking PASSed. The fan profile
was correctly BLOCKED by complete but ambiguous geometry, not a product defect.
Integrity coverage is metadata only, not full source-point hashing. Real-host nonunit
global scale remains untested. Do not silently promote those coverage claims.

All prior acceptance histories and numerical details are preserved verbatim in
`docs/ACCEPTED_DEVELOPMENT_HISTORY.md` (the prior AGENTS.md blob). Read its relevant
sections before changing accepted behavior. Its historical pending-merge wording is
superseded by the exact merged state above, not a request to repeat completed work.
Also read `docs/LIVE_CAD_SECTION_BOUNDARY_EXTRACTION.md`; the corresponding Windows
acceptance document is a retained procedure, not an outstanding 0.15.2 test gate.

## Layer-isolation responsibility boundary

Keep complete slab `(u,v,signed_depth)` evidence until coherent layers have been
analyzed. Python owns local depth observations, continuity, ambiguity and selection;
CloudCompare owns read-only complete acquisition and source provenance. Use existing
`cloud.region_query`, with NO native/DLL change. Do not begin Fusion 360 integration.

Sparse, thick or merging/crossing components block continuation even after an
explicit choice. Selection is automatic only for one usable component. Explicit
selection binds exact geometry, source, frame, acquisition and parameters through
an analysis fingerprint. Disconnected patches are separate candidates, never
implicitly joined. Explicit choice is not manufacturing acceptance.

Never select by depth sign, drop inconvenient samples, use truncated reservoir samples
as topology proof, or search parameters until a CAD outline looks good. A real fan
result may legitimately remain BLOCKED.

The previous fan slab: resolve the actual entity (historically cloud 359, name
`Assembly | Fan - scan 1`, 406,276 source points), origin `[40,0,135]`, normal
`[0,0,1]`, half-thickness 0.5, complete 5,605/5,605 acquisition. Depth approximately
-0.4995 to +0.4999 with substantial support on both sides; five independent diagonal
UV occupancy contacts. Do not assume this exact slab must become reconstructable.

## Disconnect/stall recovery

1. Inspect local status, remote heads, recent commits, open issues/PRs and CI.
2. Preserve unexpected work. Never reset, clean, force-push, delete retained branches,
   or create replacement `-retry`/`-recovery` branches because a session restarted.
3. Commit each coherent increment, verify its returned SHA and remote persistence,
   then start the next substantial change. After a failed write, re-query remote HEAD
   and recent commits rather than inferring success/failure.
4. Update this file at milestones: active branch, accepted-main parent, exact last
   coherent runtime checkpoint, CI, remaining scope and whether native code changed.
5. Save before potentially slow tests/diffs. Fetch focused log/failure excerpts;
   avoid giant repeated responses and rapid unbounded CI polling. Continue independent
   review while CI runs.

## Validation boundary

Use the development container for every available numerical, unit, protocol, CLI,
static and build check. Test actual source, not a handwritten reference presented
as product validation. Distinguish exact-source tests, replay/mocked acquisition,
native policy compilation and real CloudCompare GUI tests. Missing dependencies,
network or builds are limitations, not passing tests; preserve evidence outside Git.
Never claim a full suite, native build or fan run that was not executed.

Before requesting Windows: complete regression, compileall, diff check, schema tests,
actual MCP stdio tests, exact generated fixture-file tests, final comparison with
accepted main, green CI and proof of no native diff when claiming no rebuild.
Windows is for testing/reporting, not implementing fixes. Supply one copyable prompt
with exact branch/HEAD and targeted scope. File issues only for reproducible product
defects; valid ambiguity/refusal is not itself a defect. Close defects only after the
required retest. Do not reopen issue #13's accepted slot fix or older accepted gates
for a chat restart or documentation-only changes.

## Numerical and data safety

Use native units, never assume millimetres. Work in local/relative coordinates and
reject subprecision tolerances. Preserve cloud identity/name, section origin/normal/
bases, global shift/scale, acquisition counts/truncation, thresholds and fingerprints.
Never apply CloudCompare global shift/scale twice. Keep measured evidence, inferred
layers/boundaries/topology/primitives and accepted manufacturing intent distinct.

Keep CloudCompare visible but prefer structured geometry; do not routinely capture
viewport images or return raw point arrays. The GUI test instance may be reopened
without saving; that is not permission to delete unrelated files or working changes.
`fan_project.bin` is an authorized disposable dataset: resolve its real path and use
a working copy, never assume it is in the repository/container. Preserve source
geometry/attributes; overlays may modify only explicitly managed objects, never
identify deletable user geometry by display name alone.

Keep detailed reports, logs, screenshots, fixtures, exports and run-specific evidence
outside Git. Reusable generators/tests/procedures and recovery guidance belong in
Git. Preserve all accepted histories. Never repeat a completed full Windows/fan gate,
manual drag, reinstall or unchanged-DLL rebuild merely because a session restarted.
