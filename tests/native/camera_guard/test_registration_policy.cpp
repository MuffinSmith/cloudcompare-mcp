// SPDX-License-Identifier: GPL-2.0-or-later
#include "qMCPRegistrationPolicy.h"

#include <cmath>
#include <cstdlib>
#include <iostream>

using namespace qMCPRegistrationPolicy;

int main(int argc, char** argv)
{
    if (argc != 2)
        return 2;

    const int id = std::atoi(argv[1]);
    double rotation[3][3] = {
        {1.0, 0.0, 0.0},
        {0.0, 1.0, 0.0},
        {0.0, 0.0, 1.0},
    };
    double scale = 1.0;
    bool expectedValid = true;
    double expectedDeterminant = 1.0;

    if (id == 1)
    {
        rotation[0][0] = -1.0; // reflection
        expectedValid = false;
        expectedDeterminant = -1.0;
    }
    else if (id == 2)
    {
        scale = 1.01; // non-rigid scale
        expectedValid = false;
    }
    else if (id == 3)
    {
        rotation[0][1] = 0.02; // shear / non-orthogonal basis
        expectedValid = false;
    }
    else if (id == 4)
    {
        // Proper +90 degree rotation around Z.
        rotation[0][0] = 0.0;
        rotation[0][1] = -1.0;
        rotation[1][0] = 1.0;
        rotation[1][1] = 0.0;
    }
    else if (id != 0)
    {
        return 2;
    }

    const Diagnostics d = inspect(rotation, scale);
    const bool ok =
        d.rigidTransformValid == expectedValid
        && std::abs(d.determinant - expectedDeterminant) < 1.0e-12
        && (expectedValid ? d.properRotation : true);

    if (!ok)
    {
        std::cerr << "registration policy case " << id
                  << " failed: det=" << d.determinant
                  << " orth=" << d.orthogonalityMaxError
                  << " scale=" << d.scale << "\n";
    }
    return ok ? 0 : 1;
}
