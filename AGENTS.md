# Repository work and interruption recovery

## Active lane: 0.15.6 explicit section-target ROI isolation

Branch: `feature/live-cad-section-target-roi`. Do not recreate it on interruption.
Accepted-main parent: `809c522550274316fa0a14d2e86d90a4921bfc03`.
Recovery inspection confirmed no open issues/PRs and no newer deliberate lane.
Acquisition refactor checkpoint `de49ee7e1dc04c8d598697e21dd74f70d86773d1`
is persisted and CI36362213639 passed. Its local targeted regression:158 passed.
This checkpoint adds the independently tested numerical ROI classifier and inclusive
one-cell edge guard:62 new tests pass. Workflow/MCP integration is NEXT; this is
not yet a release-ready0.15.6. Do not merge or request Windows acceptance yet.
Temporary public-wheel bootstrap CI36362213680 passed; artifact10945423819 was
retrieved. Its temporary workflow is removed. Local offline wheel installation
works in an isolated venv with system scientific dependencies; reinstall after code
changes (editable install requires an unavailable editables wheel).

Read `docs/WINDOWS_0_15_5_ACCEPTED.md`, accepted target/layer/boundary/topology/profile
contracts, and the user's ROI handoff. Historical pending wording in old feature
documents is superseded by the accepted Windows records, not a request to retest.

Development sequence:
1. Extract reusable complete snapshot/live target acquisition from the accepted
   target workflow, preserving its validation, context and old solver behavior.
2. Add Python-only explicit half-open UV ROI classification BEFORE target analysis.
   Bounds are finite native units; retain ALL signed depths; account for every point
   inside/outside; preserve source indices and frame/shift/scale/provenance.
3. Add one-accepted-UV-cell ROI-edge guard, independent of the unchanged target
   solver. A selected candidate touching the guard must refuse, even with explicit
   target ID. No automatic bounds/scale search or budget increases.
4. Bind exact bounds, whole slab, index mapping, acquisition/context and parameters
   into domain-separated ROI selection tokens; keep snapshot/live distinct.
5. Add four snapshot/live analysis/reconstruction MCP tools, deterministic tests,
   external exact hashed fixtures, actual stdio and one-acquisition replay tests.
6. Run installed regression, compileall, diff checks and CI; prepare focused Windows
   instructions only after coherent internal results. Never label replay as GUI.

Direct network cloning/installing is unavailable in this sandbox. Source was obtained
from main CI's `tested-source-809c522...` artifact10945467790. Its Git tree is exactly
`77e6588ba7a5e4f306129c1be3c8f8e4dcaf0740`. The API-described main commit was also
reconstituted byte-identically as a shallow local baseline. GitHub writes use the
connector, with expected parent/tree/remote checks. Public dependency wheels came from the now-removed temporary bootstrap workflow.
Never archive credentials or private fan data.

## Accepted baseline; do not repeat completed gates

0.15.5 PR#19 merged at `50ff06cb383cd662ddee2a1d0e7d0445f9143719` after user
Windows acceptance and authorization. Retained feature HEAD
`f6e2fc8a19b97da7d367abd259bed50c02a7e382`; runtime/test checkpoint
`c3dac92069bf530e41fa66a6d08794e31f0d9076`: CI890 passed, zero skips.
Windows874 passed plus16 compiler-gated tests subsequently passed under MSVC.
Native qMCPBridge remains0.12.0/revision8. No DLL rebuild is justified by Python work.
Preserve all accepted branches and issue#13 slot/0.15 through0.15.5 behavior.

The declared fan diagnostic remains legitimately BLOCKED/inconclusive: complete5605
points; baseline19 blocked targets, UV-coarser10 blocked, other three probes refused
at max_targets32. No target/layer/profile selected. Do not raise budgets, choose a
depth sign, discard clutter, pick a diagnostic scale or tune an ROI to make it fit.
A later fan ROI requires explicit spatial intent declared before inspecting fits.
Whole-source integrity was metadata-only; no full-cloud equality, no real-host
nonunit scale, and no measured real-host native query count. Transformed host used
shift[-100000000,199999000,-299999000], scale1; host quantization changed exact
hashes/bounds. Do not promote replay scale2.5 or exact slab/file hashes into GUI proof.

## Stream-disconnect policy

Commit coherent small changes before long tests. Verify returned SHA, parent/tree
and remote branch persistence; update this checkpoint at milestones. After a tool
or stream failure inspect actual remote HEAD, recent commits, AGENTS and CI before
continuing. Never reset, clean, force-push, delete retained branches, or create retry,
recovery or numbered duplicate branches. Preserve unexpected work. Avoid huge logs
and rapid polling. Distinguish numerical, replay, actual stdio, CI and real GUI results.
