"""Exact files through product projection and picked ROI; mocked native, not GUI."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from cloudcompare_mcp.feature_fit import project_points_to_section
from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_spatial_intent_workflow import run_picked_roi_workflow as run
from test_section_spatial_intent import pick, authorize
from test_section_spatial_intent_workflow import NativeReplay
from test_section_target_workflow import choose

spec = importlib.util.spec_from_file_location('picked_roi_fixtures',
    Path(__file__).resolve().parents[1] / 'scripts' / 'make_section_spatial_intent_fixtures.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


@pytest.fixture(scope='module')
def intent_files(tmp_path_factory):
    output = tmp_path_factory.mktemp('picked-roi') / 'generated'
    generator.generate(output)
    return output, json.loads((output / 'manifest.json').read_text())


def record_named(manifest, name):
    return next(r for r in manifest['fixtures'] if r['name'] == name)


def inputs_from_file(output, record, *, quantize=False):
    path = output / record['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    xyz = generator.read_fixture_xyz(path)
    assert len(xyz) == record['point_count']
    shift, scale = -np.asarray(record['origin']), 2.5
    local = (xyz + shift) * scale
    if quantize:
        local = local.astype(np.float32).astype(np.float64)
        xyz = local / scale - shift
    projected = project_points_to_section(xyz, record['origin'], record['normal'])
    uvd = np.column_stack([projected['uv'], projected['signed_offsets']])
    mask = np.abs(uvd[:,2]) <= record['half_thickness']
    indices = np.flatnonzero(mask)
    assert len(indices) == record['slab_point_count']
    picks = []
    for index, point_index in enumerate(record['anchor_point_indices']):
        p = pick(xyz[point_index], index, point_index)
        p.update(position_native_local=local[point_index].tolist(), entity_name=record['name'],
                 global_shift=shift.tolist(), global_scale=scale)
        picks.append(p)
    status = dict(active=False, pick_count=len(picks), picks=picks)
    args = dict(section=dict(coordinate_space='section_uv_depth', units='native', acquisition_complete=True,
        samples_uvd=uvd[mask].tolist(), source_point_indices=indices.tolist(), frame=deepcopy(record['frame']),
        source=dict(cloud_id=359, cloud_name=record['name'], global_shift=shift.tolist(), global_scale=scale),
        provenance={'fixture_sha256': record['sha256'], 'host_float32_proxy': quantize}),
        target_parameters=deepcopy(record['target_parameters']), pick_state=status,
        pick_indices=list(range(len(picks))), margin=record['margin'], frame_provenance=record['frame_provenance'])
    native = dict(cloud_id=359, cloud_name=record['name'], coordinate_space='global', matched_count=len(indices),
        returned_count=len(indices), truncated=False, sample_strategy='all_matches',
        source_global_shift=shift.tolist(), source_global_scale=scale,
        points=[dict(point_index=int(i), position_global=xyz[i].tolist()) for i in indices])
    peer = NativeReplay()
    peer.native, peer.status = native, deepcopy(status)
    peer.current = {p['point_index']: deepcopy(p) for p in picks}
    live_args = {k: deepcopy(record[k]) for k in ('origin', 'normal', 'half_thickness', 'target_parameters', 'margin', 'frame_provenance')}
    live_args.update(cloud_id=359, frame_id=record['frame']['frame_id'], pick_indices=args['pick_indices'])
    return xyz, args, peer, live_args


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_anchor_files_derive_analyze_and_native_accounting(intent_files, name):
    output, manifest = intent_files
    record = record_named(manifest, name)
    xyz, args, peer, live_args = inputs_from_file(output, record)
    saved = deepcopy((args, peer.status, peer.native))
    intent = run(args)
    assert intent['roi'] == pytest.approx(record['declared_ideal_bounds'], abs=1e-7)
    assert intent['anchor_depth_range'] == pytest.approx([-8,8], abs=1e-7)
    assert intent['anchor_count'] == len(record['anchor_point_indices'])
    a = run(args | {'expected_intent_fingerprint':intent['intent_fingerprint']}, action='analyze')['roi_result']
    live = run(live_args, live=True, request=peer)
    assert len(peer.calls) == 3 + intent['anchor_count']
    b = run(live_args | {'expected_intent_fingerprint':live['intent_fingerprint']}, live=True, action='analyze', request=peer)['roi_result']
    assert b['status'] == a['status']
    assert b['point_accounting'] == a['point_accounting']
    assert live['intent_fingerprint'] != intent['intent_fingerprint']
    assert live['source']['global_scale'] == 2.5 and not live['shift_scale_reapplied']
    counts = a['point_accounting']
    assert counts['inside_roi_point_count'] + counts['outside_roi_point_count'] == record['slab_point_count']
    assert counts['unclassified_point_count'] == 0
    if 'inside' in record['expected']: assert counts['inside_roi_point_count'] == record['expected']['inside']
    if 'edge' in record['expected']: assert any(record['expected']['edge'] in g['touched_edges'] for g in a['candidate_guards'])
    assert (args, peer.status, peer.native) == saved
    assert len(json.dumps(intent, allow_nan=False)) < 12000 and 'samples_uvd' not in json.dumps(intent)
    assert all(m in ('metrology.pick.status','metrology.point_info','cloud.region_query') for m,p in peer.calls)


@pytest.mark.parametrize('name', generator.NAMES)
def test_exact_anchor_files_downstream_refusal_or_profile(intent_files, name):
    output, manifest = intent_files
    record = record_named(manifest, name)
    _, args, _, _ = inputs_from_file(output, record)
    args.update(layer_parameters=record['layer_parameters'], profile_parameters=record['profile_parameters'])
    args = authorize(args)
    r = run(args, action='reconstruct')['roi_result']
    expected = record['expected']
    if 'reconstruct' in expected: assert r['status'] == expected['reconstruct']
    if 'stage' in expected: assert r['blocked_stage'] == expected['stage']
    if 'edge' in expected:
        a = r['roi_analysis']
        for guard in a['candidate_guards']:
            if expected['edge'] in guard['touched_edges']:
                c = next(c for c in a['target_analysis']['candidate_targets'] if c['target_id'] == guard['target_id'])
                assert run(choose(args,c), action='reconstruct')['blocked_stage'] == 'roi_truncation_guard'
    if name in ('parallel','transformed_parallel'):
        layer = r['target_result']['layer_result']['layer_analysis']
        args.update(layer_id=layer['candidate_layers'][0]['layer_id'], expected_layer_fingerprint=layer['analysis_fingerprint'])
        r = run(args, action='reconstruct')['roi_result']
        assert r['status'] == 'candidate'
    counts = r['point_accounting']
    assert counts['selected_layer_point_count'] + counts['total_unselected_point_count'] == record['slab_point_count']
    if r['status'] == 'candidate': assert r['target_result']['layer_result']['profile']['topology']['loop_count'] >= 1


@pytest.mark.parametrize('name', ['transformed_safe','transformed_parallel'])
def test_host_float32_proxy_preserves_local_global_bookkeeping_without_hash_equivalence(intent_files, name):
    output, manifest = intent_files
    record = record_named(manifest, name)
    _, _, exact_peer, live_args = inputs_from_file(output, record)
    _, _, quantized_peer, _ = inputs_from_file(output, record, quantize=True)
    exact = run(live_args, live=True, request=exact_peer)
    quantized = run(live_args, live=True, request=quantized_peer)
    assert quantized['roi'] == pytest.approx(exact['roi'], abs=3e-6)
    assert quantized['intent_fingerprint'] != exact['intent_fingerprint']
    assert quantized['source']['global_shift'] == [-1e8,2e8,-3e8]
    assert not quantized['shift_scale_reapplied']
    args = live_args | dict(expected_intent_fingerprint=quantized['intent_fingerprint'],
                            layer_parameters=record['layer_parameters'], profile_parameters=record['profile_parameters'])
    r = run(args, live=True, action='reconstruct', request=quantized_peer)
    assert r['status'] == ('candidate' if name == 'transformed_safe' else 'blocked')
    with pytest.raises(SectionLayerError, match='Stale'):
        run(args | {'expected_intent_fingerprint':exact['intent_fingerprint']}, live=True, action='reconstruct', request=quantized_peer)


def test_reproducible_generated_bytes_and_safe_write_locations(intent_files, tmp_path):
    output, manifest = intent_files
    other = tmp_path / 'repeat'
    assert generator.generate(other) == manifest
    for record in manifest['fixtures']:
        assert (output / record['file']).read_bytes() == (other / record['file']).read_bytes()
    with pytest.raises(FileExistsError): generator.generate(output)
    with pytest.raises(ValueError, match='outside'): generator.generate(generator.ROOT / 'never-create')
