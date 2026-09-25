// SPDX-License-Identifier: GPL-2.0-or-later

#include "qMCPBridge.h"

#include <QAction>
#include <QBuffer>
#include <QCoreApplication>
#include <QFileInfo>
#include <QHostAddress>
#include <QImage>
#include <QIcon>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTcpServer>
#include <QTcpSocket>

#include <ccGLMatrix.h>
#include <ccGLWindowInterface.h>
#include <ccHObject.h>

#include <limits>

namespace
{
constexpr quint16 DEFAULT_PORT = 8765;

bool readId( const QJsonObject& object, const char* key, unsigned& id )
{
    const QJsonValue value = object.value( QLatin1String( key ) );
    if ( !value.isDouble() )
    {
        return false;
    }

    const double raw = value.toDouble();
    if ( raw < 0.0 || raw > static_cast<double>( std::numeric_limits<unsigned>::max() ) )
    {
        return false;
    }

    id = static_cast<unsigned>( raw );
    return true;
}

QJsonArray selectedIds( ccMainAppInterface* app )
{
    QJsonArray ids;
    if ( !app )
    {
        return ids;
    }

    for ( ccHObject* entity : app->getSelectedEntities() )
    {
        if ( entity )
        {
            ids.append( static_cast<qint64>( entity->getUniqueID() ) );
        }
    }
    return ids;
}
}

qMCPBridge::qMCPBridge( QObject* parent )
    : QObject( parent )
    , ccStdPluginInterface( ":/CC/plugin/qMCPBridge/info.json" )
    , m_server( new QTcpServer( this ) )
    , m_port( DEFAULT_PORT )
{
    bool ok = false;
    const int configuredPort = qEnvironmentVariableIntValue( "CLOUDCOMPARE_MCP_PORT", &ok );
    if ( ok && configuredPort > 0 && configuredPort <= 65535 )
    {
        m_port = static_cast<quint16>( configuredPort );
    }

    m_token = qEnvironmentVariable( "CLOUDCOMPARE_MCP_TOKEN" );

    connect( m_server, &QTcpServer::newConnection, this, &qMCPBridge::onNewConnection );
}

qMCPBridge::~qMCPBridge()
{
    stopServer();
}

void qMCPBridge::setMainAppInterface( ccMainAppInterface* app )
{
    ccStdPluginInterface::setMainAppInterface( app );

    if ( m_app )
    {
        startServer();
    }
    else
    {
        stopServer();
    }
}

void qMCPBridge::onNewSelection( const ccHObject::Container& )
{
    // Selection is queried live for each request, so no cached state is needed.
}

QList<QAction*> qMCPBridge::getActions()
{
    if ( !m_action )
    {
        m_action = new QAction( this );
        m_action->setIcon( QIcon( ":/CC/plugin/qMCPBridge/images/bridge.svg" ) );
        m_action->setIconText( tr( "MCP" ) );

        connect( m_action, &QAction::triggered, this, [this]()
        {
            if ( m_server->isListening() )
            {
                stopServer();
            }
            else
            {
                startServer();
            }
        } );

        updateAction();
    }

    return { m_action };
}

bool qMCPBridge::startServer()
{
    if ( m_server->isListening() )
    {
        return true;
    }

    const bool listening = m_server->listen( QHostAddress::LocalHost, m_port );
    if ( m_app )
    {
        if ( listening )
        {
            m_app->dispToConsole(
                tr( "[MCP Bridge] Listening on 127.0.0.1:%1%2" )
                    .arg( m_port )
                    .arg( m_token.isEmpty() ? QString() : tr( " (token required)" ) ),
                ccMainAppInterface::STD_CONSOLE_MESSAGE );
        }
        else
        {
            m_app->dispToConsole(
                tr( "[MCP Bridge] Could not listen on 127.0.0.1:%1: %2" )
                    .arg( m_port )
                    .arg( m_server->errorString() ),
                ccMainAppInterface::ERR_CONSOLE_MESSAGE );
        }
    }

    updateAction();
    return listening;
}

void qMCPBridge::stopServer()
{
    if ( m_server && m_server->isListening() )
    {
        m_server->close();
        if ( m_app )
        {
            m_app->dispToConsole(
                tr( "[MCP Bridge] Stopped" ),
                ccMainAppInterface::STD_CONSOLE_MESSAGE );
        }
    }
    updateAction();
}

void qMCPBridge::updateAction()
{
    if ( !m_action )
    {
        return;
    }

    if ( m_server && m_server->isListening() )
    {
        m_action->setText( tr( "MCP Bridge: stop localhost server (%1)" ).arg( m_port ) );
        m_action->setToolTip( tr( "MCP Bridge is listening on 127.0.0.1:%1. Click to stop." ).arg( m_port ) );
    }
    else
    {
        m_action->setText( tr( "MCP Bridge: start localhost server (%1)" ).arg( m_port ) );
        m_action->setToolTip( tr( "MCP Bridge is stopped. Click to listen on 127.0.0.1:%1." ).arg( m_port ) );
    }
    m_action->setStatusTip( m_action->toolTip() );
}

