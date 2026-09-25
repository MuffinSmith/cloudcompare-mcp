"""Synthetic acceptance checks: removal, coverage, edge and thin-wall retention."""
import unittest
import numpy as np
from detect_wisps import detect

class WispTests(unittest.TestCase):
    def test_strand_and_real_boundary(self):
        x,y=np.meshgrid(np.arange(-2,2.01,.1),np.arange(-2,2.01,.1))
        sheet=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
        strand=np.c_[np.zeros(8),np.zeros(8),np.linspace(.22,.7,8)]
        p=np.r_[sheet,strand];n=np.tile([0.,0.,1.],(len(sheet),1))
        bad,_=detect(p,[(sheet,n)],tolerance=.12)
        self.assertEqual(int(bad[:len(sheet)].sum()),0,'Clean surface or boundary removed')
        self.assertGreaterEqual(int(bad[len(sheet):].sum()),6,'Missed normal-direction strand')

    def test_missing_coverage_is_unknown(self):
        x,y=np.meshgrid(np.arange(-2,2.01,.1),np.arange(-2,2.01,.1))
        p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)];ref=p+np.array([20,0,0]);n=np.tile([0.,0.,1.],(len(p),1))
        bad,features=detect(p,[(ref,n)],tolerance=.12)
        self.assertFalse(bad.any());self.assertFalse(features['coverage'].any())

    def test_thin_sheet_opposite_faces(self):
        x,y=np.meshgrid(np.arange(-1,1.01,.1),np.arange(-1,1.01,.1))
        p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)]
        ref=np.r_[p,p+[0,0,.25]];n=np.r_[np.tile([0.,0.,-1.],(len(p),1)),np.tile([0.,0.,1.],(len(p),1))]
        bad,_=detect(ref,[(ref,n)],tolerance=.12)
        self.assertFalse(bad.any(),'Opposite faces of thin wall must survive')

    def test_curved_surface(self):
        angle,z=np.meshgrid(np.linspace(0,2*np.pi,120,endpoint=False),np.arange(-1,1.01,.1))
        n=np.c_[np.cos(angle.ravel()),np.sin(angle.ravel()),np.zeros(angle.size)]
        p=n*2;p[:,2]=z.ravel()
        bad,_=detect(p,[(p,n)],tolerance=.12)
        self.assertFalse(bad.any(),'A clean cylinder must survive')

    def test_uniform_registration_offset_is_not_a_wisp(self):
        x,y=np.meshgrid(np.arange(-2,2.01,.1),np.arange(-2,2.01,.1))
        p=np.c_[x.ravel(),y.ravel(),np.zeros(x.size)];n=np.tile([0.,0.,1.],(len(p),1))
        bad,_=detect(p,[(p+[0,0,.3],n)],tolerance=.12)
        self.assertFalse(bad.any(),'Uniformly offset surface is not a sparse strand')

if __name__=='__main__': unittest.main()
