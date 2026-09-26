# Image-free spatial feature discovery

Version 0.11.0 builds on the accepted 0.10.0 region-query layer so an assistant can
reason about a scan spatially without repeatedly capturing viewport images.

The main additions are:

- an exact native 3D region grid with stable per-cell covariance
- Python-side covariance shape metrics
- deterministic multi-plane discovery inside a bounded live-cloud region
- sparse 2D occupancy summaries for full-cloud slab sections

The normal workflow is now:

1. inspect entity bounds;
2. request a coarse numerical 3D grid;
3. zoom numerically into interesting cell bounds;
4. discover likely planar patches or query/fix a more precise region;
5. use the accepted direct plane/circle/cylinder fitting tools;
6. request a viewport image only when rendered visual context is genuinely needed.

## Exact 3D region grid

qMCPBridge 0.11.0 / workflow revision 7 adds:

`cloud.region_grid`

The operation scans the actual source point cloud and bins every point in the
requested bounds into a regular 3D grid.

The caller may provide:

- global or native-local coordinate space
- optional explicit min/max bounds
- X/Y/Z grid divisions
- minimum points per returned cell
- a maximum number of returned cells

The native bridge computes exact per-cell:

- point count
- fraction of all points inside the requested bounds
- centroid
- point bounds
- covariance using an online Welford-style update

The covariance update is centered online rather than subtracting two large raw
moments. This matters when a cloud uses large global coordinates.

Only the most populated eligible cells need to be returned. The response also
reports exact nonempty/eligible counts and whether the cell list was truncated.

No point records are returned by the grid operation.

## Model-facing spatial description

`describe_live_region_grid` consumes the native covariance and returns compact
shape diagnostics for each cell:

- three principal variances
- linearity
- planarity
- scattering
- RMS thickness

The raw covariance matrix is intentionally removed from the ordinary model-facing
result.

This makes the grid act like a low-token numerical 3D view. A coarse query can
show which parts of an object contain broad planar patches, thin linear structures,
or volumetric/scattered geometry. The assistant can then query only the bounds of
interesting cells at a finer resolution.

## Dominant plane discovery

`discover_live_planes` operates inside any accepted 0.10 region selector
(sphere, box, slab, or nearest query where useful).

The bridge first returns a deterministic bounded point sample from the requested
region. The Python discovery layer then uses deterministic RANSAC followed by the
already accepted orthogonal least-squares plane fitter.

Each candidate reports:

- support point count
- fraction of the complete fitting sample supporting the plane
- residual RMS/mean/median/P95/max
- global inlier bounds
- refined plane centroid/normal/basis/equation/planarity diagnostics

Candidate inliers are removed before searching for the next plane.

The result never exposes the raw fitting sample or inlier-index list to the model.

The default distance threshold is 0.2% of the sampled region's bounding-box
diagonal. Callers can supply an explicit threshold when scan units/tolerances are
known.

Because region fitting can already use a bounded deterministic sample, the result
clearly reports whether the source region had more points than were used for
discovery.

## Structured section occupancy

`describe_live_section_grid` uses the native full-cloud slab query, projects its
bounded sample into the accepted deterministic U/V section frame, and bins those
2D coordinates into a compact sparse occupancy grid.

The result includes:

- exact full-cloud slab match count
- bounded sample count and truncation state
- section plane origin/normal/U/V basis
- signed offset statistics
- U/V bounds
- nonempty occupancy cells with count, sample fraction, and U/V centroid

It does not return the raw U/V profile or an image.

This is intended as a cheap way to reason about cross-section topology before
requesting more targeted profile measurements.

## Safety

All 0.11.0 spatial/discovery operations are read-only.

They do not:

- modify source coordinates or attributes
- create labels or fit objects
- change hierarchy, selection, visibility, or frame metadata

Visible overlays remain a separate future layer so their DB-tree lifecycle can be
validated independently from the numerical discovery tools.

## Version boundary

0.11.0 contains native changes:

- cloudcompare-mcp: 0.11.0
- qMCPBridge: 0.11.0
- workflow revision: 7

A Windows native build and live acceptance run is required before merging this
branch.
