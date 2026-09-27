# Active 0.15.5 implementation checkpoint

Branch `feature/live-cad-section-target-diagnostics`, accepted-main parent
`942c56e222eb5768ae2c60f7c1b6f153db070f68`. Initial lane7f29148d; numerical core
47c84d4fab4143733da5f01530230ccd6e185878. This checkpoint adds the thin snapshot/live
workflow and47 workflow/replay tests. Combined local core+workflow: **91 passed in
5.20s**; compileall and tracked diff whitespace check passed. This is NOT realGUI
acceptance or a complete installed suite. No accepted acquisition/solver file changed.

The workflow validates the accepted analysis-only contract before I/O, acquires at
most one complete live slab, and invokes the fixed diagnostic core. Unknown scale,
selection and profile arguments refuse before I/O. Truncation/invalid records stop
before diagnostic probes. Fingerprints bind source metadata, mapping, geometry,
frame/provenance/parameters; diagnostic tokens cannot authorize accepted selection.

NEXT: add two MCP tools and registry/capability integration, actual stdio/schema tests,
exact generated fixtures (existing14 plus diagnostic-specific split/merge/budget
cases), installed full regression/CI, documentation and focusedWindows0.15.5 handoff.
Do not merge0.15.5. qMCPBridge unchanged0.12.0/rev8. Accepted0.15.4 Windows gate is
complete; read AGENTS and docs/WINDOWS_0_15_4_ACCEPTED.md rather than repeating it.
