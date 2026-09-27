# 0.13 first increment: face-constrained candidate relationships

Branch: `feature/live-hole-patterns`. The accepted 0.12 work was merged through
PR #8 at `38f92c1dd62fdba92a4fc51959289287ae6eaaed` after explicit user approval.
This next stage is implemented in Python and is **not yet Windows-accepted**.

## Compatibility and scope

- Python package: 0.13.0.
- Native qMCPBridge remains 0.12.0, workflow revision 8, unchanged from the accepted
  `fc51824d9edf7328614653c57bf3644c1db02769` native source.
- No new dependency and no DLL rebuild is required for this increment.
- New MCP tools: `analyze_hole_candidates` and `discover_live_hole_candidates`.
- Both are read-only. They do not create overlays, transform geometry, export CAD,
  classify a physical hole, or change accepted discovery/overlay implementations.

## Analysis of an existing circle discovery

Pass the **complete, unmodified JSON result** of `discover_live_circles` as
`circle_discovery` to `analyze_hole_candidates`, together with:

```json
{
  "face_origin": [0, 0, 0],
  "face_normal": [0, 0, 1],
  "plane_tolerance": 0.2,
  "diameter_tolerance": 0.1,
  "center_tolerance": 0.05,
  "spacing_tolerance": 0.1
}
```

The values above describe a synthetic native-unit fixture, NOT the user's fan.
All coordinates and lengths, including region selectors, must be global native
coordinates. Do not relabel local coordinates as global or assume millimetres.
The snapshot tool requires a single source cloud and a global/native
`circle_discovery` envelope. Candidate IDs, sample count, final support counts and
fractions must be consistent. It does not connect to the host or verify freshness.

Optional quality settings are `normal_tolerance_degrees` (default 10),
`min_support_count` (12), `min_support_fraction` (0.02),
`min_coverage_degrees` (270), and `max_fit_rms` (unset).

## Fresh live discovery plus analysis

`discover_live_hole_candidates` accepts the same face/analysis parameters plus
`cloud_id`, a global `region`, explicit `min_radius`, `max_radius`, and
`distance_threshold`. Optional limits: `sample_limit` (3000, max 10000),
`max_circles` (8, max 16), and `iterations` (800, max 2000).

It validates parameters before I/O and makes one existing `cloud.region_query`
request. For a successful sample reply, it verifies source/frame/sample counts,
invokes the accepted circle algorithm with seed 0, and analyzes the result. An
empty or undersupported sample returns no candidates. No point array is returned
to chat. Native sample counts, truncation and sampling warnings remain attached
under `input_provenance`. `scene_freshness_guaranteed` is always false because
later scene edits can make any result stale. This is not a full scene fingerprint
or integrity check.

### Empty-region compatibility with the accepted DLL

The accepted 0.12/revision 8 DLL uses error responses for valid no-match regions.
Only this new tool adapts these exact, selector-specific responses:

- Box, sphere or slab: `cloud.region_query selected no points`.
- Nearest with an explicit `max_distance`: `No point was found within nearest.max_distance`.

These return successful provisional analysis with zero candidates, groups and
spacings. Match/sample counts are zero, truncation is false, and sample strategy
is null: no sampling strategy was returned. `input_mode` is
`fresh_live_empty_region`, `live_query_completed` is true and
`live_sample_acquired` is false. `input_provenance.empty_region_evidence` records
the original native message, that the zero counts were derived from that no-match
response, and `source_frame_metadata_returned: false`. Source ID and coordinate
space describe the validated request; no returned source/frame echo, bounds,
points, scan attributes, or full-scene integrity evidence is fabricated.

The normal successful-sample path is unchanged, including its existing
`live_sample_acquired: true` marker for receipt of a structured sample reply.
Offline snapshot analysis still does not contact the bridge.

Missing/invalid clouds, a source cloud with no points, inability to inspect the
source, invalid selectors, malformed replies, and connection/timeout/authentication
failures remain errors. There is no retry, fallback region, or change to the shared
transport or other tools. In particular, direct `query_live_region` retains its
native error semantics. This fix requires no native rebuild. See
`docs/WINDOWS_EMPTY_REGION_RETEST.md` for the focused issue #11 retest.

The selected face filters final circles. It does not silently substitute another
region or project a broad face onto a plane before detection. Localize the region
first; otherwise unrelated structures can dominate bounded discovery.

## Results and interpretation

1. **Face filtering.** Canonicalize normal sign; compare normal alignment and the
   whole circle's maximum departure from the face, not only its center offset.
   Low support, low angular coverage, off-face geometry and excessive configured
   RMS are rejected with individual reason codes.
2. **Duplicates.** Select a representative by support count, RMS, then input ID.
   Every member must match every other member within center/diameter/normal limits.
   Duplicates keep their ID-to-representative mapping. No geometry is averaged.
3. **Diameter groups.** Deterministically partition by sorted diameter; each
   group's complete diameter range must fit the tolerance. Transitive chains
   cannot swallow arbitrarily different sizes.
4. **Spacing.** Return all retained candidate pairs (at most 496 for 32 inputs),
   with in-face and 3D center distances, signed face-offset difference, and
   diameter difference. Concentric candidates of different radii remain separate;
   they are not automatically interpreted as counterbores or extra mounting holes.
5. **Layouts.** Check only a complete diameter group. At least three distinct
   centers are needed for an equally spaced row; four for an equally spaced bolt
   circle. Normalize coordinates before SVD/least squares. Check line/radial error
   and adjacent spacing against `spacing_tolerance`. Angular spacing errors are
   converted to arc-length errors at the fitted pitch radius, in native units.
   Coincident centers block a layout claim. No combinatorial subset, grid,
   missing-hole, rectangular-pattern classification, or user-confirmation store
   is included in this first increment.

All output is provisional (`confirmed_holes: false`). A circular fit on a flat
surface, a boss, a spoke or a sampled rim can pass numerical checks without being
a hole. Equal sizes/spacing are relationship evidence, not topology or mechanical
intent. User-chosen tolerances are not measurement uncertainty. Fit quality is
not a calibrated probability. Three points defining a circle is not enough to
claim a bolt-circle pattern. Results do not certify bore sizes.

The result includes a deterministic in-face basis for reporting, not a committed
CAD coordinate system. Full feature acceptance, hole topology evidence, pattern
subset search, persistent references, and CAD export remain future increments.
