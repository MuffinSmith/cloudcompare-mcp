# Visual inspection progress

Read AGENTS.md and actual remote HEAD before resuming. This is a stacked draft
increment, not Windows/CloudCompare acceptance.

Native checkpoint 4b84b3a61a856bef312b73728820c2276c2a11ed passed CI run 36376174049,
including the real qMCPBridge build against CloudCompare 2.13.2 on Linux. The Python
0.16.0 tools and extra active-window focus guard were subsequently integrated at
e5070fdaf0fc87a24e0f04750d1e750e264a6287. Seven tools are registered. The temporary
source-transport helper and workflow have now been removed.

All new tests/generator are now persisted. Local installed regression: 1393 passed,
zero skips in 135.75 seconds. Focused new suite: 182 passed in 11.46 seconds,
comprising 31 compiled C++ camera policy, 59 Python camera/PNG, 65 bounded workflow
and semantic/freshness tests, 17 actual schema/dispatch/installed MCP stdio tests,
and 10 fixture checks (nine exact-hashed PLY files plus overwrite protection).
The counted installed stdio semantic cycle made 44 replay native calls, including
six region acquisitions and two PNG captures. This is replay accounting, not a
measured real CloudCompare host-query count or viewport-image interpretation.

Complete installed regression, compileall and local diff whitespace checks passed.
Final contract docs, full parent/native diff review, draft PR and final exact-head
GitHub CI remain the next checkpoint. No visible Windows/CloudCompare, actual image
interpretation or fan result is claimed. Keep PR #21 and the new branch unmerged.
