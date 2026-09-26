// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QJsonObject>
#include <QJsonValue>
#include <QString>

class ccHObject;
class ccMainAppInterface;

namespace qMCPFusionWorkflow
{
// Stops any persistent interactive picking listener before the plugin/app detaches.
void shutdownInteractiveState();

// Rich, unit-neutral entity description shared by scene.list and workflow tools.
QJsonObject describeEntity( ccHObject* entity, bool recursive );

// Handles workflow-specific bridge methods. Returns true when the method name
// belongs to this module (including methods that fail validation).
bool dispatch(
    ccMainAppInterface* app,
    const QString& method,
    const QJsonObject& params,
    QJsonValue& result,
    QString& error );
}
