"""Shared acquisition must not run target partitioning before explicit ROI isolation."""
from copy import deepcopy
from unittest.mock import Mock, patch

import numpy as np
import pytest

from cloudcompare_mcp.section_target_workflow import (
    live_target_input, snapshot_target_input, target_analysis_from_input,
    run_target_workflow, target_options,
)
from cloudcompare_mcp.section_layers import SectionLayerError
from test_section_target_workflow import snapshot, live_args, native_result, rectangle


@pytest.mark.parametrize('live', [False, True])
def test_acquisition_is_independent_of_target_solver(live):
    args = live_args() if live else snapshot()
    request = Mock(return_value=native_result())
    saved = deepcopy(args)
    with patch('cloudcompare_mcp.section_target_workflow.analyze_section_targets_uvd',
               side_effect=AssertionError('Acquisition must not partition targets')):
        data = (live_target_input(args, target_options(args['target_parameters']), request)
                if live else snapshot_target_input(args, target_options(args['target_parameters'])))
    assert len(data.samples_uvd) == 1200
    assert data.context['acquisition']['complete']
    assert args == saved
    assert request.call_count == int(live)
    if live:
        assert len(data.source_indices) == len(data.points_global) == 1200
        assert data.context['source_coordinate_bookkeeping']['shift_scale_reapplied'] is False


@pytest.mark.parametrize('live', [False, True])
def test_acquisition_then_solver_preserves_public_result(live):
    args = live_args() if live else snapshot()
    options = target_options(args['target_parameters'])
    request = Mock(return_value=native_result())
    data = live_target_input(args, options, request) if live else snapshot_target_input(args, options)
    assert target_analysis_from_input(data, options).public == run_target_workflow(args, live=live, request=request)


def test_acquisition_keeps_outside_clutter_without_spending_target_budget():
    points = np.vstack([rectangle(), [[50, 0, 0], [60, 0, 0], [70, 0, 0]]])
    args = snapshot(points)
    args['target_parameters']['max_targets'] = 1
    options = target_options(args['target_parameters'])
    data = snapshot_target_input(args, options)
    np.testing.assert_array_equal(data.samples_uvd, points)
    with pytest.raises(SectionLayerError, match='max_targets'):
        target_analysis_from_input(data, options)
