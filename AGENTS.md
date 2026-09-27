# Repository work and interruption recovery

## Active UNMERGED 0.15.4: implementation complete, Windows next

Branch: `feature/live-cad-section-target-isolation`.
Accepted-main parent: `0201cdd46381e0c79c05b33ee9de48851a18b877`.
Exact complete runtime/test checkpoint: `f2ba2eb5b09c6cc267cd2eaf33dbfde268e59080`.
Installed CI `36356259255` / job `108724473998`: **765 passed, zero skips**, 36.24 s;
compileall and diff check passed. Source tree `e13878ceebcd49c5bf19459bf738996b884fe950`.
Subsequent finalization changes are documentation only. Inspect actual remote HEAD
and current CI after a disconnect; do not recreate or restart this lane.

Local dependency-available regression: **550 passed**, zero skips, including all
16 compiled native policy tests (not a plugin build). Focused new coverage is 139
tests: 48 core, 43 workflow/replay, 18 boundary/precision/provenance, 20 exact-file,
10 MCP schema/dispatch/actual stdio tests. Local focused non-MCP subset: 129 passed;
the MCP tests and complete installed suite ran in CI, not the dependency-limited
container. All 14 fresh hashed PLY files passed product projection/snapshot/replay;
original and arbitrary-rotated/large-translated single/parallel handoff passed.
Generated files, logs and raw evidence remain outside Git.

Python 0.15.4. qMCPBridge remains accepted 0.12.0 / workflow revision 8. Native diff
against accepted main is empty. No DLL rebuild. Accepted layer/boundary/topology/
primitive solvers and server.py are unchanged; only the layer-tool registry delegates
new tools. **No real Windows/CloudCompare 0.15.4 acceptance has occurred here.**

Next action: follow `docs/WINDOWS_SECTION_TARGET_ACCEPTANCE.md` at the supplied final
HEAD after confirming green CI. Read `docs/LIVE_CAD_SECTION_TARGET_ISOLATION.md` for
contracts/refusal boundaries. Testing/reporting only, not implementation or DLL work.
Do not merge 0.15.4 and do not ask for merge authorization merely because tests pass.

## Verified recovery and draft PR #18

Recovered the existing completed branch at
`423d48e43fa7632dab3f15a82beba267e52b709a`; no replacement branch or runtime
implementation was created. Draft PR #18 now tracks this unmerged increment.
Final-documentation push CI `36356607178`, job `108725479512`, was independently
read: **765 passed, zero skips, 31.21 s**, compileall and diff check passed.
This recovery checkpoint changes AGENTS.md only; inspect the new HEAD/CI rather
than assuming the documentation checkpoint above is still the branch tip.

Fresh recovery audit: **129 passed in 6.64 s** across the four non-MCP target test
modules, plus compileall and the full accepted-main-to-feature diff check. The fresh
container lacks mcp/laspy/plyfile; the full installed suite and actual stdio results
are CI evidence, not a newly claimed full local run. No real GUI test was repeated.

Downloaded tested-source artifact `10944357424`; ZIP SHA256
`4c376178346a5a1fe4b829f25522db533787329a391e18c30be5e426aeaadd73`.
Its archive commit comment and reconstructed Git source tree matched the recovered
HEAD and `80ac93381eb7f51a4eac11bf5b6898a4d4ae94d1`. Accepted main's source tree
was also independently verified. The final change set contains 17 files; native
plugin and accepted solver diffs are empty. The saved 0.15.3 AGENTS history is
byte-for-byte equal to accepted main. No merge, reset, clean or force-push occurred.

Next action remains focused Windows acceptance using the final supplied SHA and
`docs/WINDOWS_SECTION_TARGET_ACCEPTANCE.md`, not a new development increment.
Keep PR #18 draft and unmerged. Do not rerun accepted 0.15.3 acceptance.

## Implemented scope and deliberate limits

Four snapshot/live target analysis/reconstruction tools; capabilities at
`python_section_layers.section_targets`. Pure numerical core uses declared UV/depth
voxels, six-face connectivity, unique-point support, iterative articulation guards,
one-cell UV erosion and six fixed +/- origin probes. Diagnostics never repair or
replace baseline membership. Every acquired point belongs to a reported candidate.
Multiple targets require an explicit candidate-bound token even if only one is large
or usable. Distant unsupported clutter can remain explicitly unselected; an unsafe
target itself cannot be overridden. Target then layer selection preserve all counts.

