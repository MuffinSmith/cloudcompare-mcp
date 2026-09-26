// SPDX-License-Identifier: GPL-2.0-or-later

#include "qMCPFusionWorkflow.h"

#include <QByteArray>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QMainWindow>
#include <QSet>
#include <QTextStream>

#include <FileIOFilter.h>
#include <PlyFilter.h>
#include <CloudSamplingTools.h>
#include <CCConst.h>
#include <DistanceComputationTools.h>
#include <PointCloud.h>
#include <ReferenceCloud.h>
#include <RegistrationTools.h>
#include <ccBBox.h>
#include <ccGenericMesh.h>
#include <ccGenericPointCloud.h>
#include <ccHObject.h>
#include <ccHObjectCaster.h>
#include <ccMesh.h>
#include <ccPointCloud.h>
#include <ccScalarField.h>
#include <ccGlobalShiftManager.h>
#include <ccGLMatrix.h>

#include "ccMainAppInterface.h"
#include <ccPickingHub.h>
#include <ccPickingListener.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <memory>
#include <vector>

namespace
{
constexpr double FRAME_EPS = 1.0e-9;

void addApplicationVersion( QJsonObject& result )
{
    const QString runtimeVersion = QCoreApplication::applicationVersion();
    if ( !runtimeVersion.isEmpty() )
    {
        result[ "application_version" ] = runtimeVersion;
        result[ "application_version_source" ] = "runtime_qt";
        return;
    }

#ifdef QMCP_CLOUDCOMPARE_BUILD_VERSION
    result[ "application_version" ] = QStringLiteral( QMCP_CLOUDCOMPARE_BUILD_VERSION );
    result[ "application_version_source" ] = "plugin_build_source_tree";
#else
    result[ "application_version" ] = QString();
    result[ "application_version_source" ] = "unavailable";
#endif
}

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
        const QJsonObject nativeBounds = boundsJson( localBounds );
        result[ "bounds_native" ] = nativeBounds;
        // Backwards-compatible alias used by the first live-bridge revision.
        result[ "bounding_box" ] = nativeBounds;
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

bool readVector3(
    const QJsonObject& object,
    const char* key,
    CCVector3d& value,
    QString& error )
{
    const QJsonArray array = object.value( QLatin1String( key ) ).toArray();
    if ( array.size() != 3 )
    {
        error = QString( "%1 must contain exactly three numeric values" ).arg( key );
        return false;
    }

    double components[3];
    for ( int i = 0; i < 3; ++i )
    {
        if ( !array.at( i ).isDouble() )
        {
            error = QString( "%1 must contain exactly three numeric values" ).arg( key );
            return false;
        }
        components[i] = array.at( i ).toDouble();
        if ( !std::isfinite( components[i] ) )
        {
            error = QString( "%1 values must be finite" ).arg( key );
            return false;
        }
    }

    value = CCVector3d( components[0], components[1], components[2] );
    return true;
}

QJsonArray matrixJson( const ccGLMatrix& matrix )
{
    QJsonArray out;
    const float* values = matrix.data();
    for ( int i = 0; i < 16; ++i )
    {
        out.append( static_cast<double>( values[i] ) );
    }
    return out;
}

bool readPointList(
    const QJsonObject& object,
    const char* key,
    std::vector<CCVector3d>& points,
    QString& error )
{
    const QJsonValue value = object.value( QLatin1String( key ) );
    if ( !value.isArray() )
    {
        error = QString( "%1 must be an array of [x,y,z] points" ).arg( key );
        return false;
    }

    const QJsonArray array = value.toArray();
    if ( array.size() < 3 )
    {
        error = QString( "%1 must contain at least three points" ).arg( key );
        return false;
    }

    points.clear();
    points.reserve( static_cast<size_t>( array.size() ) );
    for ( int pointIndex = 0; pointIndex < array.size(); ++pointIndex )
    {
        const QJsonArray point = array.at( pointIndex ).toArray();
        if ( point.size() != 3 )
        {
            error = QString( "%1[%2] must contain exactly three numeric values" )
                        .arg( key )
                        .arg( pointIndex );
            return false;
        }

        double coordinates[3];
        for ( int axis = 0; axis < 3; ++axis )
        {
            if ( !point.at( axis ).isDouble() )
            {
                error = QString( "%1[%2] must contain exactly three numeric values" )
                            .arg( key )
                            .arg( pointIndex );
                return false;
            }
            coordinates[axis] = point.at( axis ).toDouble();
            if ( !std::isfinite( coordinates[axis] ) )
            {
                error = QString( "%1[%2] coordinates must be finite" )
                            .arg( key )
                            .arg( pointIndex );
                return false;
            }
        }
        points.emplace_back( coordinates[0], coordinates[1], coordinates[2] );
    }

    return true;
}

double percentileSorted( const std::vector<double>& sorted, double fraction )
{
    if ( sorted.empty() )
    {
        return 0.0;
    }
    const double position = fraction * static_cast<double>( sorted.size() - 1 );
    const size_t lower = static_cast<size_t>( std::floor( position ) );
    const size_t upper = static_cast<size_t>( std::ceil( position ) );
    if ( lower == upper )
    {
        return sorted[lower];
    }
    const double weight = position - static_cast<double>( lower );
    return sorted[lower] * ( 1.0 - weight ) + sorted[upper] * weight;
}

double minimumBoundingBoxDistanceSquared(
    const ccBBox& a,
    const ccBBox& b )
{
    if ( !a.isValid() || !b.isValid() )
    {
        return std::numeric_limits<double>::infinity();
    }

    const CCVector3& aMin = a.minCorner();
    const CCVector3& aMax = a.maxCorner();
    const CCVector3& bMin = b.minCorner();
    const CCVector3& bMax = b.maxCorner();

    double squared = 0.0;
    for ( int axis = 0; axis < 3; ++axis )
    {
        double separation = 0.0;
        if ( aMax.u[axis] < bMin.u[axis] )
        {
            separation =
                static_cast<double>( bMin.u[axis] - aMax.u[axis] );
        }
        else if ( bMax.u[axis] < aMin.u[axis] )
        {
            separation =
                static_cast<double>( aMin.u[axis] - bMax.u[axis] );
        }
        squared += separation * separation;
    }
    return squared;
}

QJsonObject numericStats( std::vector<double> values )
{
    QJsonObject out;
    values.erase(
        std::remove_if(
            values.begin(),
            values.end(),
            []( double value ) { return !std::isfinite( value ); } ),
        values.end() );

    out[ "count" ] = static_cast<qint64>( values.size() );
    if ( values.empty() )
    {
        return out;
    }

    double sum = 0.0;
    double sumSquares = 0.0;
    for ( double value : values )
    {
        sum += value;
        sumSquares += value * value;
    }

    std::sort( values.begin(), values.end() );
    const double mean = sum / static_cast<double>( values.size() );
    double varianceSum = 0.0;
    for ( double value : values )
    {
        const double delta = value - mean;
        varianceSum += delta * delta;
    }

    out[ "min" ] = values.front();
    out[ "max" ] = values.back();
    out[ "mean" ] = mean;
    out[ "rms" ] = std::sqrt( sumSquares / static_cast<double>( values.size() ) );
    out[ "stddev" ] = std::sqrt( varianceSum / static_cast<double>( values.size() ) );
    out[ "median" ] = percentileSorted( values, 0.50 );
    out[ "p95" ] = percentileSorted( values, 0.95 );
    out[ "p99" ] = percentileSorted( values, 0.99 );

    const int histogramBins = 20;
    QJsonArray edges;
    QJsonArray counts;
    const double minimum = values.front();
    const double maximum = values.back();
    if ( maximum > minimum )
    {
        std::vector<qint64> binCounts( histogramBins, 0 );
        for ( double value : values )
        {
            int bin = static_cast<int>(
                ( value - minimum ) / ( maximum - minimum ) * histogramBins );
            if ( bin >= histogramBins )
                bin = histogramBins - 1;
            if ( bin < 0 )
                bin = 0;
            ++binCounts[static_cast<size_t>( bin )];
        }
        for ( int i = 0; i <= histogramBins; ++i )
        {
            edges.append(
                minimum
                + ( maximum - minimum )
                    * static_cast<double>( i ) / static_cast<double>( histogramBins ) );
        }
        for ( qint64 count : binCounts )
        {
            counts.append( count );
        }
    }
    else
    {
        edges.append( minimum );
        edges.append( maximum );
        counts.append( static_cast<qint64>( values.size() ) );
    }

    QJsonObject histogram;
    histogram[ "bin_edges" ] = edges;
    histogram[ "counts" ] = counts;
    out[ "histogram" ] = histogram;
    return out;
}

std::vector<double> scalarValues( const ccScalarField* field )
{
    std::vector<double> values;
    if ( !field )
    {
        return values;
    }
    values.reserve( field->currentSize() );
    for ( unsigned i = 0; i < field->currentSize(); ++i )
    {
        values.push_back( static_cast<double>( field->getValue( i ) ) );
    }
    return values;
}

QString uniqueScalarFieldName( ccPointCloud* cloud, const QString& baseName )
{
    QString candidate = baseName;
    int suffix = 2;
    while ( true )
    {
        const QByteArray candidateUtf8 = candidate.toUtf8();
        if ( cloud->getScalarFieldIndexByName( candidateUtf8.constData() ) < 0 )
        {
            return candidate;
        }
        candidate = QString( "%1 %2" ).arg( baseName ).arg( suffix++ );
    }
}

ccGenericMesh* requireMesh(
    ccMainAppInterface* app,
    unsigned id,
    QString& error )
{
    ccHObject* entity = findEntity( app, id );
    if ( !entity )
    {
        error = QString( "Entity %1 was not found" ).arg( id );
        return nullptr;
    }
    if ( !entity->isKindOf( CC_TYPES::MESH ) )
    {
        error = QString( "Entity %1 is not a triangle mesh" ).arg( id );
        return nullptr;
    }

    ccGenericMesh* mesh = ccHObjectCaster::ToGenericMesh( entity );
    if ( !mesh || !mesh->getAssociatedCloud() )
    {
        error = QString( "Entity %1 does not expose usable mesh geometry" ).arg( id );
        return nullptr;
    }
    return mesh;
}

QJsonObject pointCloudPointDescription(
    ccPointCloud* cloud,
    unsigned pointIndex )
{
    QJsonObject out;
    if ( !cloud || pointIndex >= cloud->size() )
    {
        return out;
    }

    const CCVector3* point = cloud->getPoint( pointIndex );
    if ( !point )
    {
        return out;
    }

    out[ "entity_id" ] = static_cast<qint64>( cloud->getUniqueID() );
    out[ "entity_name" ] = cloud->getName();
    out[ "point_index" ] = static_cast<qint64>( pointIndex );
    out[ "position_native_local" ] = vector3Json( *point );
    out[ "position_global" ] =
        vector3Json( cloud->toGlobal3d<PointCoordinateType>( *point ) );
    out[ "global_shift" ] = vector3Json( cloud->getGlobalShift() );
    out[ "global_scale" ] = cloud->getGlobalScale();

    if ( cloud->hasColors() )
    {
        const ccColor::Rgba& color = cloud->getPointColor( pointIndex );
        QJsonObject colorJson;
        colorJson[ "r" ] = static_cast<int>( color.r );
        colorJson[ "g" ] = static_cast<int>( color.g );
        colorJson[ "b" ] = static_cast<int>( color.b );
        colorJson[ "a" ] = static_cast<int>( color.a );
        out[ "rgba" ] = colorJson;
    }

    if ( cloud->hasNormals() )
    {
        out[ "normal" ] = vector3Json( cloud->getPointNormal( pointIndex ) );
    }

    QJsonObject scalarValuesJson;
    for ( unsigned fieldIndex = 0;
          fieldIndex < cloud->getNumberOfScalarFields();
          ++fieldIndex )
    {
        const CCCoreLib::ScalarField* field =
            cloud->getScalarField( static_cast<int>( fieldIndex ) );
        if ( !field || pointIndex >= field->currentSize() )
        {
            continue;
        }

        const QString fieldName = QString::fromStdString( field->getName() );
        const double value =
            static_cast<double>( field->getValue( pointIndex ) );
        if ( std::isfinite( value ) )
        {
            scalarValuesJson[ fieldName ] = value;
        }
        else
        {
            scalarValuesJson[ fieldName ] = QJsonValue();
        }
    }
    out[ "scalar_values" ] = scalarValuesJson;
    return out;
}

struct StoredPick
{
    QJsonObject json;
    CCVector3d globalPosition;
};

QJsonObject pickedItemDescription(
    const ccPickingListener::PickedItem& item,
    CCVector3d& globalPosition )
{
    QJsonObject out;
    ccHObject* entity = item.entity;
    if ( !entity )
    {
        return out;
    }

    out[ "entity_id" ] = static_cast<qint64>( entity->getUniqueID() );
    out[ "entity_name" ] = entity->getName();
    out[ "entity_kind" ] = kindOf( entity );
    out[ "item_index" ] = static_cast<qint64>( item.itemIndex );
    out[ "entity_center" ] = item.entityCenter;

    QJsonObject click;
    click[ "x" ] = item.clickPoint.x();
    click[ "y" ] = item.clickPoint.y();
    out[ "click" ] = click;

    ccGenericPointCloud* coordinateCloud = nullptr;

    if ( entity->isKindOf( CC_TYPES::POINT_CLOUD ) )
    {
        ccPointCloud* cloud = ccHObjectCaster::ToPointCloud( entity );
        coordinateCloud = cloud;

        if ( cloud && !item.entityCenter && item.itemIndex < cloud->size() )
        {
            QJsonObject pointInfo =
                pointCloudPointDescription( cloud, item.itemIndex );
            for ( auto it = pointInfo.begin(); it != pointInfo.end(); ++it )
            {
                out[ it.key() ] = it.value();
            }

            const QJsonArray globalArray =
                out.value( "position_global" ).toArray();
            if ( globalArray.size() == 3 )
            {
                globalPosition = CCVector3d(
                    globalArray.at( 0 ).toDouble(),
                    globalArray.at( 1 ).toDouble(),
                    globalArray.at( 2 ).toDouble() );
            }
        }
    }
    else if ( entity->isKindOf( CC_TYPES::MESH ) )
    {
        ccGenericMesh* mesh = ccHObjectCaster::ToGenericMesh( entity );
        if ( mesh )
        {
            coordinateCloud = mesh->getAssociatedCloud();
        }

        out[ "triangle_index" ] = static_cast<qint64>( item.itemIndex );
        out[ "barycentric" ] =
            QJsonArray{ item.uvw.x, item.uvw.y, item.uvw.z };
    }

    if ( !out.contains( "position_native_local" ) )
    {
        out[ "position_native_local" ] = vector3Json( item.P3D );
        if ( coordinateCloud )
        {
            globalPosition =
                coordinateCloud->toGlobal3d<PointCoordinateType>( item.P3D );
            out[ "position_global" ] = vector3Json( globalPosition );
            out[ "global_shift" ] =
                vector3Json( coordinateCloud->getGlobalShift() );
            out[ "global_scale" ] = coordinateCloud->getGlobalScale();
        }
        else
        {
            globalPosition = item.P3D.toDouble();
            out[ "position_global" ] = vector3Json( globalPosition );
        }
    }

    return out;
}

class MetrologyPickingSession final : public ccPickingListener
{
public:
    ~MetrologyPickingSession() override
    {
        stop();
    }

