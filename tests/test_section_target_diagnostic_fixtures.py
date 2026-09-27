"""Exact hashed files through product snapshot and one-query native replay."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.section_target_diagnostic_workflow import run_target_diagnostics
from cloudcompare_mcp.section_target_workflow import run_target_workflow
from test_section_target_fixtures import snapshot_from_file, native_from_file

spec = importlib.util.spec_from_file_location('target_diagnostic_fixtures',
    Path(__file__).resolve().parents[1] / 'scripts' / 'make_section_target_diagnostic_fixtures.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope='module')
def diagnostic_files(tmp_path_factory):
    output = tmp_path_factory.mktemp('target-diagnostics') / 'generated'
    generator.generate(output)
    return output, json.loads((output / 'manifest.json').read_text())


def check_expected(report, expected):
    assert report['panels'][0]['candidate_count'] == expected['baseline_target_count']
    if 'baseline_solver_status' in expected:
        assert report['panels'][0]['accepted_solver_status'] == expected['baseline_solver_status']
    if 'diagnostic_status' in expected:
        assert report['status'] == expected['diagnostic_status']
        panel = next(p for p in report['panels'] if p['panel_id'] == expected['panel_id'])
        if 'refusal_contains' in expected:
            assert not panel['completed'] and expected['refusal_contains'] in panel['refusal']
        else:
            assert panel['candidate_count'] == expected['probe_target_count']
            comparison = panel['baseline_comparison']
            if 'split_count' in expected:
                assert comparison['split_baseline_candidate_count'] == expected['split_count']
            if 'merge_count' in expected:
                assert comparison['merged_probe_candidate_count'] == expected['merge_count']


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_file_diagnostic_snapshot_permutation_and_live_replay(diagnostic_files, name):
    output, manifest = diagnostic_files
    record = next(r for r in manifest['fixtures'] if r['name'] == name)
    xyz, args = snapshot_from_file(output, record)  # Checks exact SHA256/count before projection.
    saved = deepcopy(args)
    report = run_target_diagnostics(args)
    check_expected(report, record['expected'])
    assert args == saved
    args['section']['samples_uvd'].reverse()
    assert run_target_diagnostics(args) == report
    assert not report['selection_authorized'] and not report['reconstruction_attempted']
    assert report['point_accounting']['unselected_point_count'] == len(xyz)
    for panel in report['panels']:
        counts = panel['point_accounting']
        assert counts['classified_point_count'] + counts['unclassified_point_count'] == len(xyz)
        if panel['completed']:
            assert sum(c['source_point_count'] for c in panel['candidate_preview']) + panel['omitted_candidate_point_count'] == len(xyz)
            if 'baseline_comparison' in panel:
                assert panel['baseline_comparison']['accounted_relation_point_count'] == len(xyz)
    encoded = json.dumps(report, allow_nan=False)
    assert len(encoded) < 75000
    for key in ('samples_uvd', 'position_global', 'target_source_indices', 'candidate_fingerprint'):
        assert key not in encoded
    native = native_from_file(output, record)
    before = deepcopy(native)
    request = Mock(return_value=native)
    args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters')}
    live = run_target_diagnostics(args | {'cloud_id': 359}, live=True, request=request)
    check_expected(live, record['expected'])
    request.assert_called_once()
    assert native == before
    # Accepted snapshot/live normal normalization may differ at floating-point
    # roundoff. Hashes bind exact geometry and are intentionally not equated.
    def comparable(panels):
        panels = deepcopy(panels)
        for panel in panels:
            for candidate in panel.get('candidate_preview', []):
                candidate.pop('region_geometry_sha256')
                candidate.pop('bounds_uvd')
            for relation in panel.get('baseline_comparison', {}).get('relation_preview', []):
                relation.pop('baseline_region_sha256')
                relation.pop('probe_region_sha256')
        return panels
    assert comparable(report['panels']) == comparable(live['panels'])
    for a, b in zip(report['panels'], live['panels']):
        for x, y in zip(a.get('candidate_preview', []), b.get('candidate_preview', [])):
            np.testing.assert_allclose(x['bounds_uvd'], y['bounds_uvd'], rtol=0,
                atol=live['source_global_coordinate_precision_floor'])
    assert live['report_fingerprint'] != report['report_fingerprint']
    assert live['source_coordinate_bookkeeping']['global_scale'] == 2.5
    assert not live['source_coordinate_bookkeeping']['shift_scale_reapplied']


@pytest.mark.parametrize('name', ['single', 'transformed_single', 'parallel', 'transformed_parallel'])
def test_diagnostic_files_do_not_change_accepted_downstream_handoff(diagnostic_files, name):
    output, manifest = diagnostic_files
    record = next(r for r in manifest['fixtures'] if r['name'] == name)
    _, args = snapshot_from_file(output, record)
    combined = args | {'layer_parameters': record['layer_parameters'], 'profile_parameters': record['profile_parameters']}
    before = run_target_workflow(combined, reconstruct=True)
    run_target_diagnostics(args)
    assert run_target_workflow(combined, reconstruct=True) == before
    if 'parallel' in name:
        assert before['blocked_stage'] == 'layer_selection'
        layers = before['layer_result']['layer_analysis']
        assert layers['candidate_layer_count'] == 2
        combined.update(layer_id=layers['candidate_layers'][0]['layer_id'],
                        expected_layer_fingerprint=layers['analysis_fingerprint'])
        before = run_target_workflow(combined, reconstruct=True)
    assert before['status'] == 'candidate'
    assert before['layer_result']['profile']['topology']['loop_count'] == 1


def test_fixture_generator_is_reproducible_and_refuses_existing_or_repo_output(diagnostic_files, tmp_path):
    output, first = diagnostic_files
    second = generator.generate(tmp_path / 'another')
    assert first == second and len(first['fixtures']) == 20
    with pytest.raises(FileExistsError):
        generator.generate(output)
    with pytest.raises(ValueError, match='outside'):
        generator.generate(generator.ROOT / 'unsafe-fixtures')
