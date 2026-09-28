# Focused Windows / CloudCompare acceptance — 0.15.6

This is a new ROI gate, not a request to repeat accepted 0.15.5 GUI acceptance.
Do not merge. Use branch `feature/live-cad-section-target-roi`, accepted-main parent
`809c522550274316fa0a14d2e86d90a4921bfc03`. Runtime/test checkpoint:
`5d618c0de30c90a4573d4c8be52174a3aed58eee`. Resolve exact current branch HEAD and
read AGENTS before testing; later documentation-only descendants may be accepted
without pretending the runtime changed. Stop on conflicting unexpected runtime work.

Internal prerequisites at the runtime checkpoint passed: 1070 tests, zero skips in
both installed sandbox and CI run 36363760167/job 108745962764; compileall and full
diff/native-immutability checks passed. Draft PR #20 is open, not merged. This is
not real-host acceptance.

## Identity and installation

Preserve all checkouts and retained branches. Do not reset, clean, force-push, reuse
an occupied branch in another worktree, or invent retry/recovery branches. A clean
isolated detached worktree at the verified HEAD is appropriate. Record HEAD, merge
base with main, Python executable/version, package version and import path, and the
actual CI run/status for that exact tested revision.

Use an isolated environment and install `.[test]` from the verified checkout.
Confirm `importlib.metadata.version('cloudcompare-mcp') == '0.15.6'` and imports are
from that checkout/environment. Run the full installed regression, compileall for
src/scripts/tests, `git diff --check`, and full diff against the accepted parent.
If ordinary Windows shell skips the 16 compiler-gated native policy tests, configure
MSVC and run those tests separately. This compiles policy tests, **not a plugin DLL**.
Do not claim zero skips without accounting for those 16 results.

Verify that `git diff <accepted-parent> HEAD -- cloudcompare-plugin` is empty.
Keep the existing qMCPBridge **0.12.0 / workflow revision 8**. Do not rebuild or
replace its DLL. Identify the visible CloudCompare process, executable/version,
loaded bridge and port owner; do not accidentally target a hidden CLI/test process.

## Generated evidence and actual MCP

Generate the fixed files into a new directory outside Git:

```powershell
python scripts/make_section_target_roi_fixtures.py C:\path\outside-repo\roi-0.15.6-fixtures
python -m pytest -q tests/test_section_target_acquisition.py tests/test_section_target_roi.py tests/test_section_target_roi_workflow.py tests/test_section_target_roi_safety.py tests/test_section_target_roi_tools.py tests/test_section_target_roi_fixtures.py tests/test_section_target_roi_stdio.py
```

Choose a genuine new output path; the generator intentionally refuses overwrite.
Read `manifest.json` and verify all 22 exact PLY SHA256 hashes. Exercise these files,
not newly approximated replacement arrays. Keep detailed reports and raw samples
outside Git. The tests include actual MCP stdio and a replay TCP peer; report those
as transport/replay tests, not visible-GUI validation.

Launch a temporary MCP stdio process from the isolated environment, not a stale
production registration. Confirm the four advertised schemas and additive ROI
capability. Exercise both snapshot tools with the bridge unavailable and both live
tools against the identified visible CloudCompare process during the next phase.
No raw point-array responses, source mutation, automatic ROI/scale search or silent
fallback is permitted.

## Focused visible-GUI fixture gate

Use disposable imported fixture entities; discover their actual cloud IDs. Do not
reuse IDs from earlier sessions. Preserve existing user clouds, selection, visibility
and overlays unless a deliberate reversible test action requires otherwise. Do not
clear managed overlays merely to simplify the test. Record/restorably scope any
GUI changes. The ROI tools themselves are read-only and request no overlays.

Use each fixture's declared origin, normal, slab thickness, ROI and parameters from
the manifest. Confirm frame identity before interpreting `(u,v)`. At minimum exercise
`outside_clutter`, `one_of_two`, `two_inside`, all four `cross_*` files, `half_open`,
`safe_margin`, `narrow_bridge`, `sparse`, `empty`, `tiny`, `parallel`, `overlap`,
`alternating_thick`, `transformed_safe`, `transformed_parallel` and
`transformed_cross_left`. Analyze remaining fixtures numerically through exact-file
product tests; a generic fan-like fixture need not reconstruct.