    bool start(
        ccMainAppInterface* app,
        int maxPicks,
        bool exclusive,
        const QSet<unsigned>& allowedIds,
        QString& error )
    {
        if ( m_active )
        {
            error =
                "A metrology picking session is already active; stop it before starting another.";
            return false;
        }

        m_hub = app ? app->pickingHub() : nullptr;
        if ( !m_hub )
        {
            error = "CloudCompare does not expose a picking hub to qMCPBridge.";
            return false;
        }
        if ( !m_hub->activeWindow() )
        {
            error = "No active CloudCompare 3D window is available for point picking.";
            return false;
        }

        m_picks.clear();
        m_allowedIds = allowedIds;
        m_maxPicks = maxPicks;
        m_exclusive = exclusive;

        if ( !m_hub->addListener(
                 this,
                 exclusive,
                 true,
                 ccGLWindowInterface::POINT_OR_TRIANGLE_PICKING ) )
        {
            m_hub = nullptr;
            error =
                "CloudCompare rejected the picking listener. Close other exclusive picking tools and try again.";
            return false;
        }

        m_active = true;
        return true;
    }

    void stop()
    {
        if ( m_active && m_hub )
        {
            m_hub->removeListener( this, true );
        }
        m_active = false;
        m_hub = nullptr;
    }

    void clear()
    {
        m_picks.clear();
    }

    bool active() const
    {
        return m_active;
    }

    size_t count() const
    {
        return m_picks.size();
    }

    const StoredPick* pick( int index ) const
    {
        if ( index < 0 || index >= static_cast<int>( m_picks.size() ) )
        {
            return nullptr;
        }
        return &m_picks[static_cast<size_t>( index )];
    }

    QJsonObject status() const
    {
        QJsonObject out;
        out[ "active" ] = m_active;
        out[ "pick_count" ] = static_cast<qint64>( m_picks.size() );
        out[ "max_picks" ] = m_maxPicks;
        out[ "exclusive" ] = m_exclusive;

        QJsonArray allowed;
        for ( unsigned id : m_allowedIds )
        {
            allowed.append( static_cast<qint64>( id ) );
        }
        out[ "allowed_entity_ids" ] = allowed;

        QJsonArray picksJson;
        for ( size_t i = 0; i < m_picks.size(); ++i )
        {
            QJsonObject pickJson = m_picks[i].json;
            pickJson[ "pick_index" ] = static_cast<qint64>( i );
            picksJson.append( pickJson );
        }
        out[ "picks" ] = picksJson;
        return out;
    }

