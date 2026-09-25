import unittest
import numpy as np
from fine_edges import detect_fine_edges

def slab():
    x,y=np.meshgrid(np.arange(-1,.001,.05),np.arange(-1,1.001,.05))
    top=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
    z,y=np.meshgrid(np.arange(-.5,.001,.05),np.arange(-1,1.001,.05))
    side=np.c_[np.zeros(z.size),y.ravel(),z.ravel()]
    p=np.r_[top,side,top-[0,0,.5]]
    n=np.r_[np.tile([0.,0.,1.],(len(top),1)),np.tile([1.,0.,0.],(len(side),1)),np.tile([0.,0.,-1.],(len(top),1))]
    return p,n

class FineEdgeTests(unittest.TestCase):
    def test_stray_beyond_side_despite_top_plane_support(self):
        p,n=slab();x=np.r_[p,[[.16,0,0],[.18,.35,-.03]]]
        bad,_=detect_fine_edges(x,[(p,n),(p,n)],tolerance=.08)
        self.assertEqual(int(bad[:-2].sum()),0)
        self.assertTrue(bad[-2:].all())

    def test_clean_slab_and_opposite_faces(self):
        p,n=slab();bad,_=detect_fine_edges(p,[(p,n),(p,n)],tolerance=.08)
        self.assertFalse(bad.any())

    def test_concave_hole_and_convex_cylinder(self):
        a,z=np.meshgrid(np.linspace(0,2*np.pi,140,endpoint=False),np.arange(-.5,.501,.05))
        n=np.c_[np.cos(a.ravel()),np.sin(a.ravel()),np.zeros(a.size)]
        p=n*2;p[:,2]=z.ravel()
        for sign in [-1,1]:
            bad,_=detect_fine_edges(p,[(p,n*sign),(p,n*sign)],tolerance=.08)
            self.assertFalse(bad.any())

    def test_missing_overlap_preserved(self):
        p,n=slab();bad,_=detect_fine_edges(p,[(p+20,n),(p+30,n)],tolerance=.08)
        self.assertFalse(bad.any())

if __name__=='__main__':unittest.main()
