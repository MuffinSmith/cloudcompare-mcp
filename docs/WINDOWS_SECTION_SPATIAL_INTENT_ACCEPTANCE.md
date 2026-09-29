# Focused Windows / visible CloudCompare acceptance: Python 0.15.7

This is the **pick-to-intent interaction gate**, not a repetition of accepted 0.15.6
Windows acceptance. Branch `feature/live-section-roi-from-picks`, draft PR #21;
accepted-main parent `2b385820ecfcb84d79aaf59ad5965e748f961466`. Resolve and record the
current exact branch HEAD and its exact-head green CI before testing. Read AGENTS.md
and [the new contract](LIVE_SECTION_SPATIAL_INTENT.md). Do not merge the PR.

Native qMCPBridge remains 0.12.0 / workflow revision 8. **Do not rebuild the DLL.**
Do not reset, clean, force-push, delete/recreate branches, change the user's permanent
MCP configuration, or replace an unrelated running environment. Preserve unexpected
checkout/runtime/scene work. Use a clean isolated detached worktree and dedicated
noneditable Python environment for this HEAD; reuse an existing exact clean test
worktree when possible. A conflicting checkout is not permission to overwrite it.

## 1. Identity and internal regression

Record exact checkout HEAD, remote branch HEAD, accepted parent, package version,
Python executable, import directory and all 31 installed Python module byte hashes
against checkout. Expected package is 0.15.7; nested solver versions remain 0.15.6 ROI,
0.15.4 target, 0.15.3 layer and 0.15.2 profile. Use the installed environment without
project-source PYTHONPATH injection for this gate and temporary MCP stdio.

Run the complete 0.15.7 installed suite, compileall and both working-tree and
accepted-main diff checks. Final internal suite has 1210 tests, including 140 new
focused tests. If the ordinary Windows shell skips 16 compiler-gated native-policy
tests, run those 16 in the existing MSVC environment and report both sets separately.
Those standalone policy tests are not a plugin/DLL rebuild. Do not claim 1210 passes
from 1194 passes plus 16 unexecuted skips.

```powershell
python -m pytest -q tests
python -m compileall -q src scripts tests
git diff --check
git diff --check 2b385820ecfcb84d79aaf59ad5965e748f961466 HEAD
git diff --exit-code 2b385820ecfcb84d79aaf59ad5965e748f961466 HEAD -- cloudcompare-plugin
```

Generate new files OUTSIDE Git in a new evidence directory:

```powershell
python scripts/make_section_spatial_intent_fixtures.py C:\path\outside-repo\new-0157-fixtures
```

Verify all 18 PLY SHA256 hashes against the manifest. Exercise the actual file bytes
through the product as the new tests do. Run the five focused modules:
`test_section_spatial_intent.py`, `_workflow.py`, `_fixtures.py`, `_tools.py`, and
`_context.py` (all under `tests/`, with the common prefix). Expected total 140.
Actual installed stdio must advertise all six new tools; snapshot calls must work
without a bridge. Counted TCP replay remains replay, not visible-host acceptance.

The first Windows attempt at HEAD `8438ba311c6d31de5a775d3ec3f17a5bca214ce6`
proved the two-anchor `safe` interaction but exposed a fixture-capture usability
problem: qMCPBridge auto-stopped a three-anchor session after repeated events on one
vertex consumed the event count. See `WINDOWS_0_15_7_PARTIAL_ACCEPTANCE.md`.
The procedure below deliberately overprovisions the event budget and uses explicit
distinct source-point indexes; it does not change ROI mathematics or provenance.

## 2. Attach safely to the existing visible host

Rediscover the current CloudCompare process/bridge; do not assume the retained
0.15.6 PID 14312 or any old cloud ID still applies. Record app/plugin versions,
configured endpoint, scene roots, selection and picking status. If there is an
active session or non-disposable preexisting captured pick work, preserve it and
report that interaction subtest BLOCKED rather than silently clearing/replacing it.
The bridge cannot restore arbitrary prior captured picks from an exported JSON file.

