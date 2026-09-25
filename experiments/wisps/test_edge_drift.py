import unittest
import numpy as np
from edge_drift import detect_edge_drift, patch_evidence


def sheet(extent=2., curve=False, drift=False):
    x, y = np.meshgrid(np.arange(-extent, extent+.001, .1), np.arange(-extent, extent+.001, .1))
    z = .12*x*x+.07*y*y if curve else np.zeros_like(x)
    dx, dy = (.24*x, .14*y) if curve else (np.zeros_like(x), np.zeros_like(y))
    if drift:
        t = np.maximum(x-(extent-.5), 0)/.5
        z += .3*t*t; dx += 1.2*t
    p = np.c_[x.ravel(), y.ravel(), z.ravel()]
    n = np.c_[-dx.ravel(), -dy.ravel(), np.ones(x.size)]
    n /= np.linalg.norm(n, axis=1)[:, None]
    return p, n


class EdgeDriftTests(unittest.TestCase):
    def test_curled_boundary_and_fringe_with_single_covering_reference(self):
        p, n = sheet(1.5, drift=True); q, qn = sheet(2.5)
        result = detect_edge_drift([(p, n), (q, qn)], tolerance=.12)
        bad, f = result[0]
        tip = (p[:, 0] > 1.39) & (abs(p[:, 1]) < .7)
        self.assertTrue(bad[tip].all())
        self.assertFalse(bad[p[:, 0] < 1.09].any())
        self.assertGreater(f['trim_fringe'].sum(), 0)
        self.assertFalse(result[1][0].any())
        self.assertFalse(bad[f['interior']].any())

    def test_clean_curvature_and_real_boundaries(self):
        small = sheet(1.5, curve=True); large = sheet(2.5, curve=True)
        for bad, _ in detect_edge_drift([small, large], tolerance=.12):
            self.assertFalse(bad.any())

    def test_uncovered_curled_boundary_preserved(self):
        p, n = sheet(1.5, drift=True); q, qn = sheet(2.5)
        for bad, _ in detect_edge_drift([(p, n), (q+20, qn)], tolerance=.12):
            self.assertFalse(bad.any())

    def test_small_alignment_error_not_trimmed(self):
        p, n = sheet(1.5); q, qn = sheet(2.5)
        for bad, _ in detect_edge_drift([(p+[0, 0, .07], n), (q, qn)], tolerance=.12):
            self.assertFalse(bad.any())

    def test_opposite_thin_face_not_used_as_replacement(self):
        p, n = sheet(1.5); q, qn = sheet(2.5)
        for bad, _ in detect_edge_drift([(p, n), (q-[0, 0, .25], -qn)], tolerance=.12):
            self.assertFalse(bad.any())

    def test_disagreeing_references_veto_deletion(self):
        p, n = sheet(1.5); q, qn = sheet(2.5)
        bad, _ = detect_edge_drift([(p, n), (q+[0, 0, .25], qn), (q, qn)], tolerance=.12)[0]
        self.assertFalse(bad.any())

    def test_patch_does_not_interpolate_across_unobserved_hole(self):
        q, qn = sheet(2.5)
        keep = np.linalg.norm(q[:, :2], axis=1) > .6
        r, _ = patch_evidence(np.array([[0., 0., .25]]), np.array([[0., 0., 1.]]),
                              q[keep], qn[keep], .12)
        self.assertTrue(np.isnan(r).all())

    def test_intact_hole_rim(self):
        a, an = sheet(1.5); b, bn = sheet(2.5)
        ka = np.linalg.norm(a[:, :2], axis=1) > .6
        kb = np.linalg.norm(b[:, :2], axis=1) > .6
        for bad, _ in detect_edge_drift([(a[ka], an[ka]), (b[kb], bn[kb])], tolerance=.12):
            self.assertFalse(bad.any())


if __name__ == '__main__':
    unittest.main()
