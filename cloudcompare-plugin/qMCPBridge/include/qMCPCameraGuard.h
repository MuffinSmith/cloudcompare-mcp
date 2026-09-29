// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>

// The production dispatcher and the standalone Qt tests share these exact rules.
namespace qMCPCameraGuard
{
inline QJsonObject payload(const QJsonObject& state)
{
    QJsonObject p = state.value("parameters").toObject();
    // Only display styling and redundant directions are outside navigation ownership.
    // Projection, explicit clipping, display scale, mode and all future fields stay guarded.
    for (const char* key : {"point_size", "line_width", "view_direction_host", "up_direction_host"})
        p.remove(QLatin1String(key));
    QJsonObject result{{"contract", "cc-camera-guard-v1"}, {"parameters", p}};
    for (const char* key : {"native_session", "window_id", "viewport_width", "viewport_height"})
        result.insert(QLatin1String(key), state.value(QLatin1String(key)));
    return result;
}
inline QString fingerprint(const QJsonObject& state)
{
    const QByteArray bytes = QByteArray("cc-camera-guard-v1\0", 19)
        + QJsonDocument(payload(state)).toJson(QJsonDocument::Compact);
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}
inline bool isDigest(const QJsonValue& value)
{
    if (!value.isString()) return false;
    const QString s = value.toString();
    if (s.size() != 64) return false;
    for (QChar c : s)
        if (!((c >= QLatin1Char('0') && c <= QLatin1Char('9'))
            || (c >= QLatin1Char('a') && c <= QLatin1Char('f')))) return false;
    return true;
}
inline bool matches(const QJsonObject& args, const QJsonObject& state, bool required = true)
{
    const bool legacy = args.contains("expected_camera_fingerprint");
    const bool modern = args.contains("expected_camera_guard_fingerprint");
    if (legacy && modern) return false; // Never silently prefer a weaker interpretation.
    if (!legacy && !modern) return !required && !args.contains("native_session") && !args.contains("window_id");
    const QString key = legacy ? "expected_camera_fingerprint" : "expected_camera_guard_fingerprint";
    const QString observed = legacy ? "camera_fingerprint" : "camera_guard_fingerprint";
    if (!isDigest(args.value(key)) || args.value(key) != state.value(observed)) return false;
    if (args.contains("native_session") && args.value("native_session") != state.value("native_session")) return false;
    if (args.contains("window_id") && args.value("window_id") != state.value("window_id")) return false;
    return true;
}
inline QJsonArray changedFields(const QJsonObject& before, const QJsonObject& after)
{
    QStringList keys = before.keys();
    for (const QString& key : after.keys()) if (!keys.contains(key)) keys.append(key);
    keys.sort();
    QJsonArray changed;
    for (const QString& key : keys) if (before.value(key) != after.value(key)) changed.append(key);
    return changed;
}
inline QJsonObject difference(const QJsonObject& before, const QJsonObject& after)
{
    QJsonObject topBefore, topAfter;
    for (const char* key : {"native_session", "window_id", "viewport_width", "viewport_height"})
    {
        topBefore.insert(QLatin1String(key), before.value(QLatin1String(key)));
        topAfter.insert(QLatin1String(key), after.value(QLatin1String(key)));
    }
    QJsonObject controlBefore{{"auto_pick_pivot_at_center", before.value("auto_pick_pivot_at_center")}};
    QJsonObject controlAfter{{"auto_pick_pivot_at_center", after.value("auto_pick_pivot_at_center")}};
    return {{"identity_fields", changedFields(topBefore, topAfter)},
        {"parameter_fields", changedFields(before.value("parameters").toObject(), after.value("parameters").toObject())},
        {"control_fields", changedFields(controlBefore, controlAfter)},
        {"guard_equal", !before.isEmpty() && !after.isEmpty() && payload(before) == payload(after)},
        {"full_equal", !before.isEmpty() && !after.isEmpty()
            && before.value("camera_fingerprint") == after.value("camera_fingerprint")}};
}
}
