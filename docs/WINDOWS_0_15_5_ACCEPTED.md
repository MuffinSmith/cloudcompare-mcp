# Accepted Windows 0.15.5 result

The user supplied this focused acceptance on 2026-09-27 and explicitly authorized
merging the accepted increment. PR #19 merged at
`50ff06cb383cd662ddee2a1d0e7d0445f9143719`. Retained feature branch:
`feature/live-cad-section-target-diagnostics`. Exact Windows-tested feature HEAD:
`f6e2fc8a19b97da7d367abd259bed50c02a7e382`. Pre-merge accepted main:
`942c56e222eb5768ae2c60f7c1b6f153db070f68`. Runtime/test checkpoint:
`c3dac92069bf530e41fa66a6d08794e31f0d9076`.

This document records the supplied report and merge authorization, not a new
independent Windows rerun. Raw per-case responses remain outside Git.

## Accepted gates

- Exact detached checkout and remote feature branch matched the tested HEAD.
- Isolated Python 0.15.5 imported from that checkout and served temporary MCP stdio.
- Visible CloudCompare 2.13.2 was PID 14312; qMCPBridge 0.12.0 / workflow revision8
  owned port8765. Native source diff was empty and no DLL was rebuilt.
- Runtime/test CI: 890 passed, zero skips. Final-head CI36359917737/job108734919196
  succeeded; changes after runtime/test checkpoint were documentation only.
- Windows installed suite: 874 passed and16 compiler-gated skips; the same16 policy
  tests passed separately under configured MSVC. The initial inaccessible system
  pytest temp directory was environmental; an isolated-temp rerun passed.
- Four diagnostic modules:125 passed. Compileall and working/staged/accepted-main
  range diff checks passed.
- Actual stdio listed both diagnostic tools and capability0.15.5 while retaining
  target/layer/profile0.15.4/0.15.3/0.15.2. Transformed snapshot worked without the
  bridge. Invalid controls/selection inputs errored; max_points=10 refused before probes.
- All20 hashed fixtures were exercised through product snapshot and visible-GUI live
  paths. Every completed/refused panel, root total, relation total and preview omission
  accounted for every point. Before/after source metadata matched. The real-host
  native query count was not measured; one-acquisition behavior is replay/unit coverage.
- Limited downstream checks were unchanged: clean single and transformed parallel
  reconstruction matched before/after diagnostics; parallel still required its
  justified layer; alternating-thick remained blocked even with explicit layer token.

Declared depth-split/depth-merge evidence behaved as intended. UV-finer refused at
max_cells49 and max_targets1 for the respective fixtures, with no retry or budget
change. The large preview retained12 omitted candidates accounting for7200 points.
Geometry, frame, source/provenance and parameter changes changed diagnostic
fingerprints; snapshot/live fingerprints differed; a diagnostic fingerprint could
not authorize accepted reconstruction.

## Transformed-host observations and coverage limits

The five transformed visible-GUI imports used global shift
`[-100000000,199999000,-299999000]` and scale1. Acquired global coordinates were
not shifted twice. Contracted discrete outcomes matched snapshot evidence. Matched
projected bounds differed by at most about3.03e-5, consistent with observed host
local-coordinate quantization; exact cross-context hashes differed. The imported
narrow bridge lost one snapshot bridge flag but retained erosion-based refusal.
No threshold was retuned.

Whole-source integrity was independently checked at scene-metadata level only. File
hashes and complete slabs do not prove full live-cloud geometry or attribute equality.
All real-host scales observed were1. Replay scale2.5 remains bookkeeping coverage,
not a real-host nonunit-scale test.

## One declared fan diagnostic: accepted BLOCKED/inconclusive evidence

The retained working copy matched the authorized Fan_project.bin SHA256. Current
visible source: ID385, `Assembly | Fan - scan 1`, 406276 points. Exactly one call
used the declared parameters. Acquisition was complete:5605 matched/sampled; root
selected0/unselected5605.

