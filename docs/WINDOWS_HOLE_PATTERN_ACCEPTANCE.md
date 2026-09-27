# Focused Windows acceptance: 0.13 Python-only candidate relationships

Continue `feature/live-hole-patterns` at the exact handoff SHA. Read `AGENTS.md`
and `docs/LIVE_HOLE_PATTERNS.md`. Do not reopen the completed 0.12 gate or issue #7.
Do not merge this unaccepted increment into main.

## Test-system authorization

This is the assistant's separate disposable Windows test system. The user permits
closing CloudCompare WITHOUT SAVING, discarding unsaved test changes, restarting,
and reopening test copies. The original fan remains elsewhere. Resolve the real
fan file path and use a working copy; do not overwrite it, delete unrelated files,
or discard Git work. Keep GUI visible but avoid routine screenshots or raw point
arrays in conversation. Reports/fixtures/logs/exports remain outside Git. Test and
report; do not implement product fixes on Windows.

## Setup (no native rebuild)

Preserve Git work, fetch and fast-forward the new existing branch. Verify exact
HEAD. Compare `cloudcompare-plugin` with native baseline
`fc51824d9edf7328614653c57bf3644c1db02769`: there must be no difference. Reuse the
accepted CloudCompare 2.13.2/Qt 5.15.2 native DLL if its identity matches; previously
accepted SHA-256 was
`53F3E39F77A5455A64C700EDDAD3B2C8082998E34BA90777E03E361C6A53EB74`.

Use the configured MCP Python environment. Stop only identified stale MCP server
processes if they lock the editable install. Run:

```powershell
python -m pip install -e ".[test]"
python -m compileall -q src scripts tests
python -m pytest -q tests
```

Restart the Python MCP server; do not rebuild/redeploy the unchanged DLL.
Expect Python 0.13.0, native plugin 0.12.0 / revision 8, 77 MCP tools, and the two
new read-only tool names. `get_live_workflow_capabilities` must include
`python_hole_patterns` with version 0.13.0. Keep the already accepted overlay
ownership/range flags intact. Record actual pass/skip counts and source paths.

## Reusable synthetic fixtures

Choose a new absolute evidence directory OUTSIDE the checkout. Run:

```powershell
python scripts/make_hole_pattern_fixtures.py --outdir <NEW_EXTERNAL_FIXTURE_DIRECTORY>
```

The generator uses exclusive writes, so choose a fresh directory instead of
replacing an old run. It creates square, row, bolt6 and irregular PLY fixtures plus
expected center/radius metadata. They are sampled circles, not physical holes.

Load `square.ply` through `load_file_live`, obtain its real cloud ID, then call
`discover_live_hole_candidates` with the following JSON, replacing 123 with that
integer ID:

```json
{
  "cloud_id": 123,
  "region": {"type":"box", "min":[-15,-15,-1], "max":[15,15,1]},
  "face_origin": [0,0,0], "face_normal": [0,0,1],
  "plane_tolerance": 0.2, "diameter_tolerance": 0.1,
  "center_tolerance": 0.05, "spacing_tolerance": 0.1,
  "min_radius": 1.5, "max_radius": 2.5, "distance_threshold": 0.03,
  "min_support_count": 40, "sample_limit": 1000,
  "max_circles": 4, "iterations": 200
}
```

Require four retained circles of radius 2; six center spacings (four 20, two
28.284271...); a provisional four-center bolt-circle with pitch diameter
28.284271... and four 90-degree gaps. No result may set confirmed_holes=true.
Repeat identically and compare the numeric output, ignoring no fields unless
explicitly documented. Confirm discovery/analysis never added scene entities.

Run ordinary `discover_live_circles` on this fixture with the same fit parameters
(`min_points` corresponds to the new tool's `min_support_count`; use matching
`min_inlier_fraction` and `min_arc_coverage_degrees`). Feed its COMPLETE returned
JSON into `analyze_hole_candidates.circle_discovery` with the face/tolerance
settings above. Relationships should match, including IDs from that result.
The snapshot tool must work with the live bridge stopped; restart only for later
live tests. It must report live_sample_acquired=false, not freshness verification.

Use `row.ply`: require a three-center row of pitch 10. Use `bolt6.ply` with
max_circles=6: require six centers, pitch diameter 20, six 60-degree gaps. Use
`irregular.ply`: require no row/bolt-circle layout even if four circles are found.
Zero candidates in an unsuitable region are a valid empty result, not a failure.

Also verify a small transformed fixture or a shifted/scaled fixture retained from
prior acceptance. All new inputs/outputs are GLOBAL native coordinates; verify
expected transformed centers/distances without relabeling local values. Send bad
radius order, nonfinite tolerance, zero face normal and local-frame snapshot: MCP
isError=true with no scene mutation. Invalid live inputs should not query the host.
Keep this targeted; do not repeat the entire previous 0.12 acceptance.

## Disposable fan smoke test and limitation reporting

Resolve/load the fan copy, use summarize_live_scene for current IDs, and localize
a plausible face using the existing numerical region/grid tools. Reuse valid
previous numeric regions only after confirming their source/frame; never reuse
historical entity IDs. Physical fan units remain unconfirmed.

Try the new live tool with deliberate radius bounds and tolerances, or analyze
fresh existing circle discoveries. Record chosen source, region, parameters,
matched/sample counts, truncation, rejected/duplicate candidates, diameter groups,
spacings and timing. Do NOT require the fan to contain a qualifying row or bolt
circle. A no-pattern result can be correct. Do not present the previous plausible
hub section as a confirmed mounting hole. Known synthetic layouts are the
numerical oracle; the fan is a realistic workflow/limitations test.

The new tools add no overlays automatically. For user inspection, explicitly call
the existing show_live_circle_overlay for a few returned circle geometries, then
clear using the accepted ownership-safe workflow. Preserve sources. For a small
fixture compare complete coordinates/attributes; for the fan check scene metadata
and an appropriate data comparison, reporting the exact coverage honestly. Avoid
forcing an expensive full-scene export just to repeat already accepted checks.

Return a compact PASS/FAIL/BLOCKED table with exact commit, Python/native versions,
DLL identity, tests, schema/transport, known patterns, negative cases, transformed
coordinates, source preservation, fan findings/limitations and report directory.
File new reproducible defects as GitHub issues. Do not reopen #7 for harness
assumptions or changed test data. Leave main and accepted branches untouched.
