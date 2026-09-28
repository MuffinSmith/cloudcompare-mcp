# One-shot guarded source integration. No numerical solver changes or workflow writes.
from pathlib import Path

def replace(path, old, new):
    p=Path(path);s=p.read_text()
    assert s.count(old)==1,(path,old,s.count(old))
    p.write_text(s.replace(old,new))

replace('src/cloudcompare_mcp/server.py','from .section_layer_tools import ',
        'from .inspection_tools import tools as inspection_tools, handlers as inspection_handlers, capabilities as inspection_capabilities\nfrom .section_layer_tools import ')
replace('src/cloudcompare_mcp/server.py','TOOLS.extend(section_layer_tools())',
        'TOOLS.extend(section_layer_tools())\nTOOLS.extend(inspection_tools())')
replace('src/cloudcompare_mcp/server.py','dispatch.update(section_layer_handlers(live_request))',
        'dispatch.update(section_layer_handlers(live_request))\n    dispatch.update(inspection_handlers(live_request))')
replace('src/cloudcompare_mcp/server.py','        native["python_feature_fitting"] = feature_fitting',
        '        camera = native.get("camera", {})\n        native["python_visual_inspection"] = inspection_capabilities(available=region_available and isinstance(camera, dict) and camera.get("available") is True and camera.get("contract") == "cc-camera-v1")\n        native["python_feature_fitting"] = feature_fitting')
replace('src/cloudcompare_mcp/server.py','        return [\n            ImageContent(type="image", data=png_b64, mimeType="image/png"),',
        '        for key in ("camera_state", "png_sha256", "capture_contract"):\n            if key in result:\n                metadata[key] = result[key]\n        return [\n            ImageContent(type="image", data=png_b64, mimeType="image/png"),')
replace('pyproject.toml','version = "0.15.7"','version = "0.16.0"')
for path in ('tests/test_section_spatial_intent_tools.py','tests/test_section_target_roi_stdio.py'):
    replace(path,"version('cloudcompare-mcp') == '0.15.7'","version('cloudcompare-mcp') == '0.16.0'")
replace('cloudcompare-plugin/qMCPBridge/src/qMCPCamera.cpp','    if (!entity->isVisible()) return false;',
        '    if (!entity->isVisible() || entity->getDisplay()!=app->getActiveGLWindow()) return false;')
replace('AGENTS.md','Python integration pending the one-shot source helper.',
        'Python 0.16.0 integration is applied. Seven new tools are registered; existing capture adds optional provenance; native focus now refuses a source displayed in another window. The helper source has been removed; remove its workflow through the connector before the final checkpoint.')
