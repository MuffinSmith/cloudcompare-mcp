# Visual inspection CI: bounded pinned dependency checkout

## Observed failed checkpoints

Documentation head `77879285f7fd6b62521a2358d51afb30656d0c7b` passed exact-head
push run 36379584524, including Python regression and the actual native build.
Companion PR run 36379587715 passed Python but failed native job 108792388396 during
upstream CloudCompare checkout, before configure or compilation.

The log shows two connection failures to the external GitLab host used by optional
`plugins/core/Standard/qColorimetricSegmenter`, lasting approximately 134 seconds
each. This is evidence of an unnecessary checkout dependency, not a camera/compiler
defect. It does not establish the cause of the earlier ChatGPT thinking failure.

The first narrower checkout, `df1311eba718a9432664064a4e808187325fa654`, fetched
CCCoreLib successfully but omitted its nested nanoflann dependency. PR run
36380098311, native job 108793895204, therefore failed configuration at
CCCoreLib/CMakeLists.txt:138 because extern/nanoflann lacked CMakeLists.txt. This
was a CI acquisition error introduced by that first correction, not an external
network failure and not a passing build. It is retained as historical evidence.

## Corrected dependency closure

The native job checks out CloudCompare v2.13.2 without recursively fetching all
optional plugins. It explicitly initializes `libs/qCC_db/extern/CCCoreLib` and
then its `extern/nanoflann` submodule. Both HEADs must equal the exact gitlinks
recorded in their immediate parent commits. Host checkout and the combined
required-dependency fetch each have a three-minute timeout. No forced update,
recursive optional fetch, mutable dependency branch or error suppression is added.

The inspected CloudCompare tag resolved to
`49dbbb662f296c7780aae717897c85b3cb3764ed`; its CCCoreLib gitlink is
`a8ce4270dfa41d5817842447b27f36094f9dfb51`. At that exact core commit, .gitmodules
lists only extern/nanoflann and CMakeLists.txt includes it unconditionally. The
workflow resolves and verifies the nanoflann pin from that core commit rather than
substituting the dependency's current default branch.

The declared host's Standard CMake list only adds optional submodule plugins when
their CMakeLists.txt exists; optional E57 support is off by default. The full actual
`QMCP_BRIDGE_PLUGIN` configure/build target, host version, Release configuration,
dependencies and failure gates remain unchanged. Python regression is unchanged.
The new push and PR runs must establish that this dependency closure builds the
bridge; this document alone is not a build result.

These changes affect CI acquisition only, not Python/native product code, numerical
solvers, generator or test behavior. Runtime validation remains the 1393-test suite
and 182-test focused suite recorded in VISUAL_INSPECTION_REVIEW.md. Read the current
PR #22 checkpoint for exact final SHA and push/PR CI results. Preserve both failed
checkpoints; do not label them passed or substitute an older green run for the new
checkout configuration. Do not merge either PR.
