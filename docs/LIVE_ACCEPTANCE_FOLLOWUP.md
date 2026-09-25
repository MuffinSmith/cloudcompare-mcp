# Windows live acceptance: remaining changes

Tested on 2026-09-25 at code commit `9724526d6212fe827a2d602702bbce98dbd99efb`, on `feature/fusion-reference-mesh-workflow`.

Environment: installed CloudCompare 2.13.2 (64-bit, Jul 6 2024), Qt 5.15.2 msvc2019_64, MSVC 14.44.35207, Python 3.13.14, NumPy 2.5.3, PyMeshLab 2025.7.post1. All geometry was synthetic; no real scan/project was used.

## Fixed and verified

The compatibility commit adds the complete `QMainWindow` definition and replaces the protected `notifyGeometryUpdate()` call with public `invalidateBoundingBox()` on the temporary conversion clone. The inspected 2.13.2 implementation invalidates bounds, releases VBOs, and clears LOD. The fresh clone has no octree. No unsafe cast or protected-member access is used.

Release/x64 built successfully. The installed executable loaded `QMCP_BRIDGE_PLUGIN.dll` from its supported per-user plugin directory, and the same process listened on `127.0.0.1:8765`. Runtime plugin version is 0.3.0. Compileall passed; `pytest -q tests` passed all six tests; experiments were excluded.

## 1. Fix the acceptance harness's scene-envelope traversal

**Priority: high. Confirmed implementation defect; reproduced twice.**

`scripts/live_fusion_acceptance.py::flatten_entities()` traverses lists and an entity's `children`, but does not traverse the bridge's top-level `entities` envelope:

```json
{"entities": [{"id": 260, "kind": "point_cloud", "children": []}], "selected_ids": []}
```

Consequently the harness reports every supplied source ID missing, even though live MCP enumeration and other tools can access them. The tested source IDs were 260, 264, 268, 272, 276, 280, 284, 288, and 292; these are session-specific, not constants to embed in the fix.

Required change: handle the scene envelope as well as standalone entities, wrapper groups, nested children, and lists. Add a regression test using the actual scene response shape. Preserve source snapshots and the existing non-destructive behavior.

Acceptance: run `scripts/live_fusion_acceptance.py` with nine dynamically discovered cloud IDs, `--units millimeters --exercise-errors`, and a fresh output directory. It must reach geometry processing, produce its report/PLY/OBJ/captures, and verify unchanged originals. Currently it exits at line 108 before mutation and produces no `fan_*` outputs.

## 2. Resolve the Windows MCP startup/lazy-import stall

**Priority: high. Reproducible runtime defect; underlying native cause not yet established.**

Starting the normal `python -m cloudcompare_mcp.server` entrypoint through an MCP stdio client allows `get_live_cloudcompare_info`, but `get_live_workflow_capabilities` stalls. Reproduced with both sandbox and normal-user server processes. A diagnostic stack shows the main thread in NumPy native module initialization, reached while importing PyMeshLab from `pymeshlab_version()`.

The tested workaround is:

```text
python -c "import numpy; from cloudcompare_mcp.server import main; main()"
```

Preloading NumPy before stdio threads start allowed both discovery calls and all tested geometry tools to succeed, using the unchanged tool handlers. Restricting OpenBLAS/OMP threads alone did not resolve the observed stall.

Required change: reproduce with the normal entrypoint and determine a safe initialization strategy. Version discovery should use installed distribution metadata rather than import the native geometry backend merely to obtain a version. That alone is not sufficient proof that later reconstruction imports cannot stall.

Acceptance: a fresh normal server must complete capability discovery and then ball pivoting and simplification without a special launcher. Use bounded test timeouts and preserve diagnostics on timeout. Keep the optional dependency optional.

## 3. Prevent export errors from requiring GUI interaction

**Priority: high for unattended use. Confirmed blocking behavior, triggered by an environmental access failure.**

An initial ball-pivot request created its temporary directory under a sandbox Windows identity. The separately running CloudCompare GUI could not write there. Rather than immediately returning an MCP error, CloudCompare displayed two modal save-error dialogs. After dismissal, MCP returned `CloudCompare export failed with error code 15`; no result mesh was added.

