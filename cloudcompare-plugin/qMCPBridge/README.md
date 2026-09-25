# qMCPBridge CloudCompare plugin

This native CloudCompare **Standard** plugin exposes a small JSON protocol on loopback so
`cloudcompare-mcp` can operate on the CloudCompare GUI process that is already open.

The listener binds only to `127.0.0.1` and defaults to TCP port `8765`.

## What the bridge exposes

- connectivity/status
- live DB-tree enumeration with CloudCompare unique entity IDs
- get/set GUI selection
- load a file into the open instance
- rename, show/hide, enable/disable, delete, and transform entities
- set standard views, zoom, and redraw
- capture the active 3D viewport as PNG

Destructive operations such as delete and transform are applied directly to the open scene.
The bridge does not provide an undo layer.

## Build inside CloudCompare

CloudCompare's plugin CMake helpers are provided by the CloudCompare source tree, so this
directory is intended to be built as part of a CloudCompare checkout.

1. Copy or symlink this `qMCPBridge` directory into:
   `CloudCompare/plugins/core/Standard/qMCPBridge`
2. Add this line to `CloudCompare/plugins/core/Standard/CMakeLists.txt`:
   `add_subdirectory( qMCPBridge )`
3. Configure CloudCompare with `-DPLUGIN_STANDARD_QMCP_BRIDGE=ON`.
4. Build/install CloudCompare normally.
5. Start CloudCompare. The plugin starts its localhost server automatically when loaded.

A compiled plugin can also live in a custom plugin directory by setting CloudCompare's
`CC_PLUGIN_PATH` environment variable.

## Configuration

Set these variables **before starting CloudCompare**:

- `CLOUDCOMPARE_MCP_PORT` — listener port, default `8765`
- `CLOUDCOMPARE_MCP_TOKEN` — optional shared token; if set, every request must include it

Set the same values for the Python MCP server. The MCP client additionally supports:

- `CLOUDCOMPARE_MCP_HOST` — default `127.0.0.1`
- `CLOUDCOMPARE_MCP_TIMEOUT` — socket timeout in seconds, default `5`

The plugin source is GPL-2.0-or-later because it links against CloudCompare's GPL plugin API.
