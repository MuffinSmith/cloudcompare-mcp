"""CloudCompare MCP Server — wraps CloudCompare CLI for AI-assisted point cloud processing."""

import base64
import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import ImageContent, TextContent, Tool

from .live import LiveBridgeError, request as live_request

# ── CloudCompare binary discovery ────────────────────────────────────────────

_CC_CANDIDATES: dict[str, list[str]] = {
    "Windows": [
        r"C:\Program Files\CloudCompare\cloudcompare.exe",
        r"C:\Program Files (x86)\CloudCompare\cloudcompare.exe",
    ],
    "Darwin": [
        "/Applications/CloudCompare.app/Contents/MacOS/CloudCompare",
        "/Applications/cloudcompare.app/Contents/MacOS/CloudCompare",
        "/usr/local/bin/cloudcompare",
    ],
    "Linux": [
        "/usr/bin/cloudcompare",
        "/usr/local/bin/cloudcompare",
        "/snap/bin/cloudcompare",
        "/opt/cloudcompare/bin/cloudcompare",
    ],
}


def find_cloudcompare() -> str | None:
    if env := os.environ.get("CLOUDCOMPARE_PATH"):
        return env if Path(env).is_file() else None
    if found := shutil.which("cloudcompare") or shutil.which("CloudCompare"):
        return found
    for candidate in _CC_CANDIDATES.get(platform.system(), []):
        if Path(candidate).is_file():
            return candidate
    return None


