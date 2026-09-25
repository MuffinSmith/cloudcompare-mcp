# Safe Fusion 360 reference-mesh workflow

This workflow is for reverse engineering geometry that already exists in an open
CloudCompare GUI. It is intentionally conservative: source entities are never
implicitly merged, resampled, smoothed, hidden, transformed, renamed, or deleted.

## Safety model

- Work from explicit entity IDs only.
- Clone before operations that create working geometry.
- Live cloud merging is concatenation only: no duplicate removal, filtering,
  resampling, smoothing, or point fusion.
- Coordinate units are unknown unless the caller confirms them. Coordinate
  magnitude is never interpreted as meters.
- CloudCompare global shift/scale is reported separately from physical-unit
  assumptions.
- Existing export files are refused unless overwrite=true.
- PLY/OBJ exports are written from the live entities, then read back and checked
  for point/triangle counts and global-coordinate bounds.
- OBJ export is rejected for point-cloud-only entities.
- Poisson reconstruction is not selected automatically.
- Every meshing/simplification result is a separate entity. Original sources stay
  in the live scene.

## Live tools

get_live_workflow_capabilities
: Reports native bridge methods, CloudCompare/plugin versions, unit policy,
  available reconstruction methods, optional Python backends, and known execution
  limitations.

clone_live_entities
: Deep-clones standalone point clouds and triangle meshes. The result includes
  source-to-clone ID mappings and full metadata.

merge_live_clouds
: Concatenates explicitly listed point clouds. coordinate_frame_policy="strict"
  rejects mismatched global shift/scale. "convert_to_first" is an explicit opt-in
  that transforms working copies into the first cloud's frame before concatenation.

reconstruct_live_mesh
: Supports two deliberately separate families:

- ball_pivoting — optional PyMeshLab full-3D local reconstruction. It requires
  point normals and does not claim that openings are preserved. Optional `name`
  and `destination_group_id` are applied to the loaded live result so generated
  meshes can remain inside an explicit MCP working group.
- delaunay_2_5d_best_fit_plane / delaunay_2_5d_axis_aligned — CloudCompare core
  2.5D reconstruction. These require explicit acknowledgement because they are
  unsuitable for a complete multi-sided mechanical assembly.

Poisson is reported as unavailable through this safe workflow rather than being
silently selected.

simplify_live_mesh
: Uses optional PyMeshLab quadric edge collapse with boundary, normal/sharp-feature,
  and topology preservation controls. It keeps the original live mesh, reports the
  achieved triangle count, before/after topology and bounds, and bidirectional
  sampled Hausdorff-distance statistics. These statistics are evidence, not proof,
  that every physical opening survived.

export_live_entity
: Writes binary PLY for point clouds and OBJ for real triangle meshes. The export
  report includes the absolute path, encoding, file size, point/triangle counts,
  global-coordinate behavior, source shift/scale, caller-supplied intended import
  units, attribute warnings, and read-back validation.

## Optional full-3D backend

CloudCompare core does not expose a persisted topology-preserving mesh decimator
through the plugin API, and its built-in Delaunay triangulation is 2.5D. The MCP
server therefore uses PyMeshLab as an optional local backend for the two missing
operations.

Install it with:

    pip install -e ".[fusion]"

No source entity is handed to PyMeshLab directly: the bridge first exports a
temporary copy of the current live geometry, PyMeshLab processes that copy, and
the result is loaded back into CloudCompare as a new entity.

### Ball pivoting parameters

- ball_radius_percent: radius as a percentage of the point-cloud bounding-box
  diagonal. Omit it to use MeshLab's automatic estimate.
- clustering_percent: clustering threshold; default 20.
- crease_threshold_degrees: normal compatibility/crease threshold; default 90 degrees.

Ball pivoting is local and is not designed to force a watertight surface, which is
preferable to automatic Poisson reconstruction for scans containing real vents,
slots, mounting holes, and open sheet-metal geometry. It still cannot guarantee
that those features survive.

### Reference simplification