For each complete host acquisition verify inside + outside = returned = matched,
zero ROI-unclassified points, and exact accounting when target analysis itself
refuses. Check per-side and union guard counts without double-counting corners.
Guard-connected candidates must refuse, including explicit candidate ID attempts.
Outside-adjacent support is all-depth projected evidence, not proof of a connection.
No automatic expansion/shrinking or choosing a different scale is allowed.

A safe single target may reach accepted reconstruction. Two supported targets must
require a target ID plus its current nested candidate fingerprint; never choose by
size, ROI-center distance or reconstruction quality. After fixing target-selection
mode, obtain fresh layer evidence before layer selection. `parallel` retains both
depths, then requires accepted layer selection. `overlap` and `alternating_thick`
remain unsafe; explicit target/layer IDs must not bypass their refusal. Record the
complete root outside/unselected counts for every downstream attempt.

Test stale ROI bounds and source/context changes in controlled disposable fixtures.
Reject ROI report and 0.15.5 diagnostic fingerprints as reconstruction authorization.
Do not run the five diagnostic panels to select ROI bounds or production scale.
A newly declared bound in an independent test is not permission for tool-driven ROI
search; keep each test's intent and expected safety property explicit.

For large-coordinate imports, record **actual** global shift/scale and acquired
frame. Already-global coordinates must not be shifted/scaled twice. Compare counts,
geometry within measured host precision and safety state; exact snapshot/live hashes
may differ after float quantization. In particular `nextafter` distinctions in a
double PLY can collapse in CloudCompare local storage: validate half-open semantics
against actual acquired values and report the representation change, rather than
requiring impossible bit-exact preservation or snapping boundaries. A nonunit-scale
claim requires an actual measured host case; replay scale 2.5 is not sufficient.

Native one-query behavior is measured by replay tests. Independently count host
queries only with appropriate noninvasive instrumentation; otherwise retain that
coverage limitation. Full slab/file hashes do not establish full-cloud geometry or
attribute equality. Record source integrity at the actual measured level, at least
scene metadata before/after, without promoting it to stronger coverage.

## One bounded optional real-fan exercise

Only after the synthetic/host gates are coherent, use the authorized working copy
of `Fan_project.bin`, verify its SHA and discover the current source entity. Old
acceptance cloud385 was session-local and must not be assumed current. Do not change
the source scan. Retained 0.15.5 fan diagnostics remain BLOCKED/inconclusive, not failed.

Declare one spatial intent and one UV ROI **before inspecting reconstruction
quality**, based on an intentionally chosen visible/picked region and a recorded
section frame. Do not derive bounds from whichever 0.15.5 panel looked convenient.
Keep the declared accepted UV/depth cells, max_targets32 and layer limits. Do not
raise limits, select a depth sign, discard clutter, search ROI sizes or retry until
a convenient outline appears. When no defensible spatial intent/frame is available,
report this optional exercise BLOCKED instead of inventing bounds.

Run one ROI analysis. Report full slab, inside/outside, edge contact, candidate states
and eligible/blocked targets. Only a genuinely supported guard-clear target may
proceed through target → layer → occupancy → topology → fitting, using fresh current
fingerprints and retaining all root accounting. Multiple candidates still require
explicit intent-bound selection. Stop on ambiguity/refusal. Fan success is not an
acceptance criterion and no automatic CAD/manufacturing claim may be made.

## Report and stop

Return PASS/FAIL/BLOCKED separately for installation/regression, exact-file numerical
tests, schema/actual stdio, replay, visible-GUI fixtures and the declared fan exercise.
Include exact tested SHA, import identity, CI run/result, point counts, selected and
unselected counts, refusal stages, observed shift/scale/precision, native query-count
coverage and actual source-integrity coverage. Keep bulky evidence outside Git.
If a reproducible product defect appears, record a minimal reproducer and stop the
affected gate; do not hide it by changing parameters or silently rebuilding the DLL.
Do not merge or broaden scope. Leave enough evidence for another chat to resume.