    void onItemPicked( const PickedItem& item ) override
    {
        if ( !m_active || !item.entity )
        {
            return;
        }

        const unsigned entityId = item.entity->getUniqueID();
        if ( !m_allowedIds.isEmpty()
             && !m_allowedIds.contains( entityId ) )
        {
            return;
        }

        CCVector3d globalPosition;
        QJsonObject json =
            pickedItemDescription( item, globalPosition );
        if ( json.isEmpty() )
        {
            return;
        }

        StoredPick stored;
        stored.json = json;
        stored.globalPosition = globalPosition;
        m_picks.push_back( stored );

        if ( m_maxPicks > 0
             && static_cast<int>( m_picks.size() ) >= m_maxPicks )
        {
            if ( m_hub )
            {
                m_hub->removeListener( this, true );
            }
            m_active = false;
            m_hub = nullptr;
        }
    }

private:
    ccPickingHub* m_hub = nullptr;
    std::vector<StoredPick> m_picks;
    QSet<unsigned> m_allowedIds;
    int m_maxPicks = 0;
    bool m_active = false;
    bool m_exclusive = true;
};

MetrologyPickingSession g_metrologyPickingSession;

bool startMetrologyPicking(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const int maxPicks = params.value( "max_picks" ).toInt( 8 );
    if ( maxPicks < 1 || maxPicks > 100 )
    {
        error = "max_picks must be between 1 and 100";
        return true;
    }

    QSet<unsigned> allowedIds;
    if ( params.contains( "allowed_entity_ids" ) )
    {
        const QJsonArray values =
            params.value( "allowed_entity_ids" ).toArray();
        for ( const QJsonValue& value : values )
        {
            if ( !value.isDouble() )
            {
                error =
                    "allowed_entity_ids must contain numeric entity IDs";
                return true;
            }

            const double raw = value.toDouble();
            if ( raw < 0.0
                 || raw > static_cast<double>(
                        std::numeric_limits<unsigned>::max() )
                 || std::floor( raw ) != raw )
            {
                error =
                    "allowed_entity_ids must contain valid entity IDs";
                return true;
            }

            const unsigned id = static_cast<unsigned>( raw );
            if ( !findEntity( app, id ) )
            {
                error =
                    QString( "Allowed picking entity %1 was not found" )
                        .arg( id );
                return true;
            }
            allowedIds.insert( id );
        }
    }

    const bool exclusive =
        params.value( "exclusive" ).toBool( true );
    if ( !g_metrologyPickingSession.start(
             app,
             maxPicks,
             exclusive,
             allowedIds,
             error ) )
    {
        return true;
    }

    QJsonObject out = g_metrologyPickingSession.status();
    out[ "instruction" ] =
        "Point picking is active in the current CloudCompare 3D window. Click visible cloud points or mesh triangles.";
    result = out;
    return true;
}

bool metrologyPickingStatus(
    QJsonValue& result )
{
    result = g_metrologyPickingSession.status();
    return true;
}

bool clearMetrologyPicks(
    QJsonValue& result )
{
    g_metrologyPickingSession.clear();
    result = g_metrologyPickingSession.status();
    return true;
}

bool stopMetrologyPicking(
    QJsonValue& result )
{
    g_metrologyPickingSession.stop();
    result = g_metrologyPickingSession.status();
    return true;
}

bool inspectCloudPoint(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned entityId = 0;
    if ( !readId( params, "entity_id", entityId ) )
    {
        error = "metrology.point_info requires numeric entity_id";
        return true;
    }

    ccPointCloud* cloud =
        requireStandaloneCloud( app, entityId, error );
    if ( !cloud )
    {
        return true;
    }

    const QJsonValue indexValue = params.value( "point_index" );
    if ( !indexValue.isDouble() )
    {
        error = "point_index must be a non-negative integer";
        return true;
    }

    const double rawIndex = indexValue.toDouble();
    if ( rawIndex < 0.0
         || rawIndex >= static_cast<double>( cloud->size() )
         || std::floor( rawIndex ) != rawIndex )
    {
        error = QString(
            "point_index must be between 0 and %1" )
                    .arg(
                        cloud->size() == 0
                            ? 0
                            : cloud->size() - 1 );
        return true;
    }

    result = pointCloudPointDescription(
        cloud,
        static_cast<unsigned>( rawIndex ) );
    return true;
}

bool readPickIndex(
    const QJsonObject& params,
    const char* key,
    int defaultIndex,
    int& index,
    QString& error )
{
    if ( !params.contains( key ) )
    {
        index = defaultIndex;
        return true;
    }

    const QJsonValue value =
        params.value( QLatin1String( key ) );
    if ( !value.isDouble() )
    {
        error = QString( "%1 must be an integer pick index" ).arg( key );
        return false;
    }

    const double raw = value.toDouble();
    if ( raw < 0.0
         || raw > static_cast<double>(
                std::numeric_limits<int>::max() )
         || std::floor( raw ) != raw )
    {
        error = QString( "%1 must be a non-negative integer pick index" ).arg( key );
        return false;
    }

    index = static_cast<int>( raw );
    return true;
}

bool measurePickedDistance(
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const int count =
        static_cast<int>( g_metrologyPickingSession.count() );
    if ( count < 2 )
    {
        error = "At least two captured picks are required for a distance measurement";
        return true;
    }

    int aIndex = count - 2;
    int bIndex = count - 1;
    if ( !readPickIndex( params, "pick_a", aIndex, aIndex, error )
         || !readPickIndex( params, "pick_b", bIndex, bIndex, error ) )
    {
        return true;
    }

    const StoredPick* a = g_metrologyPickingSession.pick( aIndex );
    const StoredPick* b = g_metrologyPickingSession.pick( bIndex );
    if ( !a || !b )
    {
        error = "Requested pick index is outside the captured pick list";
        return true;
    }

    const CCVector3d delta =
        b->globalPosition - a->globalPosition;
    const double distance =
        std::sqrt( delta.norm2d() );
    const double distanceXY =
        std::sqrt( delta.x * delta.x + delta.y * delta.y );

    QJsonObject out;
    out[ "coordinate_space" ] = "global";
    out[ "units" ] = "native";
    out[ "units_confirmed" ] = false;
    out[ "pick_a" ] = aIndex;
    out[ "pick_b" ] = bIndex;
    out[ "point_a" ] = vector3Json( a->globalPosition );
    out[ "point_b" ] = vector3Json( b->globalPosition );
    out[ "delta" ] = vector3Json( delta );
    out[ "absolute_delta" ] =
        QJsonArray{
            std::abs( delta.x ),
            std::abs( delta.y ),
            std::abs( delta.z )
        };
    out[ "distance_native" ] = distance;
    out[ "distance_xy_native" ] = distanceXY;
    result = out;
    return true;
}

bool measurePickedAngle(
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const int count =
        static_cast<int>( g_metrologyPickingSession.count() );
    if ( count < 3 )
    {
        error = "At least three captured picks are required for an angle measurement";
        return true;
    }

    int aIndex = count - 3;
    int bIndex = count - 2;
    int cIndex = count - 1;
    if ( !readPickIndex( params, "pick_a", aIndex, aIndex, error )
         || !readPickIndex( params, "pick_b", bIndex, bIndex, error )
         || !readPickIndex( params, "pick_c", cIndex, cIndex, error ) )
    {
        return true;
    }

    const StoredPick* a = g_metrologyPickingSession.pick( aIndex );
    const StoredPick* b = g_metrologyPickingSession.pick( bIndex );
    const StoredPick* c = g_metrologyPickingSession.pick( cIndex );
    if ( !a || !b || !c )
    {
        error = "Requested pick index is outside the captured pick list";
        return true;
    }

    const CCVector3d ba =
        a->globalPosition - b->globalPosition;
    const CCVector3d bc =
        c->globalPosition - b->globalPosition;
    const double baLength = std::sqrt( ba.norm2d() );
    const double bcLength = std::sqrt( bc.norm2d() );
    if ( baLength <= std::numeric_limits<double>::epsilon()
         || bcLength <= std::numeric_limits<double>::epsilon() )
    {
        error =
            "Angle measurement requires three distinct points with non-zero legs";
        return true;
    }

    double cosine =
        ( ba.x * bc.x + ba.y * bc.y + ba.z * bc.z )
        / ( baLength * bcLength );
    cosine = std::max( -1.0, std::min( 1.0, cosine ) );
    const double radians = std::acos( cosine );
    const double degrees =
        radians * 180.0 / std::acos( -1.0 );

    QJsonObject out;
    out[ "coordinate_space" ] = "global";
    out[ "units" ] = "native";
    out[ "units_confirmed" ] = false;
    out[ "pick_a" ] = aIndex;
    out[ "pick_b_vertex" ] = bIndex;
    out[ "pick_c" ] = cIndex;
    out[ "point_a" ] = vector3Json( a->globalPosition );
    out[ "point_b" ] = vector3Json( b->globalPosition );
    out[ "point_c" ] = vector3Json( c->globalPosition );
    out[ "leg_ba_native" ] = baLength;
    out[ "leg_bc_native" ] = bcLength;
    out[ "angle_radians" ] = radians;
    out[ "angle_degrees" ] = degrees;
    result = out;
    return true;
}

QJsonArray partialCloneWarnings( int warnings )
{
    QJsonArray out;
    if ( warnings & ccPointCloud::WRN_OUT_OF_MEM_FOR_COLORS )
        out.append( "colors_not_copied" );
    if ( warnings & ccPointCloud::WRN_OUT_OF_MEM_FOR_NORMALS )
        out.append( "normals_not_copied" );
    if ( warnings & ccPointCloud::WRN_OUT_OF_MEM_FOR_SFS )
        out.append( "scalar_fields_not_copied" );
    if ( warnings & ccPointCloud::WRN_OUT_OF_MEM_FOR_FWF )
        out.append( "full_waveform_data_not_copied" );
    return out;
}

ccPointCloud* requireStandaloneCloud(
    ccMainAppInterface* app,
    unsigned id,
    QString& error )
{
    ccHObject* entity = findEntity( app, id );
    if ( !entity )
    {
        error = QString( "Entity %1 was not found" ).arg( id );
        return nullptr;
    }
    if ( !entity->isA( CC_TYPES::POINT_CLOUD ) )
    {
        error = QString( "Entity %1 is not a standalone point cloud" ).arg( id );
        return nullptr;
    }
    return static_cast<ccPointCloud*>( entity );
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
         && !destination->isA( CC_TYPES::HIERARCHY_OBJECT ) )
    {
        error = QString( "Entity %1 is not a plain hierarchy/group destination" ).arg( id );
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

bool createGroup(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    const QString name = params.value( "name" ).toString().trimmed();
    if ( name.isEmpty() )
    {
        error = "group.create requires a non-empty name";
        return true;
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    std::unique_ptr<ccHObject> group( new ccHObject( name ) );
    group->setVisible( true );
    group->setEnabled( true );

    ccHObject* liveGroup = group.release();
    attachToDestination( app, liveGroup, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveGroup, false );
    out[ "created" ] = true;
    result = out;
    return true;
}

bool cropCloud(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "cloud_id", id ) )
    {
        error = "cloud.crop requires a numeric cloud_id";
        return true;
    }

    ccPointCloud* source = requireStandaloneCloud( app, id, error );
    if ( !source )
    {
        return true;
    }

    CCVector3d requestedMin;
    CCVector3d requestedMax;
    if ( !readVector3( params, "min", requestedMin, error )
         || !readVector3( params, "max", requestedMax, error ) )
    {
        return true;
    }

    for ( unsigned axis = 0; axis < 3; ++axis )
    {
        if ( requestedMax.u[axis] <= requestedMin.u[axis] )
        {
            error = "cloud.crop requires max to be greater than min on all three axes";
            return true;
        }
    }

    const QString coordinateSpace = params.value( "coordinate_space" ).toString( "native_local" );
    if ( coordinateSpace != "native_local" && coordinateSpace != "global" )
    {
        error = "coordinate_space must be 'native_local' or 'global'";
        return true;
    }

    CCVector3d localA = requestedMin;
    CCVector3d localB = requestedMax;
    if ( coordinateSpace == "global" )
    {
        localA = source->toLocal3d<double>( requestedMin );
        localB = source->toLocal3d<double>( requestedMax );
    }

    CCVector3 localMin(
        static_cast<PointCoordinateType>( std::min( localA.x, localB.x ) ),
        static_cast<PointCoordinateType>( std::min( localA.y, localB.y ) ),
        static_cast<PointCoordinateType>( std::min( localA.z, localB.z ) ) );
    CCVector3 localMax(
        static_cast<PointCoordinateType>( std::max( localA.x, localB.x ) ),
        static_cast<PointCoordinateType>( std::max( localA.y, localB.y ) ),
        static_cast<PointCoordinateType>( std::max( localA.z, localB.z ) ) );

    const bool keepInside = params.value( "keep_inside" ).toBool( true );
    const ccBBox box( localMin, localMax, true );
    std::unique_ptr<CCCoreLib::ReferenceCloud> selection( source->crop( box, keepInside ) );
    if ( !selection )
    {
        error = "CloudCompare failed to evaluate the crop selection";
        return true;
    }
    if ( selection->size() == 0 )
    {
        error = QString( "Crop selected no points on the requested %1" )
                    .arg( keepInside ? "inside" : "outside" );
        return true;
    }

    int warnings = 0;
    std::unique_ptr<ccPointCloud> cropped( source->partialClone( selection.get(), &warnings, false ) );
    if ( !cropped )
    {
        error = "CloudCompare could not allocate the cropped point cloud";
        return true;
    }

    cropped->setName(
        params.value( "name" ).toString(
            source->getName() + ( keepInside ? ".mcp_crop_inside" : ".mcp_crop_outside" ) ) );
    cropped->setVisible( true );
    cropped->setEnabled( true );

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    ccPointCloud* liveResult = cropped.release();
    attachToDestination( app, liveResult, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveResult, false );
    out[ "source_id" ] = static_cast<qint64>( id );
    out[ "source_preserved" ] = true;
    out[ "coordinate_space" ] = coordinateSpace;
    out[ "requested_min" ] = vector3Json( requestedMin );
    out[ "requested_max" ] = vector3Json( requestedMax );
    out[ "keep_inside" ] = keepInside;
    out[ "source_point_count" ] = static_cast<qint64>( source->size() );
    out[ "selected_point_count" ] = static_cast<qint64>( liveResult->size() );
    out[ "attribute_copy_warnings" ] = partialCloneWarnings( warnings );
    result = out;
    return true;
}

bool subsampleCloud(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "cloud_id", id ) )
    {
        error = "cloud.subsample requires a numeric cloud_id";
        return true;
    }

    ccPointCloud* source = requireStandaloneCloud( app, id, error );
    if ( !source )
    {
        return true;
    }
    if ( source->size() == 0 )
    {
        error = "Cannot subsample an empty cloud";
        return true;
    }

    const QString method = params.value( "method" ).toString().toLower();
    std::unique_ptr<CCCoreLib::ReferenceCloud> selection;
    QJsonObject settings;

    if ( method == "random" )
    {
        const qint64 requested = static_cast<qint64>( params.value( "target_points" ).toDouble( 0 ) );
        if ( requested <= 0 || requested >= static_cast<qint64>( source->size() ) )
        {
            error = QString( "random subsampling requires target_points between 1 and %1" )
                        .arg( source->size() - 1 );
            return true;
        }
        selection.reset(
            CCCoreLib::CloudSamplingTools::subsampleCloudRandomly(
                source,
                static_cast<unsigned>( requested ) ) );
        settings[ "target_points" ] = requested;
    }
    else if ( method == "spatial" )
    {
        const double spacing = params.value( "min_spacing" ).toDouble( 0.0 );
        if ( !std::isfinite( spacing ) || spacing <= 0.0 )
        {
            error = "spatial subsampling requires min_spacing > 0 in native coordinate units";
            return true;
        }
        CCCoreLib::CloudSamplingTools::SFModulationParams modulation( false );
        selection.reset(
            CCCoreLib::CloudSamplingTools::resampleCloudSpatially(
                source,
                static_cast<PointCoordinateType>( spacing ),
                modulation ) );
        settings[ "min_spacing_native" ] = spacing;
    }
    else if ( method == "octree" )
    {
        const int level = params.value( "octree_level" ).toInt( 0 );
        if ( level < 1 || level > static_cast<int>( CCCoreLib::DgmOctree::MAX_OCTREE_LEVEL ) )
        {
            error = QString( "octree_level must be between 1 and %1" )
                        .arg( CCCoreLib::DgmOctree::MAX_OCTREE_LEVEL );
            return true;
        }
        selection.reset(
            CCCoreLib::CloudSamplingTools::subsampleCloudWithOctreeAtLevel(
                source,
                static_cast<unsigned char>( level ),
                CCCoreLib::CloudSamplingTools::NEAREST_POINT_TO_CELL_CENTER ) );
        settings[ "octree_level" ] = level;
        settings[ "cell_rule" ] = "nearest_point_to_cell_center";
    }
    else
    {
        error = "method must be 'random', 'spatial', or 'octree'";
        return true;
    }

    if ( !selection )
    {
        error = "CloudCompare subsampling failed";
        return true;
    }
    if ( selection->size() == 0 )
    {
        error = "CloudCompare subsampling produced an empty selection";
        return true;
    }

    int warnings = 0;
    std::unique_ptr<ccPointCloud> sampled( source->partialClone( selection.get(), &warnings, false ) );
    if ( !sampled )
    {
        error = "CloudCompare could not allocate the subsampled cloud";
        return true;
    }

    sampled->setName(
        params.value( "name" ).toString( source->getName() + ".mcp_subsample_" + method ) );
    sampled->setVisible( true );
    sampled->setEnabled( true );

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    ccPointCloud* liveResult = sampled.release();
    attachToDestination( app, liveResult, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveResult, false );
    out[ "source_id" ] = static_cast<qint64>( id );
    out[ "source_preserved" ] = true;
    out[ "method" ] = method;
    out[ "settings" ] = settings;
    out[ "source_point_count" ] = static_cast<qint64>( source->size() );
    out[ "output_point_count" ] = static_cast<qint64>( liveResult->size() );
    out[ "retained_fraction" ] =
        static_cast<double>( liveResult->size() ) / static_cast<double>( source->size() );
    out[ "attribute_copy_warnings" ] = partialCloneWarnings( warnings );
    result = out;
    return true;
}

