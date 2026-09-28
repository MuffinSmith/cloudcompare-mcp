# Agent visual inspection (Python 0.16.0)

Status: internally tested, stacked draft PR #22. Visible Windows/CloudCompare and
real human semantic acceptance are not yet established. Requires native
qMCPBridge 0.13.0 / workflow revision 9; the 0.12.0 DLL is insufficient.

The primary interaction is now: inspect geometry, navigate and capture useful
views, review the returned images, propose a feature, and ask a simple semantic
question. Exact vertex picking remains the retained 0.15.7 fallback. Images supply
context, numerical geometry supplies dimensional evidence, and an explicit human
answer supplies semantic intent. None independently authorizes CAD construction.

## Public tools

| Tool | Contract |
| --- | --- |
| `get_live_camera` | Read camera state; `save=true` also creates a native restoration token. |
| `set_live_camera` | Guarded `look`, `orbit`, `pan`, `zoom`, `focus`, `restore`, or `release`. |
| `inspect_live_part` | Bounded whole-source geometry discovery and real viewport images; restore by default. |
| `propose_live_semantic_feature` | Bind reviewed image observations and a question to issued geometry and capture evidence. |
| `confirm_live_semantic_feature` | Bind an explicit `yes`, `no`, or `unsure` and its reported human text to an issued proposal fingerprint. |
| `validate_live_semantic_confirmation` | Recheck observed freshness, latest-answer identity, and conflicting affirmative roles. |
| `release_live_inspection` | Discard only this process-local inspection and its proposals/answers. |

Existing `set_live_view` is retained. Existing `capture_live_view` now includes
native camera state and PNG SHA256 provenance alongside its actual MCP image.
The Python service does not interpret images. The calling agent must review the
returned PNGs before issuing a reviewed proposal; draft automatic questions cannot
be confirmed. No precise human clicking is required by these seven tools.

## Recoverable camera contract

`get_live_camera(save=true)` stores an actual `ccViewportParameters` copy, not a
pose reconstructed from rounded JSON. Up to eight tokens are retained without
eviction. Release only tokens owned by the current operation.

Moves and restore require `native_session`, `window_id`, and
`expected_camera_fingerprint` from the latest observed camera. After every move,
use its returned guard for the next move. A baseline fingerprint is not a valid
expected-current guard after navigation. Release takes only `native_session` and
`restore_token` and does not move the camera.

| Action | Declared input / semantics |
| --- | --- |
| `look` | Nonzero `direction` and nonparallel `up` vectors. |
| `orbit` | `axis_camera` and signed `degrees` in [-180, 180]; axis is camera-space. |
| `pan` | `right_fraction` and `up_fraction`, each in [-1, 1], relative to view span. |
| `zoom` | `factor` in [0.1, 10]; values above one zoom in. |
| `focus` | Visible point-cloud `entity_id`; optionally `center_global` plus `width_global`, or `min_global` plus `max_global`. |
| `restore` | Saved `restore_token`, with current-camera guards. |

Focus always requires a declared source cloud frame, including for a global point
or box. Native host coordinates are `(global + global_shift) * global_scale`.
Cloud global scale may be nonunit. Pending display transforms, disabled/invisible
sources or ancestors, non-cloud entities, and a source attached to another display
window refuse. Entity/box framing uses a fixed display margin, not a reconstruction
ROI or an adaptive fitting tolerance.

Camera state records projection/object-centered flags, view rotation, host pivot
and camera-center parameters, view/up directions, focal distance, field of view,
aspect, clipping parameters, point/line sizes, display flags, session/window and
viewport dimensions. The reported camera center is a CloudCompare host-render
parameter, **not a global world-eye coordinate**. The computed model-view matrix
and derived near/far values are reported but not part of the equality fingerprint.

Navigation supports existing object-centered orthographic and perspective modes;
it does not add projection-mode switching or an arbitrary pose/matrix setter.
Stereo, bubble view, viewer-centered perspective and nonunit display scale refuse.
Display scale is distinct from the supported source cloud global scale.

Restore requires the same native session, active window, and viewport dimensions.
It reapplies saved viewport parameters and compares the resulting camera
fingerprint. It is not a complete GUI, scene, selection, LOD, or framebuffer
snapshot, and does not promise pixel-identical recapture. Invalid or enormous
numbers, booleans used as numbers, nonfinite values, degenerate directions and
invalid rotations refuse before applying a candidate camera state.

## Bounded inspection

`inspect_live_part` requires `distance_threshold` in global native coordinate
units, fixed before discovery. Defaults are 1024 sample points, plane/cylinder
discovery, and top/front/isometric declared views. Optional `cloud_id` chooses a
source explicitly. Without it there must be exactly one eligible point cloud;
multiple sources require a choice, not a silent largest-cloud heuristic.

