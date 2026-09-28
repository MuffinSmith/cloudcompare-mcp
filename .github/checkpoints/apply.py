from pathlib import Path
r=Path('.')
def replace(path,old,new):
 p=r/path;s=p.read_text();assert s.count(old)==1,(path,old,s.count(old));p.write_text(s.replace(old,new))
replace('cloudcompare-plugin/qMCPBridge/CMakeLists.txt',
'            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPBridge.cpp',
'            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPCamera.cpp\n            ${CMAKE_CURRENT_LIST_DIR}/include/qMCPCamera.h\n            ${CMAKE_CURRENT_LIST_DIR}/include/qMCPCameraPolicy.h\n            ${CMAKE_CURRENT_LIST_DIR}/src/qMCPBridge.cpp')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPBridge.cpp','#include "qMCPBridge.h"','#include "qMCPBridge.h"\n#include "qMCPCamera.h"\n#include <QCryptographicHash>')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPBridge.cpp','result[ "plugin_version" ] = "0.12.0";','result[ "plugin_version" ] = "0.13.0";')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPBridge.cpp','    if ( method == "view" )','    if ( method == "view.camera" )\n        return qMCPCamera::dispatch(m_app, params, error);\n\n    if ( method == "view" )')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPBridge.cpp','''        m_app->redrawAll();
        QCoreApplication::processEvents();

        const QImage image = window->doGrabFramebuffer();''','''        const QJsonObject cameraBefore = qMCPCamera::snapshot(window);
        if (params.contains("expected_camera_fingerprint")
            && params.value("expected_camera_fingerprint") != cameraBefore.value("camera_fingerprint"))
        { error = "Camera changed before viewport capture"; return {}; }
        m_app->redrawAll();
        QCoreApplication::processEvents();
        // processEvents can close/switch windows or execute another camera request.
        // Reacquire before dereferencing; do not use a potentially dangling pointer.
        window = m_app->getActiveGLWindow();
        if (!window || qMCPCamera::snapshot(window).value("camera_fingerprint") != cameraBefore.value("camera_fingerprint"))
        { error = "Camera/window changed during viewport capture"; return {}; }
        const QImage image = window->doGrabFramebuffer();''')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPBridge.cpp','''        QJsonObject result;
        result[ "width" ] = image.width();''','''        window = m_app->getActiveGLWindow();
        const QJsonObject cameraAfter = qMCPCamera::snapshot(window);
        if (cameraAfter.value("camera_fingerprint") != cameraBefore.value("camera_fingerprint"))
        { error = "Camera/window changed while grabbing framebuffer"; return {}; }
        QJsonObject result;
        result["camera_state"] = cameraAfter;
        result["png_sha256"] = QString::fromLatin1(QCryptographicHash::hash(png, QCryptographicHash::Sha256).toHex());
        result["capture_contract"] = "cc-viewport-capture-v1";
        result[ "width" ] = image.width();''')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPFusionWorkflow.cpp','result[ "workflow_revision" ] = 8;','result[ "workflow_revision" ] = 9;')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPFusionWorkflow.cpp','result[ "plugin_version" ] = "0.12.0";','result[ "plugin_version" ] = "0.13.0";')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPFusionWorkflow.cpp','''        "view.capture",
        "capabilities.get",''','''        "view.capture",
        "view.camera",
        "capabilities.get",''')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPFusionWorkflow.cpp','''    result[ "units_confirmed" ] = false;

    if ( ccHObject* parent''','''    result[ "units_confirmed" ] = false;
    bool pendingTransform = false;
    for (ccHObject* node = entity; node; node = node->getParent())
        pendingTransform = pendingTransform || node->isGLTransEnabled();
    result["pending_transform_in_hierarchy"] = pendingTransform;

    if ( ccHObject* parent''')
replace('cloudcompare-plugin/qMCPBridge/src/qMCPFusionWorkflow.cpp','''    result[ "bridge_operations" ] = bridgeOperations;''','''    result[ "bridge_operations" ] = bridgeOperations;
    result["camera"] = QJsonObject{{"available", true}, {"contract", "cc-camera-v1"},
        {"max_saved_states", 8}, {"capture_provenance", true},
        {"requires_object_centered_view", true}, {"stereo_bubble_supported", false}};''')
p=r/'.github/workflows/tests.yml';s=p.read_text().replace('  pull_request:\n','  pull_request:\n  workflow_dispatch:\n').replace('      - main\n','      - feature/live-agent-visual-inspection\n      - main\n')
s+='''
  native-plugin:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: CloudCompare/CloudCompare
          ref: v2.13.2
          path: host-source
          submodules: recursive
          persist-credentials: false
      - name: Install host build dependencies
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y ninja-build qtbase5-dev libqt5opengl5-dev qttools5-dev libqt5svg5-dev libeigen3-dev libglew-dev
      - name: Integrate exact bridge sources into declared host
        run: |
          cp -a cloudcompare-plugin/qMCPBridge host-source/plugins/core/Standard/
          printf '\\nadd_subdirectory(qMCPBridge)\\n' >> host-source/plugins/core/Standard/CMakeLists.txt
      - name: Configure CloudCompare 2.13.2
        run: cmake -S host-source -B host-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPLUGIN_STANDARD_QMCP_BRIDGE=ON -DOPTION_BUILD_CCVIEWER=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
      - name: Build actual native plugin
        run: cmake --build host-build --target QMCP_BRIDGE_PLUGIN --parallel 2
'''
p.write_text(s)
p=r/'AGENTS.md';s=p.read_text();s=s.replace('Native integration is pending the narrow checkpoint helper.','Native integration is applied; temporary checkpoint helper removed. Native 0.13.0 / revision 9 is now wired into dispatch and camera-bound PNG capture. CI including actual Linux CloudCompare 2.13.2 plugin compilation has been requested; inspect its real result.');p.write_text(s)
