# Recovery checkpoint: agent visual inspection

Branch: `feature/live-agent-visual-inspection`.
Stacked parent: `c35916d4badf5bdac815417d88cdffba56b537b7` on
`feature/live-section-roi-from-picks` (draft PR #21).
Accepted main: `2b385820ecfcb84d79aaf59ad5965e748f961466`.

## Status

Initial recovery/planning checkpoint only. Implementation and new tests are not
complete. Resolve actual remote HEAD and read subsequent commits before resuming.
Do not recreate this branch or create retry/recovery/numbered branches. Do not merge
PR #21 or the new stacked PR. Preserve unexpected work; never reset, clean, force
push or delete retained branches. Commit coherent increments and verify the returned
SHA and remote branch persistence before continuing.

The desired primary UX is agent-controlled camera inspection plus structured
geometry and simple semantic questions, not precise user vertex picking. Preserve
0.15.7 as the fallback. Do not repeat the passed safe manual fixture. Its remaining
GUI cases are still BLOCKED/unrun. No fan ROI call was performed.

Read `docs/RETAINED_0_15_7_CHECKPOINT.md`, the spatial-intent contract, and both
Windows spatial-intent reports for unchanged accepted evidence and safety limits.

## Planned narrow increment

CloudCompare v2.13.2 exposes ccViewportParameters copy/set, custom view directions,
rotation, camera translation and focal distance. The bridge currently exposes only
preset views and PNG capture, so recoverable deterministic navigation requires a
native addition. Intended milestone: Python 0.16.0, qMCPBridge 0.13.0 / revision 9.
No version or behavior change has happened at this checkpoint.

Add bounded saved-camera state, navigation, capture provenance, bounded inspection,
semantic proposals, and explicit answer binding/staleness. Vision is context only;
numerical geometry remains dimensional evidence. No new numerical reconstruction,
ROI/scale/quality search, broad CAD IR or Fusion automation. Semantic acceptance
cannot override existing numerical refusals. Keep source, selection and unrelated
overlays untouched; restoration failures must be explicit, not hidden.

## Environment

Sandbox GitHub DNS is unavailable. Recovered exact parent source from successful
Actions run 36373820422 artifact 10949957563; local tracked tree hash verified as
4521f1df9d4fa6ef389428efbf1600df0faa6529. Dependency wheels recovered from retained
bootstrap run 36367435852 artifact 10946969592. Local environment setup is in progress;
no new regression result yet. Use tracked-source artifacts for recovery, not branch
recreation. Keep local/unit, compiled policy, replay, actual MCP stdio, GitHub CI,
native plugin build and visible Windows/CloudCompare claims separate.