void qMCPBridge::onNewConnection()
{
    while ( QTcpSocket* socket = m_server->nextPendingConnection() )
    {
        connect( socket, &QTcpSocket::readyRead, this, [this, socket]()
        {
            processSocket( socket );
        } );
        connect( socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater );
    }
}

void qMCPBridge::processSocket( QTcpSocket* socket )
{
    QByteArray buffer = socket->property( "mcpBuffer" ).toByteArray();
    buffer += socket->readAll();

    qsizetype newline = -1;
    while ( ( newline = buffer.indexOf( '\n' ) ) >= 0 )
    {
        const QByteArray line = buffer.left( newline ).trimmed();
        buffer.remove( 0, newline + 1 );

        if ( line.isEmpty() )
        {
            continue;
        }

        QJsonObject response;
        QJsonParseError parseError;
        const QJsonDocument document = QJsonDocument::fromJson( line, &parseError );
        if ( parseError.error != QJsonParseError::NoError || !document.isObject() )
        {
            response[ "ok" ] = false;
            response[ "error" ] = tr( "Invalid JSON request: %1" ).arg( parseError.errorString() );
        }
        else
        {
            response = handleRequest( document.object() );
        }

        socket->write( QJsonDocument( response ).toJson( QJsonDocument::Compact ) );
        socket->write( "\n" );
        socket->flush();
    }

    socket->setProperty( "mcpBuffer", buffer );
}

QJsonObject qMCPBridge::handleRequest( const QJsonObject& request )
{
    QJsonObject response;
    response[ "id" ] = request.value( "id" );

    if ( !m_token.isEmpty() && request.value( "token" ).toString() != m_token )
    {
        response[ "ok" ] = false;
        response[ "error" ] = "Authentication failed";
        return response;
    }

    const QString method = request.value( "method" ).toString();
    if ( method.isEmpty() )
    {
        response[ "ok" ] = false;
        response[ "error" ] = "Missing request method";
        return response;
    }

    const QJsonObject params = request.value( "params" ).toObject();
    QString error;
    const QJsonValue result = dispatch( method, params, error );

    if ( !error.isEmpty() )
    {
        response[ "ok" ] = false;
        response[ "error" ] = error;
    }
    else
    {
        response[ "ok" ] = true;
        response[ "result" ] = result;
    }

    return response;
}

