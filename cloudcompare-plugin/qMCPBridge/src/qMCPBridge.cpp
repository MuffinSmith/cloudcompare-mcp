// SPDX-License-Identifier: GPL-2.0-or-later

#include "qMCPBridge.h"
#include "qMCPCamera.h"
#include "qMCPCameraGuard.h"
#include <QCryptographicHash>

#include <QAction>
#include <QBuffer>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QUuid>
#include <QHostAddress>
#include <QImage>
#include <QIcon>
#include <QJsonArray>
#include <QJsonDocument>
#include <QAbstractItemModel>
#include <QItemSelectionModel>
#include <QMainWindow>
#include <QSet>
#include <QTreeView>
#include <QTcpServer>
#include <QTcpSocket>

#include <ccGLMatrix.h>
#include <ccGLWindowInterface.h>
#include <ccHObject.h>

#include "qMCPFusionWorkflow.h"

#include <cmath>
#include <limits>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

namespace
{
constexpr quint16 DEFAULT_PORT = 8765;
int g_moduleAnchor = 0;

QString loadedModulePath()
{
#ifdef Q_OS_WIN
    HMODULE module = nullptr;
    if ( !GetModuleHandleExW(
             GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
                 | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
             reinterpret_cast<LPCWSTR>( &g_moduleAnchor ),
             &module ) )
    {
        return {};
    }

    std::wstring buffer( 32768, L'\0' );
    const DWORD length = GetModuleFileNameW(
        module,
        &buffer[0],
        static_cast<DWORD>( buffer.size() ) );
    if ( length == 0 || length >= buffer.size() )
    {
        return {};
    }
    return QDir::toNativeSeparators(
        QString::fromWCharArray( buffer.data(), static_cast<int>( length ) ) );
#else
    return {};
#endif
}

QString fileSha256( const QString& path )
{
    if ( path.isEmpty() )
    {
        return {};
    }
    QFile file( path );
    if ( !file.open( QIODevice::ReadOnly ) )
    {
        return {};
    }
    QCryptographicHash hash( QCryptographicHash::Sha256 );
    while ( !file.atEnd() )
    {
        hash.addData( file.read( 1024 * 1024 ) );
    }
    return QString::fromLatin1( hash.result().toHex() );
}

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

ccHObject* firstGeometryEntity( ccHObject* root )
{
    if ( !root )
    {
        return nullptr;
    }
    if ( root->isKindOf( CC_TYPES::MESH ) || root->isKindOf( CC_TYPES::POINT_CLOUD ) )
    {
        return root;
    }
    for ( unsigned i = 0; i < root->getChildrenNumber(); ++i )
    {
        if ( ccHObject* found = firstGeometryEntity( root->getChild( i ) ) )
        {
            return found;
        }
    }
    return nullptr;
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

QModelIndex findEntityIndex( QAbstractItemModel* model, ccHObject* entity, const QModelIndex& parent = QModelIndex() )
{
    if ( !model || !entity )
    {
        return {};
    }

    const int rows = model->rowCount( parent );
    for ( int row = 0; row < rows; ++row )
    {
        const QModelIndex index = model->index( row, 0, parent );
        if ( index.isValid() && index.internalPointer() == entity )
        {
            return index;
        }

        const QModelIndex child = findEntityIndex( model, entity, index );
        if ( child.isValid() )
        {
            return child;
        }
    }
    return {};
}

QTreeView* dbTreeView( ccMainAppInterface* app )
{
    QMainWindow* window = app ? app->getMainWindow() : nullptr;
    return window ? window->findChild<QTreeView*>( "dbTreeView" ) : nullptr;
}

QJsonArray idsToJson( const QList<unsigned>& ids )
{
    QJsonArray array;
    for ( unsigned id : ids )
    {
        array.append( static_cast<qint64>( id ) );
    }
    return array;
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
    m_sessionId = QUuid::createUuid().toString( QUuid::WithoutBraces );

    connect( m_server, &QTcpServer::newConnection, this, &qMCPBridge::onNewConnection );
}

qMCPBridge::~qMCPBridge()
{
    qMCPFusionWorkflow::shutdownInteractiveState();
    stopServer();
}

void qMCPBridge::setMainAppInterface( ccMainAppInterface* app )
{
    if ( !app )
    {
        qMCPFusionWorkflow::shutdownInteractiveState();
    }

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
        if ((method == "view.camera" || method == "view.capture") && result.isObject()
            && result.toObject().value("camera_diagnostics").isObject())
            response["error_details"]=result.toObject().value("camera_diagnostics");
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
        result[ "plugin_version" ] = "0.14.0";
        result[ "workflow_revision" ] = 10;
        result[ "process_id" ] = QCoreApplication::applicationPid();
        result[ "session_id" ] = m_sessionId;
        addApplicationVersion( result );
        result[ "port" ] = static_cast<int>( m_port );
        result[ "selected_ids" ] = selectedIds( m_app );
        ccHObject* root = m_app->dbRootObject();
        result[ "root_children" ] = root ? static_cast<int>( root->getChildrenNumber() ) : 0;
        return result;
    }

    if ( method == "runtime.handshake" )
    {
        QJsonValue workflowValue;
        QString workflowError;
        if ( !qMCPFusionWorkflow::dispatch(
                 m_app,
                 "capabilities.get",
                 QJsonObject(),
                 workflowValue,
                 workflowError )
             || !workflowError.isEmpty()
             || !workflowValue.isObject() )
        {
            error = workflowError.isEmpty()
                ? "Native capability catalog is unavailable"
                : workflowError;
            return {};
        }

        const QJsonObject capabilities = workflowValue.toObject();
        QJsonObject result;
        result[ "handshake_contract" ] = "cc-runtime-handshake-v1";
        result[ "protocol_version" ] = 1;
        result[ "plugin" ] = "qMCPBridge";
        result[ "plugin_version" ] = "0.14.0";
        result[ "workflow_revision" ] = capabilities.value( "workflow_revision" );
        result[ "supported_operations" ] = capabilities.value( "bridge_operations" );
        result[ "process_id" ] = QCoreApplication::applicationPid();
        result[ "session_id" ] = m_sessionId;
        result[ "port" ] = static_cast<int>( m_port );
        result[ "selected_ids" ] = selectedIds( m_app );
        ccHObject* root = m_app->dbRootObject();
        result[ "root_children" ] =
            root ? static_cast<int>( root->getChildrenNumber() ) : 0;
        addApplicationVersion( result );

        const QString modulePath = loadedModulePath();
        const QString moduleHash = fileSha256( modulePath );
        result[ "loaded_module_path" ] = modulePath;
        result[ "loaded_module_sha256" ] = moduleHash;
        result[ "loaded_module_identity_available" ] =
            !modulePath.isEmpty() && !moduleHash.isEmpty();
        result[ "build_identity" ] =
            QString( "qMCPBridge/0.14.0 workflow/%1" )
                .arg( capabilities.value( "workflow_revision" ).toInt() );
        result[ "safe_recovery" ] = QJsonObject{
            { "loaded_dll_change_requires_restart", true },
            { "automatic_restart_allowed", false },
            { "automatic_loaded_dll_replacement_allowed", false },
            { "preserve_open_scene_first", true },
        };
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

        QList<unsigned> requested;
        QList<unsigned> missing;
        QJsonArray invalid;
        QSet<unsigned> seen;
        for ( const QJsonValue& value : ids )
        {
            if ( !value.isDouble() )
            {
                invalid.append( value );
                continue;
            }

            const double raw = value.toDouble();
            if ( raw < 0.0
                 || raw > static_cast<double>( std::numeric_limits<unsigned>::max() )
                 || std::floor( raw ) != raw )
            {
                invalid.append( value );
                continue;
            }

            const unsigned id = static_cast<unsigned>( raw );
            if ( seen.contains( id ) )
            {
                continue; // stable de-duplication: first occurrence wins
            }
            seen.insert( id );

            if ( findEntity( id ) )
            {
                requested.append( id );
            }
            else
            {
                missing.append( id );
            }
        }

        QTreeView* tree = dbTreeView( m_app );
        QItemSelectionModel* selectionModel = tree ? tree->selectionModel() : nullptr;
        QAbstractItemModel* model = tree ? tree->model() : nullptr;

        if ( clearFirst )
        {
            if ( selectionModel )
            {
                selectionModel->clearSelection();
            }
            else
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
        }

        QList<unsigned> unresolved;
        for ( unsigned id : requested )
        {
            ccHObject* entity = findEntity( id );
            bool selected = false;

            if ( selectionModel && model && entity )
            {
                const QModelIndex index = findEntityIndex( model, entity );
                if ( index.isValid() )
                {
                    selectionModel->select( index, QItemSelectionModel::Select | QItemSelectionModel::Rows );
                    selected = selectionModel->isSelected( index );
                    entity->setSelected( selected );
                }
            }

            // Fallback is reliable for a single entity, but older CloudCompare
            // versions may replace the prior selection on each call.
            if ( !selected && entity )
            {
                m_app->setSelectedInDB( entity, true );
            }
        }

        QCoreApplication::processEvents();
        m_app->updateUI();

        const QJsonArray actual = selectedIds( m_app );
        QSet<unsigned> actualSet;
        for ( const QJsonValue& value : actual )
        {
            actualSet.insert( static_cast<unsigned>( value.toDouble() ) );
        }
        for ( unsigned id : requested )
        {
            if ( !actualSet.contains( id ) )
            {
                unresolved.append( id );
            }
        }

        QJsonObject result;
        result[ "requested_ids" ] = idsToJson( requested );
        result[ "selected_ids" ] = actual;
        result[ "missing_ids" ] = idsToJson( missing );
        result[ "invalid_ids" ] = invalid;
        result[ "unresolved_ids" ] = idsToJson( unresolved );
        result[ "duplicates_ignored" ] = ids.size() - requested.size() - missing.size() - invalid.size();
        result[ "matched_request" ] = unresolved.isEmpty() && ( !clearFirst || actualSet.size() == requested.size() );
        result[ "selection_backend" ] = selectionModel ? "db_tree_selection_model" : "main_app_fallback";
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

        ccHObject* destination = nullptr;
        if ( params.contains( "destination_group_id" ) )
        {
            unsigned destinationId = 0;
            if ( !readId( params, "destination_group_id", destinationId ) )
            {
                error = "file.load destination_group_id must be a valid numeric entity ID";
                return {};
            }

            destination = findEntity( destinationId );
            if ( !destination )
            {
                error = QString( "Destination group %1 was not found" ).arg( destinationId );
                return {};
            }
            if ( !destination->isA( CC_TYPES::HIERARCHY_OBJECT ) )
            {
                error = QString( "Entity %1 is not a plain hierarchy/group destination" ).arg( destinationId );
                return {};
            }
        }

        QString requestedName;
        if ( params.contains( "name" ) )
        {
            requestedName = params.value( "name" ).toString().trimmed();
            if ( requestedName.isEmpty() )
            {
                error = "file.load name must be non-empty when supplied";
                return {};
            }
        }

        ccHObject* loaded = m_app->loadFile( path, true );
        if ( !loaded )
        {
            error = QString( "CloudCompare failed to load: %1" ).arg( path );
            return {};
        }

        if ( !requestedName.isEmpty() )
        {
            ccHObject* geometry = firstGeometryEntity( loaded );
            if ( !geometry )
            {
                delete loaded;
                error = "Loaded file contains no point cloud or mesh to name";
                return {};
            }
            geometry->setName( requestedName );
        }

        // loadFile only constructs the hierarchy; the caller must register it
        // with the application's database and displays. If a working group was
        // requested, establish that parent before registration.
        if ( destination )
        {
            destination->addChild( loaded );
        }
        m_app->addToDB( loaded, true );
        m_app->redrawAll();
        m_app->updateUI();
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

    if ( method == "view.camera" )
        return qMCPCamera::dispatch(m_app, params, error);

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

        const QJsonObject cameraBefore = qMCPCamera::snapshot(window);
        for (auto it=params.begin();it!=params.end();++it)
            if (it.key()!="expected_camera_fingerprint" && it.key()!="expected_camera_guard_fingerprint"
                && it.key()!="native_session" && it.key()!="window_id")
            { error="Unexpected viewport capture parameter"; return {}; }
        if (!qMCPCameraGuard::matches(params,cameraBefore,false))
        { error="Camera changed before viewport capture";
          return qMCPCamera::refusal("capture.precondition",params,cameraBefore); }
        if (qMCPCamera::autoPivotOwnershipViolated(window))
        { error="Automatic center pivot changed during saved camera ownership";
          return qMCPCamera::autoPivotRefusal("capture.auto_pivot_ownership",cameraBefore); }
        m_app->redrawAll();
        QCoreApplication::processEvents();
        // Reacquire: event processing may close/switch the window or execute a request.
        window = m_app->getActiveGLWindow();
        const QJsonObject captureStart=qMCPCamera::snapshot(window);
        const QString equalityKey=params.contains("expected_camera_fingerprint")
            ? "camera_fingerprint" : "camera_guard_fingerprint";
        if (!window || captureStart.value(equalityKey)!=cameraBefore.value(equalityKey))
        { error="Camera/window changed during viewport capture";
          return qMCPCamera::refusal("capture.after_redraw",cameraBefore,captureStart); }
        if (qMCPCamera::autoPivotOwnershipViolated(window))
        { error="Automatic center pivot changed during viewport capture";
          return qMCPCamera::autoPivotRefusal("capture.after_redraw_auto_pivot",captureStart); }
        // Styling may settle during redraw, but MUST remain stable across the grab.
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

        window = m_app->getActiveGLWindow();
        const QJsonObject cameraAfter = qMCPCamera::snapshot(window);
        if (cameraAfter.value("camera_fingerprint") != captureStart.value("camera_fingerprint"))
        { error = "Camera/window changed while grabbing framebuffer";
          return qMCPCamera::refusal("capture.after_grab",captureStart,cameraAfter); }
        if (qMCPCamera::autoPivotOwnershipViolated(window))
        { error="Automatic center pivot changed while grabbing framebuffer";
          return qMCPCamera::autoPivotRefusal("capture.after_grab_auto_pivot",cameraAfter); }
        QJsonObject result;
        result["camera_state"] = cameraAfter;
        result["camera_before_redraw"]=cameraBefore;
        result["redraw_difference"]=qMCPCameraGuard::difference(cameraBefore,captureStart);
        result["png_sha256"] = QString::fromLatin1(QCryptographicHash::hash(png, QCryptographicHash::Sha256).toHex());
        result["capture_contract"] = "cc-viewport-capture-v1";
        result[ "width" ] = image.width();
        result[ "height" ] = image.height();
        result[ "png_base64" ] = QString::fromLatin1( png.toBase64() );
        return result;
    }

    QJsonValue workflowResult;
    if ( qMCPFusionWorkflow::dispatch( m_app, method, params, workflowResult, error ) )
    {
        if (method == "capabilities.get" && workflowResult.isObject())
        {
            QJsonObject caps=workflowResult.toObject();
            caps["plugin_version"]="0.14.0";
            QJsonObject camera=caps.value("camera").toObject();
            camera["guard_contract"]="cc-camera-guard-v1";
            camera["diagnostics_contract"]="cc-camera-diagnostics-v1";
            camera["auto_pivot_contract"]="cc-camera-auto-pivot-v1";
            camera["save_can_suspend_auto_pivot"]=true;
            caps["camera"]=camera;
            return caps;
        }
        return workflowResult;
    }

    error = QString( "Unknown bridge method: %1" ).arg( method );
    return {};
}

QJsonObject qMCPBridge::entityToJson( ccHObject* entity, bool recursive ) const
{
    return qMCPFusionWorkflow::describeEntity( entity, recursive );
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