def cc_run(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    binary = find_cloudcompare()
    if not binary:
        raise FileNotFoundError(
            "CloudCompare executable not found. Install CloudCompare and set "
            "the CLOUDCOMPARE_PATH environment variable if needed."
        )
    result = subprocess.run(
        [binary, "-SILENT"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode, result.stdout, result.stderr


# ── Native point cloud readers (no CloudCompare needed) ──────────────────────

def _load_las(filepath: str) -> tuple[Any, Any | None, dict]:
    """Load LAS/LAZ; return (xyz Nx3, colors Nx3 float [0,1] or None, meta)."""
    import laspy
    import numpy as np

    las = laspy.read(filepath)
    x = np.asarray(las.x, dtype=np.float64)
    y = np.asarray(las.y, dtype=np.float64)
    z = np.asarray(las.z, dtype=np.float64)
    xyz = np.column_stack([x, y, z])

    dims = [d.name for d in las.point_format.dimensions]
    has_rgb = "red" in dims and "green" in dims and "blue" in dims
    has_intensity = "intensity" in dims
    colors = None
    if has_rgb:
        r = np.asarray(las.red, dtype=np.float32)
        g = np.asarray(las.green, dtype=np.float32)
        b = np.asarray(las.blue, dtype=np.float32)
        scale = r.max()
        if scale > 255:
            scale = 65535.0
        elif scale > 1:
            scale = 255.0
        else:
            scale = 1.0
        colors = np.column_stack([r, g, b]) / scale

    meta: dict = {
        "format": "LAS",
        "point_count": len(x),
        "has_rgb": has_rgb,
        "has_intensity": has_intensity,
        "has_normals": "normal_x" in dims,
        "scalar_fields": [d for d in dims if d not in ("x", "y", "z", "red", "green", "blue")],
        "file_size_mb": round(Path(filepath).stat().st_size / 1_048_576, 2),
    }
    return xyz, colors, meta


def _load_ply(filepath: str) -> tuple[Any, Any | None, dict]:
    """Load PLY via plyfile; return (xyz, colors or None, meta)."""
    import numpy as np
    from plyfile import PlyData

    ply = PlyData.read(filepath)
    vertex = ply["vertex"]
    props = {p.name for p in vertex.properties}
    x = np.asarray(vertex["x"], dtype=np.float64)
    y = np.asarray(vertex["y"], dtype=np.float64)
    z = np.asarray(vertex["z"], dtype=np.float64)
    xyz = np.column_stack([x, y, z])

    has_rgb = {"red", "green", "blue"}.issubset(props)
    colors = None
    if has_rgb:
        r = np.asarray(vertex["red"], dtype=np.float32)
        g = np.asarray(vertex["green"], dtype=np.float32)
        b = np.asarray(vertex["blue"], dtype=np.float32)
        scale = 255.0 if r.max() > 1 else 1.0
        colors = np.column_stack([r, g, b]) / scale

    meta: dict = {
        "format": "PLY",
        "point_count": len(x),
        "has_rgb": has_rgb,
        "has_intensity": "intensity" in props,
        "has_normals": "nx" in props or "normal_x" in props,
        "scalar_fields": sorted(props - {"x", "y", "z", "red", "green", "blue", "nx", "ny", "nz"}),
        "file_size_mb": round(Path(filepath).stat().st_size / 1_048_576, 2),
    }
    return xyz, colors, meta


def _load_ascii(filepath: str) -> tuple[Any, Any | None, dict]:
    """Load whitespace-delimited XYZ/ASC/TXT (first 3 columns = x,y,z)."""
    import numpy as np

    data = np.loadtxt(filepath, comments=["#", "//", "!"])
    if data.ndim == 1:
        data = data[np.newaxis, :]
    xyz = data[:, :3].astype(np.float64)
    colors = None
    if data.shape[1] >= 6:
        rgb = data[:, 3:6].astype(np.float32)
        if rgb.max() > 1:
            rgb /= 255.0
        colors = np.clip(rgb, 0, 1)

    meta: dict = {
        "format": "ASCII",
        "point_count": len(xyz),
        "has_rgb": colors is not None,
        "has_intensity": data.shape[1] == 4,
        "has_normals": False,
        "scalar_fields": [],
        "file_size_mb": round(Path(filepath).stat().st_size / 1_048_576, 2),
    }
    return xyz, colors, meta


def _load_pcd(filepath: str) -> tuple[Any, Any | None, dict]:
    """Load ASCII PCD files (XYZRGB or XYZ)."""
    import numpy as np

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    fields: list[str] = []
    data_start = 0
    is_binary = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("FIELDS"):
            fields = stripped.split()[1:]
        elif stripped.startswith("DATA binary"):
            is_binary = True
            data_start = i + 1
            break
        elif stripped.startswith("DATA ascii"):
            data_start = i + 1
            break

    if is_binary:
        raise ValueError("Binary PCD is not supported for native reading. "
                         "Use convert_format (CloudCompare) to convert to ASCII PCD or PLY first.")

    data = np.loadtxt(lines[data_start:])
    if data.ndim == 1:
        data = data[np.newaxis, :]

    fi = {name: idx for idx, name in enumerate(fields)}
    x = data[:, fi["x"]]
    y = data[:, fi["y"]]
    z = data[:, fi["z"]]
    xyz = np.column_stack([x, y, z])

    colors = None
    if "rgb" in fi:
        # RGB packed as float
        packed = data[:, fi["rgb"]].view(np.uint32) if data.dtype == np.float32 else \
                 data[:, fi["rgb"]].astype(np.float32).view(np.uint32)
        r = ((packed >> 16) & 0xFF).astype(np.float32) / 255.0
        g = ((packed >> 8) & 0xFF).astype(np.float32) / 255.0
        b = (packed & 0xFF).astype(np.float32) / 255.0
        colors = np.column_stack([r, g, b])

    meta: dict = {
        "format": "PCD",
        "point_count": len(xyz),
        "has_rgb": colors is not None,
        "has_intensity": "intensity" in fi,
        "has_normals": "normal_x" in fi,
        "scalar_fields": [f for f in fields if f not in ("x", "y", "z", "rgb", "rgba")],
        "file_size_mb": round(Path(filepath).stat().st_size / 1_048_576, 2),
    }
    return xyz, colors, meta


def _load_cloud(filepath: str) -> tuple[Any, Any | None, dict]:
    ext = Path(filepath).suffix.lower()
    loaders = {
        ".las": _load_las, ".laz": _load_las,
        ".ply": _load_ply,
        ".pcd": _load_pcd,
        ".xyz": _load_ascii, ".asc": _load_ascii,
        ".txt": _load_ascii, ".csv": _load_ascii,
    }
    loader = loaders.get(ext)
    if loader is None:
        raise ValueError(
            f"Unsupported format '{ext}' for native reading. "
            "Supported: LAS, LAZ, PLY, PCD, XYZ, ASC, TXT. "
            "For other formats, use convert_format (CloudCompare) to convert first."
        )
    return loader(filepath)


def _cloud_meta_stats(xyz: Any, meta: dict) -> dict:
    """Append bounding-box, extent, and density stats to meta."""
    import numpy as np

    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    xmin, xmax = float(x.min()), float(x.max())
    ymin, ymax = float(y.min()), float(y.max())
    zmin, zmax = float(z.min()), float(z.max())
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    area_xy = dx * dy
    n = len(xyz)

    meta["bbox"] = {
        "x": [round(xmin, 3), round(xmax, 3)],
        "y": [round(ymin, 3), round(ymax, 3)],
        "z": [round(zmin, 3), round(zmax, 3)],
    }
    meta["units"] = meta.get("units", "unknown")
    meta["units_confirmed"] = bool(meta.get("units_confirmed", False))
    meta["extent_native"] = {
        "x": round(dx, 3), "y": round(dy, 3), "z": round(dz, 3),
    }
    meta["area_xy_native2"] = round(area_xy, 2)
    meta["density_pts_per_native_unit2"] = round(n / area_xy, 1) if area_xy > 0 else None
    return meta


# ── Visualization ─────────────────────────────────────────────────────────────

def _fig_to_base64(fig: Any) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _pick_colors(xyz: Any, colors: Any | None, color_by: str) -> tuple[Any, str | None, str]:
    """Return (c_array, cmap_name_or_None, colorbar_label)."""
    import numpy as np

    z = xyz[:, 2]
    if color_by == "rgb" and colors is not None:
        return colors, None, ""
    if color_by == "rgb" and colors is None:
        # fall back to height
        color_by = "height"
    if color_by == "intensity":
        # use Z as proxy (intensity not loaded yet for non-LAS paths)
        return z, "plasma", "Z (intensity proxy)"
    # default: height / Z
    return z, "viridis", "Z (native units)"


def _scatter_kwargs(n: int) -> dict:
    """Adaptive point size and alpha based on cloud density."""
    s = max(0.05, min(3.0, 80_000 / n))
    alpha = max(0.08, min(1.0, 60_000 / n))
    return {"s": s, "alpha": alpha, "linewidths": 0, "rasterized": True}


_BG = "#0d1117"
_FG = "#e6edf3"
_GRAY = "#8b949e"


def _ax_style(ax: Any, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(_BG)
    ax.set_title(title, color=_FG, fontsize=10, pad=4)
    ax.set_xlabel(xlabel, color=_GRAY, fontsize=8)
    ax.set_ylabel(ylabel, color=_GRAY, fontsize=8)
    ax.tick_params(colors=_GRAY, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")


def _build_figure(xyz: Any, colors: Any | None, meta: dict, color_by: str) -> Any:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import numpy as np

    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    c, cmap, cbar_label = _pick_colors(xyz, colors, color_by)
    kw = _scatter_kwargs(len(xyz))

    fig = plt.figure(figsize=(16, 11), facecolor=_BG)
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.25)

    def _add_cbar(mappable: Any, ax: Any, label: str) -> None:
        if cmap and label:
            cb = fig.colorbar(mappable, ax=ax, pad=0.02, fraction=0.04)
            cb.ax.yaxis.set_tick_params(color=_GRAY, labelcolor=_GRAY, labelsize=7)
            cb.set_label(label, color=_GRAY, fontsize=7)
            cb.outline.set_edgecolor("#30363d")

    # ── Top view (XY) ──────────────────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, 0])
    sc0 = ax0.scatter(x, y, c=c, cmap=cmap, **kw)
    _ax_style(ax0, f"Top view  (XY)", "X (native)", "Y (native)")
    ax0.set_aspect("equal", adjustable="datalim")
    _add_cbar(sc0, ax0, cbar_label)

    # ── Front view (XZ) ────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 1])
    sc1 = ax1.scatter(x, z, c=c, cmap=cmap, **kw)
    _ax_style(ax1, "Front view  (XZ)", "X (native)", "Z (native)")
    _add_cbar(sc1, ax1, cbar_label)

    # ── Side view (YZ) ─────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    sc2 = ax2.scatter(y, z, c=c, cmap=cmap, **kw)
    _ax_style(ax2, "Side view  (YZ)", "Y (native)", "Z (native)")
    _add_cbar(sc2, ax2, cbar_label)

    # ── Stats panel ────────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(_BG)
    ax3.axis("off")

    bb = meta.get("bbox", {})
    ex = meta.get("extent_native", {})
    density = meta.get("density_pts_per_native_unit2")
    sf = meta.get("scalar_fields", [])

    lines = [
        f"  Points      {meta['point_count']:>14,}",
        f"  File size   {meta.get('file_size_mb', '?'):>13} MB",
        "",
        "  Bounding box (native units)",
        f"    X  [{bb.get('x', ['?','?'])[0]:.2f}, {bb.get('x', ['?','?'])[1]:.2f}]"
        f"  Δ {ex.get('x', '?'):.2f}",
        f"    Y  [{bb.get('y', ['?','?'])[0]:.2f}, {bb.get('y', ['?','?'])[1]:.2f}]"
        f"  Δ {ex.get('y', '?'):.2f}",
        f"    Z  [{bb.get('z', ['?','?'])[0]:.2f}, {bb.get('z', ['?','?'])[1]:.2f}]"
        f"  Δ {ex.get('z', '?'):.2f}",
        "",
        f"  XY area     {meta.get('area_xy_native2', '?'):>13,.1f} unit²",
        f"  Density     {(str(density) + ' pts/unit²') if density else 'N/A':>13}",
        "",
        "  Attributes",
        f"    RGB         {'✓' if meta.get('has_rgb') else '✗'}",
        f"    Intensity   {'✓' if meta.get('has_intensity') else '✗'}",
        f"    Normals     {'✓' if meta.get('has_normals') else '✗'}",
        f"    Scalar flds {len(sf):>3}",
    ]
    if sf:
        for name in sf[:6]:
            lines.append(f"      • {name}")
        if len(sf) > 6:
            lines.append(f"      … +{len(sf) - 6} more")

    ax3.text(
        0.04, 0.97, "\n".join(lines),
        transform=ax3.transAxes,
        color=_FG, fontsize=9, va="top", fontfamily="monospace",
        linespacing=1.6,
    )
    ax3.set_title("Metadata", color=_FG, fontsize=10, pad=4)

    # ── Super-title ────────────────────────────────────────────────────────
    fname = Path(meta.get("_filepath", "point cloud")).name
    n_shown = len(xyz)
    n_total = meta["point_count"]
    subtitle = f"{n_shown:,} pts shown" + (f" (of {n_total:,})" if n_shown < n_total else "")
    fig.suptitle(f"{fname}   ·   {subtitle}", color=_FG, fontsize=12, y=0.995)

    return fig


# ── MCP Server setup ──────────────────────────────────────────────────────────

server = Server("cloudcompare-mcp")

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="get_live_cloudcompare_info",
        description=(
            "Connect to the qMCPBridge plugin in an already-open CloudCompare GUI instance. "
            "Returns bridge status, protocol version, selected entity IDs, and live scene count. "
            "Use this first when the user wants to operate on the CloudCompare window they already have open."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_live_entities",
        description=(
            "List entities in the currently open CloudCompare GUI database tree. "
            "Returns stable CloudCompare unique IDs used by the other live-instance tools."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "recursive": {"type": "boolean", "default": True},
            },
        },
    ),
    Tool(
        name="get_live_selection",
        description="Return the entities currently selected in the open CloudCompare GUI.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="set_live_selection",
        description=(
            "Select entities in the open CloudCompare GUI by unique entity ID. "
            "By default the existing selection is cleared first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}},
                "clear": {"type": "boolean", "default": True},
            },
            "required": ["ids"],
        },
    ),
    Tool(
        name="load_file_live",
        description="Load a point cloud or mesh into the already-open CloudCompare GUI instance.",
        inputSchema={
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        },
    ),
    Tool(
        name="rename_live_entity",
        description="Rename an entity in the open CloudCompare GUI by its unique ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer"},
                "name": {"type": "string"},
            },
            "required": ["entity_id", "name"],
        },
    ),
    Tool(
        name="set_live_entity_state",
        description="Show/hide and/or enable/disable an entity in the open CloudCompare GUI.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer"},
                "visible": {"type": "boolean"},
                "enabled": {"type": "boolean"},
            },
            "required": ["entity_id"],
        },
    ),
    Tool(
        name="delete_live_entities",
        description=(
            "Delete one or more entities from the open CloudCompare GUI database tree. "
            "This is destructive and the bridge does not provide an undo layer."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
            },
            "required": ["ids"],
        },
    ),
    Tool(
        name="transform_live_entity",
        description=(
            "Apply a 4x4 transform directly to an entity in the open CloudCompare GUI. "
            "Matrix values must be 16 numbers in OpenGL column-major order."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer"},
                "matrix": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 16,
                    "maxItems": 16,
                },
            },
            "required": ["entity_id", "matrix"],
        },
    ),
    Tool(
        name="set_live_view",
        description=(
            "Control the active 3D view in the open CloudCompare GUI. "
            "Supports standard orthographic directions plus zoom/redraw actions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "top", "bottom", "front", "back", "left", "right",
                        "zoom_selected", "global_zoom", "redraw",
                    ],
                },
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="capture_live_view",
        description=(
            "Capture the active 3D viewport from the currently open CloudCompare GUI "
            "and return it as a PNG image the model can inspect."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_live_workflow_capabilities",
        description=(
            "Report the live bridge's safe reverse-engineering capabilities, application/plugin versions, "
            "native-unit policy, available meshing methods, simplification backends, and execution limitations."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="clone_live_entities",
        description=(
            "Deep-clone explicitly chosen live point clouds or triangle meshes without modifying the sources. "
            "Use this before destructive or experimental reverse-engineering steps."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                "destination_group_id": {"type": "integer"},
                "name_suffix": {"type": "string", "default": ".mcp_clone"},
            },
            "required": ["ids"],
        },
    ),
    Tool(
        name="merge_live_clouds",
        description=(
            "Create a new live point cloud by concatenating only the explicitly supplied cloud IDs. "
            "No filtering, smoothing, duplicate removal, or resampling is performed. Originals are preserved."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
                "coordinate_frame_policy": {
                    "type": "string",
                    "enum": ["strict", "convert_to_first"],
                    "default": "strict",
                },
            },
            "required": ["ids"],
        },
    ),
    Tool(
        name="reconstruct_live_mesh",
        description=(
            "Create a separate mesh from a live cloud using an explicitly chosen supported reconstruction method. "
            "CloudCompare core methods exposed here are 2.5D only; Poisson is never selected automatically."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cloud_id": {"type": "integer"},
                "method": {
                    "type": "string",
                    "enum": [
                        "ball_pivoting",
                        "delaunay_2_5d_best_fit_plane",
                        "delaunay_2_5d_axis_aligned",
                    ],
                },
                "acknowledge_2_5d_limitations": {"type": "boolean", "default": False},
                "ball_radius_percent": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Ball radius as a percent of the source bounding-box diagonal. Omit to let MeshLab estimate it.",
                },
                "clustering_percent": {"type": "number", "minimum": 0, "default": 20.0},
                "crease_threshold_degrees": {"type": "number", "minimum": 0, "maximum": 180, "default": 90.0},
                "max_edge_length": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Maximum triangle edge length in the cloud's native coordinate units; 0 disables the limit.",
                },
                "projection_dimension": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 2,
                    "default": 2,
                },
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["cloud_id", "method"],
        },
    ),
    Tool(
        name="simplify_live_mesh",
        description=(
            "Request persisted reference-mesh simplification. The tool reports whether a safe topology simplifier "
            "is actually available instead of silently substituting CloudCompare display LOD decimation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_id": {"type": "integer"},
                "target_triangles": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "For fan reference meshes, normally target 200000-500000 triangles.",
                },
                "preserve_boundaries": {"type": "boolean", "default": True},
                "preserve_sharp_features": {"type": "boolean", "default": True},
                "preserve_topology": {"type": "boolean", "default": True},
                "deviation_samples": {
                    "type": "integer",
                    "minimum": 1000,
                    "maximum": 1000000,
                    "default": 100000,
                },
            },
            "required": ["mesh_id", "target_triangles"],
        },
    ),
    Tool(
        name="export_live_entity",
        description=(
            "Export current live geometry, including unsaved edits/transforms, directly from CloudCompare. "
            "Use binary PLY for point clouds and OBJ only for genuine triangle meshes. "
            "Exports are written transactionally, refuse overwrite by default, and are read back for count/bounds validation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer"},
                "path": {
                    "type": "string",
                    "description": "Absolute output path ending in .ply or .obj.",
                },
                "overwrite": {"type": "boolean", "default": False},
                "intended_import_units": {
                    "type": "string",
                    "description": "Optional caller-supplied intended units for unitless OBJ import (for example 'millimeters').",
                },
            },
            "required": ["entity_id", "path"],
        },
    ),
    Tool(
        name="get_cloudcompare_info",
        description=(
            "Check if CloudCompare is installed and return its version and path. "
            "Call this first to confirm the tool is available."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="read_cloud_metadata",
        description=(
            "Read a point cloud file natively (no CloudCompare required) and return "
            "detailed metadata: point count, bounding box, extent, XY area, density, "
            "presence of RGB/intensity/normals, and scalar field names. "
            "Supports LAS, LAZ, PLY, PCD, XYZ, ASC, TXT."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the point cloud file.",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="visualize_cloud",
        description=(
            "Render a point cloud as a multi-view image (top / front / side + metadata panel) "
            "and return it as a base64-encoded PNG the model can see directly. "
            "No CloudCompare installation required. "
            "Supports LAS, LAZ, PLY, PCD, XYZ, ASC, TXT."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the point cloud file.",
                },
                "color_by": {
                    "type": "string",
                    "enum": ["height", "rgb", "intensity"],
                    "description": (
                        "Colour scheme: 'height' = Z gradient (default), "
                        "'rgb' = stored RGB (falls back to height if absent), "
                        "'intensity' = plasma gradient."
                    ),
                    "default": "height",
                },
                "max_points": {
                    "type": "integer",
                    "description": "Maximum points to render (random subsample for speed). Default 400000.",
                    "default": 400000,
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="load_cloud_info",
        description=(
            "Load a point cloud or mesh via CloudCompare and return basic statistics. "
            "Supports LAS/LAZ, PLY, PCD, E57, XYZ, ASC, BIN, SHP, OBJ, and more. "
            "Requires CloudCompare to be installed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the point cloud or mesh file.",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="subsample",
        description=(
            "Reduce the density of a point cloud using random, spatial, or octree subsampling. "
            "Output is saved to the specified path. Requires CloudCompare."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": ["RANDOM", "SPATIAL", "OCTREE"],
                    "default": "SPATIAL",
                },
                "parameter": {
                    "type": "number",
                    "description": (
                        "RANDOM: number of points to keep (int). "
                        "SPATIAL: minimum point spacing in metres. "
                        "OCTREE: octree level (1–21)."
                    ),
                },
            },
            "required": ["input_path", "output_path", "parameter"],
        },
    ),
    Tool(
        name="compute_cloud_to_cloud_distances",
        description=(
            "Compute nearest-neighbour C2C distances from the compared cloud to the reference cloud. "
            "Saves the labelled cloud. Requires CloudCompare."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "reference_path": {"type": "string"},
                "compared_path": {"type": "string"},
                "output_path": {"type": "string"},
                "max_distance": {"type": "number", "description": "Optional max search distance (m)."},
            },
            "required": ["reference_path", "compared_path", "output_path"],
        },
    ),
    Tool(
        name="compute_cloud_to_mesh_distances",
        description="Compute signed C2M distances from a cloud to a reference mesh. Requires CloudCompare.",
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_path": {"type": "string"},
                "cloud_path": {"type": "string"},
                "output_path": {"type": "string"},
            },
            "required": ["mesh_path", "cloud_path", "output_path"],
        },
    ),
    Tool(
        name="icp_registration",
        description=(
            "Register a data cloud onto a model cloud using ICP. "
            "Returns transformation matrix and final RMS error. Requires CloudCompare."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_path": {"type": "string"},
                "data_path": {"type": "string"},
                "output_path": {"type": "string"},
                "overlap": {"type": "number", "default": 100, "description": "Expected overlap % (10–100)."},
                "iterations": {"type": "integer", "default": 20},
                "random_sampling_limit": {"type": "integer", "default": 50000},
            },
            "required": ["model_path", "data_path", "output_path"],
        },
    ),
    Tool(
        name="compute_normals",
        description="Estimate surface normals. Requires CloudCompare.",
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "mode": {"type": "string", "enum": ["LS", "QUADRIC", "TRIANGULATION"], "default": "LS"},
                "radius": {"type": "number"},
                "knn": {"type": "integer"},
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="filter_by_scalar_field",
        description="Keep only points with scalar-field value in [min_val, max_val]. Requires CloudCompare.",
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "min_val": {"type": "number"},
                "max_val": {"type": "number"},
            },
            "required": ["input_path", "output_path", "min_val", "max_val"],
        },
    ),
    Tool(
        name="statistical_outlier_removal",
        description="Remove statistical outliers (SOR filter). Requires CloudCompare.",
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "knn": {"type": "integer", "default": 6},
                "n_sigma": {"type": "number", "default": 1.0},
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="merge_clouds",
        description="Merge two or more point clouds. Requires CloudCompare.",
        inputSchema={
            "type": "object",
            "properties": {
                "input_paths": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                "output_path": {"type": "string"},
            },
            "required": ["input_paths", "output_path"],
        },
    ),
    Tool(
        name="convert_format",
        description=(
            "Convert a point cloud to a different format. "
            "Target format is inferred from the output file extension "
            "(.las, .laz, .ply, .pcd, .xyz, .asc, .e57, .obj). Requires CloudCompare."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="run_cloudcompare_command",
        description=(
            "Run an arbitrary CloudCompare CLI command. "
            "Do NOT include the binary path or -SILENT — they are added automatically. "
            "Example: [\"-O\", \"/path/cloud.las\", \"-AUTO_SAVE\", \"OFF\"]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "args": {"type": "array", "items": {"type": "string"}},
                "working_directory": {"type": "string"},
            },
            "required": ["args"],
        },
    ),
]