Use temporary installed MCP stdio against this visible host. Do not retarget the
user's permanent MCP setup. Track exactly which disposable fixture entities this
gate imports. Record actual imported global shift/scale and bounds. Global positions
from picks and region queries are already global; do not apply bookkeeping again.

Keep the source and host quiescent during each declaration/analysis sequence. Do not
save over user files, mutate source arrays, delete preexisting roots or clear unrelated
overlays. If picking cannot be safely completed, report BLOCKED, not a fake injected
pick-state success.

## 3. Real captured-pick fixtures

Use a small declared visible-host set: `safe`, `three_anchors`, `two_inside`,
`cross_left`, `parallel`, and `transformed_safe`. `near_edge` and `outside_clutter`
are useful additional cases. This is not the old 20-fixture 0.15.6 GUI gate.

For EACH chosen fixture, before calling any picked ROI analysis/reconstruction:

1. Read its manifest-declared frame, fixed thickness, target/layer/profile parameters,
   anchor point indices and explicit margin 0. They were declared independently of
   reconstruction quality. Rediscover the imported standalone source ID.
2. Explain the declared frame and canonical U/V basis. Start existing
   `start_live_picking` with that source allowlist and a fixed **event budget** of
   `min(100, max(8, 4 * declared_anchor_count))`, chosen before clicking. Native
   qMCPBridge 0.12.0 counts pick events, not unique source vertices, so do **not**
   set `max_picks` equal to the logical anchor count. Repeated clicks on one vertex
   are capture noise and must not exhaust a three-anchor session prematurely.
   Have the human click the predeclared anchor vertices. They are actual vertices in
   the same PLY but outside the slab in depth; they must not be deleted, moved or
   fabricated through point-info JSON. For disposable fixtures only, increasing the
   rendered point size or zooming the view is allowed because it changes display only,
   not geometry; record and restore any display change.
3. Use `get_live_picks` while acquisition is active. Identify the captured indexes
   whose `(entity_id, point_index)` match the **predeclared** logical anchors and
   pass only those distinct indexes to the 0.15.7 intent tools. Extra repeated pick
   records remain in the captured-state provenance but are not logical anchors.
   Once every predeclared anchor has at least one captured source vertex, call
   `stop_live_picking` and freeze the explicit distinct `pick_indices`. Selecting
   which duplicate event represents the same predeclared source point may use the
   earliest matching event; it must never depend on ROI/reconstruction quality.
   If the fixed event budget is exhausted without every predeclared anchor, that
   capture attempt is BLOCKED.
4. A fixture capture may be restarted before **any** ROI/target/reconstruction
   quality is inspected when the reason is plainly acquisition error (for example,
   a missed predeclared dot or repeated event). The restarted attempt must keep the
   same source, declared frame, logical anchor point IDs, parameters and margin.
   This is acquisition retry, not permission to reposition the intended ROI after
   seeing a fit. Verify stopped state, selected source point IDs, global/native
   coordinates and shift/scale.
5. Save the full raw captured state plus declared frame/provenance, chosen distinct indexes,
   fixed acquisition/target parameters and explicit margin BEFORE quality inspection.
6. Call `derive_live_section_roi_from_picks`. This only forms intent and acquires
   source evidence; it must not run target analysis. Save its full compact response
   and `intent_fingerprint`. Independently check UV min/max from those exact host
   picks in the returned frame. Do not substitute ideal manifest coordinates.
7. Freeze that intent. Call `analyze_live_picked_section_target_roi` with unchanged
   declaration plus `expected_intent_fingerprint`. Only then inspect target evidence.
   A reconstruction attempt uses `reconstruct_live_picked_section_target_roi_profile`
   with those same fields and the predeclared layer/profile parameters.

