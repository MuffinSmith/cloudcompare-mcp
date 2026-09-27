# Focused 0.13 empty-region retest (issue #11)

Continue `feature/live-hole-patterns` at the exact handoff SHA. This is a Python
adapter fix, not a new stage. Previous Windows acceptance at
`2c3338e8ab45624feeaf56dc3b88f0bcf1ae6750` remains attributed to that report/runtime.
Do not repeat the full fan, transformed-fixture or manual-drag acceptance.
Read `AGENTS.md` and the empty-region section of `docs/LIVE_HOLE_PATTERNS.md`.

## Permissions and setup

This is the assistant's separate disposable Windows test system. CloudCompare may
be closed WITHOUT SAVING, unsaved test changes discarded, and test copies reopened.
Preserve unrelated files and Git work. Do not overwrite the original fan. No fan
is needed here. Keep all fixtures, logs, exports and evidence outside Git.

Preserve work, fetch and fast-forward the existing branch. Do not create another
remote branch, reset, clean or force-push. Record the actual tested SHA. Verify:

```powershell
git diff --exit-code 2c3338e8ab45624feeaf56dc3b88f0bcf1ae6750 HEAD -- cloudcompare-plugin src/cloudcompare_mcp/live.py src/cloudcompare_mcp/feature_discovery.py src/cloudcompare_mcp/hole_patterns.py src/cloudcompare_mcp/server.py pyproject.toml
```

That comparison must be empty for this focused scope. Runtime code changes are
confined to `src/cloudcompare_mcp/hole_tools.py`. Reuse the accepted bridge 0.12.0 /
workflow revision 8 on CloudCompare 2.13.2 / Qt 5.15.2. Do not rebuild/redeploy it.
Verify the loaded DLL SHA-256 remains:
`53F3E39F77A5455A64C700EDDAD3B2C8082998E34BA90777E03E361C6A53EB74`.

Python remains 0.13.0; exact SHA/import location and a restarted MCP process, not
version alone, establish the new code. Use the existing configured environment
and its editable checkout. No new dependency or reinstall is required when it is
already editable. Stop/restart only identified MCP server processes to refresh
imports. Do not stop unrelated Python processes or change the native installation.

Run:

```powershell
python -m compileall -q src scripts tests
python -m pytest -q tests
```

Development count is 269 tests including 23 new boundary cases. Record actual runs
and skips separately. If the compiler is not discoverable, use the known installed
`cl.exe` as `CXX` in the configured MSVC environment for the 16 policy cases; do not
present totals from separate invocations as one test run.

## Exact issue #11 live reproduction

Use a previously generated `square.ply` with verified contents or generate fresh
fixtures outside the checkout with `scripts/make_hole_pattern_fixtures.py`.
Load the small square fixture and obtain its CURRENT point-cloud ID. Verify the
selected cloud has 480 points at the known synthetic coordinates; do not copy an
old ID. Capture scene metadata and complete fixture XYZ before the calls.

Through the actual MCP connection call `discover_live_hole_candidates`, replacing
123 with that integer ID:

```json
{
  "cloud_id": 123,
  "region": {"type":"box", "min":[100,100,100], "max":[101,101,101]},
  "face_origin": [0,0,0], "face_normal": [0,0,1],
  "plane_tolerance": 0.2, "diameter_tolerance": 0.1,
  "center_tolerance": 0.05, "spacing_tolerance": 0.1,
  "min_radius": 1.5, "max_radius": 2.5, "distance_threshold": 0.03,
  "min_support_count": 40, "sample_limit": 1000,
  "max_circles": 4, "iterations": 200
}
```

Require MCP `isError: false` (or an absent error flag, not true) and:

- Zero `candidate_count` and `input_candidate_count`; empty `candidates`,
  `duplicates`, `rejected`, `diameter_groups`, `center_spacings`,
  `concentric_candidates`.
- Under `input_provenance`, `region_match_count`, `region_sample_count` and
  `sample_count` equal zero; `region_sample_truncated: false`;
  `region_sample_strategy: null`; requested source/region/global native frame.
- `confirmed_holes: false`, `scene_mutations_requested: false`,
  `scene_freshness_guaranteed: false`, `live_sample_acquired: false`,
  `live_query_completed: true`, `input_mode: fresh_live_empty_region`.
- `input_provenance.empty_region_evidence` has
  `basis: native_no_match_response`,
  `native_error: cloud.region_query selected no points`,
  `counts_derived_from_no_match_response: true`, and
  `source_frame_metadata_returned: false`.

Repeat the same call twice and compare complete parsed results. Do not infer that
zero candidates proves anything about unqueried regions or physical holes.

Repeat using only these selector replacements, with all other inputs unchanged:

```json
{"type":"sphere", "center":[100,100,100], "radius":0.1}
{"type":"slab", "origin":[0,0,100], "normal":[0,0,1], "half_thickness":0.1}
{"type":"nearest", "center":[100,100,100], "max_distance":0.1}
```

All must return zero-candidate success. For nearest, the recorded native error
must instead be `No point was found within nearest.max_distance`.

## Controls: errors stay errors; nonempty output stays unchanged

On the same small source, the original nonempty box
`{"type":"box","min":[-15,-15,-1],"max":[15,15,1]}` must still find four radius-2
circles and the documented six spacings (four 20, two approximately 28.284271247),
with no automatic overlays. Repeat and compare complete results. Nearest with no
`max_distance` must still produce a one-point, zero-candidate sample success,
not the no-match-error adaptation. Its match/sample counts must be one.

Verify an ID not present in the CURRENT scene, bad radius order and a zero face
normal return MCP errors. Do not invent an empty-cloud pass by using an invalid
source ID. Direct `query_live_region` on the empty box should still return the
legacy native no-points error: the correction is scoped to the new hole tool.

Finally close this disposable CloudCompare WITHOUT SAVING, confirm the native
port is not served by another instance, and call the live hole tool again. It
must return a connection error, not zero-candidate success. Preserve the small
fixture's before/after geometry and scene comparison before closing. Restart the
test host afterward only as needed. No raw point arrays belong in chat or Git.

## Report and gate

Return PASS/FAIL/BLOCKED for Python tests, identity, each no-match selector,
determinism, nonempty control, unchanged legacy tool behavior, invalid/disconnected
errors, and complete small-fixture preservation. Include exact SHA, versions,
loaded DLL identity, live MCP error flags, counts, provenance and evidence path.
Distinguish replay-peer tests from real Windows live calls. Previous broad fan and
transformed checks are not rerun or relabeled by this report.

Update #11 with the actual focused result; close it only after these checks pass.
Update acceptance issue #9 using the previous broad report PLUS this targeted
retest, retaining its coverage limitations. Do not implement fixes on Windows,
reopen #7, or merge PR #10/main. A failed check remains FAIL/BLOCKED.
