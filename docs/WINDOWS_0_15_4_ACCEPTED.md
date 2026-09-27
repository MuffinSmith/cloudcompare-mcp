# Accepted Windows 0.15.4 result

The user supplied this focused acceptance summary on 2026-09-27 and explicitly
authorized merging accepted work and continuing. PR #18 merged at
`045e6d2508ab78ee31ffbac8ce7b9c11f1fcfc03`. The retained feature branch is
`feature/live-cad-section-target-isolation`; exact tested HEAD is
`4b5dfe7026f8166c0102d763a9b60e9048686996`. Pre-merge accepted main is
`0201cdd46381e0c79c05b33ee9de48851a18b877`.

This records the supplied report, not a new independent Windows rerun. The full
report with per-case hashes, fingerprints, bounds and evidence links was mentioned
but not attached to this continuation. Those details are not invented here.

## PASS: accepted product and safety gates

- Detached exact checkout, isolated Python0.15.4, native source diff empty.
- Final-head CI successful. Windows installed suite749 passed plus all16 MSVC
  policy tests passed; five target modules139 passed; compileall/diff checks passed.
- All14 PLY hashes and point counts verified. All four target tools listed through
  actual MCP stdio. Transformed snapshot reconstructed with the bridge unavailable.
- All14 fixtures exercised through the temporary stdio server and visible
  CloudCompare2.13.2/qMCPBridge0.12.0 revision8 in PID14312.
- Explicit target/layer selection, N=3600/T=2400/L=1200 accounting, stale tokens,
  truncation, unsafe targets and alternating-thick downstream layer refusal passed.

No reproducible product defect was found. The final-head CI run36356915539 was
independently checked again before merging: successful package installation,
complete pytest, compileall and diff-check steps. The prior identical-runtime/test
CI36356607178 reported765 passed, zero skips. No DLL rebuild was performed or needed.

## BLOCKED: bounded real fan (not failed)

The one complete slab had5605 points and19 candidates. All5605 points remained
accounted for and every candidate was blocked. No target was selected and no
profile attempted. Never turn this into a pass by raising limits, dropping clutter,
choosing depth signs or searching parameters until reconstruction looks convenient.

## Coverage limits retained

Actual transformed imports used global shift
`[-100000000,199999000,-299999000]` and scale1. Acquired global coordinates were
not shifted twice. Host quantization removed one narrow-bridge diagnostic flag,
but the erosion refusal remained. Do not claim identical diagnostic flags across
host quantization, or treat this as an accepted bypass of ambiguity guards.

Whole-source integrity coverage is metadata-only. No independent full-cloud
geometry/attribute comparison and no real-host nonunit-scale source were tested.
Snapshot/replay tests do not upgrade those claims. Historical source IDs and PID
are evidence for this run, not IDs to reuse without resolving the current scene.

This acceptance is complete. The retained `WINDOWS_SECTION_TARGET_ACCEPTANCE.md`
is historical procedure, not an instruction to repeat this gate in every new chat.
