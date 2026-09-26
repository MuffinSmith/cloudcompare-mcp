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
from mcp.types import CallToolResult, ImageContent, TextContent, Tool

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
        name="create_live_group",
        description=(
            "Create an empty group in the open CloudCompare DB tree for organizing MCP working results. "
            "The operation does not move or modify existing entities."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="crop_live_cloud",
        description=(
            "Create a new point cloud cropped by an axis-aligned box while preserving the source cloud. "
            "Bounds can be expressed in the cloud's native local coordinates or CloudCompare global coordinates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cloud_id": {"type": "integer"},
                "min": {
                    "type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                    "description": "Minimum X/Y/Z corner of the crop box.",
                },
                "max": {
                    "type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                    "description": "Maximum X/Y/Z corner of the crop box.",
                },
                "coordinate_space": {
                    "type": "string",
                    "enum": ["native_local", "global"],
                    "default": "native_local",
                },
                "keep_inside": {"type": "boolean", "default": True},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["cloud_id", "min", "max"],
        },
    ),
    Tool(
        name="subsample_live_cloud",
        description=(
            "Create a new subsampled point cloud from a live source without changing the source. "
            "Supports exact-count random sampling, minimum-spacing spatial sampling, and octree-level sampling."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cloud_id": {"type": "integer"},
                "method": {
                    "type": "string",
                    "enum": ["random", "spatial", "octree"],
                },
                "target_points": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Required for method=random; exact number of points to retain.",
                },
                "min_spacing": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Required for method=spatial; minimum spacing in native coordinate units.",
                },
                "octree_level": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 21,
                    "description": "Required for method=octree.",
                },
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["cloud_id", "method"],
        },
    ),
    Tool(
        name="filter_live_cloud_sor",
        description=(
            "Create a Statistical Outlier Removal filtered point cloud from a live source. "
            "The original cloud is preserved and the result is a separate entity."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cloud_id": {"type": "integer"},
                "knn": {"type": "integer", "minimum": 2, "default": 6},
                "n_sigma": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["cloud_id"],
        },
    ),
    Tool(
        name="compute_live_normals",
        description=(
            "Create a working copy of a live point cloud and compute normals on that copy. "
            "Optionally orient the computed normals with a minimum-spanning-tree pass. "
            "The source cloud is never modified."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cloud_id": {"type": "integer"},
                "radius": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Neighborhood radius in native coordinate units.",
                },
                "model": {
                    "type": "string",
                    "enum": ["LS", "QUADRIC", "TRIANGULATION"],
                    "default": "LS",
                },
                "orient_with_mst": {"type": "boolean", "default": False},
                "mst_neighbors": {"type": "integer", "minimum": 2, "maximum": 1000, "default": 6},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["cloud_id", "radius"],
        },
    ),
    Tool(
        name="register_live_icp",
        description=(
            "Estimate a rigid point-cloud-to-point-cloud ICP transform inside the already-open CloudCompare scene. "
            "Sources are never modified. By default this is preview-only and returns the transform/RMS without "
            "adding geometry; set preview_only=false to create a transformed clone of the data cloud."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "data_id": {
                    "type": "integer",
                    "description": "Standalone point cloud to align/move.",
                },
                "model_id": {
                    "type": "integer",
                    "description": "Standalone reference point cloud that remains fixed.",
                },
                "overlap_percent": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 100,
                    "description": "Estimated final overlap percentage.",
                },
                "max_iterations": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": 20,
                },
                "random_sampling_limit": {
                    "type": "integer",
                    "minimum": 3,
                    "default": 50000,
                },
                "filter_out_farthest_points": {"type": "boolean", "default": False},
                "preview_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, return the estimated transform without adding an aligned clone.",
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the aligned result when preview_only=false.",
                },
                "destination_group_id": {
                    "type": "integer",
                    "description": "Optional parent working group for the aligned result.",
                },
            },
            "required": ["data_id", "model_id"],
        },
    ),
    Tool(
        name="register_live_point_pairs",
        description=(
            "Compute a rigid coarse alignment from at least three explicit corresponding point pairs. "
            "Sources are preserved. Preview mode returns the transform/residuals without adding geometry; "
            "applied mode creates a transformed clone of the data cloud for subsequent ICP refinement."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "data_id": {"type": "integer"},
                "model_id": {"type": "integer"},
                "data_points": {
                    "type": "array",
                    "minItems": 3,
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
                "model_points": {
                    "type": "array",
                    "minItems": 3,
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
                "coordinate_space": {
                    "type": "string",
                    "enum": ["global", "native_local"],
                    "default": "global",
                    "description": (
                        "global: both point lists contain CloudCompare global coordinates. "
                        "native_local: each list is expressed in its own source entity's local coordinates."
                    ),
                },
                "preview_only": {"type": "boolean", "default": True},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["data_id", "model_id", "data_points", "model_points"],
        },
    ),
    Tool(
        name="analyze_live_c2c",
        description=(
            "Compute nearest-neighbor cloud-to-cloud distances on a temporary clone of the compared cloud. "
            "Returns distribution statistics and a histogram without changing either source. "
            "Optionally add a separate result cloud with a displayed distance scalar field."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "compared_id": {"type": "integer"},
                "reference_id": {"type": "integer"},
                "max_distance": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Maximum search distance in native coordinate units; 0 means unlimited.",
                },
                "create_result": {"type": "boolean", "default": False},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["compared_id", "reference_id"],
        },
    ),
    Tool(
        name="analyze_live_c2m",
        description=(
            "Compute cloud-to-mesh distances on a temporary clone of the compared point cloud. "
            "Returns distance statistics/histogram and supports signed distances. Sources are preserved. "
            "Optionally add a separate scalar-field result cloud for visual inspection."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "compared_id": {"type": "integer"},
                "reference_mesh_id": {"type": "integer"},
                "max_distance": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Maximum search distance in native coordinate units; 0 means unlimited.",
                },
                "signed_distances": {"type": "boolean", "default": False},
                "flip_normals": {"type": "boolean", "default": False},
                "robust": {"type": "boolean", "default": True},
                "create_result": {"type": "boolean", "default": False},
                "name": {"type": "string"},
                "destination_group_id": {"type": "integer"},
            },
            "required": ["compared_id", "reference_mesh_id"],
        },
    ),
    Tool(
        name="start_live_picking",
        description=(
            "Start an interactive CloudCompare point/triangle picking session in the active 3D viewport. "
            "The caller or GUI operator can then click visible geometry; use get_live_picks to retrieve exact "
            "picked coordinates and attributes. The session can optionally ignore entities outside an allowlist."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "max_picks": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 8,
                    "description": "Automatically stop picking after this many accepted picks.",
                },
                "allowed_entity_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional entity allowlist; clicks on other entities are ignored.",
                },
                "exclusive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Request exclusive use of CloudCompare's picking hub.",
                },
            },
        },
    ),
    Tool(
        name="get_live_picks",
        description=(
            "Return the current interactive metrology picking-session state and all captured picks, "
            "including entity/item IDs, native-local and global coordinates, and point attributes when available."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="clear_live_picks",
        description="Clear captured picks while leaving an active picking session running.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="stop_live_picking",
        description="Stop interactive picking and return the picks captured so far.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="inspect_live_point",
        description=(
            "Inspect one exact point of a standalone live point cloud by zero-based point index. "
            "Returns native-local/global coordinates plus RGB, normal, and scalar-field values when present."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "integer"},
                "point_index": {"type": "integer", "minimum": 0},
            },
            "required": ["entity_id", "point_index"],
        },
    ),
    Tool(
        name="measure_live_picked_distance",
        description=(
            "Measure Euclidean distance and XYZ deltas between two captured interactive picks in CloudCompare "
            "global coordinates. Defaults to the two most recent picks."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_a": {"type": "integer", "minimum": 0},
                "pick_b": {"type": "integer", "minimum": 0},
            },
        },
    ),
    Tool(
        name="measure_live_picked_angle",
        description=(
            "Measure the A-B-C angle from three captured interactive picks, with B as the vertex. "
            "Defaults to the three most recent picks."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_a": {"type": "integer", "minimum": 0},
                "pick_b": {"type": "integer", "minimum": 0},
                "pick_c": {"type": "integer", "minimum": 0},
            },
        },
    ),
    Tool(
        name="fit_live_plane",
        description=(
            "Fit an orthogonal least-squares plane to captured CloudCompare metrology picks. "
            "Uses global coordinates, preserves all source geometry, and reports the plane equation, "
            "basis, residual statistics, planarity diagnostics, and sampled extents."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                    "description": "Optional captured-pick indexes. Omit to use every currently captured pick.",
                },
            },
        },
    ),
    Tool(
        name="fit_live_circle",
        description=(
            "Fit a 3D circle to captured CloudCompare metrology picks by best-fit-plane projection "
            "and geometric least-squares circle refinement. Reports center, normal, diameter, "
            "arc coverage and radial/planar residual diagnostics without modifying the scene."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 4,
                    "description": "Optional captured-pick indexes. Omit to use every currently captured pick.",
                },
            },
        },
    ),
    Tool(
        name="measure_live_pick_to_plane",
        description=(
            "Fit a plane from selected captured picks and measure another captured pick to that plane "
            "in CloudCompare global/native coordinates. Returns signed and absolute distance plus projection."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "point_pick": {"type": "integer", "minimum": 0},
                "plane_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
            },
            "required": ["point_pick", "plane_pick_indices"],
        },
    ),
    Tool(
        name="compare_live_picked_planes",
        description=(
            "Fit two planes from two captured-pick sets and compare their acute angle, centroid offset, "
            "and normal-direction separation. Sources remain untouched."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "plane_a_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
                "plane_b_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
            },
            "required": ["plane_a_pick_indices", "plane_b_pick_indices"],
        },
    ),
    Tool(
        name="fit_live_line",
        description=(
            "Fit an orthogonal least-squares 3D line to captured CloudCompare metrology picks. "
            "Returns centroid, deterministic direction, span endpoints, linearity and residual diagnostics "
            "without modifying the scene."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 2,
                    "description": "Optional captured-pick indexes. Omit to use every currently captured pick.",
                },
            },
        },
    ),
    Tool(
        name="fit_live_cylinder",
        description=(
            "Fit a circular-cylinder axis and diameter to captured 3D surface picks. "
            "Uses deterministic multi-start axis search with geometric radial least squares and reports "
            "radial residuals, angular coverage and axial span. Sources remain untouched."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 6,
                    "description": "Optional captured-pick indexes. Omit to use every currently captured pick.",
                },
            },
        },
    ),
    Tool(
        name="compare_live_picked_lines",
        description=(
            "Fit two 3D lines from captured-pick sets and compare their acute angle, "
            "shortest infinite-line distance and closest points."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "line_a_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 2,
                },
                "line_b_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 2,
                },
            },
            "required": ["line_a_pick_indices", "line_b_pick_indices"],
        },
    ),
    Tool(
        name="compare_live_line_to_plane",
        description=(
            "Fit a line/axis and a plane from captured picks and report their angle, "
            "axis-point distance and intersection when one exists."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "line_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 2,
                },
                "plane_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
            },
            "required": ["line_pick_indices", "plane_pick_indices"],
        },
    ),
    Tool(
        name="compare_live_cylinders",
        description=(
            "Fit two cylinders from captured surface-pick sets and compare their infinite axes, "
            "including acute angle, shortest axis distance, closest axis points, and radius/diameter differences."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cylinder_a_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 6,
                },
                "cylinder_b_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 6,
                },
            },
            "required": ["cylinder_a_pick_indices", "cylinder_b_pick_indices"],
        },
    ),
    Tool(
        name="compare_live_cylinder_to_plane",
        description=(
            "Fit a cylinder axis and a plane from captured picks and report axis-to-plane angle, "
            "representative-axis-point distance, and intersection when one exists."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cylinder_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 6,
                },
                "plane_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
            },
            "required": ["cylinder_pick_indices", "plane_pick_indices"],
        },
    ),
    Tool(
        name="project_live_picks_to_section",
        description=(
            "Fit a section plane from captured picks and project another captured-pick set into a stable "
            "2D U/V section frame. Optionally filter profile picks by half-thickness around the fitted plane. "
            "This is a picked-profile tool; full-cloud arbitrary slab extraction is not yet implemented."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "section_plane_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 3,
                },
                "profile_pick_indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 1,
                    "description": "Captured picks to project. If omitted, all captured picks are used.",
                },
                "half_thickness": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Optional maximum absolute offset from the section plane in native/global coordinate units.",
                },
            },
            "required": ["section_plane_pick_indices"],
        },
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