bool sorFilterCloud(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "cloud_id", id ) )
    {
        error = "cloud.filter_sor requires a numeric cloud_id";
        return true;
    }

    ccPointCloud* source = requireStandaloneCloud( app, id, error );
    if ( !source )
    {
        return true;
    }

    const int knn = params.value( "knn" ).toInt( 6 );
    const double nSigma = params.value( "n_sigma" ).toDouble( 1.0 );
    if ( knn < 2 )
    {
        error = "knn must be at least 2";
        return true;
    }
    if ( !std::isfinite( nSigma ) || nSigma <= 0.0 )
    {
        error = "n_sigma must be greater than zero";
        return true;
    }

    std::unique_ptr<CCCoreLib::ReferenceCloud> selection(
        CCCoreLib::CloudSamplingTools::sorFilter( source, knn, nSigma ) );
    if ( !selection )
    {
        error = "CloudCompare SOR filtering failed";
        return true;
    }
    if ( selection->size() == 0 )
    {
        error = "SOR filtering rejected every point; no result was added";
        return true;
    }

    int warnings = 0;
    std::unique_ptr<ccPointCloud> filtered( source->partialClone( selection.get(), &warnings, false ) );
    if ( !filtered )
    {
        error = "CloudCompare could not allocate the SOR-filtered cloud";
        return true;
    }

    filtered->setName(
        params.value( "name" ).toString( source->getName() + ".mcp_sor" ) );
    filtered->setVisible( true );
    filtered->setEnabled( true );

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    ccPointCloud* liveResult = filtered.release();
    attachToDestination( app, liveResult, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveResult, false );
    out[ "source_id" ] = static_cast<qint64>( id );
    out[ "source_preserved" ] = true;
    out[ "knn" ] = knn;
    out[ "n_sigma" ] = nSigma;
    out[ "source_point_count" ] = static_cast<qint64>( source->size() );
    out[ "output_point_count" ] = static_cast<qint64>( liveResult->size() );
    out[ "removed_point_count" ] =
        static_cast<qint64>( source->size() - liveResult->size() );
    out[ "attribute_copy_warnings" ] = partialCloneWarnings( warnings );
    result = out;
    return true;
}