# ── Handler helpers ───────────────────────────────────────────────────────────

def _ok(data: dict | str) -> list[TextContent]:
    body = data if isinstance(data, str) else json.dumps(data, indent=2)
    return [TextContent(type="text", text=body)]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}, indent=2))]


def _run_result(rc: int, stdout: str, stderr: str, extra: dict | None = None) -> list[TextContent]:
    out: dict = {
        "returncode": rc,
        "stdout": stdout.strip() or "(none)",
        "stderr": stderr.strip() or "(none)",
        "success": rc == 0,
    }
    if extra:
        out.update(extra)
    return _ok(out)


def _ensure_output_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ── Native handlers ───────────────────────────────────────────────────────────

def handle_read_metadata(args: dict) -> list[TextContent]:
    import numpy as np

    fp = args["file_path"]
    if not Path(fp).exists():
        return _err(f"File not found: {fp}")
    try:
        xyz, colors, meta = _load_cloud(fp)
    except Exception as exc:
        return _err(f"Failed to read {fp}: {exc}")
    meta["_filepath"] = fp
    _cloud_meta_stats(xyz, meta)
    meta.pop("_filepath", None)
    return _ok(meta)


def handle_visualize(args: dict) -> list[ImageContent | TextContent]:
    import numpy as np

    fp = args["file_path"]
    color_by = args.get("color_by", "height")
    max_pts = int(args.get("max_points", 400_000))

    if not Path(fp).exists():
        return _err(f"File not found: {fp}")

    try:
        xyz, colors, meta = _load_cloud(fp)
    except Exception as exc:
        return _err(f"Failed to read '{fp}': {exc}")

    meta["_filepath"] = fp
    _cloud_meta_stats(xyz, meta)

    # Subsample for rendering speed
    n = len(xyz)
    if n > max_pts:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, max_pts, replace=False)
        xyz_plot = xyz[idx]
        colors_plot = colors[idx] if colors is not None else None
    else:
        xyz_plot = xyz
        colors_plot = colors

    try:
        fig = _build_figure(xyz_plot, colors_plot, meta, color_by)
        img_b64 = _fig_to_base64(fig)
    except Exception as exc:
        return _err(f"Visualization failed: {exc}")
    finally:
        try:
            import matplotlib.pyplot as plt
            plt.close("all")
        except Exception:
            pass

    meta.pop("_filepath", None)
    desc = (
        f"Point cloud: {Path(fp).name} | "
        f"{meta['point_count']:,} points | "
        f"XY extent {meta['extent_native']['x']:.1f} × {meta['extent_native']['y']:.1f} native units | "
        f"Z range {meta['bbox']['z'][0]:.2f}–{meta['bbox']['z'][1]:.2f} native units | "
        f"RGB: {'yes' if meta['has_rgb'] else 'no'} | "
        f"Density: {meta.get('density_pts_per_native_unit2', 'N/A')} pts/native-unit²"
    )

    return [
        ImageContent(type="image", data=img_b64, mimeType="image/png"),
        TextContent(type="text", text=desc + "\n\n" + json.dumps(meta, indent=2)),
    ]


