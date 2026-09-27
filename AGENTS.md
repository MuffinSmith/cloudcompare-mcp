# Repository work and interruption recovery

## Active UNMERGED 0.15.4 section-target isolation

Branch: `feature/live-cad-section-target-isolation`.
Accepted-main parent: `0201cdd46381e0c79c05b33ee9de48851a18b877`.
Initial recovery commit: `4b456f38affa8fdb250893ba5e1c148d8015ea26` (remote verified).
No merge is authorized. Preserve every retained branch and unexpected work.

Milestone: core/workflow/MCP and exact generated-file coverage implemented.
MCP runtime checkpoint: `b22e18f1a2b785642e57b7a7d1231e282caa9d77` (remote verified).
Installed CI `36355988329` passed, including schema and actual MCP stdio/TCP replay.
Local numerical/workflow/exact-file suite: 111 passed (48 core, 43 workflow,
20 file tests). All 14 freshly generated ASCII-double PLY fixtures were exercised
through product projection, snapshot and native replay, including arbitrary 3D
rotation plus [1e8,-2e8,3e8] translation. Single/parallel transformed profile handoff
passed without threshold changes. Ten MCP tests now use exact generated files for
stdio snapshot/live replay. Local MCP dependencies remain unavailable; use installed
CI for full regression/transport. Python is 0.15.4. No native/DLL changes.

Registration delegates through the existing layer-tools registry without changing
server.py or accepted handlers/solvers. Capabilities are exposed under
`python_section_layers.section_targets` (version 0.15.4); parent layer/profile
capabilities retain their accepted 0.15.3/0.15.2 versions. Snapshot/live analyze and
reconstruct tools use target_id + expected_target_fingerprint, then optionally
layer_id + expected_layer_fingerprint, as separate paired explicit choices.

The core uses explicit UV/depth voxel sizes, six-neighbor connectivity, unique-point
support, iterative articulation detection, one UV-cell erosion and six fixed
+/- origin perturbations. These are diagnostics, not repairs or parameter searches.
All points belong to reported candidates. Sparse, bridge/appendage, thin, marginal
edge/corner-contact, UV-overlap and membership-sensitive targets cannot be selected.
Multiple targets ALWAYS require explicit selection, even with one dominant/usable
target and distant unsupported clutter. A usable explicit choice can leave separate
clutter unselected, with full counts/reasons. Selection tokens bind the candidate,
whole source, frame, acquisition and parameters; snapshot/live tokens differ.

`section_target_workflow.py` acquires one complete slab BEFORE any layer analysis,
selects a supported spatial target, and passes every selected depth sample into the
UNCHANGED accepted 0.15.3 -> 0.15.2 -> 0.15.1/profile solvers. Upstream target identity
is bound into downstream layer selection. Target and layer unselected counts remain
separate with aggregate accounting. Layer budgets/refusals retain target evidence;
boundary/topology refusal retains the accepted diagnostics. Native replay coverage
includes unique indices, complete counts, source/global frame, shift/scale and
no mutation; it is not real-GUI or full-cloud integrity coverage.

Next: final review, installed regression/CI, focused Windows documentation and
recovery checkpoint. Do not request Windows until these gates pass. New fixtures
must stay outside Git. The fan-like synthetic slab has 20 explicit spatial targets;
not every target is necessarily supported, and a profile is not required. This is
not the retained real fan and no real CloudCompare test has occurred here.

## Accepted history and boundaries

Read `docs/ACCEPTED_0_15_3_HISTORY.md` (verbatim previous main AGENTS.md),
`docs/ACCEPTED_DEVELOPMENT_HISTORY.md`, and relevant accepted CAD/profile/layer docs.
Historical next/pending wording is superseded by this active lane; never recreate it.

Accepted 0.15.3: PR #17, merge `27cfd286331db177c76ce627056150e439d418c9`;
retained feature HEAD `dda5032a60143f7a17691034c337a83492a8613f`;
real-Windows tested runtime `2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`.
Windows: 610 passed plus 16 compiler-gated tests subsequently passed under MSVC.
Installed CI: 626 passed. All 12 exact fixtures and actual stdio/live GUI/safety/
handoff gates passed. Integrity was METADATA ONLY, not independent full-cloud
geometry/attribute equality. No real nonunit-scale source was tested. Do not promote
those claims or repeat this completed gate merely for a chat restart.

Retained fan: BLOCKED, not failed. Historical source 359, `Assembly | Fan - scan 1`,
406,276 source points. Slab origin [40,0,135], normal [0,0,1], half-thickness 0.5;
complete 5,605/5,605 acquisition. The declared 0.15.3 analysis exceeded 16 components,
produced no selection fingerprint and correctly did not reconstruct. Do not raise
that limit, choose a depth sign, delete clutter or parameter-search for a pass.
The new fan result may remain legitimately BLOCKED.

## Local source provenance and validation

Direct container git network access is unavailable. Accepted source came from
Actions artifact 10943288751; ZIP SHA-256
`06a934a875c6b725a68edc1d848aabbf3df9c2a0083c90996cb70c3d688d36cb`.
Archive commit comment matches accepted main. Reconstructed local Git tree exactly
matches accepted tree `6a14df038d0354f474fea37666c3e24fce2c5787`.
Local snapshot commit IDs are comparison-only, not remote commits. NumPy and pytest
are present; MCP/PLY dependencies were unavailable initially. Use actual source for
available local checks and installed CI for complete regression/transport checks.
Never claim a missing-dependency check passed. Archive tracked public source only,
not workspace credentials or user data. Keep generated files and evidence outside Git.

## Recovery and completion gate

Commit coherent increments, verify returned SHAs and remote HEAD before substantial
next work, and update this checkpoint. Save before long tests/diffs. A failed stream
is not evidence a write failed: inspect remote HEAD, recent commits, AGENTS and CI.
Never reset, clean, force-push, delete retained branches or create retry/recovery
branches. Avoid giant repeated logs and rapid polling loops.

Use only complete read-only native acquisition. Keep raw arrays server-side and
shift/scale as provenance; never apply them twice. No native changes unless existing
acquisition is proven insufficient. No Fusion, ellipse/spline, manufacturing-intent
inference or multiresolution parameter search in this increment.

Before Windows require complete installed regression, compileall, diff checks,
schemas, ACTUAL MCP stdio, clearly labeled native replay, exact generated-file tests,
final accepted-main comparison, no-native-diff proof and green CI. Windows is
focused testing/reporting, not implementing fixes. Do not merge or ask to merge on
development tests. Return exact branch/HEAD/parent, algorithm/tools, test counts,
changed files, refusal limits/native status/CI and one copyable Windows prompt.
Use a resolved working copy of authorized `fan_project.bin`, never assume its path.