def _err(msg: str) -> CallToolResult:
    """Return a model-readable MCP tool failure, not successful error text."""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps({"error": msg}, indent=2),
            )
        ],
        isError=True,
    )


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
) -> list[TextContent] | CallToolResult:
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
        from .feature_fit import feature_fit_capabilities
        native["python_feature_fitting"] = feature_fit_capabilities()
        return _ok(native)
    except (LiveBridgeError, Exception) as exc:
        return _err(str(exc))


def handle_create_live_group(args: dict) -> list[TextContent]:
    params = {"name": args["name"]}
    if "destination_group_id" in args:
        params["destination_group_id"] = args["destination_group_id"]
    return _live_call("group.create", params)


def handle_crop_live_cloud(args: dict) -> list[TextContent]:
    params = {
        "cloud_id": args["cloud_id"],
        "min": args["min"],
        "max": args["max"],
        "coordinate_space": args.get("coordinate_space", "native_local"),
        "keep_inside": bool(args.get("keep_inside", True)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.crop", params, timeout=300.0)


def handle_subsample_live_cloud(args: dict) -> list[TextContent]:
    params = {
        "cloud_id": args["cloud_id"],
        "method": args["method"],
    }
    for key in ("target_points", "min_spacing", "octree_level", "name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.subsample", params, timeout=600.0)


def handle_filter_live_cloud_sor(args: dict) -> list[TextContent]:
    params = {
        "cloud_id": args["cloud_id"],
        "knn": int(args.get("knn", 6)),
        "n_sigma": float(args.get("n_sigma", 1.0)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.filter_sor", params, timeout=600.0)


def handle_compute_live_normals(args: dict) -> list[TextContent]:
    params = {
        "cloud_id": args["cloud_id"],
        "radius": args["radius"],
        "model": args.get("model", "LS"),
        "orient_with_mst": bool(args.get("orient_with_mst", False)),
        "mst_neighbors": int(args.get("mst_neighbors", 6)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.compute_normals", params, timeout=900.0)


def handle_register_live_icp(args: dict) -> list[TextContent]:
    params = {
        "data_id": args["data_id"],
        "model_id": args["model_id"],
        "overlap_percent": float(args.get("overlap_percent", 100.0)),
        "max_iterations": int(args.get("max_iterations", 20)),
        "random_sampling_limit": int(args.get("random_sampling_limit", 50000)),
        "filter_out_farthest_points": bool(args.get("filter_out_farthest_points", False)),
        "preview_only": bool(args.get("preview_only", True)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.register_icp", params, timeout=900.0)


def handle_register_live_point_pairs(args: dict) -> list[TextContent]:
    params = {
        "data_id": args["data_id"],
        "model_id": args["model_id"],
        "data_points": args["data_points"],
        "model_points": args["model_points"],
        "coordinate_space": args.get("coordinate_space", "global"),
        "preview_only": bool(args.get("preview_only", True)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.register_point_pairs", params, timeout=300.0)


def handle_analyze_live_c2c(args: dict) -> list[TextContent]:
    params = {
        "compared_id": args["compared_id"],
        "reference_id": args["reference_id"],
        "max_distance": float(args.get("max_distance", 0.0)),
        "create_result": bool(args.get("create_result", False)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.distance_c2c", params, timeout=900.0)


def handle_analyze_live_c2m(args: dict) -> list[TextContent]:
    params = {
        "compared_id": args["compared_id"],
        "reference_mesh_id": args["reference_mesh_id"],
        "max_distance": float(args.get("max_distance", 0.0)),
        "signed_distances": bool(args.get("signed_distances", False)),
        "flip_normals": bool(args.get("flip_normals", False)),
        "robust": bool(args.get("robust", True)),
        "create_result": bool(args.get("create_result", False)),
    }
    for key in ("name", "destination_group_id"):
        if key in args:
            params[key] = args[key]
    return _live_call("cloud.distance_c2m", params, timeout=900.0)


def handle_start_live_picking(args: dict) -> list[TextContent]:
    params = {
        "max_picks": int(args.get("max_picks", 8)),
        "exclusive": bool(args.get("exclusive", True)),
    }
    if "allowed_entity_ids" in args:
        params["allowed_entity_ids"] = args["allowed_entity_ids"]
    return _live_call("metrology.pick.start", params)


def handle_get_live_picks(_args: dict) -> list[TextContent]:
    return _live_call("metrology.pick.status", {})


def handle_clear_live_picks(_args: dict) -> list[TextContent]:
    return _live_call("metrology.pick.clear", {})


def handle_stop_live_picking(_args: dict) -> list[TextContent]:
    return _live_call("metrology.pick.stop", {})


def handle_inspect_live_point(args: dict) -> list[TextContent]:
    return _live_call(
        "metrology.point_info",
        {
            "entity_id": args["entity_id"],
            "point_index": args["point_index"],
        },
    )


def handle_measure_live_picked_distance(args: dict) -> list[TextContent]:
    params = {}
    for key in ("pick_a", "pick_b"):
        if key in args:
            params[key] = args[key]
    return _live_call("metrology.measure.picked_distance", params)


def handle_measure_live_picked_angle(args: dict) -> list[TextContent]:
    params = {}
    for key in ("pick_a", "pick_b", "pick_c"):
        if key in args:
            params[key] = args[key]
    return _live_call("metrology.measure.picked_angle", params)


def _selected_live_pick_points(
    pick_indices: list[int] | None,
    *,
    minimum: int,
) -> tuple[list[list[float]], list[int], list[dict]]:
    from .feature_fit import FeatureFitError

    status = live_request("metrology.pick.status", {})
    if not isinstance(status, dict) or not isinstance(status.get("picks"), list):
        raise FeatureFitError("CloudCompare returned an invalid metrology picking-session response")

    picks = status["picks"]
    if pick_indices is None:
        indexes = list(range(len(picks)))
    else:
        indexes = list(pick_indices)

    if len(indexes) < minimum:
        raise FeatureFitError(f"At least {minimum} captured picks are required")
    if len(set(indexes)) != len(indexes):
        raise FeatureFitError("Pick-index lists must not contain duplicate indexes")

    positions: list[list[float]] = []
    selected: list[dict] = []
    for index in indexes:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(picks):
            raise FeatureFitError(
                f"Captured pick index {index!r} is outside the available range 0..{max(len(picks) - 1, 0)}"
            )
        pick = picks[index]
        if not isinstance(pick, dict):
            raise FeatureFitError(f"Captured pick {index} is malformed")
        position = pick.get("position_global")
        if not isinstance(position, list) or len(position) != 3:
            raise FeatureFitError(f"Captured pick {index} has no valid global 3D position")
        try:
            xyz = [float(component) for component in position]
        except (TypeError, ValueError) as exc:
            raise FeatureFitError(
                f"Captured pick {index} has non-numeric global coordinates"
            ) from exc

        positions.append(xyz)
        pick_copy = dict(pick)
        pick_copy["pick_index"] = index
        selected.append(pick_copy)

    return positions, indexes, selected


def _decorate_feature_fit(
    fit: dict,
    *,
    indexes: list[int],
    selected: list[dict],
) -> dict:
    out = dict(fit)
    out["coordinate_space"] = "global"
    out["units"] = "native"
    out["units_confirmed"] = False
    out["pick_indices"] = indexes
    out["source_picks"] = selected
    out["source_geometry_preserved"] = True
    return out


def handle_fit_live_plane(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_plane

    try:
        points, indexes, selected = _selected_live_pick_points(
            args.get("pick_indices"),
            minimum=3,
        )
        return _ok(
            _decorate_feature_fit(
                fit_plane(points),
                indexes=indexes,
                selected=selected,
            )
        )
    except (FeatureFitError, LiveBridgeError) as exc:
        return _err(str(exc))


def handle_fit_live_circle(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_circle_3d

    try:
        points, indexes, selected = _selected_live_pick_points(
            args.get("pick_indices"),
            minimum=4,
        )
        return _ok(
            _decorate_feature_fit(
                fit_circle_3d(points),
                indexes=indexes,
                selected=selected,
            )
        )
    except (FeatureFitError, LiveBridgeError) as exc:
        return _err(str(exc))


def handle_measure_live_pick_to_plane(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_plane, point_to_plane

    try:
        plane_points, plane_indexes, plane_picks = _selected_live_pick_points(
            args["plane_pick_indices"],
            minimum=3,
        )
        point_points, point_indexes, point_picks = _selected_live_pick_points(
            [args["point_pick"]],
            minimum=1,
        )
        plane = fit_plane(plane_points)
        measurement = point_to_plane(point_points[0], plane)
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "point_pick": point_indexes[0],
                "point_source": point_picks[0],
                "plane_pick_indices": plane_indexes,
                "plane_source_picks": plane_picks,
                "plane_fit": plane,
                "measurement": measurement,
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_compare_live_picked_planes(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_plane, plane_relationship

    try:
        points_a, indexes_a, picks_a = _selected_live_pick_points(
            args["plane_a_pick_indices"],
            minimum=3,
        )
        points_b, indexes_b, picks_b = _selected_live_pick_points(
            args["plane_b_pick_indices"],
            minimum=3,
        )
        plane_a = fit_plane(points_a)
        plane_b = fit_plane(points_b)
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "plane_a_pick_indices": indexes_a,
                "plane_b_pick_indices": indexes_b,
                "plane_a_source_picks": picks_a,
                "plane_b_source_picks": picks_b,
                "plane_a": plane_a,
                "plane_b": plane_b,
                "relationship": plane_relationship(plane_a, plane_b),
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_fit_live_line(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_line_3d

    try:
        points, indexes, selected = _selected_live_pick_points(
            args.get("pick_indices"),
            minimum=2,
        )
        return _ok(
            _decorate_feature_fit(
                fit_line_3d(points),
                indexes=indexes,
                selected=selected,
            )
        )
    except (FeatureFitError, LiveBridgeError) as exc:
        return _err(str(exc))


def handle_fit_live_cylinder(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_cylinder_3d

    try:
        points, indexes, selected = _selected_live_pick_points(
            args.get("pick_indices"),
            minimum=6,
        )
        return _ok(
            _decorate_feature_fit(
                fit_cylinder_3d(points),
                indexes=indexes,
                selected=selected,
            )
        )
    except (FeatureFitError, LiveBridgeError) as exc:
        return _err(str(exc))


def handle_compare_live_picked_lines(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_line_3d, line_relationship

    try:
        points_a, indexes_a, picks_a = _selected_live_pick_points(
            args["line_a_pick_indices"],
            minimum=2,
        )
        points_b, indexes_b, picks_b = _selected_live_pick_points(
            args["line_b_pick_indices"],
            minimum=2,
        )
        line_a = fit_line_3d(points_a)
        line_b = fit_line_3d(points_b)
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "line_a_pick_indices": indexes_a,
                "line_b_pick_indices": indexes_b,
                "line_a_source_picks": picks_a,
                "line_b_source_picks": picks_b,
                "line_a": line_a,
                "line_b": line_b,
                "relationship": line_relationship(line_a, line_b),
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_compare_live_line_to_plane(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_line_3d, fit_plane, line_plane_relationship

    try:
        line_points, line_indexes, line_picks = _selected_live_pick_points(
            args["line_pick_indices"],
            minimum=2,
        )
        plane_points, plane_indexes, plane_picks = _selected_live_pick_points(
            args["plane_pick_indices"],
            minimum=3,
        )
        line = fit_line_3d(line_points)
        plane = fit_plane(plane_points)
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "line_pick_indices": line_indexes,
                "plane_pick_indices": plane_indexes,
                "line_source_picks": line_picks,
                "plane_source_picks": plane_picks,
                "line_fit": line,
                "plane_fit": plane,
                "relationship": line_plane_relationship(line, plane),
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_compare_live_cylinders(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_cylinder_3d, line_relationship

    try:
        points_a, indexes_a, picks_a = _selected_live_pick_points(
            args["cylinder_a_pick_indices"],
            minimum=6,
        )
        points_b, indexes_b, picks_b = _selected_live_pick_points(
            args["cylinder_b_pick_indices"],
            minimum=6,
        )
        cylinder_a = fit_cylinder_3d(points_a)
        cylinder_b = fit_cylinder_3d(points_b)
        relationship = line_relationship(cylinder_a, cylinder_b)
        relationship["radius_difference"] = (
            cylinder_b["radius"] - cylinder_a["radius"]
        )
        relationship["absolute_radius_difference"] = abs(
            relationship["radius_difference"]
        )
        relationship["diameter_difference"] = (
            cylinder_b["diameter"] - cylinder_a["diameter"]
        )
        relationship["absolute_diameter_difference"] = abs(
            relationship["diameter_difference"]
        )
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "cylinder_a_pick_indices": indexes_a,
                "cylinder_b_pick_indices": indexes_b,
                "cylinder_a_source_picks": picks_a,
                "cylinder_b_source_picks": picks_b,
                "cylinder_a": cylinder_a,
                "cylinder_b": cylinder_b,
                "relationship": relationship,
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_compare_live_cylinder_to_plane(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import (
        FeatureFitError,
        fit_cylinder_3d,
        fit_plane,
        line_plane_relationship,
    )

    try:
        cylinder_points, cylinder_indexes, cylinder_picks = _selected_live_pick_points(
            args["cylinder_pick_indices"],
            minimum=6,
        )
        plane_points, plane_indexes, plane_picks = _selected_live_pick_points(
            args["plane_pick_indices"],
            minimum=3,
        )
        cylinder = fit_cylinder_3d(cylinder_points)
        plane = fit_plane(plane_points)
        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "cylinder_pick_indices": cylinder_indexes,
                "plane_pick_indices": plane_indexes,
                "cylinder_source_picks": cylinder_picks,
                "plane_source_picks": plane_picks,
                "cylinder_fit": cylinder,
                "plane_fit": plane,
                "relationship": line_plane_relationship(cylinder, plane),
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
        return _err(str(exc))


def handle_project_live_picks_to_section(args: dict) -> list[TextContent] | CallToolResult:
    from .feature_fit import FeatureFitError, fit_plane, project_points_to_section

    try:
        plane_points, plane_indexes, plane_picks = _selected_live_pick_points(
            args["section_plane_pick_indices"],
            minimum=3,
        )
        profile_points, profile_indexes, profile_picks = _selected_live_pick_points(
            args.get("profile_pick_indices"),
            minimum=1,
        )
        plane = fit_plane(plane_points)
        projection = project_points_to_section(
            profile_points,
            plane["centroid"],
            plane["normal"],
            half_thickness=args.get("half_thickness"),
        )

        selected_profile_indexes = [
            profile_indexes[index]
            for index in projection["source_indices"]
        ]
        selected_profile_picks = [
            profile_picks[index]
            for index in projection["source_indices"]
        ]

        return _ok(
            {
                "coordinate_space": "global",
                "units": "native",
                "units_confirmed": False,
                "source_geometry_preserved": True,
                "section_plane_pick_indices": plane_indexes,
                "section_plane_source_picks": plane_picks,
                "profile_pick_indices": profile_indexes,
                "selected_profile_pick_indices": selected_profile_indexes,
                "selected_profile_source_picks": selected_profile_picks,
                "section_plane": plane,
                "projection": projection,
                "full_cloud_slab_extraction": False,
            }
        )
    except (FeatureFitError, LiveBridgeError, KeyError, TypeError, ValueError) as exc:
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
                destination_group_id=args.get("destination_group_id"),
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
async def call_tool(
    name: str,
    arguments: dict,
) -> list[TextContent | ImageContent] | CallToolResult:
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
        "create_live_group": handle_create_live_group,
        "crop_live_cloud": handle_crop_live_cloud,
        "subsample_live_cloud": handle_subsample_live_cloud,
        "filter_live_cloud_sor": handle_filter_live_cloud_sor,
        "compute_live_normals": handle_compute_live_normals,
        "register_live_icp": handle_register_live_icp,
        "register_live_point_pairs": handle_register_live_point_pairs,
        "analyze_live_c2c": handle_analyze_live_c2c,
        "analyze_live_c2m": handle_analyze_live_c2m,
        "start_live_picking": handle_start_live_picking,
        "get_live_picks": handle_get_live_picks,
        "clear_live_picks": handle_clear_live_picks,
        "stop_live_picking": handle_stop_live_picking,
        "inspect_live_point": handle_inspect_live_point,
        "measure_live_picked_distance": handle_measure_live_picked_distance,
        "measure_live_picked_angle": handle_measure_live_picked_angle,
        "fit_live_plane": handle_fit_live_plane,
        "fit_live_circle": handle_fit_live_circle,
        "measure_live_pick_to_plane": handle_measure_live_pick_to_plane,
        "compare_live_picked_planes": handle_compare_live_picked_planes,
        "fit_live_line": handle_fit_live_line,
        "fit_live_cylinder": handle_fit_live_cylinder,
        "compare_live_picked_lines": handle_compare_live_picked_lines,
        "compare_live_line_to_plane": handle_compare_live_line_to_plane,
        "compare_live_cylinders": handle_compare_live_cylinders,
        "compare_live_cylinder_to_plane": handle_compare_live_cylinder_to_plane,
        "project_live_picks_to_section": handle_project_live_picks_to_section,
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

def _prepare_native_backends_for_stdio() -> None:
    """Initialize NumPy before Windows MCP stdio/async worker threads are active.

    PyMeshLab imports NumPy as part of its native-module initialization. On the
    tested Windows setup, first importing NumPy after the MCP stdio transport was
    running could stall indefinitely. Importing it here reproduces the known-good
    launcher behavior while keeping PyMeshLab itself optional and lazily loaded.
    """
    if platform.system() != "Windows":
        return
    try:
        import numpy  # noqa: F401
    except Exception:
        # Capability discovery remains usable even if an optional/native backend
        # is broken; geometry handlers will report the concrete import error.
        pass


def main() -> None:
    _prepare_native_backends_for_stdio()
    import asyncio
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
