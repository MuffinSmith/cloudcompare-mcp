# Repository work and interruption recovery

## Active, UNMERGED 0.15.4 section-target isolation

Branch: `feature/live-cad-section-target-isolation`.
Accepted-main parent: `0201cdd46381e0c79c05b33ee9de48851a18b877`.
Recovery inspection confirmed that main, no existing next-stage branch, no open
PRs/issues, and green main CI `36354798969`. The branch was created exactly once.
No merge is authorized. Preserve every retained branch and unexpected work.

Milestone: design/recovery checkpoint only; numerical core and MCP surface are next.
Python remains 0.15.3 until the new runtime is integrated. qMCPBridge is unchanged
at accepted 0.12.0 / workflow revision 8. No DLL build is needed.

The exact accepted source was obtained from Actions artifact 10943288751,
`tested-source-0201cdd46381e0c79c05b33ee9de48851a18b877`. ZIP SHA-256:
`06a934a875c6b725a68edc1d848aabbf3df9c2a0083c90996cb70c3d688d36cb`.
Its git archive comment matches the accepted-main SHA. Direct container git
network access is unavailable. Use the exact archived source for available local
checks and CI for installed regression/transport checks; never claim unavailable
checks passed. Source archives contain tracked public source only, not credentials
or user data. Detailed logs, fixture PLYs and run evidence stay outside Git.

## Design and safety contract

Add bounded, deterministic spatial target evidence BEFORE accepted 0.15.3 layers.
Keep the numerical core separate from MCP transport. Prefer explicit anisotropic
section-coordinate occupancy/connectivity, preserving U/V/depth and all point
membership. Candidate summaries must remain compact and fingerprint-bound to source,
frame, acquisition and parameters. No raw arrays in responses.

Every point must belong to a reported candidate or be explicitly accounted as
unselected/unsupported/ambiguous. Never choose the largest target automatically,
select by depth sign, discard small components, or search thresholds for a nice
profile. Multiple targets require explicit selection. Sparse, bridge/contact,
overlap or perturbation-sensitive evidence must not be hidden by selection.
A selected supported spatial target still passes through UNMODIFIED accepted
layer -> occupancy -> topology -> primitive-fitting checks. Target isolation is
not physical-part segmentation or manufacturing-intent confirmation.

Use only complete read-only `cloud.region_query` acquisition and stable Python
section projection. Retain shift/scale as provenance, never apply it twice.
No native/DLL work unless structured acquisition proves insufficient. No Fusion,
multiresolution search, ellipse/spline or unrelated feature work in this increment.

## Accepted coverage is not an outstanding test gate

Read `docs/ACCEPTED_0_15_3_HISTORY.md` (verbatim prior AGENTS.md),
`docs/ACCEPTED_DEVELOPMENT_HISTORY.md`, and the relevant accepted CAD/profile/layer
docs before changing accepted behavior. Their historical next/pending wording is
superseded by this active branch, not a request to recreate it or repeat acceptance.

Accepted 0.15.3: PR #17, merge `27cfd286331db177c76ce627056150e439d418c9`;
retained feature HEAD `dda5032a60143f7a17691034c337a83492a8613f`;
real-Windows tested runtime `2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`.
Windows: 610 passed plus 16 compiler-gated tests subsequently passed under MSVC.
Installed CI: 626 passed. All 12 exact generated fixtures and actual MCP stdio/live
GUI/safety/handoff gates passed. Source integrity was METADATA ONLY; full-cloud
geometry/attributes were not independently proved. No real nonunit-scale source
was tested. Never promote those claims or repeat this gate for a chat restart.

The retained fan is BLOCKED, not failed: historical source 359,
`Assembly | Fan - scan 1`, 406,276 source points; slab origin [40,0,135],
normal [0,0,1], half-thickness 0.5, complete 5,605/5,605 samples. The declared
0.15.3 analysis exceeded 16 components, produced no selection fingerprint and
correctly did not reconstruct. Do not raise that limit or parameter-search to
force a pass. The new fan result may remain legitimately BLOCKED.

## Disconnect recovery and completion gate

Commit coherent increments, verify returned SHAs and remote HEAD before beginning
substantial next work. Update this checkpoint at each major milestone. Before long
tests/diffs save work. A failed UI stream is not evidence a GitHub write failed:
inspect remote HEAD, recent commits, this file and CI before resuming.
Never reset, clean, force-push, delete retained branches or create retry/recovery
branches. Avoid giant repeated logs and rapid polling loops.

Before requesting focused 0.15.4 Windows acceptance require complete installed
regression, compileall, diff checks, schemas, ACTUAL MCP stdio tests, clearly labeled
native replays, exact generated PLY-file tests, final accepted-main comparison,
proof native files are unchanged and green CI. Windows is testing/reporting only,
not implementing fixes. Do not merge or request merge authorization on dev tests.

Return exact branch/HEAD/parent, tools/algorithm, test counts, changed paths,
limitations/native status/CI and one copyable focused Windows acceptance prompt.
The fan is authorized disposable test data only after resolving its actual path;
use a working copy. Do not mutate original geometry or user attributes.
