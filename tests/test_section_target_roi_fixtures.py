"""Exact files via product projection, snapshot/one-query replay and accepted chain."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.section_target_roi_workflow import run_roi_workflow
from test_section_target_fixtures import snapshot_from_file as target_snapshot_from_file, native_from_file
from test_section_target_workflow import choose

spec = importlib.util.spec_from_file_location('section_target_roi_fixtures',
    Path(__file__).resolve().parents[1] / 'scripts' / 'make_section_target_roi_fixtures.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope='module')
def roi_files(tmp_path_factory):
    output = tmp_path_factory.mktemp('roi') / 'generated'
    generator.generate(output)
    return output, json.loads((output / 'manifest.json').read_text())


def snapshot_from_file(output, record):
    xyz, args = target_snapshot_from_file(output, record)
    args['roi'] = deepcopy(record['roi'])
    return xyz, args


def record_named(manifest, name):
    return next(r for r in manifest['fixtures'] if r['name'] == name)


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_roi_file_snapshot_permutation_and_one_acquisition_replay(roi_files, name):
    output, manifest = roi_files
    record = record_named(manifest, name)
    xyz, args = snapshot_from_file(output, record)
    saved = deepcopy(args)
    a = run_roi_workflow(args)
    counts = a['point_accounting']
    assert counts['inside_roi_point_count'] + counts['outside_roi_point_count'] == len(xyz)
    assert counts['unclassified_point_count'] == 0
    assert counts['target_classified_point_count'] + counts['target_unclassified_inside_point_count'] == counts['inside_roi_point_count']
    expected = record['expected']
    if 'inside' in expected: assert counts['inside_roi_point_count'] == expected['inside']
    if 'status' in expected: assert a['status'] == expected['status']
    if 'edge' in expected: assert any(expected['edge'] in g['touched_edges'] for g in a['candidate_guards'])
    assert args == saved
    args['section']['samples_uvd'].reverse()
    assert run_roi_workflow(args) == a
    text = json.dumps(a, allow_nan=False)
    assert len(text) < 75000
    assert 'samples_uvd' not in text and 'position_global' not in text
    native = native_from_file(output, record)
    saved_native = deepcopy(native)
    request = Mock(return_value=native)
    live_args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters', 'roi')}
    b = run_roi_workflow(live_args | {'cloud_id': 359}, live=True, request=request)
    request.assert_called_once()
    assert native == saved_native
    assert b['point_accounting'] == counts
    assert b['status'] == a['status']
    assert b['roi_fingerprint'] != a['roi_fingerprint']
    assert b['source_coordinate_bookkeeping']['global_scale'] == 2.5
    assert not b['source_coordinate_bookkeeping']['shift_scale_reapplied']
    if a['target_analysis']:
        assert [(c['source_point_count'], c['blocking_reasons']) for c in a['target_analysis']['candidate_targets']] == [
            (c['source_point_count'], c['blocking_reasons']) for c in b['target_analysis']['candidate_targets']]
    if name == 'fan_like':
        assert 0 < counts['inside_roi_point_count'] < len(xyz)
        assert counts['outside_roi_point_count'] > 0  # Spatial evidence, not a required profile.


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_roi_file_downstream_or_declared_refusal(roi_files, name):
    output, manifest = roi_files
    record = record_named(manifest, name)
    xyz, args = snapshot_from_file(output, record)
    args.update(layer_parameters=record['layer_parameters'], profile_parameters=record['profile_parameters'])
    r = run_roi_workflow(args, reconstruct=True)
    expected = record['expected']
    if 'reconstruct' in expected: assert r['status'] == expected['reconstruct']
    if 'stage' in expected: assert r['blocked_stage'] == expected['stage']
    if 'edge' in expected:
        a = r['roi_analysis']
        for guard in a['candidate_guards']:
            if expected['edge'] in guard['touched_edges']:
                c = next(c for c in a['target_analysis']['candidate_targets'] if c['target_id'] == guard['target_id'])
                explicit = run_roi_workflow(choose(args, c), reconstruct=True)
                assert explicit['blocked_stage'] == 'roi_truncation_guard'
    if name in ('parallel', 'transformed_parallel'):
        layer = r['target_result']['layer_result']['layer_analysis']
        assert layer['candidate_layer_count'] == 2
        args.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
        r = run_roi_workflow(args, reconstruct=True)
        assert r['status'] == 'candidate'
        assert r['point_accounting']['selected_layer_point_count'] == 1200
    counts = r['point_accounting']
    assert counts['total_unselected_point_count'] + counts['selected_layer_point_count'] == len(xyz)
    assert (counts['outside_roi_point_count'] + counts['unselected_inside_roi_point_count']
            + counts['unselected_within_target_point_count']) == counts['total_unselected_point_count']
    if r['status'] == 'candidate':
        assert r['target_result']['layer_result']['profile']['topology']['loop_count'] >= 1


def test_exact_permuted_files_geometry_tokens_with_same_context(roi_files):
    output, manifest = roi_files
    results = []
    for name in ('outside_clutter', 'permuted_outside'):
        _, args = snapshot_from_file(output, record_named(manifest, name))
        args['section'].pop('provenance')  # Exact file hashes intentionally differ.
        results.append(run_roi_workflow(args))
    assert results[0] == results[1]


def test_roi_generator_exact_reproducibility_and_write_guards(roi_files, tmp_path):
    output, manifest = roi_files
    other = tmp_path / 'repeat'
    assert generator.generate(other) == manifest
    for record in manifest['fixtures']:
        assert hashlib.sha256((other / record['file']).read_bytes()).hexdigest() == record['sha256']
    with pytest.raises(FileExistsError): generator.generate(output)
    with pytest.raises(ValueError, match='outside'): generator.generate(generator.ROOT / 'roi-generated-forbidden')