# ── Live CloudCompare GUI bridge handlers ─────────────────────────────────────

def _live_call(
    method: str,
    params: dict | None = None,
    *,
    timeout: float | None = None,
) -> list[TextContent]:
    try:
        return _ok(live_request(method, params or {}, timeout=timeout))
    except LiveBridgeError as exc:
        return _err(str(exc))


def handle_get_live_cloudcompare_info(_args: dict) -> list[TextContent]:
    return _live_call("ping")


def handle_list_live_entities(args: dict) -> list[TextContent]:
    return _live_call("scene.list", {"recursive": bool(args.get("recursive", True))})


def handle_get_live_selection(_args: dict) -> list[TextContent]:
    return _live_call("selection.get")


def handle_set_live_selection(args: dict) -> list[TextContent]:
    return _live_call(
        "selection.set",
        {"ids": args["ids"], "clear": bool(args.get("clear", True))},
    )


def handle_load_file_live(args: dict) -> list[TextContent]:
    return _live_call("file.load", {"path": args["file_path"]})


def handle_rename_live_entity(args: dict) -> list[TextContent]:
    return _live_call(
        "entity.rename",
        {"id": args["entity_id"], "name": args["name"]},
    )


def handle_set_live_entity_state(args: dict) -> list[TextContent]:
    params = {"id": args["entity_id"]}
    if "visible" in args:
        params["visible"] = args["visible"]
    if "enabled" in args:
        params["enabled"] = args["enabled"]
    return _live_call("entity.set_state", params)


