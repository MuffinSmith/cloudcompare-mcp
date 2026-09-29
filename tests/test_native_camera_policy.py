"""Execute camera math used by the plugin. Not a Qt/plugin build or GUI test."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def camera_policy(tmp_path_factory):
    compiler = os.environ.get('CXX') or shutil.which('c++') or shutil.which('g++') or shutil.which('cl')
    if not compiler:
        pytest.skip('C++ compiler unavailable; native camera policy not executed')
    out = tmp_path_factory.mktemp('camera-policy') / ('camera.exe' if os.name == 'nt' else 'camera')
    source = ROOT / 'tests/native/test_camera_policy.cpp'
    include = ROOT / 'cloudcompare-plugin/qMCPBridge/include'
    if Path(compiler).name.lower() in ('cl', 'cl.exe', 'clang-cl', 'clang-cl.exe'):
        command = [compiler, '/nologo', '/EHsc', '/std:c++14', '/W4', '/WX', '/I'+str(include), str(source), '/Fe:'+str(out)]
    else:
        command = [compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror', '-pedantic', '-I', str(include), str(source), '-o', str(out)]
    subprocess.run(command, cwd=out.parent, check=True, capture_output=True, text=True, timeout=60)
    return out

@pytest.mark.parametrize('case', range(31))
def test_compiled_camera_policy(camera_policy, case):
    subprocess.run([str(camera_policy), str(case)], check=True, timeout=5)
