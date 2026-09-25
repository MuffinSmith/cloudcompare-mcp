# Live scan preparation tools

Version 0.4.0 begins the next phase of the live CloudCompare bridge: non-destructive
scan preparation inside the already-open GUI.

All tools in this document create new entities. They do not alter the source cloud.

## Working groups

`create_live_group` creates an empty CloudCompare DB-tree group. The returned
entity ID can be supplied as `destination_group_id` to the preparation tools so
temporary results stay organized separately from source scans.

## Axis-aligned crop

`crop_live_cloud` accepts:

- `cloud_id`
- `min: [x, y, z]`
- `max: [x, y, z]`
- `coordinate_space: "native_local" | "global"`
- `keep_inside` (default true)
- optional `name` and `destination_group_id`

For `global`, qMCPBridge converts the requested box into the source cloud's
stored local coordinate frame before cropping. The result preserves the selected
points' colors, normals, scalar fields, global shift, and scale when CloudCompare
can allocate those attribute tables. Any partial-clone allocation warnings are
returned explicitly.

## Subsampling

`subsample_live_cloud` supports three methods:

- `random`: exact `target_points`
- `spatial`: `min_spacing` in native coordinate units
- `octree`: `octree_level`, retaining the source point nearest each selected
  cell center

The returned report includes source/output point counts, retained fraction,
method settings, and attribute-copy warnings.

## Statistical Outlier Removal

`filter_live_cloud_sor` uses CCCoreLib's SOR implementation and accepts `knn`
(default 6) and `n_sigma` (default 1.0). The output is a partial clone of the
accepted points; the original remains untouched.

## Normal computation

`compute_live_normals` first clones the source point cloud, then computes normals
on the clone. Supported local models are:

- `LS`
- `QUADRIC`
- `TRIANGULATION`

A positive neighborhood `radius` is required in native coordinate units.

Set `orient_with_mst=true` to run CloudCompare's Minimum Spanning Tree normal
orientation after computation. `mst_neighbors` defaults to 6.

If computation or orientation fails, the working clone is discarded and no
result is inserted into the live DB tree.

## Safety expectations

- Source IDs must refer to standalone point clouds.
- Every operation returns `source_preserved=true`.
- Invalid parameters fail before a result is added.
- Empty crop/filter results are reported as errors rather than adding empty
  entities.
- Result entities may be placed under an explicit working group.
- Physical units are never inferred from coordinate magnitude.
