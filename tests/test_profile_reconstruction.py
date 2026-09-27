from __future__ import annotations

import math

import numpy as np
import pytest

from cloudcompare_mcp.profile_reconstruction import ProfileError, reconstruct_profile_2d


def circle_points(radius=5.0, count=96):
    theta = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))


def rectangle_points(width=20.0, height=10.0, per_side=16):
    x = width / 2.0; y = height / 2.0
    points = []
    points.extend([[v, y] for v in np.linspace(x, -x, per_side + 1)])
    points.extend([[-x, v] for v in np.linspace(y, -y, per_side + 1)[1:]])
    points.extend([[v, -y] for v in np.linspace(-x, x, per_side + 1)[1:]])
    points.extend([[x, v] for v in np.linspace(-y, y, per_side + 1)[1:-1]])
    return np.asarray(points, dtype=float)


def slot_points(centerline=20.0, radius=5.0, line_count=21, arc_count=31):
    h = centerline / 2.0
    points = []
    points.extend([[x, radius] for x in np.linspace(h, -h, line_count)])
    points.extend([
        [-h + radius * math.cos(a), radius * math.sin(a)]
        for a in np.linspace(math.pi / 2, 3 * math.pi / 2, arc_count)[1:]
    ])
    points.extend([[x, -radius] for x in np.linspace(-h, h, line_count)[1:]])
    points.extend([
        [h + radius * math.cos(a), radius * math.sin(a)]
        for a in np.linspace(3 * math.pi / 2, 5 * math.pi / 2, arc_count)[1:-1]
    ])
    return np.asarray(points, dtype=float)


def rotate_translate(points, angle=0.73, translation=(1.2e8, -2.4e8)):
    c, s = math.cos(angle), math.sin(angle)
    rotation = np.array([[c, -s], [s, c]])
    return np.asarray(points) @ rotation.T + np.asarray(translation)


def test_full_circle_is_single_circle_candidate():
    out = reconstruct_profile_2d(
        circle_points(), closed=True, fit_tolerance=1e-8,
        ordering_method="polar_closed_loop",
    )
    assert out["primitive_count"] == 1
    primitive = out["primitives"][0]
    assert primitive["type"] == "circle"
    assert primitive["radius"] == pytest.approx(5.0, abs=1e-10)
    assert primitive["fit_residuals"]["max_abs"] < 1e-10
    assert out["profile_candidates"][0]["type"] == "circle_profile_candidate"
    assert not out["raw_points_returned"]


def test_rectangle_reconstructs_four_lines_and_candidate():
    out = reconstruct_profile_2d(
        rectangle_points(), closed=True, fit_tolerance=1e-8,
        ordering_method="input", angular_tolerance_degrees=0.1,
    )
    assert [p["type"] for p in out["primitives"]] == ["line"] * 4
    candidate, = out["profile_candidates"]
    assert candidate["type"] == "rectangle_candidate"
    assert sorted(candidate["side_pair_lengths"]) == pytest.approx([10.0, 20.0], abs=1e-10)
    assert all(r["coincident_endpoint_candidate"] for r in out["relationships"])
    assert all(r["perpendicular_candidate"] for r in out["relationships"])


def test_slot_reconstructs_two_lines_two_arcs_and_candidate():
    out = reconstruct_profile_2d(
        slot_points(), closed=True, fit_tolerance=1e-8,
        ordering_method="input", angular_tolerance_degrees=0.1,
    )
    assert [p["type"] for p in out["primitives"]] == ["line", "arc", "line", "arc"]
    candidate, = out["profile_candidates"]
    assert candidate["type"] == "slot_candidate"
    assert candidate["radius"] == pytest.approx(5.0, abs=1e-10)
    assert candidate["width"] == pytest.approx(10.0, abs=1e-10)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=1e-10)
    assert candidate["overall_length"] == pytest.approx(30.0, abs=1e-10)
    assert all(r["tangent_candidate"] for r in out["relationships"])


