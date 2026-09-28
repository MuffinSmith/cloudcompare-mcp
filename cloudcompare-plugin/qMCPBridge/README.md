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
- recoverable camera snapshots and guarded look/orbit/pan/zoom/source-frame focus
- capture the active 3D viewport as PNG with camera state and content SHA256
- deep-clone live point clouds and triangle meshes
- non-destructively concatenate explicitly chosen live clouds
- report point/triangle counts, attributes, hierarchy, native/global bounds, and global shift/scale
- export live binary PLY point clouds and face-bearing OBJ meshes with read-back validation
- expose cautious 2.5D meshing plus capability discovery for optional full-3D reconstruction/simplification
- preview/apply rigid ICP and point-pair coarse registration on preserved source geometry
- live C2C/C2M quality analysis on temporary/result clones
- interactive point/triangle picking through CloudCompare's picking hub
- exact point inspection plus picked-point distance and three-point angle measurements
- bounded structured sphere/box/slab/nearest queries over live point clouds
- exact all-match region summaries with deterministic bounded point samples
- exact regular 3D region grids with stable per-cell covariance for numerical spatial inspection
- temporary managed plane/circle/cylinder/axis overlays in the source cloud coordinate frame
- overlay status and one-call clear lifecycle for visual confirmation without screenshot feedback

The Fusion-oriented workflow and its optional PyMeshLab backend are documented in
`docs/FUSION_REFERENCE_WORKFLOW.md`.

Destructive operations such as delete and transform are applied directly to the open scene.
The bridge does not provide an undo layer.

## Camera inspection in 0.13.2 / workflow revision 9

Python 0.16.2 provides bounded visual inspection and semantic confirmation using the
`view.camera` contract. **Rebuild the native plugin**; the earlier 0.12.0 DLL
does not implement these operations. Existing standard-view operations remain.
See [the camera/inspection contract](../../docs/LIVE_AGENT_VISUAL_INSPECTION.md)
and [focused Windows acceptance](../../docs/WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md).

Native saved states retain actual `ccViewportParameters` copies, with eight
explicitly released tokens and no eviction. Moves and restore check the session,
active window and expected-current camera fingerprint. Restore additionally checks
viewport dimensions. Object-centered orthographic/perspective modes are supported;
stereo, bubble view, viewer-centered mode and nonunit display scale refuse. Source
cloud global scale is a different parameter and may be nonunit. Global focus uses
a declared visible cloud in the active display and refuses pending transforms.

qMCPBridge 0.13.2 also exposes `cc-camera-auto-pivot-v1`. A saved camera may
explicitly suspend CloudCompare's automatic center-screen pivot for the lifetime
of that restoration token. This prevents host redraws from translating pivot and
camera between guarded inspection requests. Release restores the original host
auto-pivot mode and reports the post-release camera state; external re-enables
refuse as ownership conflicts instead of weakening the pose guard. See
[automatic-pivot recovery](../../docs/AUTO_PIVOT_RECOVERY.md).

Camera-center values are host-render parameters, not global world-eye positions.
Camera fingerprint equality is not framebuffer or full-GUI equality. Native PNG
capture includes camera-state checks before/after event processing and framebuffer
capture, plus an actual content SHA256. These operations do not mutate source
geometry, selection or unrelated overlays. They do not interpret images or infer
human intent. The broader bridge still exposes the separate destructive operations
listed above; camera safety is not a blanket read-only guarantee for every tool.

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
