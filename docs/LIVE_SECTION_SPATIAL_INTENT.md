# Python 0.15.7: deliberate picks to section ROI intent

Development branch `feature/live-section-roi-from-picks`, draft PR #21. This is an
additive Python-only bridge into the [accepted 0.15.6 numerical ROI workflow](LIVE_CAD_SECTION_TARGET_ROI.md).
It is not automatic ROI discovery, a manufacturing-frame solver, or CAD-model
construction. qMCPBridge remains **0.12.0 / workflow revision 8**, unchanged.
Windows/visible-host acceptance is a separate gate; see
[the focused interaction procedure](WINDOWS_SECTION_SPATIAL_INTENT_ACCEPTANCE.md).

## The deliberate interaction

Declare a section frame and fixed acquisition/analysis parameters first. Capture
human boundary-anchor picks on one standalone source cloud. Stop picking, freeze
the selected pick identities and explicit margin, and derive intent. Save that
intent before looking at target or reconstruction quality. Subsequent analysis and
reconstruction re-read current evidence and require the frozen intent fingerprint.

The anchors mean **boundaries of the intended rectangle**, not target samples to be
fitted. The tool never searches padding, moves the ROI, selects a convenient target,
or changes scale based on reconstruction quality. A valid intent followed by a
blocked target/layer/profile is a useful, reproducible result.

| Stage | Snapshot tool | Live tool |
| --- | --- | --- |
| Derive only | `derive_section_roi_from_picks` | `derive_live_section_roi_from_picks` |
| Analyze ROI/targets | `analyze_picked_section_target_roi` | `analyze_live_picked_section_target_roi` |
| Attempt justified profile | `reconstruct_picked_section_target_roi_profile` | `reconstruct_live_picked_section_target_roi_profile` |

These six surfaces separate snapshot versus host evidence and intention versus
reconstruction authorization. Capabilities appear under
`python_section_layers.section_targets.picked_spatial_intent`; accepted parent
versions are not relabeled.

## Frame contract

**Live:** supply `cloud_id`, global-coordinate `origin`, nonzero `normal`, symmetric
`half_thickness`, and nonempty `frame_id`. The existing accepted section projector
normalizes/canonicalizes the normal and deterministically constructs U/V. Inspect
the returned `section_frame`; supplying a datum normal does **not** also supply that
datum's X/Y rotation. This first live contract does not accept an independently
chosen in-plane basis.

**Snapshot:** supply the accepted complete `section_uv_depth` section envelope in
native units, with full `frame` containing `frame_id`, `origin_global`, `normal`,
`basis_u`, and `basis_v`. The basis must be orthonormal and right-handed. Supply
`source.cloud_id`, `global_shift`, and positive `global_scale`; optional source name
must agree with the picks. Optional `source_point_indices` bind exact source-index
to UVD mapping; explicit null is not equivalent to omission.

Both modes require nonempty finite JSON `frame_provenance`, at most 2048 serialized
bytes. Preserve a declaration or existing accepted fit/datum reference and its
observation fingerprint. Existing `fit_live_plane`, line/cylinder fitting and datum
tools can inform a **deliberately declared** frame; this helper does not refit them,
infer their semantic role, or authenticate their freshness. `build_live_datum_frame`
is itself snapshot-only despite its name. No ordered three-pick frame construction
is added here; three boundary anchors have no origin/U/orientation roles.

## Pick and numerical contract

`pick_indices` is required: 2..32 unique captured-session indexes. Selection-array
order is irrelevant; the original captured identities and session record order
remain bound. Each selected record must identify a real point-cloud vertex, not a
mesh triangle, entity center, or duplicate point/coordinate, and must belong to the
requested source. Integer identities and finite three-vectors reject booleans.

Live picks must be stopped (`active: false`). Snapshot callers provide the complete
stopped `pick_state`, including a coherent count and records. The bounded whole
pick state is hashed; changing an unselected record can conservatively stale intent.
The native allowed-entity list is treated as an unordered set for ordering purposes.

Global picked positions are already global. For every anchor:

```text
relative = position_global - section_origin_global
u = dot(relative, basis_u)
v = dot(relative, basis_v)
depth = dot(relative, normal)
```

`margin` is required, finite and nonnegative, in native units. No default or automatic
margin is supplied. The exact rectangle is:

```text
[u_min, u_max) = [min(anchor_u) - margin, max(anchor_u) + margin)
[v_min, v_max) = [min(anchor_v) - margin, max(anchor_v) + margin)
```

Raw anchor spans in both U and V must exceed the numerical coordinate precision
floor **before** adding margin. Padding cannot repair zero/near-zero spans. No
hidden epsilon expands the upper boundary. A point exactly on the upper boundary
is outside. Anchor signed depths are returned, but do not choose a depth sign or
crop depth evidence. The caller's already-declared symmetric slab remains the
acquisition; all depths within that complete slab are retained.

Shift/scale fields are checked and preserved, never applied to global positions a
second time. Numerical precision conditioning is not a calibrated sensor-accuracy
or host-float uncertainty model. Host import quantization may legitimately change
bounds and fingerprints; use actual acquired coordinates, not ideal file values,
and never require snapshot/live hashes to match.

## Live reads, completeness and freshness

