# Accepted main checkpoint — CloudCompare MCP 0.16.3

Current accepted branch: `main`.

Accepted merge sequence:
- PR #21 merged to main as `17803b5e94959bc7e5c3982a732ca7c36ecd4331`;
- PR #22 merged to main as `b1b04a9b86a4b24812026076be912d7a477af9d7`.

There are no open pull requests after this acceptance. Historical feature branches and
acceptance reports are retained as recovery/provenance history; do not resume them by
default. New work starts from the current `main` unless repository state has legitimately
advanced.

## Accepted runtime

- Python package: **0.16.3**
- Native bridge: **qMCPBridge 0.13.2 / workflow revision 9**
- Windows-tested native DLL SHA256:
  `88D0B067D535BAFE026525D0A1CEC61836F7B91D50E870F455B2F537E2D2A154`
- Exact 0.16.3 runtime checkpoint:
  `ae03248065feea07e80f8f956cfd36ce6f4ac8f6`

Internal validation at the accepted runtime:
- 1,449 Python tests passed, zero skips;
- 238 focused camera/inspection tests by source count;
- 37/37 native Qt camera-guard helper tests passed;
- actual qMCPBridge build against CloudCompare 2.13.2 passed;
- compileall and diff/whitespace checks passed.

## Visible Windows acceptance

The focused Windows 0.16.3 acceptance at branch head
`ca676ff0fc09f54c1e5ba381a3ce44ce92de7d11` passed:

- exact source/runtime identity;
- noneditable Python 0.16.3 installation with 34/34 module hashes;
- full 1,449/1,449 Python suite;
- focused 238/238 camera/inspection suite;
- two target-ROI stdio tests separately;
- disposable release-boundary fixture;
- authorized fan camera-only preflight;
- one bounded real fan inspection;
- exact guarded restore while camera ownership was still held;
- release back to the original CloudCompare automatic-pivot mode;
- source/scene metadata, empty selection and fit-overlay preservation checks.

The real fan inspection sampled 1,024 deterministic points from 406,276 matches,
captured top/front/isometric PNGs and ran fixed-threshold plane/cylinder discovery at
0.15 global native units. Both discovery passes returned zero numerical candidates.
No parameter was tuned to manufacture a result, and no unsupported semantic question
was asked. Human semantic confirmation therefore remained pending. This is an honest
geometry-discovery limitation, not a camera/interaction failure.

The 0.16.3 camera ownership model is accepted:
- exact protected state remains mandatory through guarded restore;
- release ends agent ownership and returns the user's original host control mode;
- post-release CloudCompare/human camera motion is evidence, not a reason for a second
  restore;
- there is no tolerance widening, sleep-until-stable loop, stale-guard refresh/retry,
  or forced second restore.

Read the retained Windows reports and `docs/AUTO_PIVOT_RECOVERY.md` for historical
details when diagnosing regressions.

## Using the tool on a new scan

A new scan is a new source context. Do not reuse fan-specific entity IDs, process IDs,
ports, bounds, fingerprints, source frame, or the fan's 0.15 threshold without new
independent justification.

Recommended first pass:

1. Verify the file/source identity and preserve the original geometry.
2. Summarize the visible scene and rediscover the intended source cloud explicitly.
3. Record point count, global shift/scale, bounds and any pending transforms.
4. Save the baseline camera with automatic-pivot suspension for owned inspection.
5. Use a small bounded set of useful views and real viewport captures.
6. Measure point spacing/noise or other independent evidence before declaring any
   fitting threshold for the new scan.
7. Run bounded structured geometry discovery with fixed declared parameters.
8. Review actual PNGs plus numerical candidates.
9. Ask the human only simple semantic questions supported by actual candidate evidence.
10. Bind explicit yes/no/unsure answers to proposal fingerprints and preserve evidence.
11. Restore while ownership is held, release, and preserve any post-release host motion.

Precise point picking remains a provenance-preserving fallback, not the primary UX.

## Next development direction if the new scan exposes the same zero-candidate issue

Do not tune thresholds repeatedly until a fit appears. The next coherent feature should
improve candidate discovery by using deterministic spatial/local neighborhoods or
bounded region partitioning so manufactured planes/cylinders receive adequate local
sample density. Keep the same separation:

- viewport/vision for semantic context;
- structured geometry for dimensions and fit evidence;
- human answers for semantic/manufacturing intent.

Any new development branch should start from current `main`, use small recoverable
commits, keep AGENTS.md current, verify each remote SHA, and preserve the established
camera/source safety contracts.

Do not jump directly to broad CAD IR/Fusion construction solely because camera
inspection is accepted. First obtain trustworthy geometric candidates and semantic
intent on the current/new scan.

## Recovery discipline

Before writing after any chat/stream failure, inspect actual `main`, recent commits,
open PRs/issues, CI and this file. Preserve unexpected work. Never reset, clean,
force-push, delete/recreate retained branches or invent retry/recovery/numbered branches
because a conversation restarted.
