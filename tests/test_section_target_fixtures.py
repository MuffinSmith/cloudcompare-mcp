"""Exact generated PLY -> product projection -> snapshot/native-replay workflows."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.section_target_workflow import run_target_workflow

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'make_section_target_fixtures.py'
spec = importlib.util.spec_from_file_location('section_target_fixture_generator', SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope='module')
def fixture_files(tmp_path_factory):
    output = tmp_path_factory.mktemp('section-targets') / 'generated'
    generator.generate(output)
    return output, json.loads((output / 'manifest.json').read_text())


def snapshot_from_file(output, record):
    path = output / record['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    xyz = generator.read_fixture_xyz(path)
    assert len(xyz) == record['point_count']
    projection = project_points_to_section(xyz, record['origin'], record['normal'])
    uvd = np.column_stack([projection['uv'], projection['signed_offsets']])
    args = dict(section=dict(coordinate_space='section_uv_depth', units='native',
        acquisition_complete=True, samples_uvd=uvd.tolist(), frame=record['frame'],
        provenance={'fixture_sha256': record['sha256']}), target_parameters=deepcopy(record['target_parameters']))
    return xyz, args


def native_from_file(output, record):
    xyz, _ = snapshot_from_file(output, record)
    return dict(cloud_id=359, cloud_name=record['name'], coordinate_space='global',
        matched_count=len(xyz), returned_count=len(xyz), truncated=False, sample_strategy='all_matches',
        source_global_shift=[-1e8, 2e8, -3e8], source_global_scale=2.5,
        points=[dict(point_index=i, position_global=row.tolist()) for i, row in enumerate(xyz)])


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_generated_target_fixture_snapshot_and_live_replay(fixture_files, name):
    output, manifest = fixture_files
    record = next(r for r in manifest['fixtures'] if r['name'] == name)
    xyz, args = snapshot_from_file(output, record)
    saved = deepcopy(args)
    result = run_target_workflow(args)
    assert result['status'] == record['expected_status'], (name, result['warnings'])
    assert result['candidate_target_count'] == record['expected_target_count']
    assert sum(c['source_point_count'] for c in result['candidate_targets']) == len(xyz)
    assert result['point_accounting']['unassigned_point_count'] == 0
    assert args == saved
    args['section']['samples_uvd'].reverse()
    assert run_target_workflow(args) == result
    assert 'samples_uvd' not in json.dumps(result)
    assert len(json.dumps(result)) < 60000
    native = native_from_file(output, record)
    before = deepcopy(native)
    live_args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'target_parameters')}
    live = run_target_workflow(live_args | {'cloud_id': 359}, live=True, request=Mock(return_value=native))
    assert native == before
    assert live['status'] == result['status']
    assert live['candidate_target_count'] == result['candidate_target_count']
    assert live['source_coordinate_bookkeeping']['global_scale'] == 2.5
    assert not live['source_coordinate_bookkeeping']['shift_scale_reapplied']
    assert live['analysis_fingerprint'] != result['analysis_fingerprint']
    assert [(c['source_point_count'], c['blocking_reasons']) for c in live['candidate_targets']] == [
        (c['source_point_count'], c['blocking_reasons']) for c in result['candidate_targets']]


@pytest.mark.parametrize('name', ['single', 'transformed_single', 'parallel', 'transformed_parallel'])
def test_exact_target_file_handoff(fixture_files, name):
    output, manifest = fixture_files
    record = next(r for r in manifest['fixtures'] if r['name'] == name)
    xyz, args = snapshot_from_file(output, record)
    args.update(layer_parameters=record['layer_parameters'], profile_parameters=record['profile_parameters'])
    result = run_target_workflow(args, reconstruct=True)
    if 'parallel' in name:
        assert result['blocked_stage'] == 'layer_selection'
        layers = result['layer_result']['layer_analysis']
        assert layers['candidate_layer_count'] == 2
        args.update(layer_id=layers['candidate_layers'][0]['layer_id'],
                    expected_layer_fingerprint=layers['analysis_fingerprint'])
        result = run_target_workflow(args, reconstruct=True)
    assert result['status'] == 'candidate', result.get('reason')
    assert result['layer_result']['profile']['topology']['loop_count'] == 1
    assert result['point_accounting']['selected_layer_point_count'] == 1200
    assert result['point_accounting']['total_unselected_point_count'] == len(xyz) - 1200


def test_exact_permuted_files_stable_geometry_tokens_when_provenance_matches(fixture_files):
    output, manifest = fixture_files
    results = []
    for name in ('two_targets', 'permuted_two'):
        record = next(r for r in manifest['fixtures'] if r['name'] == name)
        _, args = snapshot_from_file(output, record)
        # Raw file byte hashes differ; geometry/token invariance requires same source context.
        args['section'].pop('provenance')
        results.append(run_target_workflow(args))
    assert results[0] == results[1]


def test_generator_reproducibility_and_write_guards(fixture_files, tmp_path):
    output, manifest = fixture_files
    other = tmp_path / 'same'
    repeated = generator.generate(other)
    assert repeated == manifest
    for record in manifest['fixtures']:
        assert (output / record['file']).read_bytes() == (other / record['file']).read_bytes()
    with pytest.raises(ValueError, match='outside'):
        generator.generate(SCRIPT.parent / 'never-create-here')
    with pytest.raises(FileExistsError):
        generator.generate(output)
