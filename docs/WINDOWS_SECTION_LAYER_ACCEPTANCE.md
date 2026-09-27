# Focused Windows acceptance: 0.15.3 section layer isolation

This is a reusable procedure, not a completed acceptance report. Use the exact
branch/HEAD supplied by the development handoff and read AGENTS.md plus
LIVE_CAD_SECTION_LAYER_ISOLATION.md first. The active branch is
`feature/live-cad-section-layer-isolation`, based on accepted main
`cb1ee9eab9c64ff4806036a6317606938faa22e6`.

Test and report only. Do not implement fixes, merge 0.15.3, reset, clean, force-push,
delete retained branches, or overwrite unexpected working files. Preserve any
existing work. Use an isolated worktree when necessary rather than switching away
from an unrelated dirty checkout. Do not rebuild the unchanged qMCPBridge DLL.
Do not repeat the completed full 0.15.2 Windows/fan acceptance merely for this new
checkout; only exercise accepted paths as part of the new layer handoff.

## 1. Checkout, runtime and regression

Verify exact supplied HEAD, installed package 0.15.3, source checkout and interpreter
paths. Configure the Python environment for this checkout as needed; that is separate
from native DLL installation. The real GUI bridge must remain 0.12.0 / workflow
revision 8. Compare native sources to accepted main before claiming no rebuild.

Through actual MCP stdio verify all four tools are present:

- `analyze_section_layers`
- `analyze_live_section_layers`
- `reconstruct_section_layer_profile`
- `reconstruct_live_section_layer_profile`

Verify `python_section_layers.version=0.15.3` and the unchanged accepted profile
capability version 0.15.2. Retain exact output outside Git from:

```text
python -m compileall -q src scripts tests
git diff --check
python -m pytest -q tests -r s
```

If the 16 native policy tests skip because MSVC is not configured in the shell,
configure the installed compiler environment and run `tests/test_native_overlay_safety.py`
separately. Those are policy tests, not a plugin build. Distinguish dependency or
transport failures from passing product checks and from valid geometry refusals.

## 2. Exact generated fixture files

Use a new directory outside the repository:

```text
python scripts/make_section_layer_fixtures.py <new-absolute-directory>
```

Read `manifest.json`, verify its PLY hashes and point counts, and do not edit the
fixtures or tune their committed settings. Keep generated files, raw envelopes,
reports and temporary test scripts outside Git.

For snapshot MCP tests read the actual PLY coordinates, project using each manifest
origin/normal through the production section projection, and form the documented
`section_uv_depth` envelope with its complete assertion. Never flatten away signed
depth before layer analysis. The generator's strict PLY reader may be reused; it is
not a general file importer. Pass actual finite numeric rows, not documentation
placeholders. Use nested `layer_parameters` and `profile_parameters` from the manifest.

Expected snapshot classifications:

| Fixture | Expected result |
| --- | --- |
| single, sloped, noisy_within_bound, transformed_single | One usable layer, `ready` |
| parallel, transformed_parallel, fan_like | Two credible candidates, `selection_required` |
| three | Three candidates, no automatic selection |
| partial_overlap | Two candidates and positive partial-overlap diagnostics |
| crossing, too_thick, sparse | Explicit blocked evidence, no invented outline |

Report exact point/cell/observation counts, layer counts, support/thickness/depth
statistics, overlap, warnings and all blocking reasons. Sum candidate point counts
and verify every acquired point remains accounted for. Repeat an arbitrary sample
permutation and verify canonical analysis/fingerprints are stable for the same source.
Responses must be compact and contain no raw sample/position arrays.

The fixture default `min_cell_points=1` explicitly allows singly sampled edge cells;
the sparse fixture requires 3. Do not confuse either with universal real-scan support
requirements. Do not silently adjust settings when an exact fixture fails.

## 3. Snapshot selection and accepted profile handoff

Call `reconstruct_section_layer_profile` for exact single and transformed_single
files using their manifest parameters. Expect one selected component, zero unselected
points, one outer topology loop and primitive candidates through nested accepted
0.15.2 profile output. Report actual primitive types/residuals; do not substitute
historical 0.15.1 or 0.15.2 fixture measurements.

For parallel layers, call the composite without a choice first. It must return
candidates/BLOCKED at `layer_selection`, never collapse the two layers automatically.
Choose a specified candidate by its reported ID, not by fit quality; supply the exact
current analysis fingerprint. The result must account explicitly for both selected
and unselected source points. Change a parameter/frame/source snapshot and verify
that reusing the old fingerprint is rejected. Explicit choice must not bypass the
crossing/thick/sparse blocking evidence.

A deliberately too-small profile `max_edge_length` should retain layer evidence and
available occupancy diagnostics while returning the accepted topology refusal.
Manufacturing intent and user acceptance must remain false throughout.

## 4. Actual live CloudCompare gate

Keep CloudCompare visible, prefer structured geometry, and avoid routine screenshots.
Load the disposable generated PLYs into the real GUI, resolve their actual entity IDs,
and capture source metadata before/after. Use actual MCP stdio tools against the
real installed bridge, not a monkeypatch or the CI TCP replay server.