bool computeCloudNormals(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned id = 0;
    if ( !readId( params, "cloud_id", id ) )
    {
        error = "cloud.compute_normals requires a numeric cloud_id";
        return true;
    }

    ccPointCloud* source = requireStandaloneCloud( app, id, error );
    if ( !source )
    {
        return true;
    }

    const double radius = params.value( "radius" ).toDouble( 0.0 );
    if ( !std::isfinite( radius ) || radius <= 0.0 )
    {
        error = "radius must be greater than zero in native coordinate units";
        return true;
    }

    const QString modelName = params.value( "model" ).toString( "LS" ).toUpper();
    CCCoreLib::LOCAL_MODEL_TYPES model = CCCoreLib::LS;
    if ( modelName == "LS" )
        model = CCCoreLib::LS;
    else if ( modelName == "QUADRIC" )
        model = CCCoreLib::QUADRIC;
    else if ( modelName == "TRIANGULATION" )
        model = CCCoreLib::TRI;
    else
    {
        error = "model must be 'LS', 'QUADRIC', or 'TRIANGULATION'";
        return true;
    }

    const bool orientMst = params.value( "orient_with_mst" ).toBool( false );
    const int mstNeighbors = params.value( "mst_neighbors" ).toInt( 6 );
    if ( orientMst && ( mstNeighbors < 2 || mstNeighbors > 1000 ) )
    {
        error = "mst_neighbors must be between 2 and 1000";
        return true;
    }

    std::unique_ptr<ccPointCloud> working( source->cloneThis( nullptr, true ) );
    if ( !working )
    {
        error = "CloudCompare could not allocate a working clone for normal computation";
        return true;
    }

    if ( !working->computeNormalsWithOctree(
             model,
             ccNormalVectors::UNDEFINED,
             static_cast<PointCoordinateType>( radius ),
             nullptr ) )
    {
        error = "CloudCompare normal computation failed; no result was added";
        return true;
    }

    if ( orientMst && !working->orientNormalsWithMST(
                          static_cast<unsigned>( mstNeighbors ),
                          nullptr ) )
    {
        error = "CloudCompare MST normal orientation failed; no result was added";
        return true;
    }

    working->setName(
        params.value( "name" ).toString( source->getName() + ".mcp_normals" ) );
    working->showNormals( true );
    working->setVisible( true );
    working->setEnabled( true );

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    ccPointCloud* liveResult = working.release();
    attachToDestination( app, liveResult, destination );
    app->refreshAll();
    app->updateUI();

    QJsonObject out = entityDescription( liveResult, false );
    out[ "source_id" ] = static_cast<qint64>( id );
    out[ "source_preserved" ] = true;
    out[ "model" ] = modelName;
    out[ "radius_native" ] = radius;
    out[ "orient_with_mst" ] = orientMst;
    if ( orientMst )
        out[ "mst_neighbors" ] = mstNeighbors;
    out[ "normals_computed" ] = liveResult->hasNormals();
    result = out;
    return true;
}