def handle_delete_live_entities(args: dict) -> list[TextContent]:
    return _live_call("entity.delete", {"ids": args["ids"]})


def handle_transform_live_entity(args: dict) -> list[TextContent]:
    return _live_call(
        "entity.transform",
        {"id": args["entity_id"], "matrix": args["matrix"]},
    )


def handle_set_live_view(args: dict) -> list[TextContent]:
    return _live_call("view", {"action": args["action"]})


def handle_capture_live_view(_args: dict) -> list[ImageContent | TextContent]:
    try:
        result = live_request("view.capture", {})
        png_b64 = result["png_base64"]
        metadata = {
            "width": result.get("width"),
            "height": result.get("height"),
            "source": "open CloudCompare active 3D viewport",
        }
        return [
            ImageContent(type="image", data=png_b64, mimeType="image/png"),
            TextContent(type="text", text=json.dumps(metadata, indent=2)),
        ]
    except (LiveBridgeError, KeyError, TypeError) as exc:
        return _err(str(exc))


def handle_get_live_workflow_capabilities(_args: dict) -> list[TextContent]:
    try:
        native = live_request("capabilities.get", {})
        from .fusion_mesh import backend_capabilities

        native["python_backends"] = backend_capabilities()
        return _ok(native)
    except (LiveBridgeError, Exception) as exc:
        return _err(str(exc))


