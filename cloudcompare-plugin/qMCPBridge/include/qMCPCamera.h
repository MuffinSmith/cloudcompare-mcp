// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QJsonObject>
class ccMainAppInterface;
class ccGLWindowInterface;
namespace qMCPCamera
{
QJsonObject snapshot(ccGLWindowInterface* window);
QJsonObject dispatch(ccMainAppInterface* app, const QJsonObject& params, QString& error);
}
