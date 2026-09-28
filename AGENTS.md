# Repository work and interruption recovery

## Accepted main: Python 0.15.6 explicit section-target ROI isolation

PR #20 merged at `04a21fc32261fe7a071fd9ab46ee353afd33016c` after the
user-supplied focused Windows/CloudCompare acceptance. The accepted result is recorded
in `docs/WINDOWS_0_15_6_ACCEPTED.md`; post-merge merge-attribution commit
`08870217485713635a02bbc384f7ba14d62df948` is documentation only.
Always inspect actual `main`, branches, recent commits, open PRs/issues, CI and this
file before new work. Do not repeat 0.15.6 acceptance merely because a chat restarted.

Windows-tested feature HEAD:
`3a1d49550e3e1a90d4915fb197ad51688a3e836d`.
Final pre-merge acceptance-documentation HEAD:
`f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`.
Runtime/test checkpoint:
`5d618c0de30c90a4573d4c8be52174a3aed58eee`.
Accepted-main parent before PR #20:
`809c522550274316fa0a14d2e86d90a4921bfc03`.

Accepted Windows results:
- isolated Python 3.13.14 package 0.15.6; all 28 installed modules matched checkout;
- 1054 ordinary-shell regression passes plus all 16 MSVC-gated policy tests:
  effective 1070 passed;
- 22 exact generated PLY hashes verified; seven focused modules 180 / 180;
- actual isolated MCP stdio PASS; counted TCP replay PASS;
- visible CloudCompare fixture gate PASS for 20 declared fixtures;
- CloudCompare 2.13.2 / PID14312 / port8765 / qMCPBridge0.12.0 revision8;
- every complete fixture: inside + outside = returned = matched, zero ROI-unclassified;
- all four crossed edges refused even with explicit IDs; target/layer safety remained
  authoritative; no double global shift/scale application;
- transformed host shift [-100000000,199999000,-299999000], scale1; maximum observed
  file-to-host global-bound difference about 2.73e-5;
- 37 preexisting scene roots and empty selection restored after disposable imports;
- optional fan exercise correctly BLOCKED before any ROI call because no defensible
  picked spatial intent and section frame had been declared.

Retained limitations: no real-host nonunit global scale, independent real-host native
query count, or whole-cloud geometry/attribute equality. Host quantization can change
exact cross-context geometry hashes. Do not silently promote these claims.

The authorized fan and working copy SHA256 was
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`;
the current source was rediscovered as 406276 points. The retained 0.15.5 fan
diagnostic remains BLOCKED/inconclusive. Do not derive ROI bounds from convenient
diagnostic panels, search ROI sizes, raise budgets, choose a depth sign, drop clutter,
or choose whichever reconstruction looks best.

## Accepted 0.15.6 contract

Four read-only snapshot/live ROI analysis/reconstruction tools use complete slab
acquisition, explicit half-open UV bounds, all-depth inside/outside accounting and
an inclusive one-declared-UV-cell edge guard BEFORE unchanged accepted target,
layer, occupancy, topology and primitive fitting. No ROI discovery/search or scale
tuning is part of the accepted contract.

Source, whole slab including outside geometry, source-index mapping, exact ROI,
frame/acquisition/bookkeeping and target parameters bind selection. ROI/diagnostic
report fingerprints are not candidate authorization. Every selected candidate must
clear the edge guard; explicit IDs cannot override truncation or unsafe target/layer
states. Multiple targets still require explicit choice. Outside support is projected
evidence, not proof of physical connection.

Layer evidence must match target-selection mode: changing automatic to explicit
target selection requires fresh layer evidence. qMCPBridge remains 0.12.0 / workflow
revision8. The native plugin and accepted numerical target/layer/boundary/topology/
profile solvers did not change.

## Next deliberate lane: explicit pick-to-section/ROI intent

Primary goal: bridge the remaining human/agent intent gap exposed by the accepted fan
BLOCKED result. Convert deliberate CloudCompare picks / visible spatial intent into a
provenance-bound section frame and explicit numerical ROI directly consumable by
accepted 0.15.6, without using reconstruction quality to optimize the region.

Before creating a branch, inspect remote branches. If no newer deliberate lane exists,
create exactly one branch from current accepted `main`:
`feature/live-section-roi-from-picks`
Suggested Python version: 0.15.7.
Do not continue runtime work on the retained accepted 0.15.6 feature branch.

Suggested first surface:
- `derive_live_section_roi_from_picks` or a clearer equivalent;
- optionally a snapshot counterpart for deterministic offline testing;
- if frame derivation and ROI derivation are meaningfully separate, keep them as
  separate analysis tools rather than hiding ambiguity in one call.

Contract requirements:
- consume actual captured live picks and explicit source entity identity;
- require explicit frame intent or deterministic declared frame construction;
- never infer manufacturing intent from pick placement alone;
- return explicit native-unit section origin, normal, basis_u, basis_v and half-open
  `[u_min,u_max) x [v_min,v_max)` bounds usable by 0.15.6;
- bind source identity, pick IDs/coordinates, frame inputs, source/acquisition/global
  bookkeeping and algorithm contract into a stale-detectable intent fingerprint;
- changed picks, source, frame or source geometry invalidate prior intent;
- any ROI padding/margin must be explicit caller input or a fixed documented contract,
  never searched or optimized;
- never inspect target/profile reconstruction quality and then resize, rotate or
  reposition the ROI;
- keep target/layer/boundary/topology/profile analysis in accepted 0.15.6 and earlier
  solvers; do not fork them for convenience;
- output a compact request object directly usable by
  `analyze_live_section_target_roi`;
- preserve raw pick/point arrays server-side where practical;
- source geometry must remain unmodified;
- snapshot tools must work without CloudCompare if introduced;
- live tools should use captured pick data without unnecessary repeated cloud queries;
- a read-only preview overlay may be considered, but it must be clearly diagnostic,
  reversible, must not authorize reconstruction, and must not alter source geometry.

Safety/adversarial tests should include stale picks, changed source IDs, changed frame,
collinear/degenerate picks, picks from mixed entities, reordered picks where order is
not semantic, explicit order where order is semantic, large-coordinate/global-shift
cases, host quantization, ROI exactly touching selected picks, explicit padding,
malformed/nonfinite inputs, and no-double-global-shift/scale behavior.

Do not use the real fan to tune rules. Synthetic fixtures should establish deterministic
pick-to-frame/ROI behavior first. A later fan exercise may proceed only after a human
deliberately chooses the intended region/picks before seeing the resulting fit quality.

After the intent bridge, the next major architectural milestone should be a CAD
feature/model intermediate representation: datums, sections/sketches, fitted features,
dimensions/relationships, provenance, unresolved evidence and refusal state. That IR
is the foundation for an agentic model planner, solid construction and scan-to-model
validation. Avoid jumping directly to Fusion 360 automation before this representation
exists unless a minimal backend is needed to validate the IR.

## Recovery policy

Work in small recoverable increments. After every coherent change: commit it, verify
the returned SHA, verify remote branch persistence, update this file at milestones,
then begin the next substantial change. Before long tests, save current work.

If a connector/tool call or stream fails: inspect actual remote HEAD, recent commits,
this file and recent CI before doing anything. UI stream failure does not mean Git work
was lost.

Never reset, clean, force-push, delete retained branches, recreate an existing branch,
or create retry/recovery/numbered duplicate branches merely because a chat restarted.
Preserve unexpected work.

Keep numerical/unit, replay/mocked-native, actual MCP stdio, CI and visible-GUI claims
separate. Do not silently promote source-integrity or host-query-count coverage.
