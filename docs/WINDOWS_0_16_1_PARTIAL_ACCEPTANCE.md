# Windows 0.16.1 acceptance — synthetic PASS, fan auto-pivot BLOCKED

This file preserves the user-reported visible Windows acceptance of exact branch
HEAD `0be16cf8709b77f562744c19d26895717466a57c`. It is evidence from the Windows
machine, not a test executed in the development container.

## Gate results

| Gate | Result |
| --- | --- |
| Exact branch, installation and CI | PASS |
| Installed regression | PASS — 1,441 Python tests and 230 focused tests, zero skips; 35/35 separate Qt CTests |
| Visible synthetic camera guard | PASS |
| Fan camera preflight | BLOCKED by a protected camera change after focus |
| Fan inspection / human confirmation | BLOCKED — no inspection, proposal, question, answer or confirmation |

PR #21 and stacked PR #22 remained draft/unmerged and the worktree remained clean.
Exact-head push CI 36392958583 and PR integration CI 36392963324 were reported
successful. Python 0.16.1 was installed noneditably with 34/34 module hashes matching.
The isolated Release/x64 qMCPBridge 0.13.1 DLL SHA256 was
`1EBC15F39A9764E32E44DC54CDF5597EFF8479E7D55D5F15A8315E855FAD31FC`.
The visible acceptance host was CloudCompare 2.13.2, PID 3368, port 8767; IDs are
historical and must be rediscovered on later runs.

## Synthetic guard acceptance

On a disposable 144-point fixture, global default point/line sizes changed from 1/1
to 2/2. The full camera fingerprint changed while `cc-camera-guard-v1` remained equal.
A direct installed Python/native guarded capture retained the new styling. Public MCP
stdio captures and bounded inspection also passed. Modern restoration preserved the
style (`restored_guard_equal=true`, `restored_equal=false`), while the legacy strict
full guard refused the same style drift.

A separate actual camera move caused stale-guard movement and restore to refuse at
`movement.precondition`, preserving the intervening pose. Six real synthetic PNGs
were retained. Replay was not counted as acceptance evidence.

## Fan failure

Authorized fan SHA256 matched:
`79ca5f9be2b80446d984bf7300fa9b9a5cda3466b2b3ab98f40fc4b61233fcc0`.

The visible cloud contained 406,276 points, global shift `[0,0,0]`, scale `1`, with
physical units still unknown. Baseline save and guarded focus succeeded. Before the
next declared look, the new diagnostics recorded a real protected camera transition:

- camera-center Z: `628.4272923203682` -> `693.8733201556884`
- pivot Y: `-4.380668640136719` -> `-5.092193828031531`
- pivot Z: `134.0451889038086` -> `199.49121673912876`
- focal distance: preserved apart from floating-point representation

The look correctly refused at `movement.precondition`. The tester stopped, read the
current camera once, released the owned token and did not force restoration or run
fan fitting. Source count/frame, empty selection and absence of temporary overlays
were checked. There were no unrelated overlays in the isolated hosts to exercise
preservation against. No human semantic question was asked or answered; confirmation
remained pending.

Raw evidence was reported outside Git at:
`C:/Users/Admin/Documents/CloudCompare/mcp-live-test/acceptance-0161-0be16cf-20260928/`.

## Root-cause evidence from CloudCompare 2.13.2 source

The transition shape matches CloudCompare's default automatic center-pivot behavior,
not style drift. `ccGLWindowInterface` initializes `m_autoPickPivotAtCenter` enabled.
During rendering, when a center-screen pivot candidate exists, it calls
`setPivotPoint(pivot, true, false)`. The `true` requests automatic camera-position
update along with the pivot. Thus a redraw after our successful focus can translate
pivot and camera together while preserving focal distance, invalidating the exact
navigation guard before the next request.

This finding does not justify weakening pose guards. The recovery must instead own a
bounded suspension of CloudCompare automatic pivot while an inspection save token is
active, then restore the original host mode with explicit post-release evidence.
