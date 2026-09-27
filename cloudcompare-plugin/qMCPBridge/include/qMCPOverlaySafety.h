// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cmath>
#include <limits>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace qMCPOverlaySafety
{
// Runtime identities only: a name or copied/saved metadata never grants ownership.
// Node is ccHObject in production. Keeping this small policy independent of Qt
// allows its real implementation to be exercised without a CloudCompare SDK.
template <class Node>
class Ownership
{
public:
    void clear() { m_nodes.clear(); }

    bool owns( const Node* node ) const
    {
        if ( !node ) return false;
        const auto found = m_nodes.find( node->getUniqueID() );
        return found != m_nodes.end() && found->second == node;
    }

    void rememberTree( const Node* root )
    {
        if ( !root ) return;
        std::vector<const Node*> pending{ root };
        std::unordered_set<const Node*> visited;
        while ( !pending.empty() )
        {
            const Node* node = pending.back();
            pending.pop_back();
            if ( !node || !visited.insert( node ).second ) continue;
            m_nodes[node->getUniqueID()] = node;
            for ( unsigned i = 0; i < node->getChildrenNumber(); ++i )
                pending.push_back( node->getChild( i ) );
        }
    }

    bool ownsTree( const Node* root ) const
    {
        if ( !root ) return false;
        std::vector<const Node*> pending{ root };
        std::unordered_set<const Node*> visited;
        while ( !pending.empty() )
        {
            const Node* node = pending.back();
            pending.pop_back();
            // Cycles/shared children are not a safe independently owned tree.
            if ( !owns( node ) || !visited.insert( node ).second ) return false;
            for ( unsigned i = 0; i < node->getChildrenNumber(); ++i )
                pending.push_back( node->getChild( i ) );
        }
        return true;
    }

private:
    std::unordered_map<unsigned, const Node*> m_nodes;
};

template <typename Coordinate>
bool finiteCoordinate( double value )
{
    return std::isfinite( value )
        && std::abs( value ) <= static_cast<double>( std::numeric_limits<Coordinate>::max() );
}

template <typename Coordinate>
bool positiveLength( double value )
{
    return finiteCoordinate<Coordinate>( value ) && value > 0.0
        && static_cast<Coordinate>( value ) > 0;
}

// Conservative enclosing sphere: generated vertices must remain representable
// after global-to-local conversion and narrowing to CloudCompare coordinates.
template <typename Coordinate>
bool boundedCenter( double x, double y, double z, double padding )
{
    if ( !std::isfinite( padding ) || padding < 0.0 ) return false;
    const long double limit = std::numeric_limits<Coordinate>::max();
    for ( double value : { x, y, z } )
    {
        if ( !finiteCoordinate<Coordinate>( value )
             || std::abs( static_cast<long double>( value ) ) + padding > limit )
            return false;
    }
    return true;
}
}
