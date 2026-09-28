# Visual inspection increment progress

Stacked branch `feature/live-agent-visual-inspection`, parent c35916d4badf5bdac815417d88cdffba56b537b7. Do not merge either PR. Read this file alongside AGENTS.md.

First code checkpoint adds shared native camera math and 31 executable C++ policy tests. All 31 passed locally under g++ through Python 3.13.5/pytest 9.0.2. These test directions, proper rotation matrices, positive/negative orbit and inverse, finite bounds, large coordinates, pan and zoom limits. They do not constitute Qt/native plugin compilation or visible-host acceptance.

The dispatcher, existing native source integration, camera-bound capture, Python inspection and confirmation contracts are being implemented; they are NOT yet persisted at this checkpoint. Native/Python versions have not yet changed on this remote head. Resume the same branch; do not recreate it. Preserve the fallback branch and its partial Windows evidence.