Running MCP and CloudCompare as the same Windows user resolved directory access and reconstruction succeeded. This was not a geometry-algorithm failure. However, `alwaysDisplaySaveDialog=false` does not suppress all failure dialogs.

Required change: ensure the native I/O failure path used by bridge operations is noninteractive, while retaining validation and transactional cleanup. Document that the GUI process must be able to access Python-created temporary files. Do not weaken ACLs globally or silently redirect to unrelated files.

Acceptance: export to a deliberately inaccessible disposable directory must return a clear error within a bounded time, without dialogs, added entities, or partial output. Missing-parent-directory tests already return cleanly.

## 4. Complete runtime version reporting

**Priority: medium. Confirmed reporting defect.**

On this installed 2.13.2 application, `QCoreApplication::applicationVersion()` is empty, so ping/capabilities omit a usable application version. PyMeshLab reports `version: null` despite installed distribution version 2025.7.post1. Plugin version 0.3.0 is reported correctly.

Required change: use a supported CloudCompare version source/fallback for this host version, and Python distribution metadata for PyMeshLab. Distinguish build-time information from runtime host information; do not invent a version when genuinely unavailable.

## Passed live checks and caveats

| Area | Observed result |
|---|---|
| Selection | Nine simultaneously; two plus three retains five; duplicate/missing/invalid IDs reported; clear produces empty selection. |
| Metadata | All requested fields present; units remain native/unknown. |
| Cloning | Nine mappings match source metadata. Clone-only rename/0.25 mm translation does not change source geometry. |
| Merge | Nine clones yield exactly 72,000 points. Coordinates, normals, RGB, and scalar values equal concatenated source exports. Mixed RGB/scalar fills verified. |
| Frames | Genuine global-shift mismatch rejected by strict mode; conversion preserves all 40 test points' global coordinates exactly. |
| PLY | Binary export, 72,000 points, validated counts/bounds; overwrite refused. |
| Ball pivoting | Automatic radius creates 143,982 triangles; torus opening visibly retained and source unchanged. Output has two non-manifold vertices and eight unused vertices, so it is not a manufacturing-ready guarantee. |
| 2.5D | Missing acknowledgement rejected; acknowledged planar annulus with edge limit 2 retains its opening. |
| Simplification | Torus 576,000 to 300,000 triangles; genus 1/one component retained. Bidirectional maximum sampled deviations 0.0007616421 and 0.0007602899 in fixture millimeters. |
| Open boundaries | Grid 79,202 to 30,000 triangles retains 796 boundary edges and bounds. All-boundary annulus cannot meet requested reduction; tool correctly reports target not met. |
| OBJ | Directly counted 150,000 vertices and 300,000 faces; text, readback validation, units warning. |
| Failure cleanup | Nine requested invalid-operation cases preserve identical scene snapshots and leave no partial/bogus output files. Modal caveat above. |
| Source integrity | All nine original metadata snapshots unchanged; coordinates/RGB match fixtures; all exported properties unchanged after clone-only mutation. Merged source also unchanged after reconstruction. |

The source torus uses R=50, r=10 mm and bounds [-60,-60,-10] to [60,60,10]. Millimeters are supplied by the fixture generator, not inferred by the bridge. Poisson is unavailable and never selected by default. Synchronous execution and unsupported cancellation are documented limitations, not failed cancellation tests. Boundary counts and sampled deviation are correctly presented as evidence rather than proof of physical-opening preservation.

One reporting nuance worth clarifying: selection `matched_request=true` describes the filtered valid ID set even when `missing_ids` or `invalid_ids` is nonempty. All explicitly requested selection tests passed, but clients must inspect those arrays.

## Evidence on the test computer

Full report, exact MCP envelopes, native harness trace, logs, fixtures, exports, and screenshots are retained in `C:\Users\Admin\Documents\CloudCompare\mcp-live-test` (not added to Git).

Key files: `REPORT.md`, `verified-results.json`, `harness-wire.jsonl`, `harness-reproduction.log`, `server-trace.log`, `connectivity-preload.log`, `connectivity-same-user.log`, `ball-pivoting-sandbox-error.json`, `bpa-temp-error.jpg`, `loaded-modules-fixed.json`, `plugin-build-install-hashes.json`, `torus_master.ply`, `torus_reference.obj`, and the `ball-result-*`, `simplified-torus-*`, `open-grid-*` captures.
