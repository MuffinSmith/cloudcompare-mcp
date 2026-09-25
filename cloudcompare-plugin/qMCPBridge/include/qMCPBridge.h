// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "ccStdPluginInterface.h"

#include <QJsonObject>
#include <QJsonValue>

class QAction;
class QTcpServer;
class QTcpSocket;

class qMCPBridge final : public QObject, public ccStdPluginInterface
{
    Q_OBJECT
    Q_INTERFACES( ccPluginInterface ccStdPluginInterface )
    Q_PLUGIN_METADATA( IID "cccorp.cloudcompare.plugin.qMCPBridge" FILE "../info.json" )

public:
    explicit qMCPBridge( QObject* parent = nullptr );
    ~qMCPBridge() override;

    void setMainAppInterface( ccMainAppInterface* app ) override;
    void onNewSelection( const ccHObject::Container& selectedEntities ) override;
    QList<QAction*> getActions() override;

private:
    bool startServer();
    void stopServer();
    void updateAction();
    void onNewConnection();
    void processSocket( QTcpSocket* socket );

    QJsonObject handleRequest( const QJsonObject& request );
    QJsonValue dispatch( const QString& method, const QJsonObject& params, QString& error );

    QJsonObject entityToJson( ccHObject* entity, bool recursive ) const;
    ccHObject* findEntity( unsigned uniqueId ) const;
    ccHObject* findEntityRecursive( ccHObject* parent, unsigned uniqueId ) const;

    QTcpServer* m_server = nullptr;
    QAction* m_action = nullptr;
    quint16 m_port = 8765;
    QString m_token;
};
