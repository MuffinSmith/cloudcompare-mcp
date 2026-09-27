"""MCP contracts/adapters for Python-only, read-only hole candidate relationships."""
from __future__ import annotations

from copy import deepcopy
import json

from mcp.types import Tool, ToolAnnotations

from .feature_discovery import discover_circles
from .feature_fit import FeatureFitError
from .hole_patterns import analyze_hole_candidates, integer, number, settings, vector

VECTOR = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
ANALYSIS_PROPERTIES = {
    "face_origin": VECTOR, "face_normal": VECTOR,
    **{key: {"type": "number", "exclusiveMinimum": 0} for key in
       ("plane_tolerance", "diameter_tolerance", "center_tolerance", "spacing_tolerance")},
    "normal_tolerance_degrees": {"type": "number", "minimum": 0, "maximum": 90, "default": 10},
    "min_support_count": {"type": "integer", "minimum": 4, "maximum": 20000, "default": 12},
    "min_support_fraction": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.02},
    "min_coverage_degrees": {"type": "number", "minimum": 0, "maximum": 360, "default": 270},
    "max_fit_rms": {"type": "number", "exclusiveMinimum": 0},
}
REQUIRED_ANALYSIS = ["face_origin", "face_normal", "plane_tolerance", "diameter_tolerance",
                     "center_tolerance", "spacing_tolerance"]


def tools() -> list[Tool]:
    common_description = (
        "In global native units, filter circular candidates against a selected face, deduplicate, "
        "group by diameter and report center spacings and provisional row/bolt-circle layouts. "
        "Never certifies physical holes; read-only, no overlays or CAD changes. "
    )
    schemas = [
        ("analyze_hole_candidates", common_description +
         "Analyze a saved discover_live_circles result without connecting to CloudCompare. "
         "The caller must supply an unmodified global circle_discovery snapshot; freshness is not verified.",
         {"circle_discovery": {"type": "object", "description": "Complete discover_live_circles JSON result; coordinate_space must be global."}},
         ["circle_discovery"]),
        ("discover_live_hole_candidates", common_description +
         "Obtain one bounded region sample from the live host, discover circles and analyze them. "
         "Specify radius bounds and fit threshold; results remain candidates, not hole identities.",
         {
             "cloud_id": {"type": "integer", "minimum": 1},
             "region": {"type": "object", "description": "Existing global box/sphere/slab/nearest selector. Use a localized region; face settings are also global."},
             "sample_limit": {"type": "integer", "minimum": 4, "maximum": 10000, "default": 3000},
             "max_circles": {"type": "integer", "minimum": 1, "maximum": 16, "default": 8},
             "iterations": {"type": "integer", "minimum": 10, "maximum": 2000, "default": 800},
             "min_radius": {"type": "number", "exclusiveMinimum": 0},
             "max_radius": {"type": "number", "exclusiveMinimum": 0},
             "distance_threshold": {"type": "number", "exclusiveMinimum": 0},
         }, ["cloud_id", "region", "min_radius", "max_radius", "distance_threshold"]),
    ]
    return [Tool(name=name, description=description,
                 inputSchema={"type": "object", "properties": deepcopy({**ANALYSIS_PROPERTIES, **extra}),
                              "required": REQUIRED_ANALYSIS + required, "additionalProperties": False},
                 annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                             idempotentHint=True, openWorldHint=name.startswith("discover_live")))
            for name, description, extra, required in schemas]


def _analysis_kwargs(args: dict) -> dict:
    return {key: args[key] for key in ANALYSIS_PROPERTIES if key in args}


def analyze_snapshot(args: dict) -> dict:
    discovery = args["circle_discovery"]
    if not isinstance(discovery, dict) or discovery.get("type") != "circle_discovery":
        raise FeatureFitError("circle_discovery must be the complete circle discovery result")
    if discovery.get("coordinate_space") != "global" or discovery.get("units") != "native":
        raise FeatureFitError("Only global, native-unit circle discoveries are accepted; do not relabel local coordinates")
    cloud_id = integer(discovery["source_cloud_id"], "source_cloud_id", 1, 2**32 - 1)
    candidates = discovery["candidates"]
    if not isinstance(candidates, list):
        raise FeatureFitError("circle discovery candidates must be a list")
    count = integer(discovery["candidate_count"], "candidate_count", 0, 32)
    if count != len(candidates):
        raise FeatureFitError("circle discovery candidate_count does not match candidates")
    sample = integer(discovery["sample_count"], "sample_count", 0, 20000)
    # Support fractions always refer to the entire discovery sample, not a group.
    total_support = 0
    for candidate in candidates:
        support = integer(candidate["support_count"], "support_count", 4, 20000)
        fraction = number(candidate["support_fraction_of_sample"], "support_fraction_of_sample", maximum=1)
        if sample == 0 or support > sample or abs(fraction - support / sample) > 1e-9:
            raise FeatureFitError("Candidate support disagrees with the discovery sample_count")
        total_support += support
    if total_support > sample:
        raise FeatureFitError("Discovery inlier sets must be disjoint; analyze one unmodified discovery result")
    result = analyze_hole_candidates(candidates, **_analysis_kwargs(args))
    result["source_cloud_id"] = cloud_id
    result["input_provenance"] = {key: deepcopy(discovery[key]) for key in (
        "region", "region_coordinate_space", "region_match_count", "region_sample_count",
        "region_sample_truncated", "region_sample_strategy", "sample_count", "distance_threshold",
        "sampling_warning", "min_radius", "max_radius", "max_circles",
    ) if key in discovery}
    result["live_sample_acquired"] = False
    result["scene_freshness_guaranteed"] = False
    result["input_mode"] = "provided_discovery_snapshot"
    json.dumps(result, allow_nan=False)
    return result