For a dense Fusion reference mesh, a practical target is normally 200,000 to
500,000 triangles. The acceptance harness defaults to 350,000 and only simplifies
when reconstruction exceeds 500,000 triangles.

The simplifier requests boundary preservation, normal/sharp-feature preservation,
topology preservation, optimal vertex placement, planar quadrics, and automatic
cleanup. If those constraints prevent the requested triangle budget from being
reached, the achieved count and the fact that the target was not reached are
reported.

## Multi-selection fix

selection.set now drives CloudCompare's database-tree QItemSelectionModel
additively instead of repeatedly calling the single-selection wrapper.

Semantics:

- clear=true: replace the selection with all valid requested IDs.
- clear=false: add valid requested IDs to the existing selection.
- ids=[] and clear=true: clear the selection.
- duplicate IDs: first occurrence wins.
- missing IDs and invalid values: reported separately.
- the response includes the actual resulting selection, unresolved requested IDs,
  and matched_request.

The live acceptance test explicitly verifies simultaneous selection of all supplied
cloud IDs (nine in the fan test case).

## Export coordinates and units

CloudCompare's PLY and OBJ writers emit global coordinates, applying the entity's
stored global shift/scale. The bridge records the source shift/scale and validates
the written geometry by loading the file back and comparing counts and
global-coordinate bounds.

PLY is binary for this workflow.

OBJ does not reliably encode physical units. intended_import_units is metadata in
the export report, not a conversion. For the fan, pass "millimeters" only after the
physical scale has been independently confirmed.

## End-to-end live acceptance test

The repository contains scripts/live_fusion_acceptance.py.

With CloudCompare open and the rebuilt qMCPBridge loaded, run for example:

    python scripts/live_fusion_acceptance.py ^
      --cloud-id 101 ^
      --cloud-id 102 ^
      --cloud-id 103 ^
      --cloud-id 104 ^
      --cloud-id 105 ^
      --cloud-id 106 ^
      --cloud-id 107 ^
      --cloud-id 108 ^
      --cloud-id 109 ^
      --outdir C:\Users\YOU\Desktop\fan-export ^
      --units millimeters ^
      --exercise-errors

Replace the IDs with the intended aligned clouds returned by list_live_entities;
never assume every cloud in the project belongs to the final assembly.

The harness snapshots source metadata, captures a before image, verifies true
multi-selection, clones the sources, merges only the clones, exports and validates
fan_master.ply, performs ball-pivoting reconstruction when the optional backend is
installed, simplifies only if the mesh exceeds 500k triangles, exports and
validates fan_reference.obj, captures an after image, verifies the original source
snapshots are unchanged, and writes fan_export_report.json.

A successful report contains exact output paths, counts, bounds, shift/scale,
unit assumptions, reconstruction/simplification settings, topology evidence,
deviation measurements, and any feature-preservation uncertainty.

## Operations still requiring human review

There is intentionally no automatic "holes survived" assertion. For a mechanical
scan with genuine openings, numerical boundary counts and geometric deviation are
not enough to identify semantic features such as a particular ventilation slot.

After reconstruction and after simplification, visually inspect at minimum the
ventilation slots/louvers, mounting holes, thin sheet-metal edges, brackets, motor
housing transitions, and internal components that should remain disconnected.

If any are bridged or removed, keep the unsimplified/reconstructed entity and
adjust reconstruction or simplification parameters rather than repairing the
original scan.

## Long-running operations

The current localhost bridge protocol remains backwards-compatible and
request/response synchronous. Large clone/merge/export/reconstruction requests use
longer client timeouts and are transactional where practical; failed native
exports are removed instead of being reported as success.

CloudCompare's relevant plugin APIs do not provide a safe mid-operation
cancellation hook for these native database operations, and in-process PyMeshLab
filters are likewise not safely interruptible. The capabilities response therefore
reports cancellation as unsupported rather than pretending it exists. Adding a
worker-process job protocol is the remaining requirement if hard cancellation of
external meshing is needed.
