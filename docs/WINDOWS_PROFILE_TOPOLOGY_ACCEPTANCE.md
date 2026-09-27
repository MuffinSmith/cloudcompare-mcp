# Focused Windows acceptance: 0.15.1 explicit profile topology

This is a reusable test procedure, not an acceptance report. Use the exact branch/head
from the handoff. Read AGENTS.md and LIVE_CAD_PROFILE_TOPOLOGY.md first.

Do not merge, reset, clean, force-push, implement fixes on the test machine, or
rebuild the unchanged qMCPBridge 0.12.0 / workflow revision 8 DLL.

## 1. Identity and regression

Target branch:

`feature/live-cad-profile-topology`

Verify the exact supplied HEAD, package 0.15.1, source path and unchanged native
bridge 0.12.0 / workflow revision 8.

The new tools must be registered:

- `reconstruct_section_topology`
- `reconstruct_live_section_topology`

Run and retain exact outputs outside Git:

- `python -m compileall -q src scripts tests`
- `python -m pytest -q tests -r s`
- `git diff --check`

If compiler-gated native policy tests skip only because MSVC is not configured in
the process environment, configure the installed compiler environment and run those
tests separately. Do not call policy-test execution a DLL rebuild.

## 2. Snapshot topology contract

Generate fresh topology fixtures outside Git:

`python scripts/make_profile_topology_fixtures.py --output-dir <new-directory>`

Read the generated manifest.

For each PLY fixture, use the manifest frame to project its coordinates to section
U/V locally and send the resulting **unordered boundary samples** through the actual
MCP stdio tool `reconstruct_section_topology`.

Use the manifest recommended settings, including:

- `boundary_samples_only=true`
- explicit `max_edge_length`
- explicit `fit_tolerance`

Expected for both original and transformed variants:

- loop_count = 3
- role candidates exactly `outer, hole, island`
- nesting depths exactly 0, 1, 2
- hole parent = outer
- island parent = hole
- source point counts match the manifest
- outer area matches the manifest within 0.001 native-unit²
- hole circle radius within 0.001 native units of 2.5
- island circle radius within 0.001 native units of 0.8
- no raw `points_uv` array in the result
- every loop/profile remains an inferred candidate, not accepted intent

Repeat with a different input permutation and verify geometric loop roles, areas and
fitted dimensions are invariant. Source-index hashes/previews are allowed to differ
because they refer to the supplied input indexing.

Also verify expected errors for:

- `boundary_samples_only=false`
- too-small `max_edge_length` that leaves an open graph
- deliberately overlarge edge threshold that makes topology ambiguous
- duplicate coordinates
- a self-intersecting/touching boundary
- too-small loop budget

These errors must occur without inventing repaired topology.

## 3. Original real CloudCompare fixture

Load freshly generated `topology_original.ply` into the real CloudCompare instance.
Resolve its actual cloud ID and record source metadata/global shift/scale.

Call `reconstruct_live_section_topology` through the actual MCP server with the
manifest origin/normal and recommended settings.

Do not call the tool unless `boundary_samples_only=true` is an honest assertion for
this fixture.

Acceptance:

- complete acquisition: matched_count == sampled_count == manifest point count
- no truncation
- loop_count 3
- roles outer/hole/island with nesting depths 0/1/2
- correct parent chain
- source point counts match the manifest
- outer area within 0.001 native-unit²
- hole radius within 0.001 of 2.5
- island radius within 0.001 of 0.8
- result contains no raw position/sample arrays
- source coordinate bookkeeping is preserved
- source metadata unchanged before/after

Report actual values, not only PASS.

## 4. Rotated / large-translated real fixture

Repeat the same live MCP path for `topology_rotated_translated.ply`.

Record separately:

- generator mathematical translation
- CloudCompare's actual source global shift
- CloudCompare's actual global scale

Verify the MCP result preserves the native shift/scale bookkeeping exactly and does
not reapply it to already-global geometry.

Apply the same topology/dimension bounds as the original fixture.

Do not claim native nonunit-scale coverage unless the host actually uses a nonunit
scale.

## 5. Truncation and filled-slab safety gate

With a mocked/replay or isolated disposable fixture path, verify the live wrapper
returns an MCP error when the native acquisition says it is truncated.

Do not intentionally damage the real fixture to manufacture this case.

Verify `boundary_samples_only=false` fails before bridge I/O.

This increment explicitly does not infer boundaries from ordinary filled scan slabs.
Do not reinterpret that documented limitation as a product failure.

## 6. Bounded fan-project exercise

Use a working copy of `fan_project.bin`.

This is a narrow capability check, not a requirement to force the fan through the
new tool.

Look for one section where you can honestly establish that the acquired points are
boundary-only, for example an already isolated edge/outline cloud.

If such a boundary-only sample can be obtained without inventing or discarding
geometry, run `reconstruct_live_section_topology` and report loop count, nesting,
fit residuals and provenance.

If the available fan slab contains filled surfaces, front/back layers, interior
samples, or otherwise cannot satisfy `boundary_samples_only=true`, mark this fan
subtest **BLOCKED by acquisition**, not FAIL. Do not set the assertion true just to
make the tool run.

That blocked result is useful evidence for the following filled-section boundary
extraction increment.

## 7. Reporting and defect handling

Return PASS / FAIL / BLOCKED for:

- checkout/runtime identity
- full regression
- snapshot multi-loop topology
- original live fixture
- transformed live fixture
- truncation/assertion safety
- coordinate bookkeeping
- source integrity
- bounded fan exercise

Include exact numerical measurements and remaining limitations.

Open/update a GitHub issue only for a reproducible product defect. Documented refusal
to infer topology from filled samples is not a defect.

Keep reports, raw MCP envelopes, temporary scripts and generated fixtures outside Git.

Do not merge to main. Return the report to the development chat.
