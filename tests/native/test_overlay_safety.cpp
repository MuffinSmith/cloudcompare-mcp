// SPDX-License-Identifier: GPL-2.0-or-later
#include "qMCPOverlaySafety.h"
#include <cassert>
#include <cstdlib>
#include <limits>
#include <vector>

struct Node
{
    unsigned id;
    std::vector<Node*> children;
    unsigned getUniqueID() const { return id; }
    unsigned getChildrenNumber() const { return static_cast<unsigned>( children.size() ); }
    Node* getChild( unsigned index ) const { return children.at( index ); }
};

int main( int argc, char** argv )
{
    assert( argc == 2 );
    const int scenario = std::atoi( argv[1] );
    Node vertices{ 3, {} }, overlay{ 2, { &vertices } }, group{ 1, { &overlay } };
    Node user{ 4, {} }, impostor{ 1, {} };
    qMCPOverlaySafety::Ownership<Node> owned;
    owned.rememberTree( &group );
    switch ( scenario )
    {
    case 0: assert( owned.ownsTree( &group ) ); break;
    case 1:
        group.children.push_back( &user );
        assert( !owned.ownsTree( &group ) );
        break;
    case 2:
        vertices.children.push_back( &user );
        assert( !owned.ownsTree( &group ) );
        break;
    case 3: assert( !owned.owns( &impostor ) ); break;
    case 4:
        owned.clear();
        assert( !owned.ownsTree( &group ) );
        break;
    case 5:
        vertices.children.push_back( &group );
        assert( !owned.ownsTree( &group ) );
        break;
    case 6:
        group.children.push_back( &vertices );
        assert( !owned.ownsTree( &group ) );
        break;
    case 7:
        group.children.push_back( nullptr );
        assert( !owned.ownsTree( &group ) );
        break;
    case 8:
        group.children.clear();
        assert( owned.ownsTree( &group ) );
        break;
    case 9:
        assert( qMCPOverlaySafety::positiveLength<float>( 0.001 ) );
        assert( !qMCPOverlaySafety::positiveLength<float>( 0 ) );
        assert( !qMCPOverlaySafety::positiveLength<float>( -1 ) );
        assert( !qMCPOverlaySafety::positiveLength<float>( 1e-300 ) );
        assert( !qMCPOverlaySafety::positiveLength<float>( 1e300 ) );
        break;
    case 10:
        assert( !qMCPOverlaySafety::finiteCoordinate<float>( std::numeric_limits<double>::infinity() ) );
        assert( !qMCPOverlaySafety::finiteCoordinate<float>( std::numeric_limits<double>::quiet_NaN() ) );
        assert( !qMCPOverlaySafety::finiteCoordinate<float>( -1e300 ) );
        break;
    case 11:
        assert( qMCPOverlaySafety::boundedCenter<float>( -100, 200, 300, 50 ) );
        assert( !qMCPOverlaySafety::boundedCenter<float>( 0, 0, 1e300, 1 ) );
        assert( !qMCPOverlaySafety::boundedCenter<float>( 3e38, 0, 0, 1e38 ) );
        assert( !qMCPOverlaySafety::boundedCenter<float>( 0, 0, 0, -1 ) );
        assert( !qMCPOverlaySafety::boundedCenter<float>( 0, 0, 0, std::numeric_limits<double>::infinity() ) );
        break;
    // These exercise the production ownership policy across simulated hierarchy
    // edits. They do not exercise CloudCompare's drag/drop or deletion APIs.
    case 12:
    {
        Node destination{ 5, {} };
        const unsigned userId = user.getUniqueID();
        group.children.push_back( &user );
        assert( !owned.ownsTree( &group ) );
        destination.children.push_back( &user );
        group.children.pop_back();
        assert( owned.ownsTree( &group ) );
        assert( destination.getChild( 0 ) == &user );
        assert( destination.getChild( 0 )->getUniqueID() == userId );
        assert( !owned.owns( &user ) );
        // Recovery must not grant ownership to the object that was moved out.
        destination.children.clear();
        group.children.push_back( &user );
        assert( !owned.ownsTree( &group ) );
        break;
    }
    case 13:
    {
        Node destination{ 5, {} };
        vertices.children.push_back( &user );
        assert( !owned.ownsTree( &group ) );
        destination.children.push_back( &user );
        vertices.children.pop_back();
        assert( owned.ownsTree( &group ) );
        assert( group.getChild( 0 ) == &overlay );
        assert( overlay.getChild( 0 ) == &vertices );
        assert( destination.getChild( 0 ) == &user );
        assert( !owned.ownsTree( &destination ) );
        break;
    }
    case 14:
    {
        Node otherUser{ 5, {} }, destination{ 6, {} };
        group.children.push_back( &user );
        vertices.children.push_back( &otherUser );
        assert( !owned.ownsTree( &group ) );
        destination.children.push_back( &user );
        group.children.pop_back();
        assert( !owned.ownsTree( &group ) );
        destination.children.push_back( &otherUser );
        vertices.children.pop_back();
        assert( owned.ownsTree( &group ) );
        assert( destination.getChild( 0 ) == &user );
        assert( destination.getChild( 1 ) == &otherUser );
        break;
    }
    case 15:
    {
        group.children.push_back( &user );
        const auto unchanged = group.children;
        // A failed/no-op drop, or a replacement elsewhere, is not recovery.
        Node copy{ 6, {} }, destination{ 5, { &copy } };
        for ( int attempt = 0; attempt < 3; ++attempt )
            assert( !owned.ownsTree( &group ) );
        assert( group.children == unchanged );
        assert( group.getChild( 1 ) == &user );
        assert( destination.getChild( 0 ) != &user );
        assert( !owned.owns( &user ) );
        break;
    }
    default: return 2;
    }
    return 0;
}