- baseline:19 candidates, all blocked;5605 classified. Eight previewed;11 omitted
  candidates accounted for3315 points.
- UV finer: refused at max_targets32;0 classified/5605 unclassified.
- UV coarser:10 blocked candidates;5605 classified. One baseline split and four probe
  merges;5595 points changed membership. Two exact-match reason sets changed. All5605
  relation points accounted, including four omitted relations covering310 points.
- depth finer: refused at max_targets32;0 classified/5605 unclassified.
- depth coarser: refused at max_targets32;0 classified/5605 unclassified.

Result: BLOCKED/inconclusive with UV-coarser sensitivity observed. No target, layer
or profile was selected; testing stopped after that call. This is not a defect and
does not authorize raising limits, choosing a depth sign, dropping clutter, searching
scales, or selecting whichever result reconstructs best.

## Exact fixture SHA256 values

| fixture | points | GUI ID | SHA256 |
|---|---:|---:|---|
| single | 1200 | 404 | c240ccbcec5324f7e659a928506c8d2369deacd8b34108e83dbb3fd2b97a6e62 |
| coherent_clutter | 1203 | 406 | 3575a607f2126484260298bbffd9f1843116075fb7023d60fee325fd8a29cb4e |
| two_targets | 2400 | 408 | ca90de4a3b974d3e288f22403846de840d8efbce17e6fc4a2ec1e98372e0eeb3 |
| dominant | 3600 | 410 | be242b9a79b26a461c735e71afcc46b0825e2e9f326c28b0136b86be0f0e4ae0 |
| narrow_bridge | 2550 | 412 | 92922529576ced53bb03898fedc141b423c1e09006501e50c446861993b80b47 |
| parallel | 2400 | 414 | bb66b581bdb9c4c3cd7c16e55d930c7b26433ecdad202f74aa28ffad630143e0 |
| nested_choices | 3600 | 416 | 84a478d39d9477e10443b05c46702973d2999cfce679c73fb610773ce2b471fd |
| sparse | 36 | 418 | fd7d1bf94116c26fe6bdf3e1d151d3ea38dd1c323b7b69a99818653237dc2365 |
| overlap | 2400 | 420 | 5ca30cd1b14d0d3cd25c1549db24c6c213a26637fd5c260370d2c4f523e7f9d0 |
| fan_like_many | 12000 | 422 | 71b8c5793dc8bf724c17768ea80d9f0e6b3042e72ee5946b4f8f981e2ad861b4 |
| permuted_two | 2400 | 424 | 9d0aa922f44d9300619f225e5813ae9348e58448c846d30f6c97be48244ea135 |
| transformed_single | 1200 | 426 | 4deb928833222000f82e81017d2158925d6c8331fe94df420861046925dacc2a |
| transformed_two | 2400 | 428 | 7731033d5eacd459a564e5b360e6ef67680cdca544f4c54a914c58a2541e1c00 |
| transformed_parallel | 2400 | 430 | b916d16e6898588f3e8d641dd7061c48c7b94241138801d22e7cef58bd08c11e |
| depth_split | 2400 | 432 | cb443a0a1035db1518027437b7d469746dbfefda9559747b097e19be63710e8a |
| depth_merge | 2400 | 434 | e2d619bacbe2efb8b071a396077737467d3d728e9aaa562cac67ef0b94f33c7e |
| probe_cell_budget | 900 | 436 | c43ce3d281b08434e1132491288e4839c0008074ce9aefbb1507593671876ff6 |
| probe_target_budget | 36 | 438 | fd7d1bf94116c26fe6bdf3e1d151d3ea38dd1c323b7b69a99818653237dc2365 |
| transformed_depth_split | 2400 | 440 | 956741d007c7473d421416462df31e109e674ccb02e461db50f2270ebfb12fa6 |
| transformed_depth_merge | 2400 | 442 | 42439738b44c3da5a92eb9db5d4a27d9536d642af0911653b799a0d5a08b5c45 |

This acceptance is complete. Do not repeat it merely because a chat restarts.