def test_polar_ordering_recovers_shuffled_convex_slot():
    points = slot_points()
    shuffled = points[np.random.default_rng(15001).permutation(points.shape[0])]
    out = reconstruct_profile_2d(
        shuffled, closed=True, fit_tolerance=1e-8,
        ordering_method="polar_closed_loop", angular_tolerance_degrees=0.1,
    )
    candidate, = [c for c in out["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidate["radius"] == pytest.approx(5.0, abs=1e-10)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=1e-10)
    assert any("star-shaped" in w for w in out["quality_warnings"])


def test_committed_fixture_density_does_not_fragment_slot_joins():
    # scripts/make_profile_fixtures.py uses exactly these sample counts and
    # acceptance tolerances.  This guards issue #13, where two-point line
    # slivers at line/arc joins prevented slot classification.
    points = slot_points(line_count=41, arc_count=61)
    shuffled = points[np.random.default_rng(15013).permutation(points.shape[0])]
    out = reconstruct_profile_2d(
        shuffled,
        closed=True,
        fit_tolerance=0.001,
        ordering_method="polar_closed_loop",
        angular_tolerance_degrees=0.2,
    )
    assert [p["type"] for p in out["primitives"]] == ["line", "arc", "line", "arc"]
    candidate, = [c for c in out["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidate["radius"] == pytest.approx(5.0, abs=1e-8)
    assert candidate["width"] == pytest.approx(10.0, abs=2e-8)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=1e-8)
    assert candidate["overall_length"] == pytest.approx(30.0, abs=3e-8)
    assert out["summary"]["max_primitive_fit_residual"] <= 0.001


def test_committed_fixture_density_survives_large_translation():
    points = rotate_translate(
        slot_points(line_count=41, arc_count=61),
        angle=0.73,
        translation=(1.2e8, -2.4e8),
    )
    out = reconstruct_profile_2d(
        points,
        closed=True,
        fit_tolerance=0.001,
        ordering_method="polar_closed_loop",
        angular_tolerance_degrees=0.2,
    )
    assert [p["type"] for p in out["primitives"]] == ["line", "arc", "line", "arc"]
    candidate, = [c for c in out["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidate["radius"] == pytest.approx(5.0, abs=1e-5)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=1e-5)


def test_rotation_and_large_translation_preserve_slot_dimensions():
    points = rotate_translate(slot_points())
    out = reconstruct_profile_2d(
        points, closed=True, fit_tolerance=1e-4,
        ordering_method="polar_closed_loop", angular_tolerance_degrees=0.1,
    )
    candidate, = [c for c in out["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidate["radius"] == pytest.approx(5.0, abs=2e-7)
    assert candidate["centerline_length"] == pytest.approx(20.0, abs=2e-7)
    assert out["coordinate_precision_floor"] < out["fit_tolerance"]


def test_noisy_slot_remains_candidate_with_explicit_residuals():
    rng = np.random.default_rng(15002)
    points = slot_points() + rng.normal(scale=0.002, size=slot_points().shape)
    out = reconstruct_profile_2d(
        points, closed=True, fit_tolerance=0.02,
        ordering_method="polar_closed_loop", angular_tolerance_degrees=1.0,
    )
    candidates = [c for c in out["profile_candidates"] if c["type"] == "slot_candidate"]
    assert candidates
    assert out["summary"]["all_primitives_within_fit_tolerance"]
    assert 0 < out["summary"]["max_primitive_fit_residual"] <= 0.02


def test_open_line_is_one_line():
    x = np.linspace(-5, 7, 40)
    points = np.column_stack((x, 2.0 * x + 3.0))
    out = reconstruct_profile_2d(
        points, closed=False, fit_tolerance=1e-10,
        ordering_method="principal_open",
    )
    assert out["primitive_count"] == 1
    assert out["primitives"][0]["type"] == "line"
    assert out["relationships"] == []


def test_open_quarter_arc_is_one_arc():
    theta = np.linspace(0.0, math.pi / 2, 40)
    points = np.column_stack((3 + 4 * np.cos(theta), -2 + 4 * np.sin(theta)))
    out = reconstruct_profile_2d(
        points, closed=False, fit_tolerance=1e-9,
        ordering_method="input", minimum_arc_angle_degrees=10,
    )
    assert out["primitive_count"] == 1
    p = out["primitives"][0]
    assert p["type"] == "arc"
    assert abs(p["sweep_degrees"]) == pytest.approx(90.0, abs=1e-8)
    assert p["radius"] == pytest.approx(4.0, abs=1e-9)


def test_tight_tolerance_cannot_exceed_segment_budget():
    x = np.arange(20.0)
    points = np.column_stack((x, np.where((x.astype(int) % 2) == 0, 0.0, 1.0)))
    with pytest.raises(ProfileError, match="max_segments"):
        reconstruct_profile_2d(
            points, closed=False, fit_tolerance=1e-6,
            ordering_method="input", max_segments=2,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, 0.0, True])
def test_invalid_fit_tolerance_rejected(value):
    with pytest.raises(ProfileError, match="fit_tolerance"):
        reconstruct_profile_2d([[0, 0], [1, 0], [2, 0]], closed=False, fit_tolerance=value)


def test_nonfinite_points_rejected():
    with pytest.raises(ProfileError, match="finite"):
        reconstruct_profile_2d([[0, 0], [1, float("nan")], [2, 0]], closed=False, fit_tolerance=.1)


def test_ordering_contracts_are_explicit():
    with pytest.raises(ProfileError, match="requires closed=true"):
        reconstruct_profile_2d([[0, 0], [1, 0], [2, 0]], closed=False, fit_tolerance=.1, ordering_method="polar_closed_loop")
    with pytest.raises(ProfileError, match="requires closed=false"):
        reconstruct_profile_2d([[0, 0], [1, 0], [1, 1]], closed=True, fit_tolerance=.1, ordering_method="principal_open")


def test_fit_tolerance_below_large_coordinate_precision_is_rejected():
    points = np.array([[1e16, 1e16], [1e16 + 4, 1e16], [1e16 + 8, 1e16]])
    with pytest.raises(ProfileError, match="precision floor"):
        reconstruct_profile_2d(points, closed=False, fit_tolerance=1e-6)


def test_deterministic_repeat():
    points = slot_points()
    a = reconstruct_profile_2d(points, closed=True, fit_tolerance=1e-8, ordering_method="input")
    b = reconstruct_profile_2d(points, closed=True, fit_tolerance=1e-8, ordering_method="input")
    assert a == b

def test_fit_tolerance_boundary_is_inclusive():
    points = np.asarray([[0.0, 0.0], [1.0, 0.1], [2.0, 0.0]])
    probe = reconstruct_profile_2d(points, closed=False, fit_tolerance=1.0, ordering_method="input")
    line_residual = probe["primitives"][0]["fit_residuals"]["max_abs"]
    exact = reconstruct_profile_2d(points, closed=False, fit_tolerance=line_residual, ordering_method="input")
    assert exact["primitive_count"] == 1
    assert exact["primitives"][0]["type"] == "line"
    below = np.nextafter(line_residual, 0.0)
    with pytest.raises(ProfileError, match="max_segments"):
        reconstruct_profile_2d(points, closed=False, fit_tolerance=below, ordering_method="input", max_segments=1)
