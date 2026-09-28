# Windows 0.15.7 partial interaction acceptance — BLOCKED after safe fixture

Date: 2026-09-27. Branch `feature/live-section-roi-from-picks`, draft PR #21.
Tested exact HEAD: `8438ba311c6d31de5a775d3ec3f17a5bca214ce6`.
This report preserves the first visible-host result; it is **not** an accepted/merged
0.15.7 gate and does not replace the external raw evidence.

## Result

Overall: **BLOCKED at the remaining manual-pick gate.** Internal exact-head checks
passed and one real human two-anchor interaction passed. No result is claimed for
unrun target/layer/crossed-edge or fan interactions.

- Internal: installed package 0.15.7; 31/31 installed module hashes matched checkout.
  Ordinary Windows suite: **1194 passed, 16 compiler-gated skipped**. The 16 skipped
  tests subsequently ran under MSVC and **16 passed**. Five focused intent modules:
  **140 passed**. All **18/18 generated fixture hashes** verified. Compileall, both
  diff checks and unchanged native-source check passed. CI run `36370032133`
  succeeded at the exact tested HEAD.
- Visible `safe`: **PASS**. Human source vertices 1200 and 1201 were captured at
  global positions `(-3,-3,8)` and `(11,9,-8)`. Frozen intent fingerprint:
  `da33eb6bd73e1e9c973b9d5d9bd97c6304d69f1f59660063877e4180204a8947`.
  Independent projection confirmed half-open `u=[-3,11)`, `v=[-3,9)`; all 1200
  slab points were accounted for and reconstruction returned a candidate.
- `three_anchors`: **BLOCKED during capture, before ROI quality inspection**.
  Repeated native records for one vertex consumed the session's three-event
  `max_picks` before three distinct logical anchors could be collected. Further
  manual-pick attempts were stopped at the user's request.
- Not run: `two_inside`, `cross_left`, `parallel`, `transformed_safe`, live
  negative probes, and the optional fan interaction. The authorized fan file hash
  matched; **no fan ROI call occurred**.
- Restoration: **PASS with camera limitation**. Only the gate's two imports were
  removed. All 37 original root states matched baseline; selection and captured
  picks were empty and the original rotation-center option was restored. Broad scene
  framing was restored, but exact prior camera pose had not been captured.

The tester's detailed report and raw evidence remain outside Git at the recorded
Windows evidence directory. Do not invent missing GUI results or promote this partial
gate to full acceptance.

## Finding and recovery

This exposed an interaction-fixture issue rather than missing pick provenance:
qMCPBridge 0.12.0 stores exact `entity_id` / source `point_index` for every event,
but auto-stop counts events, including repeated picks of the same source vertex.
No native change is required to preserve intent.

Continuation uses a fixed overprovisioned event budget chosen before clicking,
retains every raw event in provenance, and explicitly selects distinct captured
indexes matching the already-declared logical anchor point IDs. Capture may be
retried before any reconstruction-quality inspection while the declared source,
frame, anchor IDs, margin and analysis parameters remain unchanged. This prevents
accidental repeated clicks from redefining spatial intent and does not search the ROI.
