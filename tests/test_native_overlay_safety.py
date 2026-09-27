"""Compile the actual native ownership/range policy; scene nodes are test doubles.

This is not a qMCPBridge build or live GUI test. The Windows acceptance separately
exercises these guards through the built plugin inside real CloudCompare.
"""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def native_policy_binary(tmp_path_factory):
    compiler = os.environ.get("CXX") or shutil.which("c++") or shutil.which("g++") or (shutil.which("cl") if os.name == "nt" else None)
    if not compiler:
        pytest.skip("C++ compiler unavailable; native policy execution not performed")
    binary = tmp_path_factory.mktemp("native-policy") / ("policy.exe" if os.name == "nt" else "policy")
    source = ROOT / "tests/native/test_overlay_safety.cpp"
    include = ROOT / "cloudcompare-plugin/qMCPBridge/include"
    if Path(compiler).name.lower() in ("cl", "cl.exe", "clang-cl", "clang-cl.exe"):
        command = [compiler, "/nologo", "/EHsc", "/std:c++14", "/W4", "/WX",
                   "/I" + str(include), str(source), "/Fe:" + str(binary)]
    else:
        command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                   "-I", str(include), str(source), "-o", str(binary)]
    subprocess.run(command, cwd=binary.parent, check=True,
                   capture_output=True, text=True, timeout=60)
    return binary

@pytest.mark.parametrize("scenario", range(12), ids=[
    "owned-tree", "foreign-child", "foreign-grandchild", "reused-id", "reset",
    "cycle", "shared-child", "null-child", "empty-owned-group", "length-range",
    "nonfinite-coordinate", "generated-bounds",
])
def test_native_overlay_policy(native_policy_binary, scenario):
    subprocess.run([str(native_policy_binary), str(scenario)], check=True, timeout=10)
