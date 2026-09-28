"""Read-only diagnostic workflow; accepted acquisition and solvers stay unchanged."""
from __future__ import annotations

from typing import Any, Callable

from .section_target_diagnostics import diagnose_target_analysis
from .section_target_workflow import (
    live_target_analysis, snapshot_target_analysis, validate_request,
)


def run_target_diagnostics(args: dict, *, live: bool = False,
                           request: Callable[..., Any] | None = None) -> dict:
    """Validate first, acquire once, then compare the fixed numerical stencil.

    The analysis-only accepted contract rejects selection, profile and custom-scale
    arguments before native I/O. Incomplete or over-budget baseline acquisition is
    never reissued at a different setting to manufacture a diagnostic result.
    """
    options = validate_request(args, live=live, reconstruct=False)
    baseline = (live_target_analysis(args, options, request) if live else
                snapshot_target_analysis(args, options))
    return diagnose_target_analysis(baseline)
