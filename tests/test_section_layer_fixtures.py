"""Exercise exact generated PLY files through projection and real workflow code."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.section_layer_workflow import run_layer_workflow

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'make_section_layer_fixtures.py'
spec = importlib.util.spec_from_file_location('section_layer_fixture_generator', SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope='module')
def fixture_files(tmp_path_factory):
    output = tmp_path_factory.mktemp('section-layers') / 'generated'
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
                             provenance={'fixture_sha256': record['sha256']}),
                layer_parameters=record['layer_parameters'])
    return xyz, args


@pytest.mark.parametrize('name', ['single', 'parallel', 'three', 'partial_overlap', 'sloped',
                                 'crossing', 'noisy_within_bound', 'too_thick', 'sparse', 'fan_like',
                                 'transformed_single', 'transformed_parallel'])
def test_exact_generated_fixture_classification(fixture_files, name):
    output, manifest = fixture_files
    record = next(x for x in manifest['fixtures'] if x['name'] == name)
    xyz, args = snapshot_from_file(output, record)
    saved = deepcopy(args)
    result = run_layer_workflow(args)
    assert result['status'] == record['expected_status'], (name, result['warnings'])
    if record['expected_layer_count'] is not None:
        assert result['candidate_layer_count'] == record['expected_layer_count']
    assert sum(c['source_point_count'] for c in result['candidate_layers']) == len(xyz)
    assert args == saved
    args['section']['samples_uvd'].reverse()
    assert run_layer_workflow(args) == result
    # Replayed structured native acquisition, not an actual CloudCompare instance.
    native = dict(cloud_id=101, cloud_name=name, coordinate_space='global',
                  matched_count=len(xyz), returned_count=len(xyz), truncated=False,
                  sample_strategy='all_matches', source_global_shift=[-1000, 2000, -3000], source_global_scale=2.5,
                  points=[dict(point_index=i, position_global=row.tolist()) for i, row in enumerate(xyz)])
    live_args = {k: record[k] for k in ('origin', 'normal', 'half_thickness', 'layer_parameters')}
    live_result = run_layer_workflow(live_args | {'cloud_id': 101}, live=True, request=Mock(return_value=native))
    assert live_result['status'] == record['expected_status']
    assert live_result['candidate_layer_count'] == result['candidate_layer_count']
    assert live_result['source_coordinate_bookkeeping']['global_scale'] == 2.5


@pytest.mark.parametrize('name', ['single', 'transformed_single'])
def test_exact_file_single_layer_handoff(fixture_files, name):
    output, manifest = fixture_files
    record = next(x for x in manifest['fixtures'] if x['name'] == name)
    _, args = snapshot_from_file(output, record)
    args['profile_parameters'] = record['profile_parameters']
    result = run_layer_workflow(args, reconstruct=True)
    assert result['status'] == 'candidate', result.get('reason')
    assert result['profile']['topology']['loop_count'] == 1
    assert result['profile']['version'] == '0.15.2'
    assert result['selection']['unselected_point_count'] == 0


def test_generator_refuses_repo_paths_and_overwrites(fixture_files):
    output, _ = fixture_files
    with pytest.raises(ValueError, match='outside'):
        generator.generate(SCRIPT.parent / 'never-create-fixtures-here')
    with pytest.raises(FileExistsError):
        generator.generate(output)
