# Visual inspection internal review and evidence

This is internal implementation/recovery evidence, not Windows or image acceptance.
The recovered runtime/test checkpoint is
`bef9f0135e7a7c1b15cdba0d140624fb975c8418`, stacked on
`c35916d4badf5bdac815417d88cdffba56b537b7` (PR #21), not accepted main
`2b385820ecfcb84d79aaf59ad5965e748f961466`. PR #22 already existed after the
stream failure; it was recovered, not recreated. Both PRs remain draft/unmerged.

## Recovered and independently repeated validation

| Evidence | Observed result |
| --- | --- |
| Runtime push CI 36378023620 at bef9f013 | Success; Python and actual Linux native-plugin jobs. |
| Runtime PR CI 36378197862 at bef9f013 | Success. |
| Fresh CI Python 3.12.14 installed suite | 1393 passed, zero skips, 115.61 seconds. |
| Original local installed suite | 1393 passed, zero skips, 135.75 seconds. |
| Recovery repeat, installed Python 3.13.5 | 1393 passed, zero skips, 101.13 seconds. |
| Recovery focused new suite | 182 passed, zero skips, 8.31 seconds. |
| Installed Python source hashes | 34/34 match the recovered exact source. |
| Compileall | Pass for src, scripts, tests. |
| Full parent-tree whitespace check | Pass. |
| Windows DLL / visible GUI / real image interpretation / human fan answers | Unrun. |

The 182 new tests comprise 31 compiled native camera-policy cases, 59 Python
camera/PNG cases, 65 workflow/semantic/freshness cases, 17 actual MCP
schema/dispatch/installed-stdio cases and 10 deterministic fixture checks. The
retained 1211-test baseline is included in the complete 1393 result.

Nine generated PLY files are hashed before numerical use. The actual installed MCP
subprocess semantic cycle uses counted TCP replay: 44 native requests, six region
acquisitions and two replay PNGs. It is real MCP stdio, but not actual CloudCompare
query-count measurement or viewport interpretation. Shift/scale and float behavior
in replay are numerical proxies until the visible-host gate verifies actual frames.

Push CI native job 108787735746 compiled the actual plugin against CloudCompare
v2.13.2 on Linux. Python job 108787736020 installed the package before regression.
A native compile establishes neither Windows ABI compatibility nor correct visible
camera behavior. Recovered local testing used a noneditable project install with
some reused preinstalled third-party dependencies, not pristine isolation. CI used
a fresh Python install. Container GitHub/PyPI DNS was unavailable; existing source
and dependency artifacts were used, without recreating temporary helper workflows.

## Exact source and full diff review

The recovered head archive SHA256 is
`93f9a82b3d45aed7e331ff7df0b4bbc48ce7d48f825c5fb9ac1d1fafb9b43298`.
Its reconstructed Git tree is exactly
`895e7ae39998e5caf6eb7f7fa3635b5ebea129bc` (185 files), matching GitHub.
The base archive SHA256 is
`31ed0ea49c8705815976e9141cf71a82bb233b6cd400741939f69b8de3e597c8`;
its tree is `4521f1df9d4fa6ef389428efbf1600df0faa6529` (169 files).
A local bare object database was used for content-tree comparison, not a fabricated
remote checkout/history. The complete runtime parent diff has 25 changed files,
2287 insertions and 158 deletions. Documentation added after this checkpoint must
be distinguished from runtime changes, and final exact-head CI checked separately.

Reviewed changed-file groups:

- Native: CMake source registration; new qMCPCamera.h, qMCPCameraPolicy.h and
  qMCPCamera.cpp; qMCPBridge.cpp camera/capture dispatch; qMCPFusionWorkflow.cpp
  capability/version and pending-transform metadata. Candidate viewport validation
  precedes application. Captures recheck camera/window after event processing.
  Focus validates active-window source/frame. No numerical solver or source edit
  was introduced in these changes.
- Python: inspection_camera.py validation/provenance; live_inspection.py bounded
  orchestration and evidence store; inspection_tools.py seven schemas/handlers;
  server.py additive registration; pyproject.toml version. Existing discovery,
  fitting, section, ROI, target, layer and reconstruction modules are unchanged.
- Validation: five new test modules, inspection_replay.py, native camera-policy
  test harness, and generate_visual_inspection_fixtures.py. Two retained stdio test
  files change only their expected installed package version.
- Operations/docs: tests.yml adds actual native compilation and preserves source
  archives; AGENTS.md, RETAINED_0_15_7_CHECKPOINT.md and VISUAL_INSPECTION_PROGRESS.md
  record the staged work. Temporary transport helper/workflow are absent at HEAD.

## Explicit limitations retained after review

Camera-center coordinates are host-render parameters, not a global eye pose.
Restoration equality covers the documented camera parameters, not the framebuffer
or entire GUI. Current supported projection mode is preserved, not toggled. Global
focus requires a cloud frame. Native session/endpoint and reported human answers
are not authenticated identities. Camera ownership conflicts return recovery
information rather than overwriting concurrent user movement.

Source freshness covers deterministic samples, native all-match summaries and
scene/selection/overlay metadata, not all point attributes or undetected off-sample
changes. Reads are non-atomic. The service does not perform visual interpretation,
create per-inspection overlays, detect every semantic vocabulary item, or maintain
evidence IDs across restart/release. Conflicting roles are checked for shared
candidate IDs, not arbitrary spatial overlap. None of these limitations is hidden
by a passing numerical/replay test.

The remaining gate is the focused Windows native build, visible synthetic camera
and safety checks, then bounded authorized-fan inspection and actual human semantic
answers. See WINDOWS_VISUAL_INSPECTION_ACCEPTANCE.md. Do not merge either PR or
require a complete fan CAD model at this milestone.
