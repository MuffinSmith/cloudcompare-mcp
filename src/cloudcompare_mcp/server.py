"""CloudCompare MCP Server — wraps CloudCompare CLI for AI-assisted point cloud processing."""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

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
    """Return the CloudCompare executable path, or None if not found."""
    # Env override always wins
    if env := os.environ.get("CLOUDCOMPARE_PATH"):
        return env if Path(env).is_file() else None

    # PATH lookup (works on all platforms)
    if found := shutil.which("cloudcompare") or shutil.which("CloudCompare"):
        return found

    for candidate in _CC_CANDIDATES.get(platform.system(), []):
        if Path(candidate).is_file():
            return candidate

    return None


def cc_run(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run CloudCompare with *args*; return (returncode, stdout, stderr)."""
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


# ── Server setup ─────────────────────────────────────────────────────────────

server = Server("cloudcompare-mcp")

# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="get_cloudcompare_info",
        description=(
            "Check if CloudCompare is installed and return its version and path. "
            "Call this first to confirm the tool is available."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="load_cloud_info",
        description=(
            "Load a point cloud or mesh file and return basic statistics: "
            "number of points, bounding box, available scalar fields, etc. "
            "Supports LAS/LAZ, PLY, PCD, E57, XYZ, ASC, BIN, SHP, OBJ, and more."
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
            "Output is saved to the specified path."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Absolute path to the input point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the output file.",
                },
                "method": {
                    "type": "string",
                    "enum": ["RANDOM", "SPATIAL", "OCTREE"],
                    "description": "Subsampling method.",
                    "default": "SPATIAL",
                },
                "parameter": {
                    "type": "number",
                    "description": (
                        "RANDOM: number of points to keep (int). "
                        "SPATIAL: minimum spacing between points (metres). "
                        "OCTREE: octree subdivision level (1–21)."
                    ),
                },
            },
            "required": ["input_path", "output_path", "parameter"],
        },
    ),
    Tool(
        name="compute_cloud_to_cloud_distances",
        description=(
            "Compute nearest-neighbour distances from every point in the 'compared' cloud "
            "to the 'reference' cloud (C2C distance). "
            "Returns distance statistics and saves the labelled cloud."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "reference_path": {
                    "type": "string",
                    "description": "Absolute path to the reference point cloud.",
                },
                "compared_path": {
                    "type": "string",
                    "description": "Absolute path to the compared point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the compared cloud with distance scalar field.",
                },
                "max_distance": {
                    "type": "number",
                    "description": "Maximum search distance (optional, in metres).",
                },
            },
            "required": ["reference_path", "compared_path", "output_path"],
        },
    ),
    Tool(
        name="compute_cloud_to_mesh_distances",
        description=(
            "Compute signed distances from a point cloud to a reference mesh (C2M distance). "
            "Useful for comparing a scan to a CAD model."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "mesh_path": {
                    "type": "string",
                    "description": "Absolute path to the reference mesh (OBJ, PLY, etc.).",
                },
                "cloud_path": {
                    "type": "string",
                    "description": "Absolute path to the compared point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the labelled output cloud.",
                },
            },
            "required": ["mesh_path", "cloud_path", "output_path"],
        },
    ),
    Tool(
        name="icp_registration",
        description=(
            "Register a 'data' cloud onto a 'model' cloud using the Iterative Closest Point (ICP) algorithm. "
            "Returns the transformation matrix and final RMS error."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_path": {
                    "type": "string",
                    "description": "Absolute path to the fixed reference cloud.",
                },
                "data_path": {
                    "type": "string",
                    "description": "Absolute path to the cloud to be aligned.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the aligned cloud.",
                },
                "overlap": {
                    "type": "number",
                    "description": "Expected overlap percentage between clouds (10–100). Default 100.",
                    "default": 100,
                },
                "iterations": {
                    "type": "integer",
                    "description": "Maximum ICP iterations. Default 20.",
                    "default": 20,
                },
                "random_sampling_limit": {
                    "type": "integer",
                    "description": "Number of points used during ICP (speeds up large clouds). Default 50000.",
                    "default": 50000,
                },
            },
            "required": ["model_path", "data_path", "output_path"],
        },
    ),
    Tool(
        name="compute_normals",
        description=(
            "Estimate surface normals for a point cloud using a local neighbourhood. "
            "Normals are required for many downstream operations (Poisson reconstruction, etc.)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Absolute path to the input point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the cloud with normals.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["LS", "QUADRIC", "TRIANGULATION"],
                    "description": "Normal estimation mode. LS=Least Squares (default).",
                    "default": "LS",
                },
                "radius": {
                    "type": "number",
                    "description": "Neighbourhood radius in metres. Mutually exclusive with knn.",
                },
                "knn": {
                    "type": "integer",
                    "description": "K nearest neighbours. Mutually exclusive with radius.",
                },
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="filter_by_scalar_field",
        description=(
            "Keep only points whose scalar-field value falls within [min_val, max_val]. "
            "Useful for height, intensity, or distance thresholding."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Absolute path to the input point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the filtered cloud.",
                },
                "min_val": {
                    "type": "number",
                    "description": "Minimum scalar field value to keep.",
                },
                "max_val": {
                    "type": "number",
                    "description": "Maximum scalar field value to keep.",
                },
            },
            "required": ["input_path", "output_path", "min_val", "max_val"],
        },
    ),
    Tool(
        name="statistical_outlier_removal",
        description=(
            "Remove statistical outliers by analysing the distance distribution to k nearest neighbours. "
            "Points farther than (mean + nSigma × std) from their neighbours are removed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Absolute path to the input point cloud.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the cleaned cloud.",
                },
                "knn": {
                    "type": "integer",
                    "description": "Number of nearest neighbours to consider. Default 6.",
                    "default": 6,
                },
                "n_sigma": {
                    "type": "number",
                    "description": "Sigma multiplier for outlier threshold. Default 1.0.",
                    "default": 1.0,
                },
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="merge_clouds",
        description="Merge two or more point cloud files into a single output file.",
        inputSchema={
            "type": "object",
            "properties": {
                "input_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of absolute paths to the input point clouds.",
                    "minItems": 2,
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the merged cloud.",
                },
            },
            "required": ["input_paths", "output_path"],
        },
    ),
    Tool(
        name="convert_format",
        description=(
            "Convert a point cloud or mesh file to a different format. "
            "CloudCompare infers the target format from the output file extension "
            "(e.g. .las, .laz, .ply, .pcd, .xyz, .asc, .e57, .obj)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "input_path": {
                    "type": "string",
                    "description": "Absolute path to the input file.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the output file (extension defines format).",
                },
            },
            "required": ["input_path", "output_path"],
        },
    ),
    Tool(
        name="run_cloudcompare_command",
        description=(
            "Run an arbitrary CloudCompare CLI command for advanced or unsupported operations. "
            "Do NOT include the executable path or -SILENT flag — they are added automatically. "
            "Example args: [\"-O\", \"/path/cloud.las\", \"-AUTO_SAVE\", \"OFF\"]"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CloudCompare CLI arguments (after the binary and -SILENT).",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Optional working directory for the command.",
                },
            },
            "required": ["args"],
        },
    ),
]


# ── Handler helpers ──────────────────────────────────────────────────────────

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


# ── Tool handlers ────────────────────────────────────────────────────────────

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
    return _ok({
        "binary": binary,
        "platform": platform.system(),
        "version": version_line,
        "ready": True,
    })


def handle_load_cloud_info(args: dict) -> list[TextContent]:
    fp = args["file_path"]
    if not Path(fp).exists():
        return _err(f"File not found: {fp}")

    with tempfile.TemporaryDirectory() as tmp:
        info_file = Path(tmp) / "info.txt"
        rc, stdout, stderr = cc_run([
            "-O", fp,
            "-SAVE_CLOUDS", "FILE", str(info_file),
        ])
    return _run_result(rc, stdout, stderr, {"file": fp, "size_bytes": Path(fp).stat().st_size})


def handle_subsample(args: dict) -> list[TextContent]:
    method = args.get("method", "SPATIAL").upper()
    param = args["parameter"]
    _ensure_output_dir(args["output_path"])

    if method == "RANDOM":
        ss_args = ["-SS", "RANDOM", str(int(param))]
    elif method == "OCTREE":
        ss_args = ["-SS", "OCTREE", str(int(param))]
    else:
        ss_args = ["-SS", "SPATIAL", str(param)]

    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        *ss_args,
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_c2c_distances(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    extra_args = []
    if "max_distance" in args:
        extra_args += ["-MAX_DIST", str(args["max_distance"])]

    rc, stdout, stderr = cc_run([
        "-O", args["reference_path"],
        "-O", args["compared_path"],
        "-C2C_DIST", *extra_args,
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_c2m_distances(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    rc, stdout, stderr = cc_run([
        "-O", args["mesh_path"],
        "-O", args["cloud_path"],
        "-C2M_DIST",
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_icp(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    overlap = args.get("overlap", 100)
    iterations = args.get("iterations", 20)
    rsl = args.get("random_sampling_limit", 50000)

    rc, stdout, stderr = cc_run([
        "-O", args["model_path"],
        "-O", args["data_path"],
        "-ICP",
        "-OVERLAP", str(overlap),
        "-ITER", str(iterations),
        "-RANDOM_SAMPLING_LIMIT", str(rsl),
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_compute_normals(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    mode = args.get("mode", "LS").upper()
    normal_args = ["-COMPUTE_NORMALS", mode]
    if "radius" in args:
        normal_args += ["-RADIUS", str(args["radius"])]
    elif "knn" in args:
        normal_args += ["-KNN", str(args["knn"])]

    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        *normal_args,
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
    knn = args.get("knn", 6)
    n_sigma = args.get("n_sigma", 1.0)
    rc, stdout, stderr = cc_run([
        "-O", args["input_path"],
        "-SOR", str(knn), str(n_sigma),
        "-C_EXPORT_FMT", _ext_flag(args["output_path"]),
        "-SAVE_CLOUDS", "FILE", args["output_path"],
    ])
    return _run_result(rc, stdout, stderr, {"output": args["output_path"]})


def handle_merge(args: dict) -> list[TextContent]:
    _ensure_output_dir(args["output_path"])
    open_args = []
    for p in args["input_paths"]:
        open_args += ["-O", p]

    rc, stdout, stderr = cc_run([
        *open_args,
        "-MERGE_CLOUDS",
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
    return _run_result(rc, stdout, stderr, {
        "input": args["input_path"],
        "output": args["output_path"],
    })


def handle_raw_command(args: dict) -> list[TextContent]:
    cwd = args.get("working_directory")
    try:
        rc, stdout, stderr = cc_run(args["args"], cwd=cwd)
    except FileNotFoundError as exc:
        return _err(str(exc))
    return _run_result(rc, stdout, stderr)


# ── Format helper ────────────────────────────────────────────────────────────

_EXT_TO_CC: dict[str, str] = {
    ".las": "LAS",
    ".laz": "LAS",
    ".ply": "PLY",
    ".pcd": "PCD",
    ".xyz": "ASC",
    ".asc": "ASC",
    ".txt": "ASC",
    ".e57": "E57",
    ".obj": "OBJ",
    ".bin": "BIN",
}


def _ext_flag(path: str) -> str:
    ext = Path(path).suffix.lower()
    return _EXT_TO_CC.get(ext, "PLY")


# ── MCP event handlers ───────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        dispatch = {
            "get_cloudcompare_info": handle_get_cloudcompare_info,
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
        handler = dispatch.get(name)
        if handler is None:
            return _err(f"Unknown tool: {name}")
        return handler(arguments)
    except FileNotFoundError as exc:
        return _err(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _err(f"Unexpected error: {exc}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    import asyncio
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
