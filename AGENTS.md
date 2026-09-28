# Repository work and interruption recovery

## 0.15.6 explicit ROI increment: Windows accepted, merge authorized

Resume `feature/live-cad-section-target-roi` only if PR #20 is still open.
Do not recreate it. User Windows/CloudCompare acceptance is recorded in
`docs/WINDOWS_0_15_6_ACCEPTED.md`; the user explicitly authorized merging PR #20.
Before any merge, inspect the actual PR head and exact-head CI. Do not merge a moved
or failing head. Do not repeat the completed 0.15.6 Windows gate.

Accepted Windows-tested runtime/documentation HEAD before acceptance-record commits:
`3a1d49550e3e1a90d4915fb197ad51688a3e836d`.
Runtime/test checkpoint:
`5d618c0de30c90a4573d4c8be52174a3aed58eee`.
Accepted-main parent:
`809c522550274316fa0a14d2e86d90a4921bfc03`.

The acceptance-record commits after 3a1d495 are documentation only:
- Windows installed regression: 1054 passed + 16 MSVC policy tests = effective
  1070 passed.
- 22 exact generated PLY hashes verified; seven focused modules 180 / 180.
- Actual isolated MCP stdio PASS; counted TCP replay PASS.
- Visible CloudCompare fixture gate PASS for 20 declared fixtures.
- CloudCompare 2.13.2 / PID14312 / port8765 / qMCPBridge0.12.0 revision8.
- Every complete fixture: inside + outside = returned = matched, zero ROI-unclassified.
- All four crossed edges refused even with explicit IDs; target/layer safety remained
  authoritative; no double global shift/scale application.
- Transformed host shift [-100000000,199999000,-299999000], scale1; maximum observed
  file-to-host bound difference about 2.73e-5.
- Optional fan exercise correctly BLOCKED before any ROI call because no defensible
  picked spatial intent and section frame had been declared.
- No real-host nonunit scale, independent host native-query count or whole-cloud
  geometry/attribute equality is claimed.

The authorized fan and working copy SHA256 was
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`;
the current source was independently rediscovered as 406276 points. The retained
0.15.5 diagnostic remains BLOCKED/inconclusive. Do not derive an ROI from a convenient
diagnostic panel, search ROI sizes, raise budgets, choose a depth sign, drop clutter
or select whichever reconstruction looks best.

## Accepted 0.15.6 contract

Four read-only snapshot/live ROI analysis/reconstruction tools use complete slab
acquisition, explicit half-open UV bounds, all-depth inside/outside accounting and
an inclusive one-declared-UV-cell edge guard BEFORE unchanged accepted target,
layer, occupancy, topology and fitting. No ROI discovery/search or scale tuning.

Source, whole slab including outside geometry, source-index mapping, exact ROI,
frame/acquisition/bookkeeping and target parameters bind selection. ROI/diagnostic
report fingerprints are NOT candidate authorization. Every selected candidate must
clear the edge guard; explicit IDs cannot override truncation or unsafe target/layer
states. Multiple targets still require explicit choice. Outside support is projected
evidence, not proof of physical connection.

Layer evidence must match target-selection mode: switching automatic to explicit
selection requires fresh layer evidence. Host quantization may legitimately change
exact cross-context geometry hashes; do not manufacture equality.

qMCPBridge remains 0.12.0 / workflow revision8. The native plugin and accepted
numerical target/layer/boundary/topology/profile solvers did not change.

## Next deliberate lane after PR #20 merges

Do not start substantial new runtime work until the merge is persisted and main is
re-read. Record the exact merge SHA and post-merge main checkpoint first.

The next recommended increment is a small explicit-intent bridge, tentatively
Python 0.15.7 / branch `feature/live-section-roi-from-picks` unless a newer
deliberate lane already exists.

Primary goal: turn deliberate CloudCompare picks / user spatial intent into a
provenance-bound section frame and explicit numerical ROI consumable by accepted
0.15.6, without looking at reconstruction quality to optimize the region.

Suggested contract:
- Use actual captured live picks and explicit source entity/frame inputs.
- Derive or validate a stable section frame from declared geometric intent; do not
  infer manufacturing intent.
- Produce explicit native-unit half-open UV bounds and section origin/normal/basis.
- Bind source identity, pick identities/coordinates, frame, acquisition/bookkeeping
  and algorithm contract into a stale-detectable intent fingerprint.
- A changed pick, source, frame or source geometry invalidates the intent token.
- Prefer a deterministic geometric rule for converting picks to bounds. Any padding
  must be explicit caller input or a fixed documented contract, never searched.
- Optionally provide a read-only preview overlay, but previews cannot authorize
  reconstruction and must not mutate source geometry.
- Output arguments directly usable by `analyze_live_section_target_roi`.
- Never inspect target/profile fit quality and then resize/reorient the ROI.
- Keep actual section/ROI analysis in accepted 0.15.6; do not fork its solver.
- Snapshot equivalents should remain testable without CloudCompare where practical.
- The fan may be used only after a human deliberately chooses the region/picks
  before seeing the resulting reconstruction.

After that intent bridge, the next major architectural milestone should be a CAD
feature/model intermediate representation: datums, sections/sketches, fitted
features, dimensions/relations, provenance and unresolved/refused evidence. That IR,
not another isolated fitter, is the foundation for an agentic point-cloud-to-model
planner and later solid construction / scan-to-model validation.

## Recovery policy

Commit coherent small changes, verify returned SHA and remote persistence, and keep
this file current. After stream/tool failure inspect main, branches, PRs, recent
commits, CI and AGENTS before continuing. UI failure does not prove work was lost.

Never reset, clean, force-push, delete retained branches, or create retry/recovery/
numbered duplicates merely because a chat restarted. Preserve unexpected work.

Keep numerical, replay, actual MCP stdio, CI and visible-GUI claims separate.
Do not silently promote source-integrity or host-query-count coverage.