The source must contain 24 through 5,000,000 points. Its declared whole-source
bounding box is read through the existing native region query, with a deterministic
sample of 24 through 2048 points and the all-match query summary. The original
plane/circle/cylinder discovery solvers are called once per requested kind, at most
two candidates per kind, with fixed parameters. Refusal is evidence, not a reason
to retry with better-looking settings. The service saves the baseline camera,
focuses the source, captures the requested views, rechecks observed source/scene
context, and restores its camera by default.

Hard limits per inspection: four captures; five navigation moves plus one restore;
two geometric acquisitions; three discovery calls; six initial candidates/draft
proposals; 128 KiB response metadata; 8 MiB per PNG and 16 MiB total PNG content.
There are at most sixteen cached inspections and twelve proposals per inspection,
including initial drafts. Cache exhaustion requires explicit release, not eviction.

The supported declared view names are top, bottom, front, back, left, right and
isometric. Directions/up vectors are explicitly defined in `live_inspection.py`;
these names do not independently verify equivalence to every native toolbar view
convention. Existing standard-view compatibility is part of the visible-host gate.

Default recovery uses the last camera state owned by the operation. A concurrent
human move, window change, or transport-ambiguous move is not overwritten merely
to restore the baseline. Errors return recovery details and a retained token when
safe restoration cannot be established. `restore_camera=false` intentionally
retains the inspection view and its baseline token. Inspection release does not
release camera tokens; restoring/releasing a retained camera is a separate action.

## Capture and geometric provenance

Native capture brackets framebuffer acquisition with camera checks and reacquires
the active window after event processing. Captures include dimensions, camera state
and the actual PNG byte SHA256. Python validates base64, PNG structure, chunk CRCs,
IHDR dimensions, declared hash and byte budgets. These checks are not image
interpretation or proof that a visible feature has a particular meaning.

Inspection capture evidence also binds sequence, declared view, source/scene
context and existing overlay IDs/fingerprint. Camera movement later does not alter
this frozen evidence. Candidate A/B/C labels are metadata labels, **not newly drawn
viewport labels**. Candidates bind the numerical result, fixed solver parameters,
source ID, context, and installed discovery/fitting source-code SHA256 hashes.

Python fingerprints use domain-separated SHA256 over canonical sorted compact JSON
with nonfinite values rejected. Native camera fingerprints use the separate
`cc-camera-v1` contract and Qt serialization. The context binds scene metadata,
overlay metadata, the exact returned deterministic acquisition and query summary,
the frozen query, endpoint configuration, native session and window. PNG blobs are
returned as MCP images but are not retained inside long-lived semantic objects.

## Human semantic confirmation and staleness

A reviewed proposal references issued candidate IDs and capture indexes, an allowed
semantic role, a concise question and explicit visual observations. Its fingerprint
binds that evidence and question. Semantic role names such as `possible_bolt_pattern`
or `possible_through_feature` are a vocabulary, not an implementation of complete
bolt-pattern or through-feature detection. This first orchestration discovers only
planes, circles and cylinders. Existing hole-pattern, datum and section tools remain
separate; unsupported interpretations must remain unresolved.

Confirmation requires the issued proposal fingerprint, an explicit answer and the
exact reported human answer text. Generic conversational context is not a yes.
Caller-reported observations and answer text are not authenticated vision/human
identity. All proposals and answers remain hypotheses or intent, not CAD authority.

Propose, confirm and validate each recheck the observed acquisition and
scene/selection/overlay metadata with native session/window and endpoint guards.
A detected change or failed freshness read permanently stales that inspection;
changing the source back does not resurrect its old answers. The latest answer to
a proposal supersedes previous answers. Different affirmative roles sharing an
issued candidate require semantic review; this is not general spatial-overlap
conflict detection. Camera movement alone does not stale frozen captures.

Freshness is **sample plus query summary and metadata**, not whole-cloud coordinate
or attribute equality. Reads are non-atomic, and an unobserved change-and-change-back
may be indistinguishable. Unrelated scene, selection or overlay metadata changes
can conservatively invalidate intent. Process restart or explicit inspection release
invalidates its IDs. Preserve issued packets externally before releasing them, while
recognizing that an exported packet does not keep a process-local token valid.

## Source safety and remaining gate

No source geometry, selection, or unrelated overlay mutation is requested. This
increment creates no new overlays because existing group-wide clearing does not
provide per-inspection ownership. Existing overlays are observed and preserved.
No ROI/scale/padding search, target/layer-budget increase, clutter removal,
reconstruction-quality selection, fan reconstruction, CAD IR or Fusion construction
is part of inspection. Human approval never overrides numerical refusal evidence.

See [internal review and test evidence](VISUAL_INSPECTION_REVIEW.md),
[focused Windows acceptance](WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md), and
[the retained manual-pick checkpoint](RETAINED_0_15_7_CHECKPOINT.md).
