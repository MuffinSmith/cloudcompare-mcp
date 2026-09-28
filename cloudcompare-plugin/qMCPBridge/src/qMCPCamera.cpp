// SPDX-License-Identifier: GPL-2.0-or-later
#include "qMCPCamera.h"
#include "qMCPCameraPolicy.h"
#include "qMCPCameraGuard.h"
#include <ccMainAppInterface.h>
#include <ccGLWindowInterface.h>
#include <ccViewportParameters.h>
#include <ccPointCloud.h>
#include <QCryptographicHash>
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QUuid>
#include <QSet>
#include <map>
#include <deque>

namespace qMCPCamera
{
namespace
{
const QString& session()
{
    static const QString id=QUuid::createUuid().toString(QUuid::WithoutBraces);
    return id;
}
QJsonArray vec(const CCVector3d& v) { return {v.x,v.y,v.z}; }
QJsonArray matrix(const ccGLMatrixd& m)
{
    QJsonArray a; for (int i=0;i<16;++i) a.append(m.data()[i]); return a;
}
QJsonValue nullable(double x) { return std::isfinite(x) ? QJsonValue(x) : QJsonValue(QJsonValue::Null); }
bool number(const QJsonObject& o, const char* key, double& x, double lo, double hi)
{
    const QJsonValue v=o.value(QLatin1String(key));
    if (!v.isDouble()) return false;
    x=v.toDouble(); return qMCPCameraPolicy::bounded(x,lo,hi);
}
bool readVector(const QJsonObject& o, const char* key, double* v, double limit=1.0e12)
{
    const QJsonArray a=o.value(QLatin1String(key)).toArray();
    if (a.size()!=3) return false;
    for (int i=0;i<3;++i) { if (!a[i].isDouble()) return false; v[i]=a[i].toDouble(); }
    return qMCPCameraPolicy::vector(v,limit);
}
bool valid(const ccViewportParameters& p)
{
    return p.objectCenteredView && qMCPCameraPolicy::rotation(p.viewMat.data())
        && qMCPCameraPolicy::vector(p.getPivotPoint().u)
        && qMCPCameraPolicy::vector(p.getCameraCenter().u)
        && qMCPCameraPolicy::bounded(p.getFocalDistance(),1.0e-9,1.0e12)
        && qMCPCameraPolicy::bounded(p.fov_deg,1.0,170.0)
        && qMCPCameraPolicy::bounded(p.cameraAspectRatio,0.01,100.0);
}
bool supported(ccGLWindowInterface* w)
{
    return w && valid(w->getViewportParameters()) && !w->bubbleViewModeEnabled()
        && !w->stereoModeIsEnabled() && w->getDisplayScale().x==1.0 && w->getDisplayScale().y==1.0;
}
struct Saved
{
    ccViewportParameters params;
    int window, width, height;
    bool clipping;
    bool autoPivotSuspended, autoPivotOriginal;
    CCVector2d displayScale;
    QString fingerprint, guardFingerprint;
    explicit Saved(ccGLWindowInterface* w, const QString& fp, bool suspendAutoPivot)
        : params(w->getViewportParameters()), window(w->getUniqueID()), width(w->glWidth()),
          height(w->glHeight()), clipping(w->clippingPlanesEnabled()),
          autoPivotSuspended(suspendAutoPivot), autoPivotOriginal(w->autoPickPivotAtCenter()),
          displayScale(w->getDisplayScale()), fingerprint(fp), guardFingerprint() {}
};
// Bounded diagnostic history, never an authorization cache. Token storage is separate.
std::deque<QJsonObject>& observedStates() { static std::deque<QJsonObject> s; return s; }
void remember(const QJsonObject& s)
{
    auto& history = observedStates();
    if (history.size() >= 32) history.pop_front();
    history.push_back(s);
}
std::map<QString,Saved>& saved() { static std::map<QString,Saved> s; return s; }
// At most one suspended automatic-pivot owner per window. Ordinary save tokens do
// not participate. This makes the host behavior explicit without weakening pose guards.
std::map<int,QString>& autoPivotOwners() { static std::map<int,QString> s; return s; }
ccHObject* find(ccHObject* root, unsigned id)
{
    if (!root) return nullptr;
    if (root->getUniqueID()==id) return root;
    for (unsigned i=0;i<root->getChildrenNumber();++i)
        if (auto* found=find(root->getChild(i),id)) return found;
    return nullptr;
}
bool focus(ccMainAppInterface* app, const QJsonObject& a, ccViewportParameters& p, int width, int height)
{
    double rawId;
    if (!number(a,"entity_id",rawId,1.0,4294967295.0) || std::floor(rawId)!=rawId) return false;
    auto* entity=find(app->dbRootObject(),static_cast<unsigned>(rawId));
    if (!entity || !entity->isA(CC_TYPES::POINT_CLOUD)) return false;
    for (ccHObject* node=entity;node;node=node->getParent())
        if (node->isGLTransEnabled() || !node->isEnabled()) return false;
    if (!entity->isVisible() || entity->getDisplay()!=app->getActiveGLWindow()) return false;
    auto* cloud=static_cast<ccPointCloud*>(entity);
    const double scale=cloud->getGlobalScale();
    if (!qMCPCameraPolicy::bounded(scale,1.0e-12,1.0e12)) return false;
    CCVector3d center;
    double fitWidth=0.0;
    if (a.contains("center_global"))
    {
        double c[3], globalWidth;
        if (a.contains("min_global") || a.contains("max_global")
            || !readVector(a,"center_global",c,1.0e15)
            || !number(a,"width_global",globalWidth,1.0e-12,1.0e15)) return false;
        center=cloud->toLocal3d<double>(CCVector3d(c[0],c[1],c[2]));
        fitWidth=globalWidth*scale;
    }
    else if (a.contains("min_global") || a.contains("max_global"))
    {
        double lo[3],hi[3];
        if (a.contains("width_global") || !readVector(a,"min_global",lo,1.0e15)
            || !readVector(a,"max_global",hi,1.0e15) || !qMCPCameraPolicy::bounds(lo,hi)) return false;
        const CCVector3d low(lo[0],lo[1],lo[2]), high(hi[0],hi[1],hi[2]);
        center=cloud->toLocal3d<double>(low+(high-low)*0.5);
        fitWidth=(high-low).normd()*scale*1.1;
    }
    else
    {
        if (a.contains("width_global")) return false;
        const ccBBox box=cloud->getOwnBB();
        if (!box.isValid()) return false;
        const CCVector3d low(box.minCorner()), high(box.maxCorner());
        center=low+(high-low)*0.5;
        fitWidth=(high-low).normd()*1.1;
    }
    // Fixed display framing margin only; never a reconstruction ROI or fit tolerance.
    fitWidth*=std::max(1.0,static_cast<double>(width)/(height*p.cameraAspectRatio));
    const double focal=fitWidth/p.computeDistanceToWidthRatio();
    if (!qMCPCameraPolicy::vector(center.u) || !qMCPCameraPolicy::bounded(focal,1.0e-9,1.0e12)) return false;
    p.setPivotPoint(center,false);
    p.setCameraCenter(center,false);
    p.setFocalDistance(focal);
    return true;
}
}
QJsonObject snapshot(ccGLWindowInterface* w)
{
    if (!w) return {};
    const auto& p=w->getViewportParameters();
    QJsonObject parameters{
        {"view_rotation_column_major",matrix(p.viewMat)},
        {"pivot_host",vec(p.getPivotPoint())}, {"camera_center_host",vec(p.getCameraCenter())},
        {"view_direction_host",vec(p.getViewDir())}, {"up_direction_host",vec(p.getUpDir())},
        {"focal_distance",p.getFocalDistance()}, {"fov_degrees",p.fov_deg},
        {"camera_aspect_ratio",p.cameraAspectRatio}, {"perspective",p.perspectiveView},
        {"object_centered",p.objectCenteredView}, {"z_near_coefficient",p.zNearCoef},
        {"near_clipping_depth",nullable(p.nearClippingDepth)}, {"far_clipping_depth",nullable(p.farClippingDepth)},
        {"point_size",p.defaultPointSize}, {"line_width",p.defaultLineWidth},
        {"clipping_enabled",w->clippingPlanesEnabled()},
        {"display_scale",QJsonArray{w->getDisplayScale().x,w->getDisplayScale().y}},
        {"bubble_view",w->bubbleViewModeEnabled()}, {"stereo",w->stereoModeIsEnabled()}
    };
    QJsonObject result{{"contract","cc-camera-v1"},{"native_session",session()},
        {"window_id",w->getUniqueID()},{"viewport_width",w->glWidth()},{"viewport_height",w->glHeight()},
        {"parameters",parameters}};
    const QByteArray canonical=QJsonDocument(result).toJson(QJsonDocument::Compact);
    result["camera_fingerprint"]=QString::fromLatin1(QCryptographicHash::hash(canonical,QCryptographicHash::Sha256).toHex());
    result["camera_guard_contract"]="cc-camera-guard-v1";
    result["camera_guard_fingerprint"]=qMCPCameraGuard::fingerprint(result);
    result["camera_guard_scope"]="exact_navigation_projection_clipping_window_size; excludes_point_line_size_and_redundant_directions";
    // Host interaction control, deliberately OUTSIDE the legacy full camera hash and
    // navigation guard. A suspended save token owns this control separately.
    result["auto_pivot_contract"]="cc-camera-auto-pivot-v1";
    result["auto_pick_pivot_at_center"]=w->autoPickPivotAtCenter();
    result["computed_view_matrix_column_major"]=matrix(p.computeViewMatrix());
    result["derived_z_near"]=nullable(p.zNear); result["derived_z_far"]=nullable(p.zFar);
    result["navigation_supported"]=supported(w);
    result["coordinate_policy"]="host_render_frame_not_global; camera_center_host_is_CloudCompare_parameter_not_world_eye";
    result["restore_scope"]="ccViewportParameters_and_display_scale_clipping; same_session_window_size; excludes_scene_GUI_stereo_bubble_LOD_framebuffer";
    remember(result);
    return result;
}
QJsonObject refusal(const QString& stage, const QJsonObject& expected, const QJsonObject& current)
{
    QJsonObject reference;
    if (expected.contains("parameters")) reference=expected;
    else
    {
        const bool modern=expected.contains("expected_camera_guard_fingerprint");
        const QString key=modern ? "camera_guard_fingerprint" : "camera_fingerprint";
        const QJsonValue fp=expected.value(modern ? "expected_camera_guard_fingerprint" : "expected_camera_fingerprint");
        if (qMCPCameraGuard::isDigest(fp))
            for (auto it=observedStates().rbegin();it!=observedStates().rend();++it)
                if (it->value(key)==fp) { reference=*it; break; }
    }
    QJsonObject detail{{"contract","cc-camera-diagnostics-v1"},{"stage",stage},
        {"reference_available",!reference.isEmpty()}, {"reference",reference}, {"current",current},
        {"difference",qMCPCameraGuard::difference(reference,current)}, {"authorizes_retry",false}};
    for (const char* key : {"expected_camera_fingerprint","expected_camera_guard_fingerprint","native_session","window_id"})
        if (expected.contains(QLatin1String(key))) detail.insert(QLatin1String(key),expected.value(QLatin1String(key)));
    return {{"camera_diagnostics",detail}};
}
QJsonObject autoPivotRefusal(const QString& stage, const QJsonObject& current)
{
    QJsonObject expected=current;
    expected["auto_pick_pivot_at_center"]=false;
    QJsonObject result=refusal(stage,expected,current);
    QJsonObject detail=result.value("camera_diagnostics").toObject();
    detail["auto_pivot_contract"]="cc-camera-auto-pivot-v1";
    detail["expected_auto_pick_pivot_at_center"]=false;
    detail["current_auto_pick_pivot_at_center"]=current.value("auto_pick_pivot_at_center");
    result["camera_diagnostics"]=detail;
    return result;
}
bool autoPivotOwnershipViolated(ccGLWindowInterface* w)
{
    if (!w) return false;
    return autoPivotOwners().find(w->getUniqueID())!=autoPivotOwners().end()
        && w->autoPickPivotAtCenter();
}
QJsonObject dispatch(ccMainAppInterface* app, const QJsonObject& a, QString& error)
{
    const QString action=a.value("action").toString();
    QSet<QString> allowed{"action"};
    if (action=="release") allowed.unite(QSet<QString>{"native_session","restore_token"});
    else if (action=="save") allowed.insert("suspend_auto_pivot");
    else if (action!="get" && action!="save")
    {
        allowed.unite(QSet<QString>{"native_session","window_id","expected_camera_fingerprint","expected_camera_guard_fingerprint"});
        if (action=="restore") allowed.insert("restore_token");
        else if (action=="look") allowed.unite(QSet<QString>{"direction","up"});
        else if (action=="orbit") allowed.unite(QSet<QString>{"axis_camera","degrees"});
        else if (action=="pan") allowed.unite(QSet<QString>{"right_fraction","up_fraction"});
        else if (action=="zoom") allowed.insert("factor");
        else if (action=="focus") allowed.unite(QSet<QString>{"entity_id","center_global","width_global","min_global","max_global"});
        else { error="Unknown camera action"; return {}; }
    }
    for (auto it=a.begin();it!=a.end();++it)
        if (!allowed.contains(it.key())) { error="Unexpected camera parameter: "+it.key(); return {}; }
    const QString token=a.value("restore_token").toString();
    if (action=="release")
    {
        auto it=saved().find(token);
        if (a.value("native_session").toString()!=session() || token.isEmpty() || it==saved().end())
            { error="Unknown camera token or native session"; return {}; }
        QJsonObject result{{"released",true}};
        const Saved s=it->second;
        if (s.autoPivotSuspended)
        {
            auto owner=autoPivotOwners().find(s.window);
            if (owner==autoPivotOwners().end() || owner->second!=token)
                { error="Automatic pivot ownership record is inconsistent; release refused"; return {}; }
            auto* active=app ? app->getActiveGLWindow() : nullptr;
            if (!active || active->getUniqueID()!=s.window)
                { error="Saved camera window is not active; automatic pivot release refused"; return {}; }
            const bool current=active->autoPickPivotAtCenter();
            const bool humanOverride=current; // suspension owns FALSE; TRUE was external.
            if (!humanOverride && s.autoPivotOriginal)
            {
                // Enabling CloudCompare's default auto-pivot deliberately schedules a
                // redraw. Let that one host-owned event turn finish, then report the
                // resulting camera state instead of hiding a post-release mutation.
                active->setAutoPickPivotAtCenter(true);
                QCoreApplication::processEvents();
            }
            result["auto_pivot_contract"]="cc-camera-auto-pivot-v1";
            result["auto_pivot_original_enabled"]=s.autoPivotOriginal;
            result["auto_pivot_external_override_preserved"]=humanOverride;
            active=app ? app->getActiveGLWindow() : nullptr;
            if (active && active->getUniqueID()==s.window)
            {
                result["auto_pivot_current_enabled"]=active->autoPickPivotAtCenter();
                result["auto_pivot_restored_to_original"]=(active->autoPickPivotAtCenter()==s.autoPivotOriginal);
                result["camera_state"]=snapshot(active);
            }
            else
            {
                result["auto_pivot_restored_to_original"]=false;
                result["window_changed_during_release"]=true;
            }
            autoPivotOwners().erase(owner);
        }
        saved().erase(it);
        return result;
    }
    auto* w=app ? app->getActiveGLWindow() : nullptr;
    if (!w) { error="No active 3D window"; return {}; }
    QJsonObject before=snapshot(w);
    if (action=="get") return before;
    if (action=="save")
    {
        if (a.contains("suspend_auto_pivot") && !a.value("suspend_auto_pivot").isBool())
            { error="suspend_auto_pivot must be a boolean"; return {}; }
        const bool suspendAutoPivot=a.value("suspend_auto_pivot").toBool(false);
        if (!supported(w) || w->glWidth()<=0 || w->glHeight()<=0)
            { error="Camera mode/state cannot be safely saved for inspection"; return {}; }
        if (saved().size()>=qMCPCameraPolicy::MaxSavedStates)
            { error="Camera save capacity reached; explicitly release unused tokens"; return {}; }
        if (suspendAutoPivot && autoPivotOwners().find(w->getUniqueID())!=autoPivotOwners().end())
            { error="Automatic center-pivot suspension is already owned by another camera token"; return {}; }
        const QString key=QUuid::createUuid().toString(QUuid::WithoutBraces);
        saved().emplace(key,Saved(w,before.value("camera_fingerprint").toString(),suspendAutoPivot));
        saved().at(key).guardFingerprint=before.value("camera_guard_fingerprint").toString();
        if (suspendAutoPivot)
        {
            autoPivotOwners()[w->getUniqueID()]=key;
            w->setAutoPickPivotAtCenter(false); // disabling does NOT schedule a redraw
        }
        QJsonObject result=snapshot(w);
        result["restore_token"]=key;
        result["auto_pivot_suspended_by_token"]=suspendAutoPivot;
        result["saved_auto_pick_pivot_at_center"]=saved().at(key).autoPivotOriginal;
        return result;
    }
    double windowId;
    if (!number(a,"window_id",windowId,0.0,2147483647.0) || windowId!=w->getUniqueID()
        || a.value("native_session").toString()!=session()
        || !qMCPCameraGuard::matches(a,before))
        { error="Camera session/window/fingerprint changed; movement refused"; return refusal("movement.precondition",a,before); }
    if (!supported(w) || w->glWidth()<=0 || w->glHeight()<=0)
        { error="Unsupported camera mode/state (requires object-centered, no stereo/bubble/display scale)"; return {}; }
    if (autoPivotOwnershipViolated(w))
        { error="Automatic center pivot changed during saved camera ownership; movement refused";
          return autoPivotRefusal("movement.auto_pivot_ownership",before); }
    if (action=="restore")
    {
        const auto it=saved().find(token);
        if (it==saved().end() || it->second.window!=w->getUniqueID()
            || it->second.width!=w->glWidth() || it->second.height!=w->glHeight())
            { error="Unknown camera token, different window or resized viewport; restore refused"; return {}; }
        const auto& s=it->second;
        ccViewportParameters restored=s.params;
        const bool navigationOnly=a.contains("expected_camera_guard_fingerprint");
        if (navigationOnly)
        {
            // A navigation guard never grants ownership of someone else's display style.
            restored.defaultPointSize=w->getViewportParameters().defaultPointSize;
            restored.defaultLineWidth=w->getViewportParameters().defaultLineWidth;
        }
        w->setViewportParameters(restored);
        w->setClippingPlanesEnabled(s.clipping); w->setDisplayScale(s.displayScale);
        QJsonObject applied=snapshot(w);
        w->redraw();
        if (s.autoPivotSuspended) QCoreApplication::processEvents();
        auto* settled=app ? app->getActiveGLWindow() : nullptr;
        auto result=snapshot(settled);
        if (!settled || settled->getUniqueID()!=s.window
            || (s.autoPivotSuspended && result.value("camera_guard_fingerprint")!=applied.value("camera_guard_fingerprint")))
        {
            error="Camera/window changed while restoring saved camera";
            return refusal("restore.after_redraw",applied,result);
        }
        result["restored_equal"]=result.value("camera_fingerprint").toString()==s.fingerprint;
        result["restored_guard_equal"]=result.value("camera_guard_fingerprint").toString()==s.guardFingerprint;
        result["restoration_scope"]=navigationOnly ? "navigation_preserving_current_point_line_size" : "legacy_full_viewport";
        result["restored_full_reference_fingerprint"]=s.fingerprint;
        result["auto_pivot_suspended_by_token"]=s.autoPivotSuspended;
        return result;
    }
    // Build a candidate copy; validation happens before the single host mutation.
    ccViewportParameters p=w->getViewportParameters();
    bool ok=false;
    if (action=="look")
    {
        double forward[3],up[3],m[16];
        ok=readVector(a,"direction",forward) && readVector(a,"up",up)
            && qMCPCameraPolicy::look(forward,up,m);
        if (ok) p.viewMat=ccGLMatrixd(m);
    }
    else if (action=="orbit")
    {
        double axis[3],degrees,m[16];
        ok=readVector(a,"axis_camera",axis) && number(a,"degrees",degrees,-180.0,180.0)
            && qMCPCameraPolicy::orbit(axis,degrees,m);
        if (ok) p.viewMat=ccGLMatrixd(m)*p.viewMat;
    }
    else if (action=="pan")
    {
        double x,y;
        ok=number(a,"right_fraction",x,-1.0,1.0) && number(a,"up_fraction",y,-1.0,1.0)
            && qMCPCameraPolicy::pan(x,y);
        if (ok)
        {
            auto c=p.getCameraCenter(); const double span=p.computeWidthAtFocalDist();
            c.x+=x*span; c.y+=y*span*w->glHeight()*p.cameraAspectRatio/w->glWidth();
            p.setCameraCenter(c,false);
        }
    }
    else if (action=="zoom")
    {
        double factor;
        ok=number(a,"factor",factor,0.1,10.0) && qMCPCameraPolicy::zoom(factor);
        if (ok) p.setFocalDistance(p.getFocalDistance()/factor);
    }
    else if (action=="focus") ok=focus(app,a,p,w->glWidth(),w->glHeight());
    if (!ok || !valid(p)) { error="Invalid or excessive camera movement; source/pending transform/mode may be unsupported"; return {}; }
    const int targetWindow=w->getUniqueID();
    w->setViewportParameters(p);
    QJsonObject applied=snapshot(w);
    w->redraw();
    // Complete one event turn before returning. This converts delayed host camera
    // changes into an immediate, attributable refusal. When inspection owns an
    // auto-pivot suspension, this should remain stable without any retry.
    QCoreApplication::processEvents();
    auto* settled=app ? app->getActiveGLWindow() : nullptr;
    QJsonObject result=snapshot(settled);
    if (!settled || settled->getUniqueID()!=targetWindow
        || result.value("camera_guard_fingerprint")!=applied.value("camera_guard_fingerprint"))
    {
        error="Camera/window changed after camera movement redraw";
        return refusal("movement.after_redraw",applied,result);
    }
    if (autoPivotOwnershipViolated(settled))
    {
        error="Automatic center pivot changed during saved camera ownership";
        return autoPivotRefusal("movement.auto_pivot_ownership",result);
    }
    return result;
}
}
