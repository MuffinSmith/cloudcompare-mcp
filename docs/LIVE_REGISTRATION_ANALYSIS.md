# Live coarse registration and distance analysis

Version 0.6.0 extends the live CloudCompare bridge with two pieces needed around ICP:
explicit point-pair coarse registration and quantitative C2C/C2M alignment analysis.

## Point-pair coarse registration

`register_live_point_pairs` accepts a data cloud, a fixed model cloud, and at least
three corresponding 3D points from each.

The tool uses CloudCompare/CCCoreLib's rigid Horn absolute-orientation solver. Scale
is fixed at 1.0.

Two coordinate modes are supported:

- `global`: both point lists are CloudCompare global coordinates.
- `native_local`: each point list is expressed in its own source cloud's stored
  local coordinate system.

The current implementation requires data/model clouds to share the same global
shift and scale metadata. This keeps the returned and applied transformation
unambiguous and allows the coarse result to feed directly into `register_live_icp`.

The default is `preview_only=true`. Preview returns the rigid transform and
point-pair residual statistics without adding geometry. Applied mode creates a new
transformed clone of the data cloud; neither source is modified.

The response returns two transform representations. `transformation_matrix_column_major`
maps the data cloud's stored local coordinates into the aligned local coordinates used
for the live clone. `transformation_matrix_global_column_major` expresses the
equivalent transform in CloudCompare global coordinates, including the common
shift/scale frame conversion.

Point-pair registration is intended to get badly displaced scans close enough for
ICP. It is not a replacement for ICP refinement.

## Cloud-to-cloud analysis

`analyze_live_c2c` computes nearest-neighbor distance from every point of the
compared cloud to the reference cloud.

Computation always occurs on a temporary clone, so the compared source is never
given a temporary distance scalar field.

The default `create_result=false` returns statistics only:

- minimum and maximum
- mean
- RMS
- standard deviation
- median
- P95 and P99
- a 20-bin histogram

Set `create_result=true` to add the compared clone to the scene with an
`MCP C2C distance` scalar field selected for display. An optional working group
and result name can be supplied.

`max_distance=0` means unlimited. A positive value invokes CloudCompare's maximum
search-distance behavior; callers should treat resulting statistics as capped by
that search limit.

## Cloud-to-mesh analysis

`analyze_live_c2m` computes distance from a compared point cloud to a reference
triangle mesh. It has the same stats-only/result-clone safety model as C2C.

Options include:

- unsigned or signed distances
- triangle-normal flipping for signed-distance convention
- CloudCompare's robust signed-distance edge handling
- optional maximum search distance

For signed C2M, the response includes both signed-value statistics and absolute
distance statistics.

## Frame policy

C2C and C2M currently require identical CloudCompare global shift/scale metadata
between compared and reference geometry. The bridge rejects mismatches rather than
silently comparing incompatible stored local coordinates.

## Source safety

All three tools are non-destructive:

- point-pair registration solves from small temporary correspondence clouds
- C2C/C2M compute on a clone of the compared cloud
- optional live outputs are new entities
- source names, attributes, coordinates, parentage, shift/scale and scalar fields
  should remain unchanged

## Next step

Once this native layer is accepted on Windows/CloudCompare 2.13.2, the next layer
can expose interactive picking/measurement so an assistant can acquire the
correspondences and metrology targets directly from the viewport rather than being
given explicit coordinates.
