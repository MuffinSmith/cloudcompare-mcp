"""Final-fit guards; controlled fitters isolate discovery's acceptance logic."""
from __future__ import annotations

from copy import deepcopy
import numpy as np
import pytest

from cloudcompare_mcp import feature_discovery as discovery
from cloudcompare_mcp import feature_fit


def ring(count=40):
    theta = np.linspace(0, 2*np.pi, count, endpoint=False)
    return np.column_stack((5*np.cos(theta), 5*np.sin(theta), np.zeros(count)))


@pytest.mark.parametrize("kind", ["plane", "circle", "cylinder"])
def test_final_shift_cannot_report_stale_support(monkeypatch, kind):
    if kind == "plane":
        points = np.array([[x, y, 0.] for x in range(5) for y in range(5)])
        real_fit = feature_fit.fit_plane
        good = real_fit(points)
        bad = deepcopy(good)
        bad["centroid"][2] = 1.
        last_call = 4
    elif kind == "circle":
        points = ring()
        good = feature_fit.fit_circle_3d(points)
        bad = deepcopy(good)
        bad["center"][2] = 1.
        last_call = 5
    else:
        points = np.vstack([ring(12)+[0,0,z] for z in (-4., 0., 4.)])
        good = feature_fit.fit_cylinder_3d(points)
        bad = deepcopy(good)
        bad["axis_point"][0] += 1.
        last_call = 6  # broad + one random seed + three refinements + final fit

    calls = 0
    def controlled_fit(_points):
        nonlocal calls
        calls += 1
        return deepcopy(bad if calls >= last_call else good)

    if kind == "plane":
        monkeypatch.setattr(discovery, "fit_plane", controlled_fit)
        result = discovery.discover_planes(points, distance_threshold=.01,
            min_points=20, max_planes=1, iterations=20)
    elif kind == "circle":
        monkeypatch.setattr(feature_fit, "fit_circle_3d", controlled_fit)
        result = discovery.discover_circles(points, distance_threshold=.01,
            min_points=20, max_circles=1, iterations=20)
    else:
        monkeypatch.setattr(feature_fit, "fit_cylinder_3d", controlled_fit)
        result = discovery.discover_cylinders(points, distance_threshold=.01,
            min_points=20, max_cylinders=1, restarts=1)
    assert result["candidate_count"] == 0
    assert result["unassigned_sample_count"] == len(points)


@pytest.mark.parametrize("failure", ["radius", "exception"])
def test_final_cylinder_refit_must_be_valid(monkeypatch, failure):
    points = np.vstack([ring(8)+[0,0,z] for z in (-4., 0., 4.)])
    good = feature_fit.fit_cylinder_3d(points)
    calls = 0
    def controlled_fit(_points):
        nonlocal calls
        calls += 1
        fit = deepcopy(good)
        if calls >= 6:
            if failure == "exception":
                raise feature_fit.FeatureFitError("injected final-refinement failure")
            fit["radius"] = 8.
            fit["diameter"] = 16.
        return fit
    monkeypatch.setattr(feature_fit, "fit_cylinder_3d", controlled_fit)
    result = discovery.discover_cylinders(points, distance_threshold=.01,
        min_points=12, max_cylinders=1, restarts=1, max_radius=6.)
    assert result["candidate_count"] == 0
    assert result["unassigned_sample_count"] == len(points)


def test_circle_support_matches_returned_geometry(monkeypatch):
    points = ring(80)
    good = feature_fit.fit_circle_3d(points)
    shifted = deepcopy(good)
    shifted["center"][0] += .2
    calls = 0
    def controlled_fit(_points):
        nonlocal calls
        calls += 1
        return deepcopy(shifted if calls >= 5 else good)
    monkeypatch.setattr(feature_fit, "fit_circle_3d", controlled_fit)
    result = discovery.discover_circles(points, distance_threshold=.1,
        min_points=4, min_inlier_fraction=.01, max_circles=1,
        min_arc_coverage_degrees=0., iterations=30)
    assert result["candidate_count"] == 1
    item = result["candidates"][0]
    fit = item["circle"]
    # Independent orthogonal-circle distance, not the discovery helper.
    delta = points - np.asarray(fit["center"])
    offsets = delta @ np.asarray(fit["normal"])
    projected = delta - offsets[:, None]*np.asarray(fit["normal"])
    residuals = np.hypot(offsets, np.linalg.norm(projected, axis=1)-fit["radius"])
    mask = residuals <= .1
    assert item["support_count"] == int(mask.sum())
    assert item["support_fraction_of_sample"] == pytest.approx(mask.mean())
    assert item["orthogonal_residuals"]["max_abs"] <= .1
    assert item["bounds_global"]["min"] == pytest.approx(points[mask].min(axis=0))
    assert item["refinement_sample_count"] == 80
    assert result["unassigned_sample_count"] == int((~mask).sum())
