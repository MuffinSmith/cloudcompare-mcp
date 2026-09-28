# Windows 0.16.0 partial acceptance (user-reported)

Reported 2026-09-27 America/Los_Angeles, tested HEAD
`5559f099670b0e1d86de6df793fca12ffa4ac53e`.
This preserves the user's Windows report, not a repeat run in the development container.
PR #21 and stacked PR #22 stay draft/unmerged.

## Passed

- Isolated Python 0.16.0, 34/34 installed source module hashes.
- Complete MSVC-configured suite: 1393 passed, zero skipped; focused suite: 182 passed.
- Compileall, complete-parent whitespace checks and native review.
- Rebuilt qMCPBridge 0.13.0 / workflow revision 9 in visible CloudCompare 2.13.2.
- DLL SHA256: E934A6EFE3B0A32364FF7A87FABF7CDA6383917F25913A89E4C26724A947FF71.
- Nine deterministic fixture hashes/counts; 36 returned PNGs checked for dimensions,
  hashes and visually reviewed.
- Synthetic camera movement, capture, restoration, refusal and source-safety probes.
- Synthetic inspection and yes/no/unsure, supersession, conflict and permanent-staleness
  checks. Scripted fixture answers are NOT actual human semantic acceptance.
- Original host scene/overlay inventories compared equal; selection stayed empty.

## Fan BLOCKED

Fan SHA256: 79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0.
Visible source: 406276 points, reported ID 355, shift [0,0,0], scale 1;
physical units unknown. IDs/PIDs/ports must be rediscovered.
Threshold 0.15 native units was declared from independent spacing before fitting.
Inspection and direct capture hit a reproducible camera refusal on two acceptance
hosts. No fan fit, reviewed proposal, supported human question, answer or confirmation
was reported. Do not reinterpret this as fan geometry failure or a semantic pass.
No forced restoration after lost ownership; owned tokens were released. Source count,
frame, empty selection and empty overlays were checked afterward.

Final reported acceptance host PID 9364, bridge port 8766. Raw evidence is local to
Windows under `C:/Users/Admin/Documents/CloudCompare/mcp-live-test/acceptance-0160-5559f09-20260927/`:
`ACCEPTANCE_REPORT.md` and `fan-feature-intent.json`. The development container has
not read those local files. Preserve them and inspect the actual camera states and
error phases during the focused retest.

## Diagnosis boundary / next increment

The earlier chat suggested that a full viewport fingerprint conflates image evidence
with camera ownership. This is a design hypothesis, NOT an established fan root cause:
the supplied summary does not identify which field changed. In particular derived
zNear/zFar and the computed view matrix were already outside the old equality hash.
Do not claim that removing those fields fixes the problem.

Implement narrowly scoped navigation guards, preserve full image provenance and
legacy strict guards, avoid overwriting unrelated display-style changes on restore,
and report precise field-level differences and failure phases. Actual navigation,
projection/clipping, session, window and viewport-size conflicts must still refuse.
Add native and installed-MCP regression, verify exact-head CI, then a targeted visible
Windows diagnostic/fan continuation. No picking marathon, threshold search, source
mutation, fan reconstruction, CAD IR, Fusion work or merge is authorized.
