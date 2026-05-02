# cloudcompare-mcp

Cross-platform [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [CloudCompare](https://www.danielgm.net/cc/) — lets AI assistants (Claude, etc.) process 3D point clouds and meshes via natural language.

## Features

| Tool | Description |
|------|-------------|
| `get_cloudcompare_info` | Check installation & version |
| `load_cloud_info` | Inspect file stats (points, bounding box, scalar fields) |
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

## Requirements

- **CloudCompare ≥ 2.12** — [download](https://www.danielgm.net/cc/)
- **Python ≥ 3.10**
- **uv** (recommended) or pip

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