bool registerCloudsICP(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned dataId = 0;
    unsigned modelId = 0;
    if ( !readId( params, "data_id", dataId ) || !readId( params, "model_id", modelId ) )
    {
        error = "cloud.register_icp requires numeric data_id and model_id";
        return true;
    }
    if ( dataId == modelId )
    {
        error = "cloud.register_icp requires different data and model entities";
        return true;
    }

    ccPointCloud* dataSource = requireStandaloneCloud( app, dataId, error );
    if ( !dataSource )
    {
        return true;
    }
    ccPointCloud* modelSource = requireStandaloneCloud( app, modelId, error );
    if ( !modelSource )
    {
        return true;
    }
    if ( dataSource->size() < 3 || modelSource->size() < 3 )
    {
        error = "ICP requires at least three points in both data and model clouds";
        return true;
    }
    if ( !compatibleFrames( dataSource, modelSource ) )
    {
        error =
            "Data and model coordinate frames differ. Live ICP currently requires identical "
            "CloudCompare global shift/scale metadata; convert working copies to a common frame first.";
        return true;
    }

    const double overlapPercent = params.value( "overlap_percent" ).toDouble( 100.0 );
    if ( !std::isfinite( overlapPercent ) || overlapPercent < 1.0 || overlapPercent > 100.0 )
    {
        error = "overlap_percent must be between 1 and 100";
        return true;
    }

    const int maxIterations = params.value( "max_iterations" ).toInt( 20 );
    if ( maxIterations < 1 || maxIterations > 10000 )
    {
        error = "max_iterations must be between 1 and 10000";
        return true;
    }

    const int samplingLimit = params.value( "random_sampling_limit" ).toInt( 50000 );
    if ( samplingLimit < 3 )
    {
        error = "random_sampling_limit must be at least 3";
        return true;
    }

    const bool previewOnly = params.value( "preview_only" ).toBool( true );
    const bool filterFarthest = params.value( "filter_out_farthest_points" ).toBool( false );

    QString requestedName;
    if ( params.contains( "name" ) )
    {
        requestedName = params.value( "name" ).toString().trimmed();
        if ( requestedName.isEmpty() )
        {
            error = "cloud.register_icp name must be non-empty when supplied";
            return true;
        }
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
    {
        return true;
    }

    std::unique_ptr<ccPointCloud> registrationData( dataSource->cloneThis( nullptr, true ) );
    std::unique_ptr<ccPointCloud> registrationModel( modelSource->cloneThis( nullptr, true ) );
    if ( !registrationData || !registrationModel )
    {
        error = "Could not allocate temporary ICP working copies";
        return true;
    }

    if ( !registrationData->enableScalarField() )
    {
        error = "Could not allocate the temporary ICP distance scalar field";
        return true;
    }

    CCCoreLib::ICPRegistrationTools::Parameters icp;
    icp.convType = CCCoreLib::ICPRegistrationTools::MAX_ITER_CONVERGENCE;
    icp.nbMaxIterations = static_cast<unsigned>( maxIterations );
    icp.adjustScale = false;
    icp.filterOutFarthestPoints = filterFarthest;
    icp.samplingLimit = static_cast<unsigned>( samplingLimit );
    icp.finalOverlapRatio = overlapPercent / 100.0;
    icp.modelWeights = nullptr;
    icp.dataWeights = nullptr;
    icp.transformationFilters = CCCoreLib::RegistrationTools::SKIP_NONE;
    icp.maxThreadCount = 0;
    icp.useC2MSignedDistances = false;
    icp.robustC2MSignedDistances = true;
    icp.normalsMatching = CCCoreLib::ICPRegistrationTools::NO_NORMAL;

    CCCoreLib::PointProjectionTools::Transformation transform;
    double finalRMS = 0.0;
    unsigned finalPointCount = 0;
    const CCCoreLib::ICPRegistrationTools::RESULT_TYPE icpResult =
        CCCoreLib::ICPRegistrationTools::Register(
            registrationModel.get(),
            nullptr,
            registrationData.get(),
            icp,
            transform,
            finalRMS,
            finalPointCount,
            nullptr );

    if ( icpResult >= CCCoreLib::ICPRegistrationTools::ICP_ERROR )
    {
        error = QString( "CloudCompare ICP failed with result code %1" )
                    .arg( static_cast<int>( icpResult ) );
        return true;
    }

    ccGLMatrix transformMatrix;
    transformMatrix.toIdentity();
    bool hasTransform = false;
    if ( icpResult == CCCoreLib::ICPRegistrationTools::ICP_APPLY_TRANSFO )
    {
        transformMatrix = FromCCLibMatrix<double, float>( transform.R, transform.T, transform.s );
        hasTransform = true;
    }

    QJsonObject out;
    out[ "data_id" ] = static_cast<qint64>( dataId );
    out[ "model_id" ] = static_cast<qint64>( modelId );
    out[ "data_source_preserved" ] = true;
    out[ "model_source_preserved" ] = true;
    out[ "preview_only" ] = previewOnly;
    out[ "coordinate_frame_policy" ] = "strict_same_global_shift_scale";
    out[ "overlap_percent" ] = overlapPercent;
    out[ "max_iterations" ] = maxIterations;
    out[ "random_sampling_limit" ] = samplingLimit;
    out[ "filter_out_farthest_points" ] = filterFarthest;
    out[ "final_rms_native" ] = finalRMS;
    out[ "final_point_count" ] = static_cast<qint64>( finalPointCount );
    out[ "result_code" ] = static_cast<int>( icpResult );
    out[ "transformation_available" ] = hasTransform;
    out[ "transformation_matrix_column_major" ] = matrixJson( transformMatrix );
    out[ "scale" ] = hasTransform ? transform.s : 1.0;
    out[ "result_created" ] = false;

    if ( !previewOnly && hasTransform )
    {
        std::unique_ptr<ccPointCloud> aligned( dataSource->cloneThis( nullptr, true ) );
        if ( !aligned )
        {
            error = "ICP succeeded but CloudCompare could not allocate the aligned result clone";
            return true;
        }

        aligned->applyGLTransformation_recursive( &transformMatrix );
        aligned->setName(
            requestedName.isEmpty() ? dataSource->getName() + ".mcp_icp_aligned" : requestedName );
        aligned->setVisible( true );
        aligned->setEnabled( true );

        ccPointCloud* liveAligned = aligned.release();
        attachToDestination( app, liveAligned, destination );
        app->refreshAll();
        app->updateUI();

        out[ "result_created" ] = true;
        out[ "result_entity" ] = entityDescription( liveAligned, false );
    }
    else if ( !previewOnly && !hasTransform )
    {
        out[ "note" ] = "ICP reported that no transformation was necessary; no duplicate result was created.";
    }

    result = out;
    return true;
}

bool registerPointPairs(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned dataId = 0;
    unsigned modelId = 0;
    if ( !readId( params, "data_id", dataId ) || !readId( params, "model_id", modelId ) )
    {
        error = "cloud.register_point_pairs requires numeric data_id and model_id";
        return true;
    }
    if ( dataId == modelId )
    {
        error = "cloud.register_point_pairs requires different data and model entities";
        return true;
    }

    ccPointCloud* dataSource = requireStandaloneCloud( app, dataId, error );
    if ( !dataSource )
        return true;
    ccPointCloud* modelSource = requireStandaloneCloud( app, modelId, error );
    if ( !modelSource )
        return true;

    if ( !compatibleFrames( dataSource, modelSource ) )
    {
        error =
            "Point-pair registration currently requires data and model clouds to share "
            "the same CloudCompare global shift/scale frame.";
        return true;
    }

    std::vector<CCVector3d> dataPoints;
    std::vector<CCVector3d> modelPoints;
    if ( !readPointList( params, "data_points", dataPoints, error )
         || !readPointList( params, "model_points", modelPoints, error ) )
    {
        return true;
    }
    if ( dataPoints.size() != modelPoints.size() )
    {
        error = "data_points and model_points must contain the same number of correspondences";
        return true;
    }

    const QString coordinateSpace = params.value( "coordinate_space" ).toString( "global" );
    if ( coordinateSpace != "global" && coordinateSpace != "native_local" )
    {
        error = "coordinate_space must be 'global' or 'native_local'";
        return true;
    }

    const bool previewOnly = params.value( "preview_only" ).toBool( true );
    QString requestedName;
    if ( params.contains( "name" ) )
    {
        requestedName = params.value( "name" ).toString().trimmed();
        if ( requestedName.isEmpty() )
        {
            error = "cloud.register_point_pairs name must be non-empty when supplied";
            return true;
        }
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
        return true;

    CCCoreLib::PointCloud alignedPoints;
    CCCoreLib::PointCloud referencePoints;
    if ( !alignedPoints.reserve( static_cast<unsigned>( dataPoints.size() ) )
         || !referencePoints.reserve( static_cast<unsigned>( modelPoints.size() ) ) )
    {
        error = "Could not allocate point-pair registration correspondences";
        return true;
    }

    std::vector<CCVector3d> dataLocal;
    std::vector<CCVector3d> modelLocalInDataFrame;
    std::vector<CCVector3d> modelGlobal;
    dataLocal.reserve( dataPoints.size() );
    modelLocalInDataFrame.reserve( modelPoints.size() );
    modelGlobal.reserve( modelPoints.size() );

    for ( size_t i = 0; i < dataPoints.size(); ++i )
    {
        CCVector3d dataGlobalPoint;
        CCVector3d modelGlobalPoint;
        if ( coordinateSpace == "global" )
        {
            dataGlobalPoint = dataPoints[i];
            modelGlobalPoint = modelPoints[i];
        }
        else
        {
            dataGlobalPoint =
                dataSource->toGlobal3d<PointCoordinateType>( dataPoints[i].toPC() );
            modelGlobalPoint =
                modelSource->toGlobal3d<PointCoordinateType>( modelPoints[i].toPC() );
        }

        const CCVector3d dataLocalPoint = dataSource->toLocal3d<double>( dataGlobalPoint );
        const CCVector3d targetLocalPoint = dataSource->toLocal3d<double>( modelGlobalPoint );
        dataLocal.push_back( dataLocalPoint );
        modelLocalInDataFrame.push_back( targetLocalPoint );
        modelGlobal.push_back( modelGlobalPoint );
        alignedPoints.addPoint( dataLocalPoint.toPC() );
        referencePoints.addPoint( targetLocalPoint.toPC() );
    }

    CCCoreLib::PointProjectionTools::Transformation transform;
    if ( !CCCoreLib::HornRegistrationTools::FindAbsoluteOrientation(
             &alignedPoints,
             &referencePoints,
             transform,
             true ) )
    {
        error =
            "Point-pair registration failed. Correspondences may be collinear, duplicated, "
            "or otherwise geometrically degenerate.";
        return true;
    }

    ccGLMatrix transformMatrix =
        FromCCLibMatrix<double, float>( transform.R, transform.T, transform.s );

    const double frameScale = dataSource->getGlobalScale();
    const CCVector3d frameShift = dataSource->getGlobalShift();
    const CCVector3d globalTranslation =
        ( transform.R * frameShift ) * transform.s
        + transform.T * ( 1.0 / frameScale )
        - frameShift;
    const ccGLMatrix globalTransformMatrix =
        FromCCLibMatrix<double, float>( transform.R, globalTranslation, transform.s );

    std::vector<double> residuals;
    residuals.reserve( dataLocal.size() );
    for ( size_t i = 0; i < dataLocal.size(); ++i )
    {
        const CCVector3d predictedLocal =
            ( transform.R * dataLocal[i] ) * transform.s + transform.T;
        const CCVector3d predictedGlobal =
            dataSource->toGlobal3d<PointCoordinateType>( predictedLocal.toPC() );
        residuals.push_back(
            std::sqrt( ( predictedGlobal - modelGlobal[i] ).norm2d() ) );
    }

    QJsonObject out;
    out[ "data_id" ] = static_cast<qint64>( dataId );
    out[ "model_id" ] = static_cast<qint64>( modelId );
    out[ "correspondence_count" ] = static_cast<qint64>( dataPoints.size() );
    out[ "coordinate_space" ] = coordinateSpace;
    out[ "data_source_preserved" ] = true;
    out[ "model_source_preserved" ] = true;
    out[ "preview_only" ] = previewOnly;
    out[ "scale" ] = transform.s;
    out[ "transformation_matrix_column_major" ] = matrixJson( transformMatrix );
    out[ "transformation_matrix_frame" ] = "data_native_local";
    out[ "transformation_matrix_global_column_major" ] = matrixJson( globalTransformMatrix );
    out[ "pair_residuals_global_native" ] = numericStats( residuals );
    out[ "result_created" ] = false;

    if ( !previewOnly )
    {
        std::unique_ptr<ccPointCloud> aligned( dataSource->cloneThis( nullptr, true ) );
        if ( !aligned )
        {
            error = "Point-pair registration succeeded but the aligned result clone could not be allocated";
            return true;
        }
        aligned->applyGLTransformation_recursive( &transformMatrix );
        aligned->setName(
            requestedName.isEmpty()
                ? dataSource->getName() + ".mcp_point_pair_aligned"
                : requestedName );
        aligned->setVisible( true );
        aligned->setEnabled( true );

        ccPointCloud* liveAligned = aligned.release();
        attachToDestination( app, liveAligned, destination );
        app->refreshAll();
        app->updateUI();
        out[ "result_created" ] = true;
        out[ "result_entity" ] = entityDescription( liveAligned, false );
    }

    result = out;
    return true;
}

bool analyzeCloudToCloud(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned comparedId = 0;
    unsigned referenceId = 0;
    if ( !readId( params, "compared_id", comparedId )
         || !readId( params, "reference_id", referenceId ) )
    {
        error = "cloud.distance_c2c requires numeric compared_id and reference_id";
        return true;
    }

    ccPointCloud* comparedSource = requireStandaloneCloud( app, comparedId, error );
    if ( !comparedSource )
        return true;
    ccPointCloud* referenceSource = requireStandaloneCloud( app, referenceId, error );
    if ( !referenceSource )
        return true;
    if ( comparedSource->size() == 0 || referenceSource->size() == 0 )
    {
        error = "C2C distance analysis requires non-empty compared and reference clouds";
        return true;
    }
    if ( !compatibleFrames( comparedSource, referenceSource ) )
    {
        error =
            "C2C distance analysis currently requires identical CloudCompare global "
            "shift/scale metadata.";
        return true;
    }

    const double maxDistance = params.value( "max_distance" ).toDouble( 0.0 );
    if ( !std::isfinite( maxDistance ) || maxDistance < 0.0 )
    {
        error = "max_distance must be non-negative in native coordinate units";
        return true;
    }

    const bool createResult = params.value( "create_result" ).toBool( false );
    QString requestedName;
    if ( params.contains( "name" ) )
    {
        requestedName = params.value( "name" ).toString().trimmed();
        if ( requestedName.isEmpty() )
        {
            error = "cloud.distance_c2c name must be non-empty when supplied";
            return true;
        }
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
        return true;

    std::unique_ptr<ccPointCloud> working( comparedSource->cloneThis( nullptr, true ) );
    if ( !working )
    {
        error = "Could not allocate the C2C analysis working clone";
        return true;
    }

    const QString scalarName = uniqueScalarFieldName( working.get(), "MCP C2C distance" );
    const QByteArray scalarNameUtf8 = scalarName.toUtf8();
    const int scalarIndex = working->addScalarField( scalarNameUtf8.constData() );
    if ( scalarIndex < 0 )
    {
        error = "Could not allocate the C2C distance scalar field";
        return true;
    }
    working->setCurrentScalarField( scalarIndex );

    ccScalarField* scalarField =
        static_cast<ccScalarField*>( working->getScalarField( scalarIndex ) );
    if ( !scalarField )
    {
        error = "Could not access the C2C distance scalar field";
        return true;
    }

    bool cappedByBoundingBoxes = false;
    if ( maxDistance > 0.0 )
    {
        const double maxDistanceSquared = maxDistance * maxDistance;
        const double boundsDistanceSquared =
            minimumBoundingBoxDistanceSquared(
                working->getOwnBB(),
                referenceSource->getOwnBB() );

        if ( boundsDistanceSquared >= maxDistanceSquared )
        {
            // Every possible point pair is at least maxDistance apart, therefore
            // CloudCompare's capped-distance semantics are exactly maxDistance for
            // every compared point. CCCoreLib 2.13.2 can otherwise fail while
            // synchronizing octrees when the cropped overlap slab contains no
            // source points (ERROR_SYNCHRONIZE_OCTREES_FAILURE / -968).
            scalarField->fill( static_cast<ScalarType>( maxDistance ) );
            cappedByBoundingBoxes = true;
        }
    }

    if ( !cappedByBoundingBoxes )
    {
        CCCoreLib::DistanceComputationTools::Cloud2CloudDistancesComputationParams distanceParams;
        distanceParams.maxSearchDist = static_cast<ScalarType>( maxDistance );
        distanceParams.multiThread = true;
        distanceParams.maxThreadCount = 0;
        distanceParams.localModel = CCCoreLib::NO_MODEL;
        distanceParams.resetFormerDistances = true;

        const int computationResult =
            CCCoreLib::DistanceComputationTools::computeCloud2CloudDistances(
                working.get(),
                referenceSource,
                distanceParams );
        if ( computationResult < CCCoreLib::DistanceComputationTools::DISTANCE_COMPUTATION_RESULTS::SUCCESS )
        {
            error = QString( "CloudCompare C2C distance computation failed with code %1" )
                        .arg( computationResult );
            return true;
        }
    }

    scalarField->computeMinAndMax();
    const std::vector<double> values = scalarValues( scalarField );
    const QJsonObject distanceStats = numericStats( values );
    const qint64 validDistanceCount =
        static_cast<qint64>( distanceStats.value( "count" ).toDouble() );

    QJsonObject out;
    out[ "compared_id" ] = static_cast<qint64>( comparedId );
    out[ "reference_id" ] = static_cast<qint64>( referenceId );
    out[ "compared_source_preserved" ] = true;
    out[ "reference_source_preserved" ] = true;
    out[ "max_distance_native" ] = maxDistance;
    out[ "distances_capped_by_max_distance" ] = maxDistance > 0.0;
    out[ "capped_by_bounding_box_short_circuit" ] = cappedByBoundingBoxes;
    out[ "scalar_field_name" ] = scalarName;
    out[ "point_count" ] = static_cast<qint64>( working->size() );
    out[ "valid_distance_count" ] = validDistanceCount;
    out[ "invalid_distance_count" ] =
        static_cast<qint64>( working->size() ) - validDistanceCount;
    out[ "distance_stats_native" ] = distanceStats;
    out[ "result_created" ] = false;

    if ( createResult )
    {
        working->setCurrentDisplayedScalarField( scalarIndex );
        working->showSF( true );
        working->showColors( false );
        working->setName(
            requestedName.isEmpty()
                ? comparedSource->getName() + ".mcp_c2c"
                : requestedName );
        working->setVisible( true );
        working->setEnabled( true );

        ccPointCloud* liveResult = working.release();
        attachToDestination( app, liveResult, destination );
        app->refreshAll();
        app->updateUI();
        out[ "result_created" ] = true;
        out[ "result_entity" ] = entityDescription( liveResult, false );
    }

    result = out;
    return true;
}

bool analyzeCloudToMesh(
    ccMainAppInterface* app,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error )
{
    unsigned comparedId = 0;
    unsigned meshId = 0;
    if ( !readId( params, "compared_id", comparedId )
         || !readId( params, "reference_mesh_id", meshId ) )
    {
        error = "cloud.distance_c2m requires numeric compared_id and reference_mesh_id";
        return true;
    }

    ccPointCloud* comparedSource = requireStandaloneCloud( app, comparedId, error );
    if ( !comparedSource )
        return true;
    ccGenericMesh* referenceMesh = requireMesh( app, meshId, error );
    if ( !referenceMesh )
        return true;
    if ( comparedSource->size() == 0 || referenceMesh->size() == 0 )
    {
        error = "C2M distance analysis requires a non-empty cloud and mesh";
        return true;
    }

    ccGenericPointCloud* meshCloud = referenceMesh->getAssociatedCloud();
    if ( !compatibleFrames( comparedSource, meshCloud ) )
    {
        error =
            "C2M distance analysis currently requires the cloud and mesh to share "
            "identical CloudCompare global shift/scale metadata.";
        return true;
    }

    const double maxDistance = params.value( "max_distance" ).toDouble( 0.0 );
    if ( !std::isfinite( maxDistance ) || maxDistance < 0.0 )
    {
        error = "max_distance must be non-negative in native coordinate units";
        return true;
    }

    const bool signedDistances = params.value( "signed_distances" ).toBool( false );
    const bool flipNormals = params.value( "flip_normals" ).toBool( false );
    const bool robust = params.value( "robust" ).toBool( true );
    const bool createResult = params.value( "create_result" ).toBool( false );

    QString requestedName;
    if ( params.contains( "name" ) )
    {
        requestedName = params.value( "name" ).toString().trimmed();
        if ( requestedName.isEmpty() )
        {
            error = "cloud.distance_c2m name must be non-empty when supplied";
            return true;
        }
    }

    ccHObject* destination = nullptr;
    if ( !resolveDestination( app, params, destination, error ) )
        return true;

    std::unique_ptr<ccPointCloud> working( comparedSource->cloneThis( nullptr, true ) );
    if ( !working )
    {
        error = "Could not allocate the C2M analysis working clone";
        return true;
    }

    const QString scalarName = uniqueScalarFieldName(
        working.get(),
        signedDistances ? "MCP C2M signed distance" : "MCP C2M distance" );
    const QByteArray scalarNameUtf8 = scalarName.toUtf8();
    const int scalarIndex = working->addScalarField( scalarNameUtf8.constData() );
    if ( scalarIndex < 0 )
    {
        error = "Could not allocate the C2M distance scalar field";
        return true;
    }
    working->setCurrentScalarField( scalarIndex );

    CCCoreLib::DistanceComputationTools::Cloud2MeshDistancesComputationParams distanceParams;
    distanceParams.maxSearchDist = static_cast<ScalarType>( maxDistance );
    distanceParams.useDistanceMap = false;
    distanceParams.signedDistances = signedDistances;
    distanceParams.flipNormals = flipNormals;
    distanceParams.multiThread = true;
    distanceParams.maxThreadCount = 0;
    distanceParams.robust = robust;

    const int computationResult =
        CCCoreLib::DistanceComputationTools::computeCloud2MeshDistances(
            working.get(),
            referenceMesh,
            distanceParams );
    if ( computationResult < CCCoreLib::DistanceComputationTools::DISTANCE_COMPUTATION_RESULTS::SUCCESS )
    {
        error = QString( "CloudCompare C2M distance computation failed with code %1" )
                    .arg( computationResult );
        return true;
    }

    ccScalarField* scalarField =
        static_cast<ccScalarField*>( working->getScalarField( scalarIndex ) );
    scalarField->computeMinAndMax();
    const std::vector<double> values = scalarValues( scalarField );
    const QJsonObject distanceStats = numericStats( values );
    const qint64 validDistanceCount =
        static_cast<qint64>( distanceStats.value( "count" ).toDouble() );

    QJsonObject out;
    out[ "compared_id" ] = static_cast<qint64>( comparedId );
    out[ "reference_mesh_id" ] = static_cast<qint64>( meshId );
    out[ "compared_source_preserved" ] = true;
    out[ "reference_source_preserved" ] = true;
    out[ "max_distance_native" ] = maxDistance;
    out[ "distances_capped_by_max_distance" ] = maxDistance > 0.0;
    out[ "signed_distances" ] = signedDistances;
    out[ "flip_normals" ] = flipNormals;
    out[ "robust" ] = robust;
    out[ "scalar_field_name" ] = scalarName;
    out[ "point_count" ] = static_cast<qint64>( working->size() );
    out[ "valid_distance_count" ] = validDistanceCount;
    out[ "invalid_distance_count" ] =
        static_cast<qint64>( working->size() ) - validDistanceCount;
    out[ "distance_stats_native" ] = distanceStats;
    if ( signedDistances )
    {
        std::vector<double> absoluteValues;
        absoluteValues.reserve( values.size() );
        for ( double value : values )
        {
            absoluteValues.push_back( std::abs( value ) );
        }
        out[ "absolute_distance_stats_native" ] = numericStats( absoluteValues );
    }
    out[ "result_created" ] = false;

    if ( createResult )
    {
        working->setCurrentDisplayedScalarField( scalarIndex );
        working->showSF( true );
        working->showColors( false );
        working->setName(
            requestedName.isEmpty()
                ? comparedSource->getName() + ".mcp_c2m"
                : requestedName );
        working->setVisible( true );
        working->setEnabled( true );

        ccPointCloud* liveResult = working.release();
        attachToDestination( app, liveResult, destination );
        app->refreshAll();
        app->updateUI();
        out[ "result_created" ] = true;
        out[ "result_entity" ] = entityDescription( liveResult, false );
    }

    result = out;
    return true;
}

QJsonObject capabilities()
{
    QJsonObject result;
    result[ "protocol_version" ] = 1;
    result[ "workflow_revision" ] = 5;
    result[ "units_policy" ] =
        "Coordinates are reported in native units. Units remain unknown unless supplied by the caller.";
    result[ "global_coordinate_export" ] =
        "CloudCompare PLY and OBJ writers emit global coordinates using stored global shift/scale.";

    result[ "plugin_version" ] = "0.7.0";

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
        "entity.export",
        "group.create",
        "cloud.crop",
        "cloud.subsample",
        "cloud.filter_sor",
        "cloud.compute_normals",
        "cloud.register_icp",
        "cloud.register_point_pairs",
        "cloud.distance_c2c",
        "cloud.distance_c2m",
        "metrology.pick.start",
        "metrology.pick.status",
        "metrology.pick.clear",
        "metrology.pick.stop",
        "metrology.point_info",
        "metrology.measure.picked_distance",
        "metrology.measure.picked_angle"
    };
    result[ "bridge_operations" ] = bridgeOperations;

    QJsonArray workflowOperations{
        "entity.clone",
        "cloud.merge",
        "mesh.reconstruct",
        "mesh.simplify",
        "entity.export",
        "group.create",
        "cloud.crop",
        "cloud.subsample",
        "cloud.filter_sor",
        "cloud.compute_normals",
        "cloud.register_icp",
        "cloud.register_point_pairs",
        "cloud.distance_c2c",
        "cloud.distance_c2m",
        "metrology.pick.start",
        "metrology.pick.status",
        "metrology.pick.clear",
        "metrology.pick.stop",
        "metrology.point_info",
        "metrology.measure.picked_distance",
        "metrology.measure.picked_angle"
    };
    result[ "workflow_operations" ] = workflowOperations;

    QJsonObject scanPreparation;
    scanPreparation[ "non_destructive_results" ] = true;
    scanPreparation[ "crop_axis_aligned" ] = true;
    scanPreparation[ "crop_coordinate_spaces" ] = QJsonArray{ "native_local", "global" };
    scanPreparation[ "subsampling_methods" ] = QJsonArray{ "random", "spatial", "octree" };
    scanPreparation[ "sor_filter" ] = true;
    scanPreparation[ "normal_models" ] = QJsonArray{ "LS", "QUADRIC", "TRIANGULATION" };
    scanPreparation[ "mst_normal_orientation" ] = true;
    result[ "scan_preparation" ] = scanPreparation;

    QJsonObject registration;
    registration[ "icp_point_cloud_to_point_cloud" ] = true;
    registration[ "preview_only_supported" ] = true;
    registration[ "creates_aligned_clone" ] = true;
    registration[ "scale_adjustment_supported" ] = false;
    registration[ "coordinate_frame_policy" ] = "strict_same_global_shift_scale";
    registration[ "parameters" ] = QJsonArray{
        "overlap_percent",
        "max_iterations",
        "random_sampling_limit",
        "filter_out_farthest_points",
        "preview_only",
        "name",
        "destination_group_id"
    };
    registration[ "point_pair_registration" ] = true;
    registration[ "point_pair_coordinate_spaces" ] = QJsonArray{ "global", "native_local" };
    registration[ "point_pair_minimum_correspondences" ] = 3;
    result[ "registration" ] = registration;

    QJsonObject comparison;
    comparison[ "cloud_to_cloud" ] = true;
    comparison[ "cloud_to_mesh" ] = true;
    comparison[ "stats_only_default" ] = true;
    comparison[ "optional_scalar_field_result" ] = true;
    comparison[ "statistics" ] = QJsonArray{
        "min", "max", "mean", "rms", "stddev", "median", "p95", "p99", "histogram"
    };
    comparison[ "signed_c2m" ] = true;
    result[ "comparison" ] = comparison;

    QJsonObject metrology;
    metrology[ "interactive_point_picking" ] = true;
    metrology[ "point_or_triangle_picking" ] = true;
    metrology[ "entity_filtering" ] = true;
    metrology[ "auto_stop_after_max_picks" ] = true;
    metrology[ "point_attribute_inspection" ] = true;
    metrology[ "picked_point_distance" ] = true;
    metrology[ "picked_three_point_angle" ] = true;
    metrology[ "coordinate_space" ] = "global";
    metrology[ "units_policy" ] =
        "Distances use CloudCompare native coordinate units; physical units remain caller-supplied.";
    result[ "metrology" ] = metrology;

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
        if ( raw < 0.0
             || raw > static_cast<double>( std::numeric_limits<unsigned>::max() )
             || std::floor( raw ) != raw )
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
        const double raw = value.toDouble();
        if ( raw < 0.0
             || raw > static_cast<double>( std::numeric_limits<unsigned>::max() )
             || std::floor( raw ) != raw )
        {
            error = "cloud.merge contains an invalid entity ID";
            return true;
        }
        const unsigned id = static_cast<unsigned>( raw );
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
            // Public in CloudCompare 2.13.2; also invalidates VBOs and LOD.
            // cloneThis(nullptr, true) creates a fresh cloud without an octree.
            working->invalidateBoundingBox();
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

    // Probe write access from the CloudCompare GUI process before entering an
    // exporter. Some filters can surface native/UI errors on access failures;
    // bridge operations must fail promptly and noninteractively instead.
    QFile writeProbe( tempPath );
    if ( !writeProbe.open( QIODevice::WriteOnly ) )
    {
        error = QString( "CloudCompare process cannot write to output directory '%1': %2" )
                    .arg( parentDir.absolutePath(), writeProbe.errorString() );
        return true;
    }
    writeProbe.close();
    if ( !QFile::remove( tempPath ) )
    {
        error = QString( "CloudCompare process could not remove export write probe: %1" ).arg( tempPath );
        return true;
    }

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
void shutdownInteractiveState()
{
    g_metrologyPickingSession.stop();
}

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
        addApplicationVersion( out );
        out[ "plugin" ] = "qMCPBridge";
        result = out;
        return true;
    }
    if ( method == "group.create" )
    {
        return createGroup( app, params, result, error );
    }
    if ( method == "cloud.crop" )
    {
        return cropCloud( app, params, result, error );
    }
    if ( method == "cloud.subsample" )
    {
        return subsampleCloud( app, params, result, error );
    }
    if ( method == "cloud.filter_sor" )
    {
        return sorFilterCloud( app, params, result, error );
    }
    if ( method == "cloud.compute_normals" )
    {
        return computeCloudNormals( app, params, result, error );
    }
    if ( method == "cloud.register_icp" )
    {
        return registerCloudsICP( app, params, result, error );
    }
    if ( method == "cloud.register_point_pairs" )
    {
        return registerPointPairs( app, params, result, error );
    }
    if ( method == "cloud.distance_c2c" )
    {
        return analyzeCloudToCloud( app, params, result, error );
    }
    if ( method == "cloud.distance_c2m" )
    {
        return analyzeCloudToMesh( app, params, result, error );
    }
    if ( method == "metrology.pick.start" )
    {
        return startMetrologyPicking( app, params, result, error );
    }
    if ( method == "metrology.pick.status" )
    {
        return metrologyPickingStatus( result );
    }
    if ( method == "metrology.pick.clear" )
    {
        return clearMetrologyPicks( result );
    }
    if ( method == "metrology.pick.stop" )
    {
        return stopMetrologyPicking( result );
    }
    if ( method == "metrology.point_info" )
    {
        return inspectCloudPoint( app, params, result, error );
    }
    if ( method == "metrology.measure.picked_distance" )
    {
        return measurePickedDistance( params, result, error );
    }
    if ( method == "metrology.measure.picked_angle" )
    {
        return measurePickedAngle( params, result, error );
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
