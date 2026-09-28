// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <cmath>

// Shared by the actual camera dispatcher and compiled, host-independent tests.
namespace qMCPCameraPolicy
{
constexpr int MaxSavedStates = 8;
inline bool bounded(double x, double lo, double hi)
{
    return std::isfinite(x) && x >= lo && x <= hi;
}
inline bool vector(const double* v, double limit = 1.0e12)
{
    return bounded(v[0], -limit, limit) && bounded(v[1], -limit, limit)
        && bounded(v[2], -limit, limit);
}
inline bool normalize(double* v)
{
    if (!vector(v)) return false;
    const double n = std::hypot(std::hypot(v[0], v[1]), v[2]);
    if (!bounded(n, 1.0e-12, 1.0e12)) return false;
    for (int i = 0; i < 3; ++i) v[i] /= n;
    return true;
}
inline void cross(const double* a, const double* b, double* out)
{
    out[0] = a[1]*b[2] - a[2]*b[1];
    out[1] = a[2]*b[0] - a[0]*b[2];
    out[2] = a[0]*b[1] - a[1]*b[0];
}
inline bool look(double* forward, double* up, double* columnMajor)
{
    if (!normalize(forward) || !normalize(up)) return false;
    double right[3]; cross(forward, up, right);
    const double n = std::hypot(std::hypot(right[0], right[1]), right[2]);
    if (n < 1.0e-6 || !normalize(right)) return false;
    cross(right, forward, up);
    std::fill(columnMajor, columnMajor + 16, 0.0);
    columnMajor[15] = 1.0;
    for (int i = 0; i < 3; ++i)
    {
        columnMajor[4*i] = right[i];
        columnMajor[4*i+1] = up[i];
        columnMajor[4*i+2] = -forward[i];
    }
    return true;
}
inline bool orbit(double* axis, double degrees, double* m)
{
    if (!normalize(axis) || !bounded(degrees, -180.0, 180.0)) return false;
    const double a = degrees * 3.14159265358979323846 / 180.0;
    const double c = std::cos(a), s = std::sin(a), t = 1.0-c;
    const double x=axis[0], y=axis[1], z=axis[2];
    const double rows[9] = {t*x*x+c, t*x*y-s*z, t*x*z+s*y,
                           t*x*y+s*z, t*y*y+c, t*y*z-s*x,
                           t*x*z-s*y, t*y*z+s*x, t*z*z+c};
    std::fill(m, m+16, 0.0); m[15]=1.0;
    for (int r=0;r<3;++r) for (int col=0;col<3;++col) m[col*4+r]=rows[r*3+col];
    return true;
}
inline bool rotation(const double* m)
{
    for (int i=0;i<16;++i) if (!std::isfinite(m[i])) return false;
    for (int r=0;r<3;++r) for (int c=0;c<3;++c)
    {
        double dot=0.0;
        for (int k=0;k<3;++k) dot += m[r*4+k]*m[c*4+k];
        if (std::abs(dot-(r==c?1.0:0.0)) > 1.0e-6) return false;
    }
    double crossed[3]; cross(m,m+4,crossed);
    const double determinant=crossed[0]*m[8]+crossed[1]*m[9]+crossed[2]*m[10];
    return std::abs(determinant-1.0)<1.0e-6
        && m[3]==0.0 && m[7]==0.0 && m[11]==0.0
        && m[12]==0.0 && m[13]==0.0 && m[14]==0.0 && m[15]==1.0;
}
inline bool bounds(const double* lo, const double* hi)
{
    if (!vector(lo,1.0e15) || !vector(hi,1.0e15)) return false;
    bool nonzero=false;
    for (int i=0;i<3;++i) { if (lo[i]>hi[i]) return false; nonzero |= lo[i]<hi[i]; }
    return nonzero;
}
inline bool zoom(double factor) { return bounded(factor,0.1,10.0); }
inline bool pan(double x, double y) { return bounded(x,-1.0,1.0) && bounded(y,-1.0,1.0); }
}
