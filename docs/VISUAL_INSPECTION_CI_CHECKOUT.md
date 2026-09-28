# Visual inspection CI: optional-submodule checkout failure

The documentation head `77879285f7fd6b62521a2358d51afb30656d0c7b` passed exact-head
push run 36379584524, including Python regression and the actual native build.
Companion PR run 36379587715 passed Python but failed native job 108792388396 during
upstream CloudCompare checkout, before configure or compilation.

The log shows two connection failures to the external GitLab host used by optional
`plugins/core/Standard/qColorimetricSegmenter`, lasting approximately 134 seconds
each. This is evidence of an unnecessary checkout dependency, not a camera/compiler
defect. It does not establish the cause of the earlier ChatGPT thinking failure.

## Narrow correction

The native job now checks out CloudCompare v2.13.2 without recursively fetching all
optional plugins. It explicitly initializes only `libs/qCC_db/extern/CCCoreLib` and
checks that its HEAD equals the exact gitlink recorded in the host commit. Host and
required-submodule fetch steps each have a three-minute timeout. No forced update,
recursive optional fetch, mutable dependency branch or error suppression is added.

The declared host's Standard CMake list only adds optional submodule plugins when
their CMakeLists.txt exists; optional E57 support is off by default. The full actual
`QMCP_BRIDGE_PLUGIN` configure/build target, host version, Release configuration,
dependencies and failure gates remain unchanged. Python regression is unchanged.
The new CI run must establish that this narrower checkout still builds the bridge;
this document alone is not a build result.

This change affects CI acquisition only, not Python/native product code, numerical
solvers, generator or test behavior. Runtime validation remains the 1393-test suite
and 182-test focused suite recorded in VISUAL_INSPECTION_REVIEW.md. Read the current
PR #22 checkpoint for exact final SHA and push/PR CI results. Preserve the failed
run as historical evidence; do not label it passed or substitute an older green run
for the new checkout configuration. Do not merge either PR.