def handle_clone_live_entities(args: dict) -> list[TextContent]:
    params = {
        "ids": args["ids"],
        "name_suffix": args.get("name_suffix", ".mcp_clone"),
    }
    if "destination_group_id" in args:
        params["destination_group_id"] = args["destination_group_id"]
    return _live_call("entity.clone", params, timeout=300.0)


def handle_merge_live_clouds(args: dict) -> list[TextContent]:
    params = {
        "ids": args["ids"],
        "coordinate_frame_policy": args.get("coordinate_frame_policy", "strict"),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.merge", params, timeout=600.0)


def handle_reconstruct_live_mesh(args: dict) -> list[TextContent]:
    if args["method"] == "ball_pivoting":
        try:
            from .fusion_mesh import FusionMeshBackendError, reconstruct_ball_pivoting

            result = reconstruct_ball_pivoting(
                cloud_id=int(args["cloud_id"]),
                ball_radius_percent=args.get("ball_radius_percent"),
                clustering_percent=float(args.get("clustering_percent", 20.0)),
                crease_threshold_degrees=float(args.get("crease_threshold_degrees", 90.0)),
                name=args.get("name"),
            )
            return _ok(result)
        except (FusionMeshBackendError, LiveBridgeError, Exception) as exc:
            return _err(str(exc))

    params = {
        "cloud_id": args["cloud_id"],
        "method": args["method"],
        "acknowledge_2_5d_limitations": bool(args.get("acknowledge_2_5d_limitations", False)),
    }
    for key in ("max_edge_length", "projection_dimension", "name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("mesh.reconstruct", params, timeout=600.0)


def handle_simplify_live_mesh(args: dict) -> list[TextContent]:
    try:
        from .fusion_mesh import FusionMeshBackendError, simplify_quadric

        result = simplify_quadric(
            mesh_id=int(args["mesh_id"]),
            target_triangles=int(args["target_triangles"]),
            preserve_boundaries=bool(args.get("preserve_boundaries", True)),
            preserve_sharp_features=bool(args.get("preserve_sharp_features", True)),
            preserve_topology=bool(args.get("preserve_topology", True)),
            deviation_samples=int(args.get("deviation_samples", 100_000)),
        )
        return _ok(result)
    except (FusionMeshBackendError, LiveBridgeError, Exception) as exc:
        return _err(str(exc))


def handle_export_live_entity(args: dict) -> list[TextContent]:
    params = {
        "entity_id": args["entity_id"],
        "path": args["path"],
        "overwrite": bool(args.get("overwrite", False)),
    }
    if "intended_import_units" in args:
        params["intended_import_units"] = args["intended_import_units"]
    return _live_call("entity.export", params, timeout=600.0)


# ── CloudCompare handlers ─────────────────────────────────────────────────────

def handle_get_cloudcompare_info(_args: dict) -> list[TextContent]:
    binary = find_cloudcompare()
    if not binary:
        return _err(
            "CloudCompare not found. Install it from https://www.danielgm.net/cc/ "
            "and optionally set the CLOUDCOMPARE_PATH environment variable."
        )
    rc, stdout, stderr = cc_run(["--version"])
    version_line = next(
        (ln for ln in (stdout + stderr).splitlines() if "cloudcompare" in ln.lower()),
        stdout.strip() or stderr.strip() or "version unknown",
    )
    return _ok({"binary": binary, "platform": platform.system(), "version": version_line, "ready": True})


def handle_load_cloud_info(args: dict) -> list[TextContent]:
    fp = args["file_path"]
    if not Path(fp).exists():
        return _err(f"File not found: {fp}")
    with tempfile.TemporaryDirectory() as tmp:
        rc, stdout, stderr = cc_run(["-O", fp, "-SAVE_CLOUDS", "FILE", str(Path(tmp) / "info.txt")])
    return _run_result(rc, stdout, stderr, {"file": fp, "size_bytes": Path(fp).stat().st_size})


def handle_subsample(args: dict) -> list[TextContent]:
    method = args.get("method", "SPATIAL").upper()
    param = args["parameter"]
    _ensure_output_dir(args["output_path"])
    ss_args = (
        ["-SS", "RANDOM", str(int(param))] if method == "RANDOM" else
        ["-SS", "OCTREE", str(int(param))] if method == "OCTREE" else
        ["-SS", "SPATIAL", str(param)]
    )
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"], *ss_args,
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_c2c_distances(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    extra = ["-MAX_DIST", str(args["max_distance"])] if "max_distance" in args else []
    rc, stdout, stderr = cc_run([
        "-O", args["reference_path"], "-O", args["compared_path"],
        "-C2C_DIST", *extra,
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_c2m_distances(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["mesh_path"], "-O", args["cloud_path"], "-C2M_DIST",
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_icp(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["model_path"], "-O", args["data_path"],
        "-ICP",
        "-OVERLAP", str(args.get("overlap", 100)),
        "-ITER", str(args.get("iterations", 20)),
        "-RANDOM_SAMPLING_LIMIT", str(args.get("random_sampling_limit", 50000)),
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_compute_normals(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    mode = args.get("mode", "LS").upper()
    extra = (["-RADIUS", str(args["radius"])] if "radius" in args else
             ["-KNN", str(args["knn"])] if "knn" in args else [])
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        "-COMPUTE_NORMALS", mode, *extra,
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_filter_sf(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        "-FILTER_SF", str(args["min_val"]), str(args["max_val"]),
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_sor(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        "-SOR", str(args.get("knn", 6)), str(args.get("n_sigma", 1.0)),
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_merge(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    open_args: list[str] = []
    for p in args["input_paths"]:
        open_args += ["-O", p]
    rc, stdout, stderr = cc_run([
        *open_args, "-MERGE_CLOUDS",
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_convert(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"input": args["input_path"], "output": args["output_path"]})


def handle_raw_command(args: dict) -> list[TextContent]:
    try:
        rc, stdout, stderr = cc_run(args["args"], cwd=args.get("working_directory"))
    except FileNotFoundError as exc:
        return _err(str(exc))
    return _run_result(rc, stdout, stderr)


# ── Format helper ─────────────────────────────────────────────────────────────

_EXT_TO_CC: dict[str, str] = {
    ".las": "LAS", ".laz": "LAS", ".ply": "PLY", ".pcd": "PCD",
    ".xyz": "ASC", ".asc": "ASC", ".txt": "ASC",
    ".e57": "E57", ".obj": "OBJ", ".bin": "BIN",
}


def _ext_flag(path: str) -> str:
    return _EXT_TO_CC.get(Path(path).suffix.lower(), "PLY")


# ── MCP event handlers ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    dispatch = {
        "get_live_cloudcompare_info": handle_get_live_cloudcompare_info,
        "list_live_entities": handle_list_live_entities,
        "get_live_selection": handle_get_live_selection,
        "set_live_selection": handle_set_live_selection,
        "load_file_live": handle_load_file_live,
        "rename_live_entity": handle_rename_live_entity,
        "set_live_entity_state": handle_set_live_entity_state,
        "delete_live_entities": handle_delete_live_entities,
        "transform_live_entity": handle_transform_live_entity,
        "set_live_view": handle_set_live_view,
        "capture_live_view": handle_capture_live_view,
        "get_live_workflow_capabilities": handle_get_live_workflow_capabilities,
        "clone_live_entities": handle_clone_live_entities,
        "merge_live_clouds": handle_merge_live_clouds,
        "reconstruct_live_mesh": handle_reconstruct_live_mesh,
        "simplify_live_mesh": handle_simplify_live_mesh,
        "export_live_entity": handle_export_live_entity,
        "get_cloudcompare_info": handle_get_cloudcompare_info,
        "read_cloud_metadata": handle_read_metadata,
        "visualize_cloud": handle_visualize,
        "load_cloud_info": handle_load_cloud_info,
        "subsample": handle_subsample,
        "compute_cloud_to_cloud_distances": handle_c2c_distances,
        "compute_cloud_to_mesh_distances": handle_c2m_distances,
        "icp_registration": handle_icp,
        "compute_normals": handle_compute_normals,
        "filter_by_scalar_field": handle_filter_sf,
        "statistical_outlier_removal": handle_sor,
        "merge_clouds": handle_merge,
        "convert_format": handle_convert,
        "run_cloudcompare_command": handle_raw_command,
    }
    try:
        handler = dispatch.get(name)
        if handler is None:
            return _err(f"Unknown tool: {name}")
        return handler(arguments)
    except FileNotFoundError as exc:
        return _err(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _err(f"Unexpected error in '{name}': {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import asyncio
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
