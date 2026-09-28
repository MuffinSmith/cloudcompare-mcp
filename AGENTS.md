# Repository work and interruption recovery

## Active lane: Python 0.15.7 picked section ROI intent

Branch `feature/live-section-roi-from-picks`, draft PR #21, accepted-main parent
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Do not recreate this branch or merge it.
Recovery found main at that SHA, no newer lane and no open PR/issue. Main CI
`36366822554` succeeded. Core checkpoint `eba1d516dad6299f9691c37bcb7b95a19ff687ef`;
MCP/workflow checkpoint `20fe3a6ba32870f8cacd6a80747c20638014b7ed`;
exact fixture checkpoint `00c52e133854ae86ac2fabf653e174734775216f`.

Implemented six tools: snapshot/live `derive[_live]_section_roi_from_picks`,
`analyze[_live]_picked_section_target_roi`, and
`reconstruct[_live]_picked_section_target_roi_profile` (consult actual KINDS for
literal names). Package is now 0.15.7. Old ROI contract remains 0.15.6; only the
installed-package version assertion in its stdio test changes. Native and accepted
numerical solvers remain unchanged.

Explicit frame + 2..32 distinct boundary anchors + explicit nonnegative margin.
No frame solver, inferred manufacturing datum, ROI discovery, hidden padding or
quality-driven adjustment. Live origin/normal uses the accepted canonical section
basis; snapshot requires full explicit right-handed orthonormal frame. Degenerate
raw spans cannot be repaired using margin. Anchor depth is reported, not used to
crop ROI depth evidence.

Every live call requires stopped picks, reads current point-info for each selected
source anchor, and brackets ONE complete slab query with pick-status reads. A valid
N-anchor call requests N+3 native reads, no mutation. Malformed inputs can stop
before I/O; stale anchors stop before acquisition. Whole captured status is hashed,
with selected anchor identities preserved and selection-array ordering ignored.

The wrapper recomputes intent before analysis/reconstruction, rejects stale expected
intent, and binds the fingerprint into unchanged accepted ROI context. Target and
layer evidence inherit it. Intent, report, preview or foreign numerical ROI tokens
cannot override target/layer selection or edge-guard refusal.

## Testing checkpoint and remaining work

Local results in separate focused runs: 49 core numerical + 36 workflow/freshness
+ 39 exact-file/transformed/quantization + 10 MCP schema/dispatch/installed stdio =
134 passing new tests. Installed stdio snapshot used an unavailable bridge; live
stdio used a counted TCP replay over exact generated files. This is NOT visible
CloudCompare validation. Eighteen deterministic PLY files include actual anchor
vertices, generated outside Git. Two/three anchors, clutter, two targets, all crossed
edges, near edge, narrow bridge, layers, sparse/overlap/thick evidence and arbitrary
rotation/large coordinates are covered. Host float32 behavior is a numerical proxy.

Next: verify complete installed regression, compileall, diff checks, full accepted-main
diff and exact-head CI. Audit source bytes against installed modules and persisted
GitHub source artifact. Then write contract/README/focused Windows acceptance docs,
update this checkpoint and PR summary. No Windows/fan gate or merge has occurred.

The sandbox cannot resolve GitHub/PyPI. Accepted source came from main's successful
CI artifact, Git tree `06105cff75a49ad196257c1247f9034d2f86a6bb`, with exact main
commit SHA reconstructed and verified locally. Temporary dependency bootstrap
`36367435852` succeeded; public wheels recovered; bootstrap workflow removed. The
regular CI workflow now includes this branch and uses a noneditable installation.
Local package installation is noneditable; some preinstalled third-party dependencies
are reused through the environment. Do not call that pristine dependency isolation.
Use workflow source artifacts for exact recovery when direct cloning is unavailable.

## Honest boundaries

Native qMCPBridge 0.12.0/revision8 has no scene/picking generation counter or atomic
multi-call snapshot. Freshness binds observed complete slab and selected anchors,
not unobserved whole-cloud geometry/attributes. Identical unobserved ABA changes
cannot be detected. Snapshot evidence and frame provenance are caller asserted,
not authenticated live datum evidence. Snapshot/live fingerprints are separated.
Do not silently promote any of these claims. No native change/rebuild is needed.

## Accepted 0.15.6 baseline (do not repeat its Windows gate)

Read `docs/WINDOWS_0_15_6_ACCEPTED.md` and `docs/LIVE_CAD_SECTION_TARGET_ROI.md`.
PR #20 merged `04a21fc32261fe7a071fd9ab46ee353afd33016c`; main checkpoint
`2b385820ecfcb84d79aaf59ad5965e748f961466`. Windows feature HEAD
`3a1d49550e3e1a90d4915fb197ad51688a3e836d`; runtime/test checkpoint
`5d618c0de30c90a4573d4c8be52174a3aed58eee`; final acceptance docs
`f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`; pre-0.15.6 accepted main
`809c522550274316fa0a14d2e86d90a4921bfc03`.

Accepted Windows: 1054 ordinary installed passes plus 16 MSVC passes = 1070;
28 installed module hashes; 22 generated PLY hashes; seven focused modules 180/180;
actual MCP stdio, counted TCP replay and 20 visible CloudCompare fixtures passed.
CloudCompare 2.13.2/PID14312/port8765, qMCPBridge0.12.0 revision8. All-depth complete
inside+outside accounting, zero ROI-unclassified, all four crossed guards refused,
multiple targets explicit and layers required fresh matching selection evidence.
37 scene roots and empty selection restored. Native did not change.

Retained limits: no real-host nonunit scale, independent real-host native query count,
or whole-cloud geometry/attribute equality proof. Transformed host shift was
[-100000000,199999000,-299999000], scale1; maximum file/host bound difference about
2.73e-5. Host quantization can legitimately alter exact cross-context hashes.

## Fan and next architecture

Authorized fan/working-copy SHA256:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
Rediscovered source 406276 points. No 0.15.6 fan ROI call occurred: no defensible
picked intent/frame was declared. Retained 0.15.5 diagnostic remains BLOCKED.

Future fan gate: verify file hash, rediscover source, explicitly declare frame, have
the human deliberately choose boundary-anchor picks, freeze intent, THEN inspect
ROI/reconstruction evidence. Never derive bounds from convenient diagnostic panels,
search ROI sizes, raise target/layer budgets, choose depth signs, discard clutter or
select whichever reconstruction looks best. Trustworthy intent with refused geometry
is a useful success. Do not tune fixtures to the real fan.

After this bridge is accepted, the next architecture is a CAD feature/model IR for
datums, sketches, features, dimensions, dependencies, evidence and unresolved/refused
regions. Do not bundle that model graph or broad Fusion automation into 0.15.7.

## Recovery discipline

Before resumed work inspect actual main/branches/recent commits/open PRs/issues/CI
and this file. Preserve unexpected work. Commit coherent increments, verify returned
SHA AND remote ref, update this file at milestones, then proceed. Save before long
tests. Stream timeout does not imply Git work was lost. Never reset, clean, force-push,
delete retained branches, recreate this lane or add retry/recovery/numbered branches.
Keep numerical, mocked-native/replay, installed stdio, CI and visible-GUI claims separate.