Complete global-coordinate native acquisition only, no reservoir topology proof.
Source/frame/acquisition/parameter fingerprints bind selection; live index mapping
is included. No double shift/scale. Fingerprints cover acquired slab geometry, not
independent whole-cloud geometry/attribute equality. A selected target still passes
UNCHANGED accepted 0.15.3 -> 0.15.2 -> 0.15.1/fitting guards (layer default16).
Subcell/unsampled connections, wide necks and all possible grid phases are not proved
absent; harmless thin appendages can conservatively block. No manufacturing intent,
largest-target preference, sign selection, adaptive search, Fusion, ellipse or spline.

## Accepted history is not an outstanding gate

Original main AGENTS.md is preserved verbatim in `docs/ACCEPTED_0_15_3_HISTORY.md`.
Also read `docs/ACCEPTED_DEVELOPMENT_HISTORY.md` and relevant accepted CAD documents.
Their historical next/pending wording is superseded by this active lane.
Accepted 0.15.3: PR17 merge `27cfd286331db177c76ce627056150e439d418c9`;
retained feature HEAD `dda5032a60143f7a17691034c337a83492a8613f`;
actual Windows runtime `2f952f005243ee8cbdb3c4c1a0a3363a4b40cb05`.
Windows610 passed +16 policy tests later passed under MSVC; CI626 passed. All12 exact
fixtures and actual stdio/GUI/safety/handoff gates passed. Integrity was METADATA
ONLY, not independently full-cloud; no actual nonunit-scale source was tested.
Do not repeat this completed acceptance just because a chat restarted or inflate it.

Retained real fan: BLOCKED, not failed. Historical cloud359, `Assembly | Fan - scan 1`,
406276 points; slab [40,0,135], normal[0,0,1], half0.5, complete5605/5605. Declared
0.15.3 analysis exceeded16 components, produced no token and did not reconstruct.
Never raise limits, remove clutter, choose a depth sign or parameter-search to make
it pass. New target-stage fan diagnostics may also remain legitimately BLOCKED.
The focused Windows procedure predeclares one bounded coarse target analysis.
Resolve actual fan_project.bin and scene identity; use a working copy, not assumptions.

## Persistence and reproducibility

Remote checkpoints (all verified): recovery `4b456f38affa8fdb250893ba5e1c148d8015ea26`,
core `b910000fe435a0589e1e2e64df9bbc084d5edff0`, workflow
`34e0606882a881f860661f742e5f77aecdf0b271`, MCP
`b22e18f1a2b785642e57b7a7d1231e282caa9d77`, fixtures
`7cb0df8b416dbdc85cdcd23d91f7c9a675554843`, full tests `f2ba2eb5b09c6cc267cd2eaf33dbfde268e59080`.

Direct container Git networking was unavailable. Accepted source came from Actions
artifact10943288751, ZIP SHA256
`06a934a875c6b725a68edc1d848aabbf3df9c2a0083c90996cb70c3d688d36cb`.
The archive commit comment matched accepted main; reconstructed local Git tree
matched `6a14df038d0354f474fea37666c3e24fce2c5787`. Every checkpoint's local source
tree matched the remote tree. Local mirror commit IDs are not remote commit IDs.
CI artifacts archive tracked public source only, never credentials or user data.

Commit coherent increments and verify returned SHAs plus remote persistence before
substantial next work. Update this file at milestones and save before long tests.
A failed stream does not imply a failed GitHub write: inspect HEAD, commits, AGENTS
and CI. Never reset, clean, force-push, delete retained branches or create retry/
recovery/-2 branches. Preserve unexpected work and unrelated active checkouts.
Avoid giant repeated log dumps and rapid polling loops. Before any later Windows
gate require installed full regression, compileall/diff checks, actual stdio/schema,
replay/file coverage, final accepted-main/native comparison, green CI and this
checkpoint. Return exact identities, counts, limitations and one focused test prompt.