For single and transformed_single, run both live analysis and the live composite with
the manifest frame/slab/parameters. Record equal matched/sampled counts and explicit
no truncation. Expect one usable layer and the same structural single outer-loop
handoff. Native float storage may perturb numerical values; report actual precision,
residuals and source metadata rather than claiming bitwise identity with snapshots.
A changed classification for an exact fixture must be reported, not hidden by tuning.

For parallel, transformed_parallel, three, partial_overlap and fan_like, verify
credible separate candidates, explicit overlap where applicable, and refusal of
automatic multi-layer continuation. For at least the original and transformed
parallel fixtures, perform an explicit current-fingerprint choice through the live
composite and account for all selected/unselected points. Obtain a live fingerprint;
a snapshot fingerprint must not be reused for a different source.

For sloped/noisy fixtures verify one supported component within the declared local
thickness bound. For crossing, too_thick and sparse fixtures verify honest blocked
evidence and refusal even with an explicit choice. Report the reason class and actual
counts rather than requiring a convenient profile or a hardcoded crossing count.

Each live call must use complete acquisition. Deliberately lower `max_points` on a
disposable fixture to verify a structured error rather than reservoir-based topology.
Do not alter a real source to manufacture truncation. Existing automated tests cover
malformed/duplicate/out-of-slab replay records; do not describe replay tests as real
host validation of malformed native behavior.

## 5. Coordinate provenance and source integrity

Record separately the generator transform, actual CloudCompare source global shift,
actual global scale, section origin/normal/bases, acquisition counts and source/layer
fingerprints. Verify global shift/scale is not applied twice. The generated large
translation is approximately `[100000000,-200000000,300000000]`; do not assume it is
the GUI's exact chosen global shift. Measure that shift.

Record actual integrity coverage: at minimum source entity metadata before/after.
A sampled hash covers only those sampled points. Claim full source-point integrity
only if a full before/after export/hash was actually performed. The new tool's bounded
acquisition hashes are not full-cloud before/after verification.

Do not claim real native nonunit-scale acceptance merely because snapshot/replay tests
use scale 2.5. Record whether any real GUI source actually uses nonunit scale. Preserve
the earlier metadata-only and scale-1 acceptance limitations where not expanded.

## 6. One bounded real fan exercise

Use a working copy of the retained `fan_project.bin`; resolve its actual path and
entity identity rather than assuming historical IDs. The prior selected source was
cloud 359, `Assembly | Fan - scan 1`, 406,276 points; slab origin `[40,0,135]`, normal
`[0,0,1]`, half-thickness 0.5, with complete 5,605/5,605 acquisition. These are context,
not values to force the current host to reproduce.

Declare one justified native-unit UV neighborhood, depth separation, local thickness,
neighbor step and support requirement BEFORE running the analysis. For an initial
bounded diagnostic of this historical slab, an explicitly exploratory baseline is
UV cell 5.0, separation 0.15, local thickness 0.08, neighbor step 0.10, minimum cell
support 3, minimum layer cells 4, 20,000 points/cells and 16 components. These settings
are not calibrated manufacturing tolerances or promised successful reconstruction.
Do not search parameter combinations until a CAD outline passes. If the scale or
source makes those settings inappropriate, state the rationale for the single chosen
alternative before seeing its reconstruction result.

Run `analyze_live_section_layers` once on that complete bounded slab. Report source
identity, matched/sampled counts, depth quantiles, UV scale/support, local modes,
layer summaries, overlap, ambiguity/thickness/sparse reasons and fingerprints.
An over-budget or unsupported result may legitimately remain BLOCKED. Do not select
positive/negative depth, delete one side or weaken accepted 0.15.2 occupancy safety.

Only if evidence supports one usable layer, or a defensible explicit caller choice
among wholly usable candidates is specified, call the composite for that exact layer.
Retain layer evidence, selected/unselected counts, occupancy diagnostics, topology,
primitive fits/residuals, provenance and ambiguity. BLOCKED is a valid fan outcome;
success means honestly explaining/separating depth structure, not producing a CAD
outline at all costs. No real fan success is claimed by synthetic fan_like tests.

## 7. Report and stop

Return PASS / FAIL / BLOCKED for checkout/runtime, complete regression, exact files,
snapshot analysis/selection, actual MCP transport, original/transformed live paths,
all safety fixtures, coordinate bookkeeping, source integrity and bounded fan.
Include exact checkout HEAD, installed Python/native versions, test counts/skips,
actual numerical diagnostics, selected/unselected counts, primitive residuals, no raw
arrays, no source mutation, and every coverage limitation. Keep raw evidence outside Git.

Open a GitHub issue only for a reproducible product defect, with exact SHA, minimal
fixture and failure. A documented ambiguity or correct refusal is not itself a defect.
Do not implement a fix on the acceptance machine and do not merge 0.15.3. Return the
report to the development chat for review and separate user merge approval.
