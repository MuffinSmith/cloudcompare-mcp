# Focused Windows acceptance: Python-only 0.14 datums/relationships

This is a reusable procedure, **not an acceptance report**. Read AGENTS.md and
LIVE_CAD_DATUM_RELATIONSHIPS.md first. Use the exact branch/head from the handoff.
Do not merge, reset, clean, force-push, switch development lanes, implement fixes,
or rebuild the unchanged 0.12.0 / revision 8 DLL. Python package 0.14.0 is new.
Keep CloudCompare visible, but do not routinely use screenshots or send point arrays
to chat. Save all probes, raw outputs and reports outside Git.

## 1. Checkout and runtime identity

Inspect status, current branch, remote heads and AGENTS.md. Preserve unrelated work.
A clean checkout on another retained branch (for example `feature/live-hole-patterns`)
is **not** a conflict and is not a reason to stop. Fetch the target branch, switch to
`feature/live-cad-datum-relationships`, and fast-forward it only to the supplied
exact SHA. If the target branch does not yet exist locally, create a tracking checkout
from the matching remote branch. Do not reset, clean, force-checkout, or discard work.
BLOCK only for actual uncommitted/staged work that would be endangered, unexpected
branch divergence, a remote target that does not match the supplied SHA, or a failed
safe switch/fast-forward. Confirm no diff under `cloudcompare-plugin` versus accepted
main `e39949759c6386e5cd0387983c43a74f26e6a58e`.

Using the actual MCP interpreter, install the Python checkout and test dependencies
as needed, then restart only its Python MCP process if needed. Verify package path,
package version 0.14.0, tool listing, and live plugin 0.12.0 / workflow revision 8.
Do not mistake a stale MCP process or another checkout for a product failure.
Run `python -m compileall -q src scripts tests`, `python -m pytest -q tests`, and
`git diff --check`, keeping exact counts and output outside Git. Note platform
skips honestly. Existing 0.13 acceptance is not reopened by this step.

## 2. Actual MCP snapshot contract

Through the running MCP server, not just a direct Python function, call both tools
with the documented synthetic example. Relationship analysis receives only its
own allowed arguments, not datum-specific IDs. Verify the expected `[3,4,0]` origin,
+X/+Y/+Z with the explicit hints, determinant +1, orthonormality, native-unit labels,
candidate states and complete feature-reference attribution. Repeat each call and
reverse feature input order: output should be deterministic and inputs untouched.

Verify a malformed global/local envelope, wrong units, NaN/Inf via a Python probe,
zero direction, duplicate IDs, unknown ID and nearly parallel/degenerate secondary
definition return MCP `isError` without scene operations. Verify that sign hints can
flip X/Z while preserving right-handedness and that an ambiguous hint fails.
Run the committed real-stdio test as well: it deliberately has invalid bridge
configuration to prove these snapshot tools do not require a host connection.

Use an offline snapshot with a nonzero `global_shift` and nonunit positive
`global_scale`; verify these are copied exactly, not applied again. This is **snapshot
bookkeeping coverage**, not proof of actual native nonunit-scale behavior.

## 3. Real-host acquisition -> snapshot -> datum

Generate fixtures once into a NEW directory outside the checkout:

`python scripts/make_datum_fixtures.py --output-dir <new-outside-repo-directory>`

Resolve the manifest and actual files. It contains isolated primary-plane,
secondary-plane, and bore clouds for original and rotated/large-translated variants.
Load into the real CloudCompare test instance using the accepted loading workflow.
Keep generated entities clearly separate; do not operate on user geometry by name
alone. The instance may be reopened without saving when needed, but unrelated
files and changes must not be deleted.

For each variant, identify the actual cloud IDs, record source metadata and use
existing bounded `fit_live_region_plane` and `fit_live_region_cylinder` tools to
measure the isolated clouds. Use global selectors enclosing manifest bounds, padded
in all axes (a zero-thickness box is invalid). Plane samples up to 2000 points and
cylinder samples up to 2000 cover these fixtures. Use actual fit outputs unchanged;
do not replace imperfect results with manifest geometry. Check the existing fit
quality and finite values before feeding them forward.

Construct the datum from the two plane fits and the cylinder-origin axis. Supply
manifest X/Z hints, `minimum_datum_angle_degrees: 1`, and an explicitly documented
native-unit distance tolerance (0.02 is a starting fixture acceptance bound, not
physical uncertainty). Analyze relationships with angular tolerance 0.2 degrees.
Compare the result numerically against the manifest using a local harness: origin
within 0.02 native units, axes within 0.2 degrees, orthogonality error <= 1e-12,
determinant within 1e-12 of +1, and bore radius within 0.02 native units. Report
actual residuals, not just PASS. Do not loosen bounds silently to manufacture a pass.

For the large-translation variant, record actual native global-shift/scale metadata
returned by the host. Confirm fitted positions really match the global manifest;
do not relabel local values or apply source shift twice. Native nonidentity shift
is a separate coverage claim from arbitrary mathematical rotation. If nonunit
native scale was not exercised, explicitly mark it untested even though supplied
snapshot scale preservation was checked.

Compare source metadata before and after. New tools must not load, transform,
rename, sample, delete, export or create overlays. Existing fits acquire samples;
new tools only consume their snapshots. Keep acquisition tests distinct from the
new snapshot computation. Do not claim full point integrity from metadata alone.

## 4. Small fan-project exercise

Resolve `fan_project.bin` as the authorized disposable test copy; do not assume a
path or overwrite the original. Use a working copy. Select one component and obtain
a suitable primary plane and nonparallel secondary plane/axis using existing
structured fitting/discovery. A bore perpendicular to a primary plane can define
an origin but cannot also define its in-plane X direction; degenerate definitions
should fail. Do not invent an edge direction to make a frame succeed. If a suitable
second observation cannot be obtained in bounded work, report this fan subtest as
BLOCKED with the actual acquisition limitation; the synthetic results remain valid.

Build and analyze the measured snapshots, retaining cloud IDs, fit/sample residuals,
known coordinate bookkeeping and fingerprinted source evidence. Report measured
relationships in native units, not confirmed wall thickness, holes or design intent.
Record any missing metadata and any origin/sign ambiguity. Inspect before/after
source metadata and compare a documented selected-cloud XYZ/normals sample locally
where practical. State exactly whether integrity evidence was metadata-only,
sampled, or full-cloud; do not generalize selected-component coverage to all clouds.

## 5. Result and defect handling

Report PASS / FAIL / BLOCKED by subtest, exact checkout and running Python paths,
plugin/runtime versions, numerical residuals, test counts, source-integrity scope,
coordinate-bookkeeping scope and remaining limitations. Keep raw evidence outside
Git. For a product defect, open/update a GitHub issue with the exact source/runtime,
minimal repro, expected/actual behavior and compact evidence. Do not implement fixes
on the testing machine. Return the report for correction and focused retest.

A successful run is not merge authorization. Stop without merging to main.
