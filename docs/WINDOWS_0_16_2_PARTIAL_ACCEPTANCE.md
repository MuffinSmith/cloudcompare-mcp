# Windows 0.16.2 acceptance — exact restore PASS, post-release host motion BLOCKED old policy

This preserves the user-reported Windows retest of exact branch HEAD
`728e37214c591187d9cb06af573f091011f940ed`. The raw report/evidence remains on the
Windows machine; this document records the reported observations without claiming an
independent container reproduction.

## Gate results

| Gate | Result |
| --- | --- |
| Installed Python 0.16.2, native 0.13.2 / revision 9, capabilities | PASS |
| Complete Python suite; separate Qt tests | PASS — 1,447 Python; 37/37 Qt, zero skips |
| Disposable fixture normal automatic-pivot cycle | PASS |
| External UI re-enable probe | BLOCKED — Windows UI automation could not target the host window |
| Fan camera preflight | BLOCKED by the 0.16.2 Python policy after release |
| Fan inspection / human confirmation | NOT RUN; confirmation pending |

The rebuilt qMCPBridge 0.13.2 DLL SHA256 was
`88D0B067D535BAFE026525D0A1CEC61836F7B91D50E870F455B2F537E2D2A154`.
The focused command produced 236 passes, not the earlier estimated 237, with zero
skips; two target-ROI stdio tests passed separately. Both exact-head push and PR CI
were reported successful. No repository change or merge occurred on Windows.

## Fan observation

The authorized fan hash and scene metadata matched before/after. Selection and fit
overlays remained empty. This does not establish complete in-memory point/normal
equality.

The bounded camera sequence reached a successful guarded restore matching the saved
baseline while the token still owned automatic-pivot suspension. No native request
refused. During `release`, qMCPBridge restored CloudCompare automatic pivot to ON.
That host behavior then moved camera-center Z and pivot Z by approximately
`0.000185967` host units and therefore changed the navigation guard. The tester did
not refresh the guard, retry, force another restore, or run fan inspection.

## Contract correction

This result establishes that 0.16.2 placed the ownership boundary one step too late.
The exact safety requirement was already met: restore matched the baseline while the
agent still owned the suspension token. `release` deliberately returns the original
CloudCompare host behavior; motion caused by restored host control (or concurrent
human navigation after that boundary) must be preserved and reported, not treated as
a failed agent restore.

Python 0.16.3 therefore keeps the exact pre-release guard as authoritative and
records post-release navigation differences without retrying, overwriting, applying
tolerances, or claiming the final host pose equals the baseline. Native qMCPBridge
0.13.2 remains unchanged.
