# cloudcompare-mcp

Cross-platform [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [CloudCompare](https://www.danielgm.net/cc/) — lets AI assistants (Claude, etc.) process 3D point clouds and meshes via natural language.

## Fusion 360 live reference-mesh workflow

For safe reverse engineering from an already-open CloudCompare scene, including
live cloning/merging, validated PLY/OBJ export, optional full-3D ball-pivoting
reconstruction, reference-mesh simplification, and the end-to-end acceptance
harness, see [docs/FUSION_REFERENCE_WORKFLOW.md](docs/FUSION_REFERENCE_WORKFLOW.md).

## Features

### Native tools (no CloudCompare required)

| Tool | Description |
|------|-------------|
| `read_cloud_metadata` | Parse a cloud and return point count, bounding box, extent, density, RGB/intensity/normals presence |
| `visualize_cloud` | **Render top / front / side views + metadata panel as a base64 PNG the model can see directly** |

### Live CloudCompare GUI tools (requires qMCPBridge plugin)

These tools operate on the **CloudCompare instance that is already open** instead of launching a new CLI process.

| Tool | Description |
|------|-------------|
| `get_live_cloudcompare_info` | Check connectivity to the open CloudCompare GUI |
| `list_live_entities` | Read the current DB tree and entity IDs |
| `get_live_selection` | Read the current GUI selection |
| `set_live_selection` | Select entities by CloudCompare unique ID |
| `load_file_live` | Load a file into the open GUI |
| `rename_live_entity` | Rename an entity |
| `set_live_entity_state` | Show/hide or enable/disable an entity |
| `delete_live_entities` | Remove entities from the current DB tree |
| `transform_live_entity` | Apply a 4x4 transform to an entity |
| `set_live_view` | Change standard view / zoom / redraw |
| `capture_live_view` | Return the active CloudCompare viewport as a PNG the model can see |

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
