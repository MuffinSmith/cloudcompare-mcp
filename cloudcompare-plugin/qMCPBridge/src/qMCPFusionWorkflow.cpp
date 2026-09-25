// SPDX-License-Identifier: GPL-2.0-or-later

#include "qMCPFusionWorkflow.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QSet>
#include <QTextStream>

#include <FileIOFilter.h>
#include <PlyFilter.h>
#include <ccGenericMesh.h>
#include <ccGenericPointCloud.h>
#include <ccHObject.h>
#include <ccHObjectCaster.h>
#include <ccMesh.h>
#include <ccPointCloud.h>
#include <ccScalarField.h>
#include <ccGlobalShiftManager.h>

#include "ccMainAppInterface.h"

#include <cmath>
#include <limits>
#include <memory>
#include <vector>

namespace
{
constexpr double FRAME_EPS = 1.0e-9;

ccHObject* findEntityRecursive( ccHObject* parent, unsigned id )
{
    if ( !parent )
    {
        return nullptr;
    }
    if ( parent->getUniqueID() == id )
    {
        return parent;
    }
    for ( unsigned i = 0; i < parent->getChildrenNumber(); ++i )
    {
        if ( ccHObject* found = findEntityRecursive( parent->getChild( i ), id ) )
        {
            return found;
        }
    }
    return nullptr;
}

ccHObject* findEntity( ccMainAppInterface* app, unsigned id )
{
    return findEntityRecursive( app ? app->dbRootObject() : nullptr, id );
}

bool readId( const QJsonObject& object, const char* key, unsigned& id )
{
    const QJsonValue value = object.value( QLatin1String( key ) );
    if ( !value.isDouble() )
    {
        return false;
    }

    const double raw = value.toDouble();
    if ( raw < 0.0
         || raw > static_cast<double>( std::numeric_limits<unsigned>::max() )
         || std::floor( raw ) != raw )
    {
        return false;
    }

    id = static_cast<unsigned>( raw );
    return true;
}

QJsonArray vector3Json( const CCVector3d& value )
{
    return QJsonArray{ value.x, value.y, value.z };
}

QJsonArray vector3Json( const CCVector3& value )
{
    return QJsonArray{ value.x, value.y, value.z };
}

QJsonObject boundsJson( const ccBBox& bounds )
{
    QJsonObject result;
    if ( !bounds.isValid() )
    {
        return result;
    }

    const CCVector3& minimum = bounds.minCorner();
    const CCVector3& maximum = bounds.maxCorner();
    result[ "min" ] = vector3Json( minimum );
    result[ "max" ] = vector3Json( maximum );
    result[ "extent" ] = QJsonArray{
        static_cast<double>( maximum.x - minimum.x ),
        static_cast<double>( maximum.y - minimum.y ),
        static_cast<double>( maximum.z - minimum.z )
    };
    return result;
}

QJsonObject globalBoundsJson( ccGenericPointCloud* cloud )
{
    QJsonObject result;
    if ( !cloud )
    {
        return result;
    }

    const ccBBox bounds = cloud->getOwnBB();
    if ( !bounds.isValid() )
    {
        return result;
    }

    // Global shift/scale is affine with a positive scale, so transforming the
    // two local AABB corners is sufficient and avoids scanning millions of points.
    const CCVector3d a = cloud->toGlobal3d<PointCoordinateType>( bounds.minCorner() );
    const CCVector3d b = cloud->toGlobal3d<PointCoordinateType>( bounds.maxCorner() );
    const CCVector3d minimum(
        std::min( a.x, b.x ),
        std::min( a.y, b.y ),
        std::min( a.z, b.z ) );
    const CCVector3d maximum(
        std::max( a.x, b.x ),
        std::max( a.y, b.y ),
        std::max( a.z, b.z ) );

    result[ "min" ] = vector3Json( minimum );
    result[ "max" ] = vector3Json( maximum );
    result[ "extent" ] = QJsonArray{
        maximum.x - minimum.x,
        maximum.y - minimum.y,
        maximum.z - minimum.z
    };
    return result;
}

QJsonArray scalarFieldsJson( ccPointCloud* cloud )
{
    QJsonArray fields;
    if ( !cloud )
    {
        return fields;
    }

    for ( unsigned i = 0; i < cloud->getNumberOfScalarFields(); ++i )
    {
        const CCCoreLib::ScalarField* sf = cloud->getScalarField( static_cast<int>( i ) );
        if ( sf )
        {
            fields.append( QString::fromStdString( sf->getName() ) );
        }
    }
    return fields;
}

QString kindOf( ccHObject* entity )
{
    if ( !entity )
    {
        return "unknown";
    }
    if ( entity->isKindOf( CC_TYPES::MESH ) )
    {
        return "mesh";
    }
    if ( entity->isKindOf( CC_TYPES::POINT_CLOUD ) )
    {
        return "point_cloud";
    }
    if ( entity->isKindOf( CC_TYPES::HIERARCHY_OBJECT ) )
    {
        return "group";
    }
    return "object";
}

QJsonObject entityDescription( ccHObject* entity, bool recursive )
{
    QJsonObject result;
    if ( !entity )
    {
        return result;
    }

    result[ "id" ] = static_cast<qint64>( entity->getUniqueID() );
    result[ "name" ] = entity->getName();
    result[ "kind" ] = kindOf( entity );
    result[ "class_id" ] = static_cast<int>( entity->getClassID() );
    result[ "visible" ] = entity->isVisible();
    result[ "enabled" ] = entity->isEnabled();
    result[ "child_count" ] = static_cast<int>( entity->getChildrenNumber() );
    result[ "units" ] = "unknown";
    result[ "units_confirmed" ] = false;

    if ( ccHObject* parent = entity->getParent() )
    {
        QJsonObject parentInfo;
        parentInfo[ "id" ] = static_cast<qint64>( parent->getUniqueID() );
        parentInfo[ "name" ] = parent->getName();
        result[ "parent" ] = parentInfo;
    }

    const ccBBox localBounds = entity->getOwnBB();
    if ( localBounds.isValid() )
    {
        result[ "bounds_native" ] = boundsJson( localBounds );
    }

    ccGenericPointCloud* geometry = nullptr;
    ccGenericMesh* genericMesh = nullptr;
    if ( entity->isKindOf( CC_TYPES::MESH ) )
    {
        genericMesh = ccHObjectCaster::ToGenericMesh( entity );
        if ( genericMesh )
        {
            geometry = genericMesh->getAssociatedCloud();
            result[ "triangle_count" ] = static_cast<qint64>( genericMesh->size() );
        }
    }
    else if ( entity->isKindOf( CC_TYPES::POINT_CLOUD ) )
    {
        geometry = ccHObjectCaster::ToGenericPointCloud( entity );
    }

    if ( geometry )
    {
        result[ "point_count" ] = static_cast<qint64>( geometry->size() );
        result[ "has_normals" ] = geometry->hasNormals();
        result[ "has_colors" ] = geometry->hasColors();
        result[ "global_shift" ] = vector3Json( geometry->getGlobalShift() );
        result[ "global_scale" ] = geometry->getGlobalScale();
        result[ "is_shifted" ] = geometry->isShifted();
        result[ "bounds_global_native" ] = globalBoundsJson( geometry );

        if ( ccPointCloud* cloud = dynamic_cast<ccPointCloud*>( geometry ) )
        {
            const QJsonArray fields = scalarFieldsJson( cloud );
            result[ "scalar_fields" ] = fields;
            result[ "has_scalar_fields" ] = !fields.isEmpty();
        }
        else
        {
            result[ "scalar_fields" ] = QJsonArray();
            result[ "has_scalar_fields" ] = false;
        }
    }

    if ( recursive && entity->getChildrenNumber() )
    {
        QJsonArray children;
        for ( unsigned i = 0; i < entity->getChildrenNumber(); ++i )
        {
            children.append( entityDescription( entity->getChild( i ), true ) );
        }
        result[ "children" ] = children;
    }

    return result;
}

bool compatibleFrames( const ccGenericPointCloud* a, const ccGenericPointCloud* b )
{
    if ( !a || !b )
    {
        return false;
    }
    const double scaleDelta = std::abs( a->getGlobalScale() - b->getGlobalScale() );
    const double shiftDelta2 = ( a->getGlobalShift() - b->getGlobalShift() ).norm2d();
    return scaleDelta <= FRAME_EPS && shiftDelta2 <= FRAME_EPS * FRAME_EPS;
}

void attachToDestination(
    ccMainAppInterface* app,
    ccHObject* entity,
    ccHObject* destination )
{
    if ( destination && destination != app->dbRootObject() )
    {
        destination->addChild( entity );
    }
    app->addToDB( entity, false, true, false, false );
}

bool resolveDestination(
    ccMainAppInterface* app,
    const QJsonObject& params,
    ccHObject*& destination,
    QString& error )
{
    destination = app->dbRootObject();
    if ( !params.contains( "destination_group_id" ) )
    {
        return true;
    }

    unsigned id = 0;
    if ( !readId( params, "destination_group_id", id ) )
    {
        error = "destination_group_id must be a valid numeric entity ID";
        return false;
    }

    destination = findEntity( app, id );
    if ( !destination )
    {
        error = QString( "Destination group %1 was not found" ).arg( id );
        return false;
    }

    if ( destination != app->dbRootObject()
         && !destination->isKindOf( CC_TYPES::HIERARCHY_OBJECT ) )
    {
        error = QString( "Entity %1 is not a hierarchy/group destination" ).arg( id );
        return false;
    }
    return true;
}

ccHObject* firstGeometry( ccHObject* root, bool wantMesh )
{
    if ( !root )
    {
        return nullptr;
    }
    if ( wantMesh ? root->isKindOf( CC_TYPES::MESH ) : root->isKindOf( CC_TYPES::POINT_CLOUD ) )
    {
        return root;
    }
    for ( unsigned i = 0; i < root->getChildrenNumber(); ++i )
    {
        if ( ccHObject* found = firstGeometry( root->getChild( i ), wantMesh ) )
        {
            return found;
        }
    }
    return nullptr;
}

bool nearlyEqual( double a, double b, double scale = 1.0 )
{
    const double tolerance = 1.0e-5 * std::max( 1.0, std::abs( scale ) );
    return std::abs( a - b ) <= tolerance;
}

bool boundsEquivalent( const QJsonObject& a, const QJsonObject& b )
{
    const QJsonArray amin = a.value( "min" ).toArray();
    const QJsonArray amax = a.value( "max" ).toArray();
    const QJsonArray bmin = b.value( "min" ).toArray();
    const QJsonArray bmax = b.value( "max" ).toArray();
    if ( amin.size() != 3 || amax.size() != 3 || bmin.size() != 3 || bmax.size() != 3 )
    {
        return false;
    }

    for ( int i = 0; i < 3; ++i )
    {
        const double span = amax.at( i ).toDouble() - amin.at( i ).toDouble();
        if ( !nearlyEqual( amin.at( i ).toDouble(), bmin.at( i ).toDouble(), span )
             || !nearlyEqual( amax.at( i ).toDouble(), bmax.at( i ).toDouble(), span ) )
        {
            return false;
        }
    }
    return true;
}

QJsonObject capabilities()
{
    QJsonObject result;
    result[ "protocol_version" ] = 1;
    result[ "workflow_revision" ] = 1;
    result[ "units_policy" ] =
        "Coordinates are reported in native units. Units remain unknown unless supplied by the caller.";
    result[ "global_coordinate_export" ] =
        "CloudCompare PLY and OBJ writers emit global coordinates using stored global shift/scale.";

    result[ "plugin_version" ] = "0.3.0";

    QJsonArray bridgeOperations{
        "ping",
        "scene.list",
        "selection.get",
        "selection.set",
        "file.load",
        "entity.rename",
        "entity.set_state",
        "entity.delete",
        "entity.transform",
        "view",
        "view.capture",
        "capabilities.get",
        "entity.clone",
        "cloud.merge",
        "mesh.reconstruct",
        "mesh.simplify",
        "entity.export"
    };
    result[ "bridge_operations" ] = bridgeOperations;

    QJsonArray workflowOperations{
        "entity.clone",
        "cloud.merge",
        "mesh.reconstruct",
        "mesh.simplify",
        "entity.export"
    };
    result[ "workflow_operations" ] = workflowOperations;

    QJsonArray meshing;
    {
        QJsonObject method;
        method[ "id" ] = "delaunay_2_5d_best_fit_plane";
        method[ "available" ] = true;
        method[ "full_3d" ] = false;
        method[ "hole_preservation_guaranteed" ] = false;
        method[ "warning" ] =
            "Projects the cloud to a best-fit plane. Unsuitable for a complete multi-sided fan assembly.";
        method[ "parameters" ] = QJsonArray{ "max_edge_length" };
        meshing.append( method );
    }
    {
        QJsonObject method;
        method[ "id" ] = "delaunay_2_5d_axis_aligned";
        method[ "available" ] = true;
        method[ "full_3d" ] = false;
        method[ "hole_preservation_guaranteed" ] = false;
        method[ "warning" ] =
            "Axis-aligned 2.5D triangulation cannot represent overlapping surfaces along the projection axis.";
        method[ "parameters" ] = QJsonArray{ "max_edge_length", "projection_dimension" };
        meshing.append( method );
    }
    {
        QJsonObject method;
        method[ "id" ] = "poisson";
        method[ "available" ] = false;
        method[ "full_3d" ] = true;
        method[ "requires_explicit_hole_filling_opt_in" ] = true;
        method[ "warning" ] =
            "Not exposed by qMCPBridge because Poisson is watertight-oriented and may bridge real slots and openings.";
        meshing.append( method );
    }
    {
        QJsonObject method;
        method[ "id" ] = "external_local_surface_reconstruction";
        method[ "available" ] = false;
        method[ "full_3d" ] = true;
        method[ "dependency" ] =
            "An external reconstruction backend (for example a ball-pivoting implementation) must be installed and integrated.";
        method[ "hole_preservation_guaranteed" ] = false;
        meshing.append( method );
    }
    result[ "meshing_methods" ] = meshing;

    QJsonArray simplification;
    {
        QJsonObject method;
        method[ "id" ] = "cloudcompare_core";
        method[ "available" ] = false;
        method[ "reason" ] =
            "CloudCompare core exposes display LOD decimation, not a topology-preserving export simplifier.";
        simplification.append( method );
    }
    {
        QJsonObject method;
        method[ "id" ] = "external_qem";
        method[ "available" ] = false;
        method[ "dependency" ] =
            "Optional external simplifier required. Do not confuse display LOD with persisted mesh simplification.";
        simplification.append( method );
    }
    result[ "simplification_methods" ] = simplification;

    QJsonObject execution;
    execution[ "model" ] = "synchronous_gui_thread";
    execution[ "status_reporting" ] = "final_response_only";
    execution[ "cancellation_supported" ] = false;
    execution[ "note" ] =
        "The current localhost protocol is request/response. Operations are kept transactional where practical; "
        "external long-running backends should add async job/status/cancel before being advertised.";
    result[ "execution" ] = execution;

    return result;
}

bool cloneEntities(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const QJsonArray ids = params.value( "ids" ).toArray();
    if ( ids.isEmpty() )
    {
        error = "entity.clone requires at least one source ID";
        return true;
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    const QString suffix = params.value( "name_suffix" ).toString( ".mcp_clone" );

    struct PendingClone
    {
        unsigned sourceId = 0;
        ccHObject* source = nullptr;
        ccHObject* clone = nullptr;
    };
    std::vector<PendingClone> pending;
    QSet<unsigned> seen;

    for ( const QJsonValue& value : ids )
    {
        if ( !value.isDouble() )
        {
            error = "entity.clone IDs must all be numeric";
            break;
        }
        const double raw = value.toDouble();
        if ( raw < 0.0 || raw > static_cast<double>( std::numeric_limits<unsigned>::max() ) )
        {
            error = "entity.clone contains an invalid entity ID";
            break;
        }

        const unsigned id = static_cast<unsigned>( raw );
        if ( seen.contains( id ) )
        {
            continue;
        }
        seen.insert( id );

        ccHObject* source = findEntity( app, id );
        if ( !source )
        {
            error = QString( "Entity %1 was not found" ).arg( id );
            break;
        }

        ccHObject* clone = nullptr;
        if ( source->isA( CC_TYPES::POINT_CLOUD ) )
        {
            clone = static_cast<ccPointCloud*>( source )->cloneThis( nullptr, false );
        }
        else if ( source->isA( CC_TYPES::MESH ) )
        {
            clone = static_cast<ccMesh*>( source )->cloneMesh();
        }
        else
        {
            error = QString( "Entity %1 has unsupported clone type '%2'" )
                        .arg( id )
                        .arg( kindOf( source ) );
            break;
        }

        if ( !clone )
        {
            error = QString( "Failed to clone entity %1 (likely insufficient memory)" ).arg( id );
            break;
        }

        clone->setName( source->getName() + suffix );
        pending.push_back( PendingClone{ id, source, clone } );
        QCoreApplication::processEvents();
    }

    if ( !error.isEmpty() )
    {
        for ( PendingClone& item : pending )
        {
            delete item.clone;
            item.clone = nullptr;
        }
        return true;
    }

    QJsonArray mappings;
    for ( PendingClone& item : pending )
    {
        attachToDestination( app, item.clone, destination );
        QJsonObject mapping;
        mapping[ "source_id" ] = static_cast<qint64>( item.sourceId );
        mapping[ "clone_id" ] = static_cast<qint64>( item.clone->getUniqueID() );
        mapping[ "source" ] = entityDescription( item.source, false );
        mapping[ "clone" ] = entityDescription( item.clone, false );
        mappings.append( mapping );
        item.clone = nullptr; // ownership is now in the DB tree
    }

    app->refreshAll();
    app->updateUI();

    QJsonObject out;
    out[ "mappings" ] = mappings;
    out[ "source_entities_unchanged" ] = true;
    result = out;
    return true;
}

bool mergeClouds(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const QJsonArray ids = params.value( "ids" ).toArray();
    if ( ids.isEmpty() )
    {
        error = "cloud.merge requires one or more explicit cloud IDs";
        return true;
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    std::vector<ccPointCloud*> inputs;
    QJsonArray inputIds;
    QSet<unsigned> seen;
    quint64 expectedCount = 0;

    for ( const QJsonValue& value : ids )
    {
        if ( !value.isDouble() )
        {
            error = "cloud.merge IDs must all be numeric";
            return true;
        }
        const unsigned id = static_cast<unsigned>( value.toDouble() );
        if ( seen.contains( id ) )
        {
            continue;
        }
        seen.insert( id );

        ccHObject* entity = findEntity( app, id );
        if ( !entity )
        {
            error = QString( "Entity %1 was not found" ).arg( id );
            return true;
        }
        if ( !entity->isA( CC_TYPES::POINT_CLOUD ) )
        {
            error = QString( "Entity %1 is not a standalone point cloud" ).arg( id );
            return true;
        }

        ccPointCloud* cloud = static_cast<ccPointCloud*>( entity );
        inputs.push_back( cloud );
        inputIds.append( static_cast<qint64>( id ) );
        expectedCount += static_cast<quint64>( cloud->size() );
    }

    if ( expectedCount > std::numeric_limits<unsigned>::max() )
    {
        error = "Merged cloud would exceed CloudCompare's supported point-index range";
        return true;
    }

    const QString framePolicy = params.value( "coordinate_frame_policy" ).toString( "strict" );
    if ( framePolicy != "strict" && framePolicy != "convert_to_first" )
    {
        error = "coordinate_frame_policy must be 'strict' or 'convert_to_first'";
        return true;
    }

    ccPointCloud* first = inputs.front();
    for ( size_t i = 1; i < inputs.size(); ++i )
    {
        if ( !compatibleFrames( first, inputs[i] ) && framePolicy == "strict" )
        {
            error = QString(
                "Input cloud coordinate frames differ. Refusing merge. "
                "Use coordinate_frame_policy='convert_to_first' only when that conversion is explicitly intended." );
            return true;
        }
    }

    std::unique_ptr<ccPointCloud> merged( new ccPointCloud(
        params.value( "name" ).toString( "MCP merged cloud" ) ) );

    if ( first->isShifted() )
    {
        merged->setGlobalShift( first->getGlobalShift() );
        merged->setGlobalScale( first->getGlobalScale() );
    }

    QJsonArray attributeNotes;
    bool anyColors = false;
    bool allColors = true;
    bool anyNormals = false;
    bool allNormals = true;
    QSet<QString> allFieldNames;
    QSet<QString> commonFieldNames;
    bool firstFields = true;

    for ( ccPointCloud* input : inputs )
    {
        anyColors |= input->hasColors();
        allColors &= input->hasColors();
        anyNormals |= input->hasNormals();
        allNormals &= input->hasNormals();

        QSet<QString> thisFields;
        for ( unsigned sfIndex = 0; sfIndex < input->getNumberOfScalarFields(); ++sfIndex )
        {
            const CCCoreLib::ScalarField* sf = input->getScalarField( static_cast<int>( sfIndex ) );
            if ( sf )
            {
                thisFields.insert( QString::fromStdString( sf->getName() ) );
            }
        }
        allFieldNames.unite( thisFields );
        if ( firstFields )
        {
            commonFieldNames = thisFields;
            firstFields = false;
        }
        else
        {
            commonFieldNames.intersect( thisFields );
        }

        std::unique_ptr<ccPointCloud> working;
        ccPointCloud* appendSource = input;
        if ( !compatibleFrames( first, input ) && framePolicy == "convert_to_first" )
        {
            working.reset( input->cloneThis( nullptr, true ) );
            if ( !working )
            {
                error = "Failed to allocate a coordinate-frame conversion copy";
                return true;
            }

            for ( unsigned pointIndex = 0; pointIndex < working->size(); ++pointIndex )
            {
                const CCVector3* local = input->getPoint( pointIndex );
                const CCVector3d global = input->toGlobal3d<PointCoordinateType>( *local );
                const CCVector3d targetLocal = first->toLocal3d<double>( global );
                CCVector3* targetPoint = const_cast<CCVector3*>( working->getPointPersistentPtr( pointIndex ) );
                *targetPoint = targetLocal.toPC();
            }
            working->setGlobalShift( first->getGlobalShift() );
            working->setGlobalScale( first->getGlobalScale() );
            working->notifyGeometryUpdate();
            appendSource = working.get();
        }

        const unsigned before = merged->size();
        merged->append( appendSource, before, true, false );
        if ( merged->size() != before + appendSource->size() )
        {
            error = "CloudCompare could not allocate the complete merged cloud; no result was added";
            return true;
        }
        QCoreApplication::processEvents();
    }

    if ( anyColors && !allColors )
    {
        attributeNotes.append(
            "Some inputs lacked colors; CloudCompare fills those points with white in the merged cloud." );
    }
    if ( anyNormals && !allNormals )
    {
        attributeNotes.append(
            "Some inputs lacked normals; CloudCompare fills those points with the default/zero normal index." );
    }
    if ( allFieldNames != commonFieldNames )
    {
        attributeNotes.append(
            "Scalar fields not present on every input are retained with NaN values where an input lacked that field." );
    }

    if ( merged->size() != expectedCount )
    {
        error = QString( "Merged point-count verification failed: expected %1, got %2" )
                    .arg( expectedCount )
                    .arg( merged->size() );
        return true;
    }

    merged->showColors( anyColors );
    merged->showNormals( anyNormals );
    merged->setVisible( true );
    merged->setEnabled( true );

    ccPointCloud* liveMerged = merged.release();
    attachToDestination( app, liveMerged, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveMerged, false );
    out[ "input_ids" ] = inputIds;
    out[ "expected_point_count" ] = static_cast<qint64>( expectedCount );
    out[ "point_count_verified" ] = true;
    out[ "coordinate_frame_policy" ] = framePolicy;
    out[ "attribute_handling" ] = attributeNotes;
    out[ "originals_preserved" ] = true;
    result = out;
    return true;
}

bool reconstructMesh(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "cloud_id", id ) )
    {
        error = "mesh.reconstruct requires a numeric cloud_id";
        return true;
    }

    ccHObject* sourceEntity = findEntity( app, id );
    if ( !sourceEntity )
    {
        error = QString( "Entity %1 was not found" ).arg( id );
        return true;
    }
    if ( !sourceEntity->isA( CC_TYPES::POINT_CLOUD ) )
    {
        error = "mesh.reconstruct currently requires a standalone ccPointCloud";
        return true;
    }

    const QString method = params.value( "method" ).toString();
    if ( method != "delaunay_2_5d_best_fit_plane"
         && method != "delaunay_2_5d_axis_aligned" )
    {
        error =
            "This bridge exposes only CloudCompare core 2.5D Delaunay reconstruction. "
            "Poisson is intentionally not auto-exposed; a local full-3D backend must be integrated explicitly.";
        return true;
    }

    if ( !params.value( "acknowledge_2_5d_limitations" ).toBool( false ) )
    {
        error =
            "2.5D reconstruction requires acknowledge_2_5d_limitations=true. "
            "It is not suitable for a complete multi-sided fan assembly and does not guarantee preservation of holes.";
        return true;
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    ccPointCloud* source = static_cast<ccPointCloud*>( sourceEntity );
    std::unique_ptr<ccPointCloud> working( source->cloneThis( nullptr, true ) );
    if ( !working )
    {
        error = "Failed to allocate a working clone for mesh reconstruction";
        return true;
    }

    const double maxEdgeRaw = params.value( "max_edge_length" ).toDouble( 0.0 );
    if ( maxEdgeRaw < 0.0 )
    {
        error = "max_edge_length must be non-negative in native coordinate units";
        return true;
    }

    int dimension = params.value( "projection_dimension" ).toInt( 2 );
    if ( dimension < 0 || dimension > 2 )
    {
        error = "projection_dimension must be 0, 1, or 2";
        return true;
    }

    const CCCoreLib::TRIANGULATION_TYPES type =
        method == "delaunay_2_5d_axis_aligned"
            ? CCCoreLib::DELAUNAY_2D_AXIS_ALIGNED
            : CCCoreLib::DELAUNAY_2D_BEST_LS_PLANE;

    ccMesh* mesh = ccMesh::Triangulate(
        working.get(),
        type,
        false,
        static_cast<PointCoordinateType>( maxEdgeRaw ),
        static_cast<unsigned char>( dimension ) );

    if ( !mesh )
    {
        error = "CloudCompare failed to create the requested 2.5D mesh";
        return true;
    }

    mesh->setName( params.value( "name" ).toString( source->getName() + ".mcp_mesh" ) );
    working->setEnabled( false );
    mesh->addChild( working.release() );

    attachToDestination( app, mesh, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( mesh, false );
    out[ "source_id" ] = static_cast<qint64>( id );
    out[ "method" ] = method;
    out[ "max_edge_length_native" ] = maxEdgeRaw;
    out[ "projection_dimension" ] = dimension;
    out[ "source_preserved" ] = true;
    out[ "hole_preservation_guaranteed" ] = false;
    out[ "warning" ] =
        "This is 2.5D Delaunay reconstruction. It can bridge gaps within the projection and cannot represent a complete multi-sided assembly.";
    result = out;
    return true;
}

bool simplifyMesh(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    Q_UNUSED( app );

    unsigned id = 0;
    if ( !readId( params, "mesh_id", id ) )
    {
        error = "mesh.simplify requires a numeric mesh_id";
        return true;
    }

    const qint64 target = static_cast<qint64>( params.value( "target_triangles" ).toDouble( 0 ) );
    if ( target <= 0 )
    {
        error = "target_triangles must be greater than zero";
        return true;
    }

    QJsonObject out;
    out[ "supported" ] = false;
    out[ "mesh_id" ] = static_cast<qint64>( id );
    out[ "requested_target_triangles" ] = target;
    out[ "reason" ] =
        "CloudCompare core does not expose a persisted topology-preserving mesh simplifier through its plugin API. "
        "Display LOD decimation is not suitable for export.";
    out[ "required_backend" ] =
        "Integrate an external simplifier that can preserve boundaries/sharp features and report geometric deviation.";
    out[ "source_preserved" ] = true;
    result = out;
    return true;
}

bool exportEntity(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "entity_id", id ) )
    {
        error = "entity.export requires a numeric entity_id";
        return true;
    }

    ccHObject* entity = findEntity( app, id );
    if ( !entity )
    {
        error = QString( "Entity %1 was not found" ).arg( id );
        return true;
    }

    const QString requestedPath = params.value( "path" ).toString();
    if ( requestedPath.isEmpty() )
    {
        error = "entity.export requires an absolute path";
        return true;
    }
    QFileInfo targetInfo( requestedPath );
    if ( !targetInfo.isAbsolute() )
    {
        error = "entity.export refuses relative paths; provide an explicit absolute path";
        return true;
    }

    const QString suffix = targetInfo.suffix().toLower();
    if ( suffix != "ply" && suffix != "obj" )
    {
        error = "entity.export supports only binary PLY point clouds and OBJ triangle meshes";
        return true;
    }

    const bool overwrite = params.value( "overwrite" ).toBool( false );
    if ( targetInfo.exists() && !overwrite )
    {
        error = QString( "Output already exists and overwrite=false: %1" ).arg( targetInfo.absoluteFilePath() );
        return true;
    }

    ccGenericPointCloud* sourceCloud = nullptr;
    ccGenericMesh* sourceMesh = nullptr;
    if ( suffix == "ply" )
    {
        if ( !entity->isKindOf( CC_TYPES::POINT_CLOUD ) || entity->isKindOf( CC_TYPES::MESH ) )
        {
            error = "PLY workflow export requires a point-cloud entity";
            return true;
        }
        sourceCloud = ccHObjectCaster::ToGenericPointCloud( entity );
    }
    else
    {
        if ( !entity->isKindOf( CC_TYPES::MESH ) )
        {
            error = "OBJ mesh export requires a real triangle mesh; point-cloud-only OBJ export is refused";
            return true;
        }
        sourceMesh = ccHObjectCaster::ToGenericMesh( entity );
        if ( !sourceMesh || sourceMesh->size() == 0 )
        {
            error = "OBJ mesh export requires at least one triangle";
            return true;
        }
        sourceCloud = sourceMesh->getAssociatedCloud();
    }

    if ( !sourceCloud )
    {
        error = "Selected entity has no exportable geometry";
        return true;
    }

    QDir parentDir = targetInfo.dir();
    if ( !parentDir.exists() )
    {
        error = QString( "Output directory does not exist: %1" ).arg( parentDir.absolutePath() );
        return true;
    }

    const QString finalPath = targetInfo.absoluteFilePath();
    const QString tempPath = finalPath + ".mcp-partial";
    QFile::remove( tempPath );

    FileIOFilter::Shared filter = FileIOFilter::FindBestFilterForExtension( suffix );
    if ( !filter )
    {
        error = QString( "No CloudCompare export filter is registered for .%1" ).arg( suffix );
        return true;
    }

    if ( suffix == "ply" )
    {
        // PLY_DEFAULT is CloudCompare's binary mode. Disable the dialog below.
        PlyFilter::SetDefaultOutputFormat( PLY_DEFAULT );
    }

    FileIOFilter::SaveParameters saveParams;
    saveParams.alwaysDisplaySaveDialog = false;
    saveParams.parentWidget = app->getMainWindow();

    const CC_FILE_ERROR saveError = FileIOFilter::SaveToFile(
        entity,
        tempPath,
        saveParams,
        filter );
    if ( saveError != CC_FERR_NO_ERROR )
    {
        QFile::remove( tempPath );
        error = QString( "CloudCompare export failed with error code %1" ).arg( static_cast<int>( saveError ) );
        return true;
    }

    if ( overwrite && QFileInfo::exists( finalPath ) && !QFile::remove( finalPath ) )
    {
        QFile::remove( tempPath );
        error = QString( "Could not replace existing output file: %1" ).arg( finalPath );
        return true;
    }
    if ( !QFile::rename( tempPath, finalPath ) )
    {
        QFile::remove( tempPath );
        error = QString( "Could not atomically move completed export into place: %1" ).arg( finalPath );
        return true;
    }

    bool objHasFaces = true;
    qint64 objFaceLines = 0;
    if ( suffix == "obj" )
    {
        objHasFaces = false;
        QFile objFile( finalPath );
        if ( objFile.open( QIODevice::ReadOnly | QIODevice::Text ) )
        {
            QTextStream stream( &objFile );
            while ( !stream.atEnd() )
            {
                const QString line = stream.readLine();
                if ( line.startsWith( "f " ) )
                {
                    objHasFaces = true;
                    ++objFaceLines;
                }
            }
        }
        if ( !objHasFaces )
        {
            QFile::remove( finalPath );
            error = "OBJ validation failed: exported file contained no face records";
            return true;
        }
    }

    FileIOFilter::LoadParameters loadParams;
    loadParams.alwaysDisplayLoadDialog = false;
    loadParams.shiftHandlingMode = ccGlobalShiftManager::NO_DIALOG_AUTO_SHIFT;
    loadParams.parentWidget = app->getMainWindow();

    CC_FILE_ERROR loadError = CC_FERR_NO_ERROR;
    std::unique_ptr<ccHObject> loaded(
        FileIOFilter::LoadFromFile( finalPath, loadParams, loadError ) );
    if ( !loaded || loadError != CC_FERR_NO_ERROR )
    {
        QFile::remove( finalPath );
        error = QString( "Export read-back validation failed with error code %1; output was removed" )
                    .arg( static_cast<int>( loadError ) );
        return true;
    }

    ccHObject* loadedGeometry = firstGeometry( loaded.get(), suffix == "obj" );
    if ( !loadedGeometry )
    {
        QFile::remove( finalPath );
        error = "Export read-back validation found no expected geometry; output was removed";
        return true;
    }

    ccGenericPointCloud* loadedCloud = suffix == "obj"
        ? ccHObjectCaster::ToGenericMesh( loadedGeometry )->getAssociatedCloud()
        : ccHObjectCaster::ToGenericPointCloud( loadedGeometry );
    ccGenericMesh* loadedMesh = suffix == "obj"
        ? ccHObjectCaster::ToGenericMesh( loadedGeometry )
        : nullptr;

    const bool pointsMatch = loadedCloud && loadedCloud->size() == sourceCloud->size();
    const bool trianglesMatch = !sourceMesh
        || ( loadedMesh && loadedMesh->size() == sourceMesh->size() );
    const bool boundsMatch = loadedCloud
        && boundsEquivalent( globalBoundsJson( sourceCloud ), globalBoundsJson( loadedCloud ) );

    if ( !pointsMatch || !trianglesMatch || !boundsMatch )
    {
        QFile::remove( finalPath );
        error = QString(
            "Export read-back verification failed (points=%1, triangles=%2, bounds=%3); output was removed" )
                    .arg( pointsMatch )
                    .arg( trianglesMatch )
                    .arg( boundsMatch );
        return true;
    }

    QFileInfo completed( finalPath );
    QJsonArray warnings;
    if ( suffix == "obj" )
    {
        warnings.append( "OBJ does not reliably encode physical units." );
        warnings.append( "Scalar fields are not expected to round-trip through OBJ." );
        warnings.append( "CloudCompare may emit material/texture sidecar files when the mesh uses them." );
    }
    else
    {
        warnings.append(
            "PLY stores the written global coordinates but does not preserve CloudCompare's global-shift bookkeeping as a native PLY concept." );
    }

    QJsonObject out;
    out[ "path" ] = QDir::toNativeSeparators( completed.absoluteFilePath() );
    out[ "format" ] = suffix.toUpper();
    out[ "encoding" ] = suffix == "ply" ? "binary" : "text";
    out[ "file_size_bytes" ] = completed.size();
    out[ "point_count" ] = static_cast<qint64>( sourceCloud->size() );
    out[ "triangle_count" ] = sourceMesh ? static_cast<qint64>( sourceMesh->size() ) : 0;
    out[ "has_normals" ] = sourceCloud->hasNormals();
    out[ "has_colors" ] = sourceCloud->hasColors();
    if ( ccPointCloud* sourcePointCloud = dynamic_cast<ccPointCloud*>( sourceCloud ) )
    {
        out[ "scalar_fields" ] = scalarFieldsJson( sourcePointCloud );
    }
    else
    {
        out[ "scalar_fields" ] = QJsonArray();
    }
    out[ "obj_face_records" ] = objFaceLines;
    out[ "coordinates_written" ] = "global";
    out[ "source_global_shift" ] = vector3Json( sourceCloud->getGlobalShift() );
    out[ "source_global_scale" ] = sourceCloud->getGlobalScale();
    out[ "intended_import_units" ] = params.value( "intended_import_units" ).toString( "unknown" );
    out[ "units_confirmed_by_source" ] = false;
    out[ "bounds_global_native" ] = globalBoundsJson( sourceCloud );
    out[ "readback_verified" ] = true;
    out[ "counts_verified" ] = pointsMatch && trianglesMatch;
    out[ "bounds_verified" ] = boundsMatch;
    out[ "attribute_loss_warnings" ] = warnings;
    result = out;
    return true;
}
}

namespace qMCPFusionWorkflow
{
QJsonObject describeEntity( ccHObject* entity, bool recursive )
{
    return entityDescription( entity, recursive );
}

bool dispatch(
    ccMainAppInterface* app,
    const QString& method,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    if ( method == "capabilities.get" )
    {
        QJsonObject out = capabilities();
        out[ "application_version" ] = QCoreApplication::applicationVersion();
        out[ "plugin" ] = "qMCPBridge";
        result = out;
        return true;
    }
    if ( method == "entity.clone" )
    {
        return cloneEntities( app, params, result, error );
    }
    if ( method == "cloud.merge" )
    {
        return mergeClouds( app, params, result, error );
    }
    if ( method == "mesh.reconstruct" )
    {
        return reconstructMesh( app, params, result, error );
    }
    if ( method == "mesh.simplify" )
    {
        return simplifyMesh( app, params, result, error );
    }
    if ( method == "entity.export" )
    {
        return exportEntity( app, params, result, error );
    }
    return false;
}
}
