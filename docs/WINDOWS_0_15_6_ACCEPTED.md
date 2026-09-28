# Accepted Windows 0.15.6 result

The user supplied this focused acceptance on 2026-09-27 and explicitly authorized
merging PR #20. PR #20 subsequently merged at
`04a21fc32261fe7a071fd9ab46ee353afd33016c`. Exact Windows-tested feature HEAD:
`3a1d49550e3e1a90d4915fb197ad51688a3e836d`. Final pre-merge documentation HEAD:
`f2ec9970feb8a2ff43d04a4939a34f2fdb01fd45`. Accepted-main parent:
`809c522550274316fa0a14d2e86d90a4921bfc03`. Runtime/test checkpoint:
`5d618c0de30c90a4573d4c8be52174a3aed58eee`. Changes after the Windows-tested
head were acceptance documentation/recovery notes only.

This document records the supplied Windows/CloudCompare report and merge
authorization; it does not claim a new independent host rerun. Detailed raw
responses, recovery scripts and the full accepted-parent diff remain outside Git.

## Accepted gates

- Isolated Windows Python 3.13.14 noneditable install reported package 0.15.6;
  all 28 installed Python modules matched checkout bytes.
- Installed regression: 1,054 passed with 16 compiler-gated policy tests skipped
  in the ordinary shell; those same 16 passed under configured MSVC. Effective
  total: 1,070 passed.
- `python -m compileall`, `git diff --check`, exact-head push CI and PR CI passed.
- All 22 generated PLY SHA256 hashes were verified; the seven new focused modules
  passed 180 / 180.
- Actual isolated MCP stdio advertised all four 0.15.6 ROI tools. Snapshot calls
  ran without the bridge; live calls reached the visible CloudCompare host.
- Counted TCP replay verified one native query per valid call. This is replay
  coverage only and does not independently measure real-host query count.
- Visible CloudCompare fixture acceptance passed for 20 declared fixtures.
- qMCPBridge remained 0.12.0 / workflow revision 8 and `cloudcompare-plugin`
  had no accepted-parent diff; no DLL rebuild was required.

The visible host was CloudCompare 2.13.2, PID 14312, owning bridge port 8765.
Every completed fixture acquisition satisfied
`inside + outside = returned = matched` with zero ROI-unclassified points.
Safe cases reconstructed through the unchanged accepted chain. Two targets inside
one ROI required explicit current target selection. All four crossed-edge cases
refused at `roi_truncation_guard`, including explicit-ID attempts. Parallel
layers required fresh layer evidence after target-selection mode was fixed.
Overlap, narrow-bridge, sparse and alternating-thick cases retained their safety
refusals. Root selected/unselected accounting remained complete through downstream
attempts.

## Host representation observations

CloudCompare collapsed the exact-double half-open fixture's `nextafter`
distinctions to acquired values 0, 5 and 10. Membership against the actual acquired
host values was 6 inside / 6 outside. This is accepted representation evidence,
not permission to snap ROI bounds or demand impossible cross-context bit equality.

Transformed imports reported global shift
`[-100000000, 199999000, -299999000]`, global scale 1, with no double
application. Maximum observed file-to-host global-bound difference was about
`2.73e-5`, consistent with host local-coordinate quantization.

No real-host nonunit global scale, independently measured host native query count,
or whole-cloud geometry/attribute equality is claimed. The 37 preexisting scene
roots and empty selection matched the saved baseline after disposable acceptance
imports were removed.

## Optional fan exercise remains correctly BLOCKED

The authorized `Fan_project.bin` and working copy shared SHA256
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.
The current source was independently rediscovered as a 406,276-point cloud.

No defensible picked spatial intent and section frame were declared before
reconstruction-quality inspection, so **no 0.15.6 fan ROI call was made**. This
is the correct bounded outcome, not a product failure. The retained 0.15.5 fan
diagnostic therefore remains BLOCKED/inconclusive.

Do not convert this accepted result into permission to derive ROI bounds from a
convenient diagnostic panel, search ROI sizes, raise `max_targets`, choose a
depth sign, discard clutter, or select whichever candidate reconstructs best.
A future fan ROI requires explicit human/agent spatial intent declared first.

## Accepted interpretation

0.15.6 establishes a deterministic, provenance-bound spatial narrowing stage
before the accepted target/layer/boundary/topology/profile chain. The host gate
confirmed the intended refusal boundaries and coordinate bookkeeping. It does
**not** establish manufacturing intent, automatic ROI discovery, general
point-cloud-to-CAD autonomy, or stronger source-integrity claims than those
actually measured.

The next product increment should address the missing intent bridge exposed by the
fan gate: convert deliberate CloudCompare picks/visible spatial intent into a
provenance-bound section frame and explicit numerical ROI **without** using
reconstruction quality to optimize the bounds.