A valid N-anchor call performs these existing native operations:

1. `metrology.pick.status`, requiring stopped picks.
2. N `metrology.point_info` reads, checking cached source identity, coordinates and
   global bookkeeping against current source points.
3. Exactly one complete `cloud.region_query` slab acquisition through the accepted
   0.15.6/target acquisition verifier.
4. Another `metrology.pick.status`, requiring unchanged stopped captured state.

Configured bridge host/port are checked before/after and bound into context. Tokens
and credentials are not echoed or hashed into intent. The valid-call total is
**N+3 native reads**, including one slab query. Invalid or stale evidence can stop
earlier. This is wrapper call accounting, not independently measured host execution.
No geometry, attributes, selection, visibility, camera or overlays are changed by
these six tools. Existing picking-start/stop tools remain separate operations.

Derivation performs acquisition for source provenance but **does not run target
analysis**. It therefore requires the caller's fixed `target_parameters` and a
complete slab within the accepted 20,000-point/cell ceilings. Truncated or invalid
acquisition refuses rather than returning a purported complete intent. No target
budget is raised and no outside evidence is silently dropped.

Keep CloudCompare geometry quiescent during calls. These are multiple reads, **not
an atomic scene snapshot**. Native 0.12.0 has no scene/picking generation counter.
Same-endpoint host restarts or unobserved change-and-change-back events may be
indistinguishable. The configured endpoint is not authenticated process identity.
Freshness covers observed complete slab and selected anchors, **not unobserved
whole-cloud geometry/attributes**. Snapshot evidence is caller asserted, not a
live-scene freshness proof. The tool deliberately makes none of those stronger
claims.

## Fingerprints and safe downstream handoff

The SHA256 intent payload binds the contract/version domain, snapshot/live context,
complete slab geometry, source/index mapping, source identity and bookkeeping,
explicit frame and its provenance, selected captured identities, whole pick-state
hash, live current-anchor point-info hashes, configured endpoint, exact derived
bounds, explicit margin and normalized declared target parameters. Canonical geometry
hashes tolerate sample ordering only when paired source-index evidence stays identical.

Analysis and reconstruction require `expected_intent_fingerprint`. They recompute
current intent before running the ROI solver. Changed picks, observed source
geometry/context, frame, margin, target parameters or configured endpoint stale the
old token. Deriving a new token does not refresh an old target or layer selection.

The wrapper places `upstream_section_spatial_intent` into the existing ROI context.
The unchanged ROI fingerprint then binds the target candidates; the existing target
selection context binds layer evidence and the profile handoff. This is not merely
four numbers detached from their originating picks. Responses retain compact
`spatial_intent` beside the unchanged-version `roi_result`.

The returned `numerical_roi_request_fields` are a convenience for older tools. A
bare 0.15.6 numerical ROI call does **not** claim to prove pick provenance. Use the
picked wrappers for a provenance-preserving chain. The old four 0.15.6 tools and
all accepted numerical solvers are unchanged.

An intent fingerprint is not target/layer authorization. Multiple targets still
require `target_id` plus that nested candidate's `candidate_fingerprint` as
`expected_target_fingerprint`. Layer selection still requires `layer_id` and the
matching layer-analysis fingerprint as `expected_layer_fingerprint`. Switching
between automatic and explicit target selection requires fresh layer evidence.
Report fingerprints, foreign workflow tokens and explicit IDs do not override the
ROI's inclusive one-cell edge guard or unsafe evidence. Sparse/overlapping targets,
narrow bridges, unsupported/thick layers and ambiguous topology remain refused.

## Compact output and errors

Derivation returns source/frame summary, exact selected global/local coordinates,
projected U/V/depth, anchor identity hashes, margin, half-open bounds/spans, depth
range, intent fingerprint, configured live endpoint, call-accounting scope and
warnings. It returns no raw slab/cloud array. `ready` means the intent was formed,
not that manufacturing intent or reconstruction was accepted.

Analysis/reconstruction return `spatial_intent` and `roi_result`, copying downstream
`status`, `blocked_stage` and `reason` where applicable. Malformed inputs and stale
fingerprints are MCP errors; ordinary insufficient geometry remains structured
blocked evidence. `manufacturing_intent_confirmed` and `user_accepted` remain false.
No preview or diagnostic overlay token authorizes reconstruction; no new preview
helper is included in this increment.

## Development evidence and next milestone

The deterministic generator writes 18 hashed PLY fixtures outside Git, including
actual boundary-anchor vertices. Cases cover clean/clutter/two-target regions,
all crossed edges, near-edge risk, narrow bridge, layers, sparse/overlap/thick
samples, generic fan-like clutter, three anchors, and arbitrary rotation plus
approximately [1e8,-2e8,3e8] translation. Exact bytes are read through product
projection and workflows; a float32-local host proxy is explicitly not a real host.
Installed MCP stdio exercises snapshots without a bridge and live calls against a
counted TCP replay. See AGENTS.md for exact checkpoint/results and the separate
Windows procedure. No real fan analysis was performed during internal development.

After interaction acceptance, the next architectural step is a CAD feature/model
intermediate representation for datums, sketches, fitted features, dimensions,
relationships, evidence, dependencies and unresolved/refused regions—not broad
Fusion automation bundled into this bridge.