QJsonValue qMCPBridge::dispatch( const QString& method, const QJsonObject& params, QString& error )
{
    if ( !m_app )
    {
        error = "CloudCompare application interface is not available";
        return {};
    }

    if ( method == "ping" )
    {
        QJsonObject result;
        result[ "protocol_version" ] = 1;
        result[ "plugin" ] = "qMCPBridge";
        result[ "process_id" ] = QCoreApplication::applicationPid();
        result[ "application_version" ] = QCoreApplication::applicationVersion();
        result[ "port" ] = static_cast<int>( m_port );
        result[ "selected_ids" ] = selectedIds( m_app );
        ccHObject* root = m_app->dbRootObject();
        result[ "root_children" ] = root ? static_cast<int>( root->getChildrenNumber() ) : 0;
        return result;
    }

    if ( method == "scene.list" )
    {
        const bool recursive = !params.contains( "recursive" ) || params.value( "recursive" ).toBool( true );
        QJsonArray entities;
        if ( ccHObject* root = m_app->dbRootObject() )
        {
            for ( unsigned i = 0; i < root->getChildrenNumber(); ++i )
            {
                entities.append( entityToJson( root->getChild( i ), recursive ) );
            }
        }

        QJsonObject result;
        result[ "entities" ] = entities;
        result[ "selected_ids" ] = selectedIds( m_app );
        return result;
    }

    if ( method == "selection.get" )
    {
        QJsonArray entities;
        for ( ccHObject* entity : m_app->getSelectedEntities() )
        {
            if ( entity )
            {
                entities.append( entityToJson( entity, false ) );
            }
        }
        return entities;
    }

    if ( method == "selection.set" )
    {
        const QJsonArray ids = params.value( "ids" ).toArray();
        const bool clearFirst = !params.contains( "clear" ) || params.value( "clear" ).toBool( true );

        if ( clearFirst )
        {
            const ccHObject::Container previous = m_app->getSelectedEntities();
            for ( ccHObject* entity : previous )
            {
                if ( entity )
                {
                    m_app->setSelectedInDB( entity, false );
                }
            }
        }

        QJsonArray missing;
        for ( const QJsonValue& value : ids )
        {
            if ( !value.isDouble() )
            {
                continue;
            }

            const unsigned id = static_cast<unsigned>( value.toDouble() );
            if ( ccHObject* entity = findEntity( id ) )
            {
                m_app->setSelectedInDB( entity, true );
            }
            else
            {
                missing.append( static_cast<qint64>( id ) );
            }
        }

        m_app->updateUI();

        QJsonObject result;
        result[ "selected_ids" ] = selectedIds( m_app );
        result[ "missing_ids" ] = missing;
        return result;
    }

    if ( method == "file.load" )
    {
        const QString path = params.value( "path" ).toString();
        if ( path.isEmpty() )
        {
            error = "file.load requires a path";
            return {};
        }
        if ( !QFileInfo::exists( path ) )
        {
            error = QString( "File not found: %1" ).arg( path );
            return {};
        }

        ccHObject* loaded = m_app->loadFile( path, true );
        if ( !loaded )
        {
            error = QString( "CloudCompare failed to load: %1" ).arg( path );
            return {};
        }

        // loadFile only constructs the hierarchy; the caller must register it
        // with the application's database and displays.
        m_app->addToDB( loaded, true );
        m_app->redrawAll();
        return entityToJson( loaded, true );
    }

    if ( method == "entity.rename" )
    {
        unsigned id = 0;
        if ( !readId( params, "id", id ) )
        {
            error = "entity.rename requires a numeric id";
            return {};
        }

        const QString name = params.value( "name" ).toString();
        if ( name.isEmpty() )
        {
            error = "entity.rename requires a non-empty name";
            return {};
        }

        ccHObject* entity = findEntity( id );
        if ( !entity )
        {
            error = QString( "Entity %1 was not found" ).arg( id );
            return {};
        }

        entity->setName( name );
        m_app->updateUI();
        return entityToJson( entity, false );
    }

    if ( method == "entity.set_state" )
    {
        unsigned id = 0;
        if ( !readId( params, "id", id ) )
        {
            error = "entity.set_state requires a numeric id";
            return {};
        }

        ccHObject* entity = findEntity( id );
        if ( !entity )
        {
            error = QString( "Entity %1 was not found" ).arg( id );
            return {};
        }

        bool changed = false;
        if ( params.value( "visible" ).isBool() )
        {
            entity->setVisible( params.value( "visible" ).toBool() );
            changed = true;
        }
        if ( params.value( "enabled" ).isBool() )
        {
            entity->setEnabled( params.value( "enabled" ).toBool() );
            changed = true;
        }

        if ( !changed )
        {
            error = "entity.set_state requires visible and/or enabled";
            return {};
        }

        entity->prepareDisplayForRefresh_recursive();
        m_app->refreshAll();
        m_app->updateUI();
        return entityToJson( entity, false );
    }

    if ( method == "entity.delete" )
    {
        const QJsonArray ids = params.value( "ids" ).toArray();
        if ( ids.isEmpty() )
        {
            error = "entity.delete requires at least one id";
            return {};
        }

        QJsonArray deleted;
        QJsonArray missing;
        for ( const QJsonValue& value : ids )
        {
            if ( !value.isDouble() )
            {
                continue;
            }

            const unsigned id = static_cast<unsigned>( value.toDouble() );
            ccHObject* entity = findEntity( id );
            if ( !entity || entity == m_app->dbRootObject() )
            {
                missing.append( static_cast<qint64>( id ) );
                continue;
            }

            m_app->removeFromDB( entity, true );
            deleted.append( static_cast<qint64>( id ) );
        }

        m_app->refreshAll();
        m_app->updateUI();

        QJsonObject result;
        result[ "deleted_ids" ] = deleted;
        result[ "missing_ids" ] = missing;
        return result;
    }

    if ( method == "entity.transform" )
    {
        unsigned id = 0;
        if ( !readId( params, "id", id ) )
        {
            error = "entity.transform requires a numeric id";
            return {};
        }

        const QJsonArray matrixJson = params.value( "matrix" ).toArray();
        if ( matrixJson.size() != 16 )
        {
            error = "entity.transform requires exactly 16 matrix values in OpenGL column-major order";
            return {};
        }

        double matrixData[16];
        for ( int i = 0; i < 16; ++i )
        {
            if ( !matrixJson.at( i ).isDouble() )
            {
                error = "entity.transform matrix values must all be numeric";
                return {};
            }
            matrixData[i] = matrixJson.at( i ).toDouble();
        }

        ccHObject* entity = findEntity( id );
        if ( !entity )
        {
            error = QString( "Entity %1 was not found" ).arg( id );
            return {};
        }

        const ccGLMatrix transform( matrixData );
        entity->applyGLTransformation_recursive( &transform );
        entity->notifyGeometryUpdate();
        entity->prepareDisplayForRefresh_recursive();
        m_app->refreshAll();
        m_app->updateUI();

        return entityToJson( entity, false );
    }

    if ( method == "view" )
    {
        const QString action = params.value( "action" ).toString().toLower();

        if ( action == "top" )
            m_app->setView( CC_TOP_VIEW );
        else if ( action == "bottom" )
            m_app->setView( CC_BOTTOM_VIEW );
        else if ( action == "front" )
            m_app->setView( CC_FRONT_VIEW );
        else if ( action == "back" )
            m_app->setView( CC_BACK_VIEW );
        else if ( action == "left" )
            m_app->setView( CC_LEFT_VIEW );
        else if ( action == "right" )
            m_app->setView( CC_RIGHT_VIEW );
        else if ( action == "zoom_selected" )
            m_app->zoomOnSelectedEntities();
        else if ( action == "global_zoom" )
            m_app->setGlobalZoom();
        else if ( action == "redraw" )
            m_app->redrawAll();
        else
        {
            error = "Unknown view action";
            return {};
        }

        QJsonObject result;
        result[ "action" ] = action;
        return result;
    }

    if ( method == "view.capture" )
    {
        ccGLWindowInterface* window = m_app->getActiveGLWindow();
        if ( !window )
        {
            error = "There is no active CloudCompare 3D view";
            return {};
        }

        m_app->redrawAll();
        QCoreApplication::processEvents();

        const QImage image = window->doGrabFramebuffer();
        if ( image.isNull() )
        {
            error = "CloudCompare could not capture the active 3D view";
            return {};
        }

        QByteArray png;
        QBuffer buffer( &png );
        if ( !buffer.open( QIODevice::WriteOnly ) || !image.save( &buffer, "PNG" ) )
        {
            error = "Failed to encode the active 3D view as PNG";
            return {};
        }

        QJsonObject result;
        result[ "width" ] = image.width();
        result[ "height" ] = image.height();
        result[ "png_base64" ] = QString::fromLatin1( png.toBase64() );
        return result;
    }

    error = QString( "Unknown bridge method: %1" ).arg( method );
    return {};
}

