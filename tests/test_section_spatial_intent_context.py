"""Live transport context and canonical source mapping are part of intent evidence."""
from copy import deepcopy

import pytest

from cloudcompare_mcp.section_layers import SectionLayerError
from cloudcompare_mcp.section_spatial_intent import GEOMETRY_KEYS
from cloudcompare_mcp.section_spatial_intent_workflow import run_picked_roi_workflow as run
from test_section_spatial_intent import snapshot
from test_section_spatial_intent_workflow import NativeReplay, live_args


@pytest.mark.parametrize('when', ['before_call', 'during_acquisition'])
def test_same_geometry_at_changed_bridge_endpoint_is_not_same_live_context(monkeypatch, when):
    monkeypatch.setenv('CLOUDCOMPARE_MCP_HOST','127.0.0.1')
    monkeypatch.setenv('CLOUDCOMPARE_MCP_PORT','8765')
    monkeypatch.setenv('CLOUDCOMPARE_MCP_TOKEN','test-secret-do-not-echo')
    peer, args = NativeReplay(), live_args()
    first = run(args,live=True,request=peer)
    assert first['configured_bridge_endpoint'] == {'host':'127.0.0.1','port':8765}
    assert 'test-secret-do-not-echo' not in str(first)
    if when == 'before_call': monkeypatch.setenv('CLOUDCOMPARE_MCP_PORT','8766')
    def request(method,params,**kwargs):
        result = peer(method,params,**kwargs)
        if when == 'during_acquisition' and method == 'cloud.region_query':
            monkeypatch.setenv('CLOUDCOMPARE_MCP_PORT','8766')
        return result
    with pytest.raises(SectionLayerError,match='Stale spatial intent|endpoint changed'):
        run(args|{'expected_intent_fingerprint':first['intent_fingerprint']},live=True,action='analyze',request=request)


def test_native_point_info_does_not_need_picking_event_only_fields():
    peer = NativeReplay()
    peer.current = {index:{k:p[k] for k in GEOMETRY_KEYS} for index,p in peer.current.items()}
    assert all('pick_index' not in p and 'entity_kind' not in p for p in peer.current.values())
    args = live_args()
    first = run(args,live=True,request=peer)
    out = run(args|{'expected_intent_fingerprint':first['intent_fingerprint']},live=True,action='analyze',request=peer)
    assert out['status'] == 'ready'


def test_allowed_source_set_order_is_not_intent_order():
    args = snapshot()
    args['pick_state']['allowed_entity_ids'] = [359,999]
    first = run(args)
    args['pick_state']['allowed_entity_ids'].reverse()
    assert run(args) == first


def test_snapshot_geometry_and_index_permutation_preserves_intent():
    args = snapshot()
    args['section']['source_point_indices'] = list(range(len(args['section']['samples_uvd'])))
    first = run(args)
    reordered = deepcopy(args)
    reordered['section']['source_point_indices'].reverse()
    reordered['section']['samples_uvd'].reverse()
    assert run(reordered) == first


def test_explicit_null_source_index_mapping_is_not_absence():
    args = snapshot()
    args['section']['source_point_indices'] = None
    with pytest.raises(SectionLayerError,match='source_point_indices'):
        run(args)
