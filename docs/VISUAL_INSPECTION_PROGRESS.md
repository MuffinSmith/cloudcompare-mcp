# Visual inspection progress

Branch: feature/live-agent-visual-inspection. Existing stacked draft PR #22 is based
on feature/live-section-roi-from-picks at c35916d4badf5bdac815417d88cdffba56b537b7.
PR #21 and PR #22 remain draft/unmerged. Read AGENTS.md and actual remote refs before
resuming; a failed chat stream did not lose the implemented camera/inspection work.

Runtime checkpoint bef9f0135e7a7c1b15cdba0d140624fb975c8418 passed push CI 36378023620
and PR CI 36378197862. Push CI includes Python regression and actual qMCPBridge
compilation against CloudCompare v2.13.2 on Linux. Python is 0.16.0; native is
0.13.0 / workflow revision 9. No temporary transport helper/workflow remains.

Recovery repeated the full installed suite: 1393 passed, zero skips in 101.13 s.
Focused new suite: 182 passed in 8.31 s. All 34/34 installed Python source hashes
match. Exact head source tree and full parent diff were verified and reviewed;
compileall and parent-tree git diff --check passed. See VISUAL_INSPECTION_REVIEW.md
for test categories, replay accounting, artifact hashes and limitations.

The camera/semantic contract and focused Windows procedure are now documented in
LIVE_AGENT_VISUAL_INSPECTION.md and WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md.
Documentation completion does not itself establish new-head CI: inspect the actual
latest branch SHA and its push run; PR #22 carries the final run/result checkpoint.

Next gate after exact-head CI is the Windows DLL build and visible synthetic camera
checks, then bounded fan semantic review with actual human answers. No visible
Windows/viewport/human acceptance, fan ROI/reconstruction result, or full CAD model
is claimed. Preserve the old passed safe-pick and blocked/unrun manual evidence.