QJsonObject qMCPBridge::entityToJson( ccHObject* entity, bool recursive ) const
{
    QJsonObject result;
    if ( !entity )
    {
        return result;
    }

    result[ "id" ] = static_cast<qint64>( entity->getUniqueID() );
    result[ "name" ] = entity->getName();
    result[ "class_id" ] = static_cast<int>( entity->getClassID() );
    result[ "enabled" ] = entity->isEnabled();
    result[ "visible" ] = entity->isVisible();
    result[ "child_count" ] = static_cast<int>( entity->getChildrenNumber() );

    // Local geometry bounds make transformations inspectable independently
    // of camera position, selection decoration, and viewport screenshots.
    const ccBBox bounds = entity->getOwnBB();
    if ( bounds.isValid() )
    {
        const CCVector3& minimum = bounds.minCorner();
        const CCVector3& maximum = bounds.maxCorner();
        QJsonObject box;
        box[ "min" ] = QJsonArray{ minimum.x, minimum.y, minimum.z };
        box[ "max" ] = QJsonArray{ maximum.x, maximum.y, maximum.z };
        result[ "bounding_box" ] = box;
    }

    QString kind = "object";
    if ( entity->isKindOf( CC_TYPES::POINT_CLOUD ) )
        kind = "point_cloud";
    else if ( entity->isKindOf( CC_TYPES::MESH ) )
        kind = "mesh";
    else if ( entity->isKindOf( CC_TYPES::HIERARCHY_OBJECT ) )
        kind = "group";
    result[ "kind" ] = kind;

    if ( recursive && entity->getChildrenNumber() > 0 )
    {
        QJsonArray children;
        for ( unsigned i = 0; i < entity->getChildrenNumber(); ++i )
        {
            children.append( entityToJson( entity->getChild( i ), true ) );
        }
        result[ "children" ] = children;
    }

    return result;
}

ccHObject* qMCPBridge::findEntity( unsigned uniqueId ) const
{
    return findEntityRecursive( m_app ? m_app->dbRootObject() : nullptr, uniqueId );
}

ccHObject* qMCPBridge::findEntityRecursive( ccHObject* parent, unsigned uniqueId ) const
{
    if ( !parent )
    {
        return nullptr;
    }

    if ( parent->getUniqueID() == uniqueId )
    {
        return parent;
    }

    for ( unsigned i = 0; i < parent->getChildrenNumber(); ++i )
    {
        if ( ccHObject* match = findEntityRecursive( parent->getChild( i ), uniqueId ) )
        {
            return match;
        }
    }

    return nullptr;
}