def _global_region(region: dict) -> dict:
    """Validate finite known selector fields before opening a socket."""
    if not isinstance(region, dict):
        raise FeatureFitError("region must be a global region selector")
    kind = region.get("type")
    fields = {"box": ("min", "max"), "sphere": ("center",),
              "slab": ("origin", "normal"), "nearest": ("center",)}
    if kind not in fields:
        raise FeatureFitError("region.type must be box, sphere, slab, or nearest")
    out = {"type": kind}
    for name in fields[kind]:
        out[name] = vector(region[name], f"region.{name}").tolist()
    if kind == "box" and any(a >= b for a, b in zip(out["min"], out["max"])):
        raise FeatureFitError("region box min must be less than max on every axis")
    if kind == "sphere":
        out["radius"] = number(region["radius"], "region.radius", positive=True)
    if kind == "slab":
        if not any(out["normal"]):
            raise FeatureFitError("region.normal must be nonzero")
        out["half_thickness"] = number(region["half_thickness"], "region.half_thickness")
    if kind == "nearest" and "max_distance" in region:
        out["max_distance"] = number(region["max_distance"], "region.max_distance")
    if set(region) != set(out):
        raise FeatureFitError("region contains unsupported fields; coordinates must be global")
    return out


def discover_live(args: dict, request_region) -> dict:
    cfg = settings(_analysis_kwargs(args))
    cloud = integer(args["cloud_id"], "cloud_id", 1, 2**32 - 1)
    limit = integer(args.get("sample_limit", 3000), "sample_limit", 4, 10000)
    maximum = integer(args.get("max_circles", 8), "max_circles", 1, 16)
    iterations = integer(args.get("iterations", 800), "iterations", 10, 2000)
    threshold = number(args["distance_threshold"], "distance_threshold", positive=True)
    minimum_radius = number(args["min_radius"], "min_radius", positive=True)
    maximum_radius = number(args["max_radius"], "max_radius", positive=True)
    if minimum_radius > maximum_radius:
        raise FeatureFitError("min_radius must not exceed max_radius")
    if cfg["min_support_count"] > limit or cfg["min_support_fraction"] <= 0:
        raise FeatureFitError("Live discovery requires min_support_count <= sample_limit and positive min_support_fraction")
    region = _global_region(args["region"])
    native = request_region(cloud_id=cloud, region=region, coordinate_space="global", max_points=limit)
    if native.get("cloud_id") != cloud or native.get("coordinate_space") != "global":
        raise FeatureFitError("Live sample returned a different source or coordinate frame")
    records = native.get("points")
    if not isinstance(records, list) or len(records) > limit:
        raise FeatureFitError("Live sample is missing or exceeds sample_limit")
    positions = [vector(point["position_global"], "sample position_global").tolist() for point in records]
    returned = integer(native["returned_count"], "returned_count", 0, limit)
    matched = integer(native["matched_count"], "matched_count", 0, 2**53 - 1)
    if (returned != len(positions) or matched < returned or not isinstance(native.get("truncated"), bool)
            or native["truncated"] != (returned < matched)):
        raise FeatureFitError("Live sample count/truncation metadata is inconsistent")
    if len(positions) < cfg["min_support_count"]:
        discovery = {"type": "circle_discovery", "sample_count": len(positions),
                     "candidate_count": 0, "candidates": [], "distance_threshold": threshold,
                     "min_radius": minimum_radius, "max_radius": maximum_radius, "max_circles": maximum}
    else:
        discovery = discover_circles(
            positions, distance_threshold=threshold, min_radius=minimum_radius,
            max_radius=maximum_radius, max_circles=maximum, iterations=iterations,
            min_points=cfg["min_support_count"], min_inlier_fraction=cfg["min_support_fraction"],
            min_arc_coverage_degrees=cfg["min_coverage_degrees"], random_seed=0,
        )
    discovery.update(coordinate_space="global", units="native", source_cloud_id=cloud,
                     region=region, region_coordinate_space="global", region_match_count=matched,
                     region_sample_count=returned, region_sample_truncated=native["truncated"],
                     region_sample_strategy=native.get("sample_strategy"))
    if native["truncated"]:
        discovery["sampling_warning"] = "Candidates describe a bounded sample, not exhaustive feature detection."
    result = analyze_snapshot({**_analysis_kwargs(args), "circle_discovery": discovery})
    result["input_mode"] = "fresh_live_region_sample"
    result["live_sample_acquired"] = True
    result["scene_mutations_requested"] = False
    return result
