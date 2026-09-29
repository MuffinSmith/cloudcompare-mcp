// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QJsonObject>
class ccMainAppInterface;
class ccGLWindowInterface;
namespace qMCPCamera
{
QJsonObject refusal(const QString& stage, const QJsonObject& expected, const QJsonObject& current);
QJsonObject autoPivotRefusal(const QString& stage, const QJsonObject& current);
bool autoPivotOwnershipViolated(ccGLWindowInterface* window);
QJsonObject snapshot(ccGLWindowInterface* window);
QJsonObject dispatch(ccMainAppInterface* app, const QJsonObject& params, QString& error);
}