Expected outcomes: clean and transformed-safe supported profiles; three-anchor
bounds consistent with all declared anchors; two targets retain explicit choice;
crossed edge refuses even explicit target IDs; parallel layers require explicit
fresh layer evidence. No malformed, stale, ambiguous or unsafe evidence should be
converted to permission. Record actual results rather than asserting expectations.

Check compact intent-to-ROI context binding, inside+outside=complete returned slab,
zero ROI-unclassified points and downstream point accounting. Anchor depths must be
reported but must not choose a depth sign or filter the slab. Actual request logs
can support caller-side counts, but the wrapper's N+3 report alone is not independent
host instrumentation. Do not silently promote it to native execution-count proof.

For fixed negative probes on DISPOSABLE fixtures, reuse a frozen intent after changing
one explicit margin or frame label: it must stale. A separately predeclared positive
margin test may use margin 0.25; this is a distinct test, not an attempt to make a
blocked reconstruction pass. Retain the original result. Reordering only the
selected-index array should leave intent unchanged. Restarting/clearing only this
gate's own captured fixture picks must not authorize reconstruction with the old
intent. Do not mutate the fan or real source to test staleness.

Host float32 quantization can alter coordinates and hashes. Compare geometry in the
actual acquired frame using justified numerical tolerances; do not require file/live
or snapshot/live fingerprints to match. Record nonunit-scale coverage only if the
real host actually supplies it. Existing proxy tests are not such a measurement.

## 4. Optional fan interaction, only after synthetic gates

Authorized `Fan_project.bin` / working-copy SHA256:

`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`

Verify the authorized file hash and independently rediscover the current source;
406276 points was the retained count, not a hard-coded entity ID. Do not open a
second copy unnecessarily or silently substitute another file/source.

Before any fan ROI analysis, have the human deliberately declare what spatial area
and section plane are intended. Reuse explicit accepted datum/fit geometry only
with its actual provenance and a deliberate semantic declaration. The first live
contract uses canonical U/V from origin/normal, not arbitrary datum X/Y. Freeze the
frame, symmetric thickness, target/layer/profile parameters and margin before quality
inspection. Then capture actual human boundary-anchor picks on that source, stop,
and save all picked/frame evidence. The human interaction must actually occur; an
agent must not claim the human intended whatever a diagnostic happens to show.

Derive once, freeze the exact returned bounds/fingerprint, then analyze. No resizing,
padding search, scale search, higher target/layer budgets, positive/negative-depth
selection, clutter removal, convenient diagnostic-derived rectangle, or choosing the
best-looking reconstruction. No repeated repositioning after inspecting outcomes.
If acquisition exceeds the complete-slab budget, intent derivation itself is BLOCKED;
do not turn a truncated acquisition into a valid intent. If guards, target/layer
ambiguity or unsafe geometry remain, report BLOCKED and retain that useful evidence.
A reproducible ready intent with blocked reconstruction can pass the interaction
subtest; it is not a reconstructed-fan success.

The 0.15.6 fan exercise made no ROI call; the old 0.15.5 result remains inconclusive.
Do not rewrite that history. No real fan call has been performed in the Linux/CI
work for 0.15.7.

## 5. Restore and report

Remove only disposable fixture imports created by this gate. Stop/clear only the
gate's disposable fixture picking sessions; preserve frozen fan picks/evidence for
follow-on work. Restore preexisting roots/selection and other state changed by test
setup where supported. A metadata/sample check is not whole-cloud attribute equality.
Report restoration limitations rather than claiming an unsupported complete restore.

Save reports and JSON evidence OUTSIDE Git. Return PASS/FAIL/BLOCKED per subtest,
exact HEAD/package/import/module hashes, full and focused test counts, fixture hashes,
actual stdio/replay versus GUI coverage, frozen declarations/picks/intents, all refusal
stages, actual shift/scale/precision observations and scene restoration evidence.
Retain limits: no atomic scene epoch, no unobserved whole-cloud proof, and no real-host
nonunit scale/query-count claim without new independent evidence. Report reproducible
product defects separately; do not merge PR #21 or begin a CAD-model IR in this gate.
