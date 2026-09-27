# Windows acceptance: 0.12 candidates and overlay safety

Continue `feature/live-feature-candidates-overlays`; do not create another branch.
Use the exact commit supplied in the handoff and report the actual tested SHA.
Read `AGENTS.md` and `LIVE_FEATURE_CANDIDATES.md` first. Do not merge into `main`
until the entire acceptance, including the real fan project, passes.

## Permission and evidence boundary

This is the assistant's separate Windows test system. The user explicitly permits
closing or restarting CloudCompare **without saving**, dismissing save prompts by
discarding changes, and reopening the disposable test data. The user's original
fan project is safely retained elsewhere. Resolve the actual `fan_project.bin`
path and use a working copy. Never overwrite the original or delete unrelated files.
This permission does not authorize discarding unexpected Git work.

The Windows assistant tests and reports; it does not implement product fixes.
Record new defects in GitHub Issues with the tested SHA and a small reproduction.
Keep reports, fixtures, raw logs, exports, and screenshots outside Git. Keep the GUI
visible for the user, but use numerical tools instead of routine screenshots or
putting point arrays into chat context.

## Build and identity

Preserve local work before switching/updating branches. Fetch, fast-forward the
existing branch, and verify HEAD. Do not reset, clean, or force-push.

Using the same Python interpreter as the configured MCP server:

```powershell
python -m pip install -e ".[test]"
python -m compileall -q src scripts tests
python -m pytest -q tests
```

Record all skips. The native policy tests automatically support `cl.exe` when it
is on PATH in a Visual Studio developer shell, or GCC/Clang when available. They
are not substitutes for loading the actual DLL. Restart the Python MCP process
so it is not using a cached older module/tool schema.

Close the test CloudCompare without saving. Rebuild qMCPBridge against the matching
host sources/ABI using `cloudcompare-plugin/qMCPBridge/README.md`. The known
previous Windows lane was CloudCompare 2.13.2 / Qt 5.15.2 msvc2019_64 / x64 Release;
verify the actual local installation rather than assuming those paths or versions.
Deploy only the bridge DLL or use the configured `CC_PLUGIN_PATH`; do not replace
installed CloudCompare/Qt/core libraries with unrelated build outputs.

Restart CloudCompare and confirm the responding process is the intended one.
`ping` and `capabilities.get` must report 0.12.0 / workflow revision 8. In the native
`fit_overlays` capabilities require:

```json
{
  "ownership_policy": "runtime_identity_and_recursive_preflight",
  "foreign_descendants_block_clear": true,
  "source_local_range_validation": true
}
```

These flags distinguish the hardened DLL from the earlier 0.12 build. Verify the
MCP tool inventory includes circle/cylinder discovery, all four overlay creation
tools, and overlay status/clear.

## Repeatable native overlay safety

Load a small standalone point-cloud fixture first, obtain its real entity ID, and
run the following with an absolute output directory outside the checkout:

```powershell
python scripts/live_overlay_acceptance.py --source-cloud-id <ID> --outdir <ABSOLUTE-EXTERNAL-TEST-DIRECTORY>
```

The script refuses to touch pre-existing overlays. It performs 19 checks covering
all four overlay kinds (five entities because a cylinder includes its axis),
invalid requests with/without existing overlays, same-name user-group protection,
foreign nested descendants, idempotent clear, manual managed-group deletion and
recreation, and restoration of scene metadata. A failure leaves the test instance
for diagnosis instead of attempting potentially unsafe cleanup; close without
saving to recover. The report explicitly does **not** claim a full point/attribute
checksum or visual acceptance.

Also test a real unrelated disposable cloud moved beneath an overlay/group:
status must return `clear_safe: false`; clear and creation must refuse without
changing the tree. Never delete that cloud as a workaround. Move it out, then retry.
The group name is not ownership; objects loaded from an earlier saved session must
not become deletable just because their name or copied metadata matches.

## Synthetic candidate tests and numerical examples

Generate small deterministic PLY fixtures in the external test directory, not Git:

- A circle centered at `[10,20,30]`, radius 5, normal `[0,0,1]`, with at least 360
  points around a full turn. Include a second trial with small noise and outliers.
