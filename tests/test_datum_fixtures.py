"""Reusable fixture generator correctness and no-overwrite safety."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("datum_fixtures", Path(__file__).resolve().parents[1] / "scripts" / "make_datum_fixtures.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fixture_manifest_and_no_overwrite(tmp_path):
    destination = tmp_path / "datum-fixtures"
    manifest = MODULE.create_fixtures(destination)
    for variant in manifest["variants"].values():
        r, t = np.array(variant["rotation"]), np.array(variant["translation"])
        np.testing.assert_allclose(r.T @ r, np.eye(3), atol=1e-14)
        for name, record in variant["files"].items():
            xyz = np.loadtxt(record["path"])
            assert len(xyz) == record["point_count"]
            local = (xyz-t) @ r
            if name == "primary": np.testing.assert_allclose(local[:, 2], 0, atol=1e-7)
            if name == "secondary": np.testing.assert_allclose(local[:, 1], 0, atol=1e-7)
            if name == "bore": np.testing.assert_allclose(np.linalg.norm(local[:, :2]-[3, 4], axis=1), 2, atol=1e-7)
    with pytest.raises(FileExistsError): MODULE.create_fixtures(destination)


def test_fixture_generator_refuses_repository_output():
    with pytest.raises(ValueError, match="outside"):
        MODULE.create_fixtures(Path(__file__).resolve().parents[1] / "must-not-create")
