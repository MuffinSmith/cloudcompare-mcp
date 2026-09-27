# Repository work and interruption recovery

## Accepted main: 0.15.2

The user explicitly authorized the 0.15.2 merge and then a separate 0.15.3
layer-isolation increment. PR #16 merged `feature/live-cad-section-boundary-extraction`
into main at `8f2e0317f9eeff14547db1d83c100549c65fb18c`.
The retained feature HEAD is `e4e53f7632e58843ea78780b88a2ab539cee1a94`.
Push CI `36350201179` and PR CI `36350227336` both completed successfully before
merge. The merge tree exactly matches that checked HEAD. This follow-up is recovery
documentation only. Preserve the feature branch; do not merge it again.

Windows-tested HEAD: `7610eceff68704132ff44086d8d070fbb10b5c38`.
Runtime/product checkpoint: `0fd59d19156f6d80087e1c43b2096482aa85715f`.
Python: 0.15.2. qMCPBridge: unchanged accepted 0.12.0 / workflow revision 8.
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

## Next deliberate lane: 0.15.3 layer isolation

Create or resume `feature/live-cad-section-layer-isolation` from current accepted
main; inspect remote heads first, never recreate it after a disconnect. Do not
continue runtime development on the accepted 0.15.2 branch. The user's approval
DOES NOT authorize merging 0.15.3; that requires its own targeted real-Windows
acceptance and explicit user approval.

Keep complete slab `(u,v,signed_depth)` evidence until coherent layers have been
analyzed. Python owns local depth observations, continuity, ambiguity and selection;
CloudCompare owns read-only complete acquisition and source provenance. Prefer
existing `cloud.region_query`, with NO native/DLL change. Do not begin Fusion 360
integration in this increment.

Return compact deterministic layer candidates, support/thickness/overlap/crossing
warnings and source/layer fingerprints. Hand only a safe or explicitly chosen usable
layer to the unchanged accepted 0.15.2 occupancy, 0.15.1 topology and primitive fitter.
Never select by depth sign, drop inconvenient samples, use truncated reservoir samples
as topology proof, or search parameters until a CAD outline looks good. Automatic
continuation requires one unambiguous supported coherent layer. Explicit selection
is not manufacturing acceptance. A real fan result may legitimately remain BLOCKED.

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
static and build check. Test the actual source, not a handwritten reference presented
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
