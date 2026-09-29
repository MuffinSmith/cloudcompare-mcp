// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <cmath>

namespace qMCPRegistrationPolicy
{
struct Diagnostics
{
    double determinant = 0.0;
    double orthogonalityMaxError = 0.0;
    double scale = 1.0;
    bool properRotation = false;
    bool unitScale = false;
    bool rigidTransformValid = false;
};

inline Diagnostics inspect(
    const double rotation[3][3],
    double scale,
    double tolerance = 1.0e-5 )
{
    Diagnostics result;
    result.scale = scale;
    result.determinant =
        rotation[0][0] * ( rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1] )
        - rotation[0][1] * ( rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0] )
        + rotation[0][2] * ( rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0] );

    double maxError = 0.0;
    for ( int columnA = 0; columnA < 3; ++columnA )
    {
        for ( int columnB = 0; columnB < 3; ++columnB )
        {
            double dot = 0.0;
            for ( int row = 0; row < 3; ++row )
            {
                dot += rotation[row][columnA] * rotation[row][columnB];
            }
            const double expected = columnA == columnB ? 1.0 : 0.0;
            maxError = std::max( maxError, std::abs( dot - expected ) );
        }
    }

    result.orthogonalityMaxError = maxError;
    result.properRotation =
        std::isfinite( result.determinant )
        && std::abs( result.determinant - 1.0 ) <= tolerance
        && maxError <= tolerance;
    result.unitScale =
        std::isfinite( scale )
        && std::abs( scale - 1.0 ) <= tolerance;
    result.rigidTransformValid =
        result.properRotation && result.unitScale;
    return result;
}
}
