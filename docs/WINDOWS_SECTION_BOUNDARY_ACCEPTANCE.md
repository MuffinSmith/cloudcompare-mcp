# Focused Windows acceptance: 0.15.2 filled-section boundary extraction

This is a reusable test procedure, not an acceptance report. Use the exact branch
and HEAD supplied by the development handoff. Read `AGENTS.md` and
`LIVE_CAD_SECTION_BOUNDARY_EXTRACTION.md` first.

Do not merge, reset, clean, force-push, implement fixes on the Windows test machine,
or rebuild the unchanged qMCPBridge 0.12.0 / workflow revision 8 DLL.

Do not repeat accepted 0.15/0.15.1 Windows topology testing except where the new
filled-section path directly exercises the accepted solver.

## 1. Identity and regression

Target branch:

`feature/live-cad-section-boundary-extraction`

Verify:

- exact supplied HEAD;
- package 0.15.2;
- expected source checkout;
- unchanged native bridge 0.12.0 / workflow revision 8;
- registered tools:
  - `extract_section_boundary_evidence`
  - `reconstruct_filled_section_profile`
  - `reconstruct_live_filled_section_profile`

Run and retain exact output outside Git:

- `python -m compileall -q src scripts tests`
- `git diff --check`
- `python -m pytest -q tests -r s`

If the 16 compiler-gated native policy tests skip only because MSVC is not configured
in the current shell, configure the installed compiler environment and run those
tests separately. That is policy-test execution, not a DLL rebuild.

## 2. Generate fresh committed-code fixtures

Generate into a new directory outside the repository:

`python scripts/make_filled_section_boundary_fixtures.py --output-dir <new-directory>`

Read `manifest.json`. Do not edit the generated PLY files.

Exercise the **actual MCP stdio tools**, not a handwritten reference
implementation.

## 3. Snapshot filled-section evidence

For `filled_section_original.ply` and
`filled_section_rotated_translated.ply`:

1. read exact PLY coordinates;
2. use the manifest frame to project to U/V;
3. call `extract_section_boundary_evidence` through MCP stdio using the manifest
   cell/support settings;
4. call `reconstruct_filled_section_profile` using the manifest topology/fit
   settings.

Expected structural result:

- 3 connected contours;
- 2 material components;
- accepted topology layer recovers roles `outer, hole, island`;
- nesting depths `0, 1, 2`;
- no raw `points_uv` or live position array in either response;
- extraction reports explicit cell size, occupied cells, boundary cells/edges,
  support statistics, source fingerprints, and grid sensitivity;
- every boundary/topology/profile result remains `inferred_candidate`;
- manufacturing intent is not marked confirmed.

Report actual primitive fits and residuals. Do not substitute the old 0.15.1
boundary-only fixture measurements for this occupancy-derived result.

Repeat with a different input permutation and verify geometric diagnostics remain
invariant apart from source-index hashes/previews tied to supplied indexing.

## 4. Resolution, density, and narrow-feature behavior

Run the exact generated nonuniform-density and narrow-feature PLYs.

For nonuniform density, report:

- source point count;
- occupied cells;
- support min/median/P90/max;
- coefficient of variation;
- warnings;
- contour count and topology result.

The implementation may either reconstruct within the documented bounds or report an
honest support/grid warning. It must not silently discard low-density geometry.

For the narrow feature, verify the notch remains evident at the manifest cell size.
Do not accept a result that silently fills/smooths it into the bounding rectangle.

Also exercise deliberate bad inputs:

- too-small `cell_size` relative to coordinate precision;
- grossly too-large `cell_size`;
- isolated one-cell noise with `min_component_cells > 1`;
- diagonal-only grid contact;
- too-small `max_boundary_points`;
- malformed/nonfinite section coordinates.

These must fail explicitly rather than repair the input.

## 5. Original real CloudCompare fixture

Load `filled_section_original.ply` into the real CloudCompare GUI. Resolve its
actual cloud ID and record source metadata, global shift, and global scale.

Call `reconstruct_live_filled_section_profile` through the actual MCP server with
the manifest section frame and recommended settings.

Acceptance requires complete acquisition:

`matched_count == sampled_count`

and no truncation.

Report actual:

- slab matched/sampled counts;
- cell size;
- raw/supported occupied-cell counts;
- boundary cell/edge counts;
- material-component and contour counts;
- grid sensitivity;
- recovered loop topology;
- primitive fits/residuals;
- source shift/scale;
- projection-depth diagnostic.

Verify the source entity metadata is unchanged before/after.

## 6. Rotated / large-translated live fixture

Repeat the live path for `filled_section_rotated_translated.ply`.

Record separately:

- generator mathematical translation;
- CloudCompare's actual global shift;
- CloudCompare's actual global scale;
- MCP bookkeeping.

Verify the MCP result does not apply source shift/scale twice and recovers the same
structural topology as the original fixture.

Do not claim native nonunit-scale coverage unless the host actually uses one.

## 7. Truncation and projected-layer safety

Use a mocked/replay path or a deliberately bounded disposable fixture to verify the
live wrapper errors when acquisition is truncated or matched/sample counts differ.
Do not damage the real fixture to create this case.

Load or replay `filled_section_overlapping_layers.ply` with the manifest's larger
half-thickness. The live wrapper should reject it as possible multiple/thick
projected surfaces rather than claiming a trustworthy 2D material outline.

This is a safety/refusal acceptance check, not a requirement to force a profile.

## 8. Bounded fan-project exercise

Use a working copy of the retained `fan_project.bin`.

The purpose of this stage is specifically to remove the old
`boundary_samples_only=true` requirement for a normal filled section. Select one
bounded fan slab similar in scale to the previous 5,605-point exercise, but do not
tune the algorithm specifically to the fan.

The live call is valid only if acquisition is complete and does not exceed the 20,000
sample limit. If it does, isolate a smaller region/cloud rather than relying on
reservoir sampling.

Report:

- fan cloud ID/name and source point count;
- slab matched/sampled counts;
- half-thickness and signed-offset diagnostics;
- cell size;
- raw/supported occupied cells;
- boundary cells/edges;
- material-component/contour count;
- grid-origin sensitivity;
- topology roles/nesting if recovered;
- primitive fits and residuals;
- warnings;
- whether multiple projected surfaces or another unsupported condition is present.

PASS is not defined as "must produce a CAD profile." A truthful BLOCKED result for
unsupported/ambiguous occupancy is acceptable evidence. Never weaken thresholds or
discard inconvenient components solely to make the fan pass.

## 9. Source integrity and reporting

Capture source metadata before and after live tests. The new tools are read-only and
must not mutate the source.

Return PASS / FAIL / BLOCKED for:

- checkout/runtime identity;
- complete regression;
- exact generated fixture files;
- snapshot filled-section evidence;
- snapshot composite reconstruction;
- original live fixture;
- transformed live fixture;
- density/narrow-feature behavior;
- truncation/layer ambiguity safety;
- coordinate bookkeeping;
- source integrity;
- bounded fan exercise.

Include actual numerical diagnostics and limitations. Keep reports, generated
fixtures, raw MCP envelopes, screenshots, and temporary scripts outside Git.

Open/update a GitHub issue only for a reproducible product defect. A documented
refusal caused by incomplete acquisition, grid sensitivity, or projected-layer
ambiguity is not by itself a defect.

Do not merge to main. Return the report to the development chat.