- A cylinder around the Z axis through `[40,20,30]`, radius 4, spanning Z=20 to 40,
  with at least 36 angular samples at 21 axial positions. Include a noisy trial.
- A small fixture with RGB, normals, and a scalar field for source integrity checks.

Load through `file.load` or the configured MCP equivalent; use returned IDs rather
than names or historical IDs. Circle tool example (replace `CIRCLE_ID`):

```json
{
  "cloud_id": "CIRCLE_ID",
  "region": {"type":"box", "min":[4,14,29], "max":[16,26,31]},
  "coordinate_space":"global",
  "sample_limit":1000,
  "distance_threshold":0.05,
  "min_radius":4.5,
  "max_radius":5.5,
  "max_circles":1,
  "min_points":100,
  "min_arc_coverage_degrees":270
}
```

Cylinder tool example (replace `CYLINDER_ID`):

```json
{
  "cloud_id":"CYLINDER_ID",
  "region":{"type":"box", "min":[35,15,19], "max":[45,25,41]},
  "coordinate_space":"global",
  "sample_limit":2000,
  "distance_threshold":0.05,
  "min_radius":3.5,
  "max_radius":4.5,
  "max_cylinders":1,
  "min_points":200,
  "min_angular_coverage_degrees":270,
  "restarts":32
}
```

The ID placeholders above must become integer IDs, not strings. Check centers,
radii, axis direction (allow sign reversal), coverage, support and residuals against
the known fixture. Repeat identical calls to check determinism. Sample truncation
must be reported honestly. Empty/unsuitable regions and invalid thresholds must
return controlled errors/empty candidates without scene mutation.

Display candidates with `show_live_circle_overlay` / `show_live_cylinder_overlay`,
using the returned global center/normal/radius or span endpoints. Verify the visible
alignment and fixed colors: plane cyan, circle yellow, cylinder magenta, axis green.
A plausible fit is only a candidate, not a confirmed mounting hole.

## Shift/scale, source integrity and the real fan

Repeat a known-feature fixture with nonzero global shift and nonunit global scale.
Use global overlay coordinates and verify its global placement and dimensions,
not just that it exists. Test finite but enormous values (e.g. 1e300) and local
underflow/indistinguishable endpoints: controlled rejection, no new group or partial
cylinder. NaN/Infinity must be rejected by the Python transport before sending.

Before/after discovery and a complete create/status/clear lifecycle, compare source
IDs, hierarchy, names, visibility/enabled flags, counts, bounds, shift/scale, normals,
colors and scalar fields. For the small attribute-rich fixture additionally compare
all point and attribute values (or deterministic exported data digests). Scene
metadata equality alone does not establish unchanged per-point attributes.

Resolve and load the user's disposable `fan_project.bin` working copy. Start with
`summarize_live_scene`, not a giant recursive dump into the conversation. Find the
main scan from its current returned ID. Use structured grid/region queries to find
a plausible mounting face and hub/bore. Search bounded local regions, initially
with a 2,000-5,000-point fitting sample. Do not interpret native units as millimetres
without confirmation and do not apply synthetic fixture sizes to the fan.

Show the strongest few circle/cylinder candidates for the user to see, clear them,
and verify source preservation and responsiveness. Record chosen regions, numeric
parameters, timings, candidate quality and limitations. A failure to find a real
feature must be reported, not replaced by a visually plausible invented result.
This phase must not remesh, simplify, transform, or overwrite the original scan.

## Report and acceptance gate

Return a compact PASS/FAIL/BLOCKED table covering exact checkout, Python tests,
Windows DLL build/load, runtime identity, synthetic candidates, overlay lifecycle,
ownership guards, shifted/scaled coordinates, source integrity, real fan workflow,
and visible responsiveness. Include tested SHA, Python/CloudCompare/Qt versions,
process/DLL paths and the external report directory. No fixtures or evidence in Git.

Issue #7 remains open until the Windows ownership/range and fan retests pass.
A Linux compiler pass is not a Windows runtime pass. A mocked boundary or synthetic
fixture pass is not a fan-project pass. Do not merge main on partial acceptance.
