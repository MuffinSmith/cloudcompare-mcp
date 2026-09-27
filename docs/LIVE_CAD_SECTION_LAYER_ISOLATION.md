# 0.15.3 development: depth-aware section layer isolation

Active branch: `feature/live-cad-section-layer-isolation`.
Accepted-main parent: `cb1ee9eab9c64ff4806036a6317606938faa22e6`.
PR #16 merged accepted 0.15.2 at `8f2e0317f9eeff14547db1d83c100549c65fb18c`.
This lane is NOT accepted and must NOT be merged without its own Windows gate and
explicit user approval. qMCPBridge remains unchanged 0.12.0 / workflow revision 8.

## Initial numerical checkpoint

`section_layers.py` is a separate pure-Python numerical core. It retains every
sample as `[u,v,signed_depth]`, bins at an explicit native-unit UV cell scale,
splits local depth observations only at gaps strictly greater than the caller's
depth separation, and connects compatible observations in 4-neighbor UV cells.
Local depth span equal to the thickness bound is allowed; a neighbor median step
equal to its bound is allowed. Thickness must be less than separation.

Sparse observations, excessive local thickness, one-to-many neighbor correspondence,
or a connected component containing multiple modes from the same cell make the
analysis unusable. They are reported, never discarded. Component/point/cell/mode
limits fail explicitly instead of truncating. Exact duplicate samples do not create
additional local support. Every supplied point remains in one candidate component.

Candidate summaries include source counts, UV footprint, depth distribution, local
thickness/residual, continuity, overlap and canonical geometry fingerprints. Outputs
contain no raw sample arrays. Layer IDs are geometry-derived. Explicit selection
requires the exact current analysis fingerprint; it cannot bypass unsupported or
ambiguous observations. Only one wholly supported unambiguous component can be
selected automatically. Multiple credible components require explicit choice.

This is resolution-dependent evidence, not proof of physical layer identity or
manufacturing intent. Disconnected coplanar patches are deliberately NOT joined.
A chosen component is a coherent surface patch, not necessarily the whole desired
part. Subthreshold surfaces and crossings between unsampled locations cannot be
ruled out. No sign-based selection, morphological repair, or parameter search.

## Recovery state

Initial local numerical validation: 43 tests passed, including thresholds, one/two/
three layers, partial overlap, crossings, sparse/duplicate support, deterministic
selection, arbitrary projection and large translation. Full regression is delegated
to CI because this container lacks MCP/PLY dependencies and its package network is
unavailable; do not label a dependency failure as a passing full local suite.

Still required: snapshot/live MCP plumbing, exact generated-file fixtures and tests,
actual MCP stdio/schema coverage, safe selected-layer handoff to accepted 0.15.2,
complete final regression/compileall/diff checks, green CI, README and a targeted
Windows acceptance procedure. Do not request Windows testing yet. Preserve raw test
reports and generated geometry outside Git; reusable generators/tests belong here.
