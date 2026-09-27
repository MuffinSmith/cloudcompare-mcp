# cloudcompare-mcp

Cross-platform [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [CloudCompare](https://www.danielgm.net/cc/) — lets AI assistants (Claude, etc.) process 3D point clouds and meshes via natural language.

## Fusion 360 live reference-mesh workflow

For safe reverse engineering from an already-open CloudCompare scene, including
live cloning/merging, validated PLY/OBJ export, optional full-3D ball-pivoting
reconstruction, reference-mesh simplification, and the end-to-end acceptance
harness, see [docs/FUSION_REFERENCE_WORKFLOW.md](docs/FUSION_REFERENCE_WORKFLOW.md).

The next live workflow layer adds non-destructive crop, subsampling, SOR filtering,
normal computation/orientation, and working groups. See
[docs/LIVE_SCAN_PREPARATION.md](docs/LIVE_SCAN_PREPARATION.md).

Live rigid registration now supports preview-only and clone-producing point-cloud
ICP. See [docs/LIVE_REGISTRATION.md](docs/LIVE_REGISTRATION.md).

Coarse point-pair registration plus live C2C/C2M quality analysis are documented in
[docs/LIVE_REGISTRATION_ANALYSIS.md](docs/LIVE_REGISTRATION_ANALYSIS.md).

Interactive viewport picking, point inspection, distance and angle measurements are
documented in [docs/LIVE_METROLOGY.md](docs/LIVE_METROLOGY.md).

Plane/circle fitting and derived metrology from captured picks are documented in
[docs/LIVE_FEATURE_FITTING.md](docs/LIVE_FEATURE_FITTING.md).

Line/cylinder fitting and picked cross-section projection are documented in
[docs/LIVE_CYLINDER_SECTIONS.md](docs/LIVE_CYLINDER_SECTIONS.md).

Structured point-cloud region queries, direct region fitting, and image-free slab
sections are documented in [docs/LIVE_REGION_FITTING.md](docs/LIVE_REGION_FITTING.md).

Image-free spatial grids, plane discovery, and section occupancy are documented in
[docs/LIVE_FEATURE_DISCOVERY.md](docs/LIVE_FEATURE_DISCOVERY.md).

Automatic circle/cylinder candidate discovery and temporary visible fit overlays
are documented in [docs/LIVE_FEATURE_CANDIDATES.md](docs/LIVE_FEATURE_CANDIDATES.md).

## Features

### Native tools (no CloudCompare required)

| Tool | Description |
|------|-------------|
| `read_cloud_metadata` | Parse a cloud and return point count, bounding box, extent, density, RGB/intensity/normals presence |
| `visualize_cloud` | **Render top / front / side views + metadata panel as a base64 PNG the model can see directly** |
| `reconstruct_section_profile` | Reconstruct candidate line/arc/circle CAD geometry from a supplied 2D section snapshot without live I/O |

### Live CloudCompare GUI tools (requires qMCPBridge plugin)

These tools operate on the **CloudCompare instance that is already open** instead of launching a new CLI process.

| Tool | Description |
|------|-------------|
| `get_live_cloudcompare_info` | Check connectivity to the open CloudCompare GUI |
| `list_live_entities` | Read the current DB tree and entity IDs |
| `summarize_live_scene` | Compact image-free geometry inventory for locating major clouds/meshes |
| `get_live_selection` | Read the current GUI selection |
| `set_live_selection` | Select entities by CloudCompare unique ID |
| `load_file_live` | Load a file into the open GUI |
| `rename_live_entity` | Rename an entity |
| `set_live_entity_state` | Show/hide or enable/disable an entity |
| `delete_live_entities` | Remove entities from the current DB tree |
| `transform_live_entity` | Apply a 4x4 transform to an entity |
| `set_live_view` | Change standard view / zoom / redraw |
| `capture_live_view` | Return the active CloudCompare viewport as a PNG the model can see |
| `create_live_group` | Create a DB-tree group for organizing working results |
| `crop_live_cloud` | Non-destructively crop a cloud by an axis-aligned box in local or global coordinates |
| `subsample_live_cloud` | Create random, spatial, or octree-subsampled working clouds |
| `filter_live_cloud_sor` | Create a Statistical Outlier Removal filtered working cloud |
| `compute_live_normals` | Compute normals on a working copy with optional MST orientation |
| `register_live_icp` | Preview or create a non-destructive rigid ICP-aligned working copy |
| `register_live_point_pairs` | Coarse rigid alignment from explicit corresponding point pairs |
| `analyze_live_c2c` | Live cloud-to-cloud distance statistics and optional scalar-field result |
| `analyze_live_c2m` | Live cloud-to-mesh distance statistics and optional scalar-field result |
| `start_live_picking` | Start interactive point/triangle picking in the visible CloudCompare viewport |
| `get_live_picks` | Read captured picks with exact coordinates and attributes |
| `clear_live_picks` | Clear captured picks while leaving picking active |
| `stop_live_picking` | Stop the picking listener and return captured picks |
| `inspect_live_point` | Inspect exact coordinates/RGB/normal/scalars for a point index |
| `measure_live_picked_distance` | Measure distance and XYZ deltas between captured picks |
| `measure_live_picked_angle` | Measure a three-point angle from captured picks |
| `fit_live_plane` | Fit an orthogonal least-squares plane to captured global picks |
| `fit_live_circle` | Fit a 3D circle/hole with diameter and residual diagnostics |
| `measure_live_pick_to_plane` | Measure a captured point to a fitted picked plane |
| `compare_live_picked_planes` | Compare fitted plane angle and normal-direction offsets |
| `fit_live_line` | Fit a 3D line/edge from captured global picks |
| `fit_live_cylinder` | Fit a cylinder/bore/shaft axis and diameter with residual diagnostics |
| `compare_live_picked_lines` | Compare fitted line/axis angle and shortest distance |
| `compare_live_line_to_plane` | Compare a fitted line/axis with a fitted plane |
| `compare_live_cylinders` | Compare fitted cylinder axes, offsets, and diameter differences |
| `compare_live_cylinder_to_plane` | Compare a fitted cylinder axis with a fitted plane |
| `project_live_picks_to_section` | Project captured profile picks into a fitted 2D section frame |
| `query_live_region` | Inspect sphere/box/slab/nearest live-cloud geometry without a screenshot |
| `fit_live_region_plane` | Fit a plane directly to a live-cloud region without manual picking |
| `fit_live_region_circle` | Fit a circle/hole directly to a live-cloud region |
| `fit_live_region_cylinder` | Fit a cylinder/bore/shaft directly to a live-cloud region |
| `extract_live_section` | Extract and project a full-cloud slab into a compact 2D section summary |
| `reconstruct_live_section_profile` | Reconstruct compact line/arc/circle profile candidates from a bounded live slab sample while keeping raw points server-side |
| `describe_live_region_grid` | Numerical 3D spatial view with exact cell counts and shape metrics |
| `discover_live_planes` | Discover dominant planar patches inside a live-cloud region |
| `describe_live_section_grid` | Compact sparse 2D occupancy summary of a full-cloud slab section |
| `discover_live_circles` | Discover robust circle/hole candidates with support and coverage diagnostics |
| `discover_live_cylinders` | Discover dominant cylinder/bore/shaft candidates with support diagnostics |
| `show_live_plane_overlay` | Show a temporary cyan fitted-plane overlay |
| `show_live_circle_overlay` | Show a temporary yellow fitted-circle overlay |
| `show_live_cylinder_overlay` | Show a temporary magenta cylinder and optional green axis |
| `show_live_axis_overlay` | Show a temporary green axis/line overlay |
| `get_live_fit_overlays` | Inspect the managed temporary overlay group |
| `clear_live_fit_overlays` | Remove all managed fit overlays without touching source scans |

The plugin source is included under `cloudcompare-plugin/qMCPBridge`. It runs a newline-delimited JSON control server bound to `127.0.0.1:8765` by default. See that directory's README for CloudCompare build/install instructions.

Environment variables:

- `CLOUDCOMPARE_MCP_HOST` — MCP-side host, default `127.0.0.1`
- `CLOUDCOMPARE_MCP_PORT` — bridge port, default `8765` (set before starting both CloudCompare and the MCP server)
- `CLOUDCOMPARE_MCP_TOKEN` — optional shared token
- `CLOUDCOMPARE_MCP_TIMEOUT` — MCP-side socket timeout in seconds, default `5`

### CloudCompare tools (requires CloudCompare installation)

| Tool | Description |
|------|-------------|
| `get_cloudcompare_info` | Check installation & version |
| `load_cloud_info` | Inspect file stats via CloudCompare |
| `subsample` | Reduce density — random / spatial / octree |
| `compute_cloud_to_cloud_distances` | C2C nearest-neighbour distances |
| `compute_cloud_to_mesh_distances` | C2M signed distances |
| `icp_registration` | Align two clouds with ICP |
| `compute_normals` | Estimate surface normals |
| `filter_by_scalar_field` | Threshold points by scalar value |
| `statistical_outlier_removal` | Remove noise with SOR filter |
| `merge_clouds` | Merge multiple clouds into one |
| `convert_format` | Convert between LAS/LAZ, PLY, PCD, XYZ, E57, OBJ… |
| `run_cloudcompare_command` | Escape hatch for arbitrary CLI commands |

### How `visualize_cloud` works

`visualize_cloud` reads the point cloud natively in Python, renders a 4-panel figure, and returns an `ImageContent` (base64 PNG) alongside a JSON description. The model can see the image directly — no display or CloudCompare needed.

```
┌─────────────────┬─────────────────┐
│   Top  (XY)     │   Front  (XZ)   │
│                 │                 │
├─────────────────┼─────────────────┤
│   Side  (YZ)    │  Metadata stats │
│                 │  (pts, bbox,    │
│                 │   density, …)   │
└─────────────────┴─────────────────┘
```

Color modes: `height` (viridis Z gradient, default) · `rgb` (stored RGB) · `intensity` (plasma).

## Requirements

- **Python ≥ 3.10**
- **uv** (recommended) or pip
- **CloudCompare ≥ 2.12** — [download](https://www.danielgm.net/cc/) *(only for CloudCompare tools)*

Python dependencies installed automatically: `numpy`, `matplotlib`, `laspy[lazrs]`, `plyfile`.

## Installation

### Quickstart with `uvx` (no install needed)

```bash
uvx cloudcompare-mcp
```

### Install locally

```bash
pip install cloudcompare-mcp
cloudcompare-mcp
```

## CloudCompare binary detection

The server looks for CloudCompare in this order:

1. `CLOUDCOMPARE_PATH` environment variable
2. System `PATH` (`cloudcompare` / `CloudCompare`)
3. Platform default locations:

| Platform | Default path |
|----------|-------------|
| macOS | `/Applications/CloudCompare.app/Contents/MacOS/CloudCompare` |
| Windows | `C:\Program Files\CloudCompare\cloudcompare.exe` |
| Linux | `/usr/bin/cloudcompare` |

Set `CLOUDCOMPARE_PATH` to override:

```bash
export CLOUDCOMPARE_PATH="/opt/custom/cloudcompare"
```

## MCP client configuration

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "cloudcompare": {
      "command": "uvx",
      "args": ["cloudcompare-mcp"]
    }
  }
}
```

### Claude Code (`~/.claude/settings.json`)

```json
{
  "mcpServers": {
    "cloudcompare": {
      "command": "uvx",
      "args": ["cloudcompare-mcp"]
    }
  }
}
```

With a custom binary path:

```json
{
  "mcpServers": {
    "cloudcompare": {
      "command": "uvx",
      "args": ["cloudcompare-mcp"],
      "env": {
        "CLOUDCOMPARE_PATH": "/path/to/cloudcompare"
      }
    }
  }
}
```

## Usage example

Once configured in Claude Desktop or Claude Code:

> "Load my scan.las file and subsample it spatially to 5 cm, then remove statistical outliers."

Claude will call the appropriate tools in sequence and report results.

## Supported file formats

LAS · LAZ · PLY · PCD · XYZ · ASC · TXT · E57 · OBJ · BIN · SHP

## License

MIT

## Python-only 0.13 candidate relationships (accepted)

The accepted native bridge remains 0.12.0 / workflow revision 8. New read-only
`analyze_hole_candidates` and `discover_live_hole_candidates` tools filter circular
candidates against a face, group by diameter and measure center spacing, with
provisional row/bolt-circle checks. Numerical patterns are not confirmed physical
holes. See [scope and examples](docs/LIVE_HOLE_PATTERNS.md) and the
[focused Windows test procedure](docs/WINDOWS_HOLE_PATTERN_ACCEPTANCE.md).
This increment passed its broad and focused Windows acceptance gates and was
merged through PR #10. See AGENTS.md for exact source attribution and coverage
limits. No DLL rebuild was required.


## Python-only 0.14 CAD datums and feature relationships (accepted)

`analyze_feature_relationships` measures relationships between supplied global/native
plane, line, circle, cylinder and point snapshots. `build_live_datum_frame` constructs
an explicit right-handed coordinate frame from a primary plane, a secondary
plane/axis and an optional origin feature. Both tools analyze snapshots **without
connecting to CloudCompare**; the `live` datum name does not imply live validation.
Results retain source fingerprints/provenance and distinguish numerical candidates
from physical manufacturing intent. The native bridge remains 0.12.0 / workflow
revision 8, unchanged. The increment passed real Windows/CloudCompare acceptance
and was merged through PR #12; the fan datum acquisition limitation is retained as
coverage, not a product defect. See [contracts and examples](docs/LIVE_CAD_DATUM_RELATIONSHIPS.md).

## Python-only 0.15 CAD profile reconstruction (accepted first increment)

`reconstruct_section_profile` turns an explicit 2D section snapshot into compact
line/arc/circle primitives plus adjacency/tangency and circle/rectangle/slot
candidates without live I/O. `reconstruct_live_section_profile` reuses the accepted
native slab-region query, keeps raw sampled points server-side, projects them to a
stable section frame, and returns the same compact candidate representation.
Ordering assumptions are explicit: caller order, polar closed-loop ordering, or
principal-axis open ordering. Candidate geometry is not accepted manufacturing
intent. The first increment passed its real Windows/CloudCompare gate after issue #13
was fixed and retested, then merged through PR #14. Ellipses, rounded-rectangle
classification, explicit multi-loop/non-star-shaped topology, and spline fallback
remain later 0.15 work. The native bridge remains unchanged at 0.12.0 / revision 8.
See [profile contracts](docs/LIVE_CAD_PROFILE_RECONSTRUCTION.md) and AGENTS.md for
accepted source/retest attribution and retained coverage limits.


## Python-only 0.15.1 explicit profile topology (development)

`reconstruct_section_topology` recovers one or more closed loops from unordered 2D
**boundary samples**, classifies outer/hole/island nesting candidates, and feeds each
loop into the accepted line/arc/circle profile fitter.
`reconstruct_live_section_topology` applies the same logic to a complete live slab
sample while preserving source coordinate bookkeeping.

Both tools require the caller to explicitly assert `boundary_samples_only=true` and
choose a native-unit `max_edge_length`. The live tool refuses truncated acquisition.
This stage supports concave/non-star-shaped boundary loops and multiple loops, but it
does not infer a boundary from a filled scan section or repair intersecting/touching
topology. qMCPBridge remains unchanged at 0.12.0 / revision 8.

See [profile topology contracts](docs/LIVE_CAD_PROFILE_TOPOLOGY.md) and the
[Windows acceptance procedure](docs/WINDOWS_PROFILE_TOPOLOGY_ACCEPTANCE.md).
