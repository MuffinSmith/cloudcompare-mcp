# Repository work and interruption recovery

## Accepted 0.15.5; next runtime lane must be separate

PR #19 merged after explicit user authorization at
`50ff06cb383cd662ddee2a1d0e7d0445f9143719`.
Exact Windows-tested retained feature HEAD:
`f6e2fc8a19b97da7d367abd259bed50c02a7e382` on
`feature/live-cad-section-target-diagnostics`.
Pre-merge main: `942c56e222eb5768ae2c60f7c1b6f153db070f68`.
Runtime/test checkpoint: `c3dac92069bf530e41fa66a6d08794e31f0d9076`.
Final-head CI36359917737/job108734919196 succeeded; runtime CI36359440529 had
**890 passed, zero skips**. Python0.15.5. qMCPBridge remains0.12.0/revision8.
No DLL rebuild.

Read `docs/WINDOWS_0_15_5_ACCEPTED.md`. User-reported Windows acceptance:
874 passed plus16 compiler-gated tests passed under MSVC; diagnostic modules125;
compileall/diff checks PASS; both actual MCP stdio tools/capabilities PASS; all20
hashed fixtures PASS through snapshot and visible GUI; limited downstream behavior
unchanged. No reproducible defect. Whole-source integrity remains metadata-only;
no full-cloud equality and no real-host nonunit scale. Actual transformed host shift
[-100000000,199999000,-299999000], scale1; no double application. Host quantization
changed exact hashes/bounds and one bridge flag while erosion still refused.

Fan diagnostic is accepted BLOCKED/inconclusive evidence: exact authorized working
copy, source ID385/name `Assembly | Fan - scan 1`/406276 points; complete5605-point
slab. Baseline19 blocked candidates. UV-finer, depth-finer and depth-coarser refused
at max_targets32. UV-coarser produced10 blocked candidates, one baseline split,
four probe merges,5595 membership-changed points and two exact-match reason changes.
All points accounted; no target/layer/profile selected. Do not retune, raise limits,
drop clutter or choose a probe because it reconstructs better.

0.15.5 acceptance is COMPLETE. Do not repeat 0.15.5/0.15.4/0.15.3 gates because a
chat restarts. Historical pre-acceptance AGENTS is preserved verbatim in
`docs/ACCEPTED_0_15_5_DEVELOPMENT_HISTORY.md`; earlier accepted histories/contracts
remain valid. Retain all accepted branches.

## Suggested next increment: 0.15.6 explicit section-target ROI isolation

First recover exact repository state: current main, branches, recent commits, open
PRs/issues, CI, AGENTS, README and accepted target/layer/profile docs. If a deliberate
newer lane already exists, resume it. Otherwise create exactly one branch from current
accepted main: `feature/live-cad-section-target-roi`. Suggested Python version0.15.6.
Do not continue runtime work on the accepted0.15.5 branch.

Goal: let the caller explicitly declare a bounded section-space ROI before accepted
0.15.4 target analysis, so dense/cluttered slabs can be narrowed by human/assistant
spatial intent without weakening target/layer safety. Prefer Python-only; no native
bridge change unless existing complete slab acquisition proves insufficient.

Initial contract to investigate:
- acquire one complete slab and project to accepted (u,v,signed_depth) coordinates;
- accept explicit finite native-unit UV bounds [u_min,u_max) x [v_min,v_max);
- retain ALL depths inside the UV ROI so accepted0.15.3 layer analysis remains honest;
- classify every slab point exactly once as inside ROI or outside ROI; outside points
  are explicit unselected evidence, never silently discarded;
- run unchanged accepted0.15.4 target analysis only on in-ROI samples;
- preserve source indices/fingerprints/provenance/global shift-scale;
- bind ROI bounds, frame, source, acquisition and target parameters into stale-safe
  fingerprints; changing any of them invalidates prior choice;
- report ROI point count, outside count, UV/depth ranges, candidate summaries and
  compact accounting; raw arrays remain server-side;
- use deterministic half-open boundary semantics and test exact/nextafter edges;
- detect targets touching/crossing the ROI boundary. A one-accepted-UV-cell edge band
  is a reasonable first guard derived from uv_cell_size, not a searched parameter.
  Boundary contact must block automatic reconstruction because the ROI may truncate a
  physical target. Explicit target selection must NOT override truncation evidence;
- multiple supported in-ROI targets still require accepted fingerprint-bound target
  selection. Then use unchanged0.15.3 layer,0.15.2 occupancy,0.15.1 topology/fitting;
- no automatic ROI search, largest-target preference, diagnostic-scale selection,
  manufacturing-intent inference or choosing whichever ROI/profile looks nicest.

Possible tools: `analyze_section_target_roi`, `analyze_live_section_target_roi`,
`reconstruct_section_target_roi_profile`, `reconstruct_live_section_target_roi_profile`.
Names may change only for a clearer contract. Keep analysis/reconstruction separate.

Fixtures/tests should include: one target inside with outside clutter; two targets with
one outside; multiple targets inside; target crossing each ROI edge; target exactly on
half-open boundary; safe target separated from edge guard; narrow bridge leaving ROI;
sparse/unsupported ROI; empty/tiny ROI; permutation; arbitrary rotation and large
translation; stale ROI/source/frame/parameter tokens; complete vs truncated live
acquisition; max budgets; nonfinite/malformed bounds; compact output/no arrays; no
source mutation; shift/scale preservation; target->layer->occupancy/topology handoff;
and unchanged accepted downstream behavior. Generated exact files stay outside Git.

The real fan is evidence, not a success criterion. Do NOT invent/tune an ROI from the
0.15.5 probe results merely to get a profile. Synthetic/internal work must be coherent
and CI-green first. A later real-fan test should use an ROI explicitly derived from a
visible/picked spatial intent declared before seeing reconstruction quality. It may
still be BLOCKED. Never use diagnostic panel quality to choose the ROI.

Do not mix ellipse/rounded-rectangle/spline/Fusion work into this increment. Do not
merge0.15.6 without a separate focused Windows gate and explicit authorization.

## Stream-disconnect recovery policy

Work in small recoverable increments. After each coherent change: commit, verify the
returned SHA/parent/tree and remote branch persistence, update AGENTS at milestones,
then continue. Save before long tests. On disconnect inspect actual remote HEAD,
recent commits, AGENTS and CI; a UI stream failure does not imply GitHub work was lost.
Never reset, clean, force-push, delete retained branches, or create retry/recovery/-2
branches merely because a chat restarted. Preserve unexpected work. Avoid giant CI
log dumps and rapid polling. Distinguish local numerical tests, replay/mocked native,
actual MCP stdio, CI and real GUI evidence. Never promote metadata-only integrity or
replayed nonunit scale into stronger claims.
