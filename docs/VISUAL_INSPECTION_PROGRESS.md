# Visual inspection progress

Read AGENTS.md for the current checkpoint and actual remote HEAD before resuming.

- Stacked parent: c35916d4badf5bdac815417d88cdffba56b537b7; do not merge PR #21.
- Native camera/capture checkpoint: 4b84b3a61a856bef312b73728820c2276c2a11ed.
- Exact native-checkpoint CI 36376174049 succeeded, including the actual qMCPBridge
  build against CloudCompare 2.13.2 on Linux. Local full suite: 1242 passed.
- New Python camera/inspection/semantic core now persisted. Local focused suite:
  182 passed. New tests/generator and server registration are being persisted next;
  do not interpret this as final exact-head validation.
- No new visible Windows/CloudCompare, actual image interpretation or fan test result.
- Temporary source helper must be removed along with its workflow before the final
  checkpoint. Workflow edits require the connector, not the Actions token.
