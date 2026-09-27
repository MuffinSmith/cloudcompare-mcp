# Focused Windows acceptance: Python-only 0.15 profile reconstruction

This is a reusable test procedure, not an acceptance report. Use the exact branch and
head supplied in the handoff. Read AGENTS.md and LIVE_CAD_PROFILE_RECONSTRUCTION.md.
Do not merge, reset, clean, force-push, implement fixes on the test machine, or rebuild
the unchanged qMCPBridge 0.12.0 / workflow revision 8 DLL.

## 1. Checkout/runtime identity

Preserve unrelated work. A clean checkout on another retained branch is not a
conflict: fetch, safely switch to `feature/live-cad-profile-reconstruction`, and
fast-forward only to the supplied exact head. Block only for actual local work at
risk, divergence, target mismatch or a failed safe switch. Verify there is no native
source diff under `cloudcompare-plugin` versus the accepted 0.14 main baseline.

Using the configured MCP interpreter, install the Python checkout/test dependencies
and restart only the Python MCP process when necessary. Verify package 0.15.0, source
path, registered `reconstruct_section_profile` and `reconstruct_live_section_profile`,
and live plugin 0.12.0 / revision 8.

Run and retain exact outputs outside Git:

- `python -m compileall -q src scripts tests`
- `python -m pytest -q tests -r s`
- `git diff --check`

If compiler-gated native policy tests skip, configure the already installed MSVC
environment and run those skipped tests separately as in prior acceptance. Do not
claim a DLL build from policy-test success.

## 2. Snapshot/no-host profile contract

Through the actual MCP stdio server, test `reconstruct_section_profile` with synthetic
native U/V data for:

- exact circle -> one circle + circle candidate
- rectangle -> four lines + rectangle candidate
- slot -> two lines/two arcs + slot candidate
- open line and open arc
- rotated/noisy examples
- reversed/shuffled closed-slot input using `polar_closed_loop`

Verify repeat determinism, compact outputs, raw points not echoed, candidate—not
accepted—semantics, provenance/frame preservation, and no live bridge request.
Malformed coordinate space/units, NaN/Inf, zero/negative tolerance, incompatible
ordering mode and too-small segment budget must return MCP errors. Test a tolerance
exactly at a measured residual boundary and immediately below it.

## 3. Real CloudCompare fixture path

Generate fixtures once into a new directory outside the checkout:

`python scripts/make_profile_fixtures.py --output-dir <new-outside-repo-directory>`

Load both PLY files into the real CloudCompare test instance. Resolve actual cloud IDs
and record scene metadata/global shift/scale. Do not alter source entities.

For each manifest variant call `reconstruct_live_section_profile` through MCP using
the manifest origin/normal and recommended settings. The tool must acquire via the
real native slab query; do not replace its live result with direct Python geometry.

Expected compact result:

- primitive sequence: two lines and two arcs (cyclic rotation of the sequence is OK)
- `slot_candidate`
- radius within 0.01 native units of 5
- width within 0.02 native units of 10
- centerline length within 0.02 native units of 20
- overall length within 0.03 native units of 30
- line parallel error <= 0.2 degrees
- each semicircle error <= 0.5 degrees
- all primitive maximum residuals <= the supplied fit tolerance

Report actual residuals and dimensions. For the large translated fixture record the
host's actual global shift/scale separately from the generator's mathematical
translation. Verify the MCP result preserves the native region query's shift/scale
bookkeeping exactly and does not apply it again to the already-global profile geometry.
Do not claim native nonunit-scale coverage unless the host actually uses one.

Confirm the MCP result contains no raw `points_uv` or `position_global` sample arrays.
Record all-match/sample counts, sampling strategy and whether truncation occurred.

## 4. Bounded real-scan exercise

Use a working copy of `fan_project.bin`, not the original. Do **not** repeat the 0.14
fan-datum gate. Select one component/section where a simple single closed outline can
reasonably be isolated. Establish an explicit global section plane from already
measured geometry, then try `reconstruct_live_section_profile` with an honest native
fit tolerance.

If the section contains multiple loops, severe occlusion, non-star-shaped topology or
mixed surfaces such that `polar_closed_loop` is not justified, report this subtest
BLOCKED by the documented first-increment ordering limitation. Do not discard points,
invent an order, or promote a bad fit merely to produce a CAD candidate. A clean
BLOCKED result here is useful evidence for the next 0.15 boundary-graph increment,
not automatically a product defect.

If a simple loop is available, report primitive residuals/candidates and inspect
before/after source metadata. State integrity coverage precisely; do not generalize a
selected-component check to the full project.

## 5. Result/defect handling

Return PASS / FAIL / BLOCKED per subtest with exact checkout/runtime paths, versions,
test counts/skips, fixture measurements, ordering mode, acquisition/truncation data,
coordinate bookkeeping and source-integrity scope. Keep raw evidence outside Git.

Open/update a GitHub issue only for a reproducible product defect. Documented ordering
limitations are not defects unless the implementation violates its stated contract.
Do not implement fixes on the Windows acceptance machine. Stop without merging.
