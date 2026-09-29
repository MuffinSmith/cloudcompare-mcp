"""Numerical intentional anchors, with no GUI or native calls."""
from copy import deepcopy
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_spatial_intent import selected_picks, verify_current_pick
from cloudcompare_mcp.section_spatial_intent_workflow import run_picked_roi_workflow as run
from test_section_target_roi_workflow import snapshot as roi_snapshot


def pick(xyz, index, point=None):
    return dict(pick_index=index, entity_id=359, entity_name='fixture', entity_kind='point_cloud',
                entity_center=False, point_index=100000 + index if point is None else point,
                item_index=100000 + index if point is None else point,
                position_global=list(xyz), position_native_local=list(xyz), global_shift=[0, 0, 0],
                global_scale=1, click={'x': index, 'y': index})


def state(anchors=((-3, -3, 4), (11, 9, -4))):
    return dict(active=False, pick_count=len(anchors), picks=[pick(p, i) for i, p in enumerate(anchors)])


def snapshot(points=None, anchors=None, reconstruct=False):
    args = roi_snapshot(points, reconstruct)
    args.pop('roi')
    args['section'].update(frame=dict(frame_id='declared-xy', origin_global=[0, 0, 0],
                                     normal=[0, 0, 1], basis_u=[1, 0, 0], basis_v=[0, 1, 0]),
                           source=dict(cloud_id=359, cloud_name='fixture', global_shift=[0, 0, 0], global_scale=1))
    args.update(pick_state=state() if anchors is None else state(anchors), pick_indices=[0, 1],
                margin=0, frame_provenance={'declaration': 'Explicit XY section, not inferred from anchors'})
    return args


def authorize(args):
    derive = {k: v for k, v in args.items() if k not in ('layer_parameters', 'profile_parameters',
              'target_id', 'expected_target_fingerprint', 'layer_id', 'expected_layer_fingerprint', 'expected_intent_fingerprint')}
    return args | {'expected_intent_fingerprint': run(derive)['intent_fingerprint']}


def test_opposite_corners_no_target_analysis_io_mutation_or_depth_crop():
    args = snapshot()
    saved = deepcopy(args)
    native = Mock(side_effect=AssertionError('native I/O'))
    with patch('cloudcompare_mcp.section_spatial_intent_workflow.analyze_roi_input', side_effect=AssertionError('analysis during declaration')):
        out = run(args, request=native)
    assert out['roi'] == dict(u_min=-3, u_max=11, v_min=-3, v_max=9)
    assert out['anchor_depth_range'] == [-4, 4]
    assert not out['anchor_depth_used_for_cropping'] and out['half_open']
    assert args == saved
    native.assert_not_called()


def test_many_anchors_and_selection_order_invariant():
    args = snapshot(anchors=[[-3, 0, 8], [3, -3, -8], [11, 4, 0], [2, 9, 2]])
    args['pick_indices'] = [0, 1, 2, 3]
    a = run(args)
    args['pick_indices'].reverse()
    b = run(args)
    assert a == b and a['roi'] == dict(u_min=-3, u_max=11, v_min=-3, v_max=9)


@pytest.mark.parametrize('margin', [0, .25, 2])
def test_explicit_margin_only(margin):
    args = snapshot() | {'margin': margin}
    out = run(args)
    assert out['roi'] == dict(u_min=-3-margin, u_max=11+margin, v_min=-3-margin, v_max=9+margin)


@pytest.mark.parametrize('value', [-1, True, '1', None, float('nan'), float('inf'), [1]])
def test_invalid_margin(value):
    with pytest.raises(SectionLayerError):
        run(snapshot() | {'margin': value})


@pytest.mark.parametrize('anchors', [[[0, 0, 0], [0, 1, 0]], [[0, 0, 0], [1, 0, 0]], [[0, 0, 0], [0, 0, 0]]])
@pytest.mark.parametrize('margin', [0, 2])
def test_degenerate_spans_not_repaired_with_padding(anchors, margin):
    with pytest.raises(SectionLayerError):
        run(snapshot(anchors=anchors) | {'margin': margin})


@pytest.mark.parametrize('field,value', [('position_global', [True, 1, 2]), ('position_global', [1, float('nan'), 2]),
    ('position_native_local', [0, '1', 2]), ('global_shift', [0, 0]), ('global_scale', True),
    ('global_scale', 0), ('entity_id', True), ('entity_id', 88), ('point_index', False),
    ('item_index', 1), ('pick_index', 9), ('entity_kind', 'mesh'), ('entity_center', True)])
def test_invalid_and_mixed_source_pick_records(field, value):
    args = snapshot()
    args['pick_state']['picks'][1][field] = value
    with pytest.raises(SectionLayerError):
        run(args)


@pytest.mark.parametrize('indices', [[0, 0], [0], [0, 2], [False, 1], [0, 1.5], list(range(33))])
def test_bad_explicit_indexes(indices):
    with pytest.raises(SectionLayerError):
        run(snapshot() | {'pick_indices': indices})


@pytest.mark.parametrize('key,value', [('active', True), ('active', 0), ('pick_count', 3), ('pick_count', True), ('picks', [])])
def test_stopped_coherent_pick_state_required(key, value):
    args = snapshot()
    args['pick_state'][key] = value
    with pytest.raises(SectionLayerError):
        run(args)


def test_duplicate_source_point_refused():
    args = snapshot()
    args['pick_state']['picks'][1].update(point_index=100000, item_index=100000)
    with pytest.raises(SectionLayerError, match='Duplicate source'):
        run(args)


@pytest.mark.parametrize('key', ['frame_id', 'origin_global', 'basis_u', 'normal'])
def test_explicit_frame_required(key):
    args = snapshot()
    del args['section']['frame'][key]
    with pytest.raises(SectionLayerError):
        run(args)


def test_no_ordered_frame_construction_or_silent_plane_fitting():
    with pytest.raises(SectionLayerError, match='unknown'):
        run(snapshot() | {'ordered_frame_picks': [0, 1, 2]})


def test_current_point_revalidation_is_geometry_not_local_global_conversion():
    p = state()['picks'][0]
    assert verify_current_pick(p, p)
    for key, value in [('position_global', [0, 0, 0]), ('global_scale', 2), ('entity_id', 2), ('point_index', True)]:
        with pytest.raises(SectionLayerError):
            verify_current_pick(p, p | {key: value})


def test_unselected_duplicate_click_events_are_bound_but_do_not_consume_logical_anchors():
    args = snapshot(anchors=[[-3, -3, 4], [-3, -3, 4], [11, 9, -4], [2, -3, 1]])
    # The native picker may emit the same source vertex more than once.  Keep the
    # raw event in provenance, but deliberately select distinct predeclared anchors.
    args['pick_state']['picks'][1].update(point_index=100000, item_index=100000)
    args['pick_indices'] = [0, 2, 3]
    first = run(args)
    assert first['anchor_count'] == 3
    assert first['pick_indices'] == [0, 2, 3]
    assert first['roi'] == dict(u_min=-3, u_max=11, v_min=-3, v_max=9)

    reordered = deepcopy(args)
    reordered['pick_indices'] = [3, 0, 2]
    assert run(reordered) == first

    # Even unselected duplicate events remain part of the frozen captured session,
    # so changing one invalidates the old intent rather than silently discarding it.
    changed = deepcopy(args)
    changed['pick_state']['picks'][1]['click']['x'] += 1
    assert run(changed)['intent_fingerprint'] != first['intent_fingerprint']
