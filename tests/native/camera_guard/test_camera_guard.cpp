// SPDX-License-Identifier: GPL-2.0-or-later
#include "qMCPCameraGuard.h"
#include <cstdlib>
#include <iostream>
using namespace qMCPCameraGuard;

QJsonObject state()
{
    QJsonObject p{{"view_rotation_column_major",QJsonArray{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1}},
        {"pivot_host",QJsonArray{0,0,0}},{"camera_center_host",QJsonArray{0,0,10}},
        {"view_direction_host",QJsonArray{0,0,-1}},{"up_direction_host",QJsonArray{0,1,0}},
        {"focal_distance",10.0},{"fov_degrees",50.0},{"camera_aspect_ratio",1.0},
        {"perspective",false},{"object_centered",true},{"z_near_coefficient",0.005},
        {"near_clipping_depth",QJsonValue(QJsonValue::Null)},{"far_clipping_depth",QJsonValue(QJsonValue::Null)},
        {"point_size",1.0},{"line_width",1.0},{"clipping_enabled",false},
        {"display_scale",QJsonArray{1,1}},{"bubble_view",false},{"stereo",false}};
    return {{"contract","cc-camera-v1"},{"native_session","session"},{"window_id",3},
        {"viewport_width",640},{"viewport_height",480},{"parameters",p}};
}
void stamp(QJsonObject& s)
{
    QJsonObject full{{"contract",s.value("contract")},{"native_session",s.value("native_session")},
        {"window_id",s.value("window_id")},{"viewport_width",s.value("viewport_width")},
        {"viewport_height",s.value("viewport_height")},{"parameters",s.value("parameters")}};
    s["camera_fingerprint"]=QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(full).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
    s["camera_guard_fingerprint"]=fingerprint(s);
}
int main(int argc,char** argv)
{
    if (argc!=2) return 2;
    const int id=std::atoi(argv[1]);
    auto a=state();stamp(a);auto b=a;
    auto p=b.value("parameters").toObject();
    const QStringList protectedKeys{"view_rotation_column_major","pivot_host","camera_center_host",
        "focal_distance","fov_degrees","camera_aspect_ratio","perspective","object_centered",
        "z_near_coefficient","near_clipping_depth","far_clipping_depth","clipping_enabled",
        "display_scale","bubble_view","stereo","future_navigation_control"};
    bool ok=false;
    if(id<16)
    {
        p[protectedKeys.at(id)]=QJsonArray{42};b["parameters"]=p;stamp(b);
        ok=a.value("camera_guard_fingerprint")!=b.value("camera_guard_fingerprint")
            && difference(a,b).value("parameter_fields").toArray().contains(protectedKeys.at(id));
    }
    else if(id<20)
    {
        const QString key=QStringList{"native_session","window_id","viewport_width","viewport_height"}.at(id-16);
        b[key]="different";stamp(b);
        ok=!difference(a,b).value("guard_equal").toBool()
            && a.value("camera_guard_fingerprint")!=b.value("camera_guard_fingerprint");
    }
    else if(id<24)
    {
        const QString key=QStringList{"point_size","line_width","view_direction_host","up_direction_host"}.at(id-20);
        p[key]=QJsonArray{42};b["parameters"]=p;stamp(b);
        ok=difference(a,b).value("guard_equal").toBool()
            && !difference(a,b).value("full_equal").toBool()
            && a.value("camera_guard_fingerprint")==b.value("camera_guard_fingerprint");
    }
    else if(id==24)
    {
        b["derived_z_near"]=123;b["computed_view_matrix_column_major"]=QJsonArray{42};stamp(b);
        ok=difference(a,b).value("guard_equal").toBool() && difference(a,b).value("full_equal").toBool();
    }
    else
    {
        QJsonObject args{{"expected_camera_guard_fingerprint",a.value("camera_guard_fingerprint")},
            {"native_session",a.value("native_session")},{"window_id",a.value("window_id")}};
        if(id==25) ok=matches(args,a);
        if(id==26) {p["point_size"]=2;b["parameters"]=p;stamp(b);ok=matches(args,b);}
        if(id==27) {p["line_width"]=2;b["parameters"]=p;stamp(b);ok=!matches(QJsonObject{{"expected_camera_fingerprint",a.value("camera_fingerprint")}},b);}
        if(id==28) {args["expected_camera_fingerprint"]=a.value("camera_fingerprint");ok=!matches(args,a);}
        if(id==29) {args["expected_camera_guard_fingerprint"]=true;ok=!matches(args,a);}
        if(id==30) {args["expected_camera_guard_fingerprint"]=QString(64,QLatin1Char('A'));ok=!matches(args,a);}
        if(id==31) {args["native_session"]="replacement";ok=!matches(args,a);}
        if(id==32) {args["window_id"]=true;ok=!matches(args,a);}
        if(id==33) ok=!matches(QJsonObject(),a) && matches(QJsonObject(),a,false);
        if(id==34) ok=!matches(QJsonObject{{"native_session","wrong"}},a,false)
            && !matches(QJsonObject{{"window_id",3}},a,false);
    }
    if (!ok) std::cerr<<"camera guard case "<<id<<" failed\n";
    return ok ? 0 : 1;
}
