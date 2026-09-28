// SPDX-License-Identifier: GPL-2.0-or-later
#include "qMCPCameraPolicy.h"
#include <cstdlib>
#include <limits>
using namespace qMCPCameraPolicy;
int main(int argc,char** argv)
{
    if(argc!=2) return 2;
    int k=std::atoi(argv[1]); double f[3]={0,0,-1},u[3]={0,1,0},m[16],axis[3]={0,1,0};
    bool ok=false;
    if(k<7)
    {
        const double dirs[7][3]={{0,0,-1},{0,0,1},{0,1,0},{0,-1,0},{1,0,0},{-1,0,0},{-1,-1,-1}};
        for(int i=0;i<3;++i) f[i]=dirs[k][i];
        if(k==2 || k==3) {u[1]=0;u[2]=1;}
        ok=look(f,u,m) && rotation(m);
    }
    if(k==7 || k==8 || k==9) ok=orbit(axis,k==7?90:k==8?-90:180,m)&&rotation(m);
    if(k==10) ok=!orbit(axis,181,m);
    if(k==11) ok=!orbit(axis,std::numeric_limits<double>::quiet_NaN(),m);
    if(k==12) {axis[1]=0;ok=!orbit(axis,30,m);}
    if(k==13) {f[2]=0;ok=!look(f,u,m);}
    if(k==14) {u[1]=0;u[2]=1;ok=!look(f,u,m);}
    if(k==15) {u[1]=1e-9;u[2]=1;ok=!look(f,u,m);}
    if(k==16) {f[0]=std::numeric_limits<double>::infinity();ok=!look(f,u,m);}
    if(k==17) {double v[3]={1e8,-2e8,3e8};ok=vector(v);}
    if(k==18) {double v[3]={1e30,0,0};ok=!vector(v);}
    if(k==19) ok=zoom(0.1);
    if(k==20) ok=zoom(10);
    if(k==21) ok=!zoom(0.09);
    if(k==22) ok=pan(-1,1);
    if(k==23) ok=!pan(2,0);
    if(k>=24 && k<=27)
    {
        double lo[3]={1e8,-2e8,3e8},hi[3]={1e8+10,-2e8+5,3e8+2};
        if(k==25) hi[0]=lo[0]-1;
        if(k==26) hi[2]=lo[2];
        if(k==27) for(int i=0;i<3;++i) hi[i]=lo[i];
        ok=bounds(lo,hi)==(k==24||k==26);
    }
    if(k==28) {look(f,u,m);m[0]=-m[0];ok=!rotation(m);}
    if(k==29) {look(f,u,m);m[12]=1;ok=!rotation(m);}
    if(k==30)
    {
        double inverse[16];orbit(axis,37,m);orbit(axis,-37,inverse);ok=true;
        for(int r=0;r<4;++r) for(int c=0;c<4;++c)
        {double v=0;for(int j=0;j<4;++j) v+=m[j*4+r]*inverse[c*4+j];ok=ok&&std::abs(v-(r==c?1:0))<1e-12;}
    }
    return ok?0:1;
}
