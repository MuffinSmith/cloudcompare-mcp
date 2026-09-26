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
- deep-clone live point clouds and triangle meshes
- non-destructively concatenate explicitly chosen live clouds
- report point/triangle counts, attributes, hierarchy, native/global bounds, and global shift/scale
- export live binary PLY point clouds and face-bearing OBJ meshes with read-back validation
- expose cautious 2.5D meshing plus capability discovery for optional full-3D reconstruction/simplification
- preview/apply rigid ICP and point-pair coarse registration on preserved source geometry
- live C2C/C2M quality analysis on temporary/result clones
- interactive point/triangle picking through CloudCompare's picking hub
- exact point inspection plus picked-point distance and three-point angle measurements

The Fusion-oriented workflow and its optional PyMeshLab backend are documented in
`docs/FUSION_REFERENCE_WORKFLOW.md`.

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

Build against the source release and Qt major version used by the installed
CloudCompare. The plugin uses the host build's Qt 5 or Qt 6 targets. For
CloudCompare 2.13.2 on Windows, use the `v2.13.2` source tag, Qt 5.15.2
`msvc2019_64`, and a compatible MSVC Release/x64 toolchain. Build just
`QMCP_BRIDGE_PLUGIN` and its dependencies; do not copy the rebuilt CloudCompare
libraries over an existing installation. Restart CloudCompare after configuring
the plugin path or replacing the plugin DLL.

The `ping` response includes `process_id` and `application_version` to identify
the GUI process. `capabilities.get` reports the bridge workflow revision, supported
operations, unit policy, and meshing/simplification limitations. Entity responses
report native-coordinate and global-coordinate bounds separately. Physical units
remain `unknown` unless the caller supplies independent unit information.

## Configuration

Set these variables **before starting CloudCompare**:

- `CLOUDCOMPARE_MCP_PORT` — listener port, default `8765`
- `CLOUDCOMPARE_MCP_TOKEN` — optional shared token; if set, every request must include it

Set the same values for the Python MCP server. The MCP client additionally supports:

- `CLOUDCOMPARE_MCP_HOST` — default `127.0.0.1`
- `CLOUDCOMPARE_MCP_TIMEOUT` — socket timeout in seconds, default `5`; long-running
  geometry tools override this per request without changing the lightweight inspection timeout

The plugin source is GPL-2.0-or-later because it links against CloudCompare's GPL plugin API.
