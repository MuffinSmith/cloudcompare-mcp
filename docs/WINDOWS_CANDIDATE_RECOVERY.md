# Focused Windows retest: move the same foreign cloud out, then clear

This is the remaining recovery case for issue #7, not another full acceptance run.
Use the existing `feature/live-feature-candidates-overlays` branch. Preserve local
work; do not reset, clean, force-push, create another branch, or modify product code.

## What must remain unchanged

The Windows-tested runtime baseline is
`fc51824d9edf7328614653c57bf3644c1db02769`. A tests/documentation-only follow-up does
not require rebuilding the DLL, reinstalling the package, or repeating the passed
synthetic/fan workflows. Verify this before applying the reduced scope:

```powershell
git diff --exit-code fc51824d9edf7328614653c57bf3644c1db02769 HEAD -- src cloudcompare-plugin pyproject.toml scripts
```

A nonzero result, changed runtime configuration, or an unverified DLL requires
review before carrying forward earlier results. Use the same configured Python
and DLL. The reported Windows-tested DLL SHA-256 is
`53F3E39F77A5455A64C700EDDAD3B2C8082998E34BA90777E03E361C6A53EB74`.
Verify the responding process/module and the hardened `fit_overlays` flags. The
new policy tests can be run separately in the existing MSVC developer environment:

```powershell
python -m pytest -q tests/test_native_overlay_safety.py
```

There are 16 policy cases. Four additional cases exercise the actual policy header
across simulated move-out, nested move-out, partial recovery and no-op/copy cases.
Their scene nodes are test doubles: they are NOT Windows live-host evidence.

## Permission and minimal setup

This is the separate disposable Windows test system. The user authorizes closing
CloudCompare **without saving**, discarding test changes and reopening a working
copy. This does not authorize discarding repository work or unrelated files.

Use a small disposable cloud, not the multi-million-point fan. Reuse the previous
450-point unrelated test-cloud fixture where practical. Existing verified source
and fixture paths may be read from the local evidence directory recorded in the prior Windows report for issue
#7. Keep any new reports, exports and test fixtures outside Git.

Do not use saved/reloaded overlay objects as the active managed group: the previous
saved-session test intentionally established that a new runtime does not own them.
Create a fresh managed overlay group in the current process, referencing a separate
small source cloud. Create a disposable clone of the unrelated small cloud inside
that managed group, as in the already-passed foreign-cloud refusal test. Only this
initial test setup creates a clone; the recovery step must move that SAME object.

Create one ordinary empty top-level group, outside the managed group, with a unique
name such as `MCP Recovery Destination <run suffix>`. Record the current integer IDs
for the source, foreign cloud, managed group and destination. Names only locate UI
rows; the structured entity IDs establish identity. Do not reuse historical IDs.

Record the baseline tree, foreign-cloud records or deterministic export digest,
and source integrity data. Use the prior tester's existing integrity helpers where
available; do not infer unchanged points from bounds alone.

## Before the move

Confirm all of the following in the SAME running process:

1. The foreign cloud is a descendant of the active managed group.
2. `fit.overlay.status` returns `active: true` and `clear_safe: false`.
3. `fit.overlay.clear` refuses; creation also refuses; tree and source data remain
   unchanged. These are controlled errors, not reasons to weaken the guard.

The read-only `scene.list` with `recursive: true` and overlay status provide the
required hierarchy evidence. Store full responses locally, not in chat context.

## Perform one real hierarchy move

Move only the foreign cloud to the ordinary destination group. Do not clone,
export/reload, delete or replace it. Do not restart CloudCompare between this move
and the retry: saved-session safety is a separate, already-tested behavior.

For GUI input, select only the foreign cloud, then drag its row/name onto the
**destination group's row/name**, not its checkbox or an ambiguous insertion line.
Use move semantics (no Ctrl-copy modifier). CloudCompare 2.13.2's host implementation
accepts `Qt::MoveAction`, resolves the new parent from the drop target, and rejects
leaf destinations and some dependent geometry. See the upstream source:

https://github.com/CloudCompare/CloudCompare/blob/v2.13.2/qCC/db_tree/ccDBRoot.cpp

This source inspection does not establish why the previous automated drag failed.
A standalone test cloud and an explicit ordinary group minimize target ambiguity.

Make at most one carefully targeted automated attempt, then inspect `scene.list`.
If the parent did not change, stop the automation loop and ask the user for this
single manual gesture, with the exact two visible names. Prepare and reveal both
rows before asking. The user may do the drag; the assistant then checks IDs and
runs the assertions. Do not repeatedly try unverified coordinates, inject code
into the host, add a new product mutation API, or unlock dependent mesh vertices.

## After the move, before clearing

Verify from a new structured tree response that:

- The SAME foreign-cloud ID is a direct child of the destination group and no
  longer a descendant of the managed group.
- The destination is still outside the managed group; the managed group ID and
  current process are unchanged.
- The foreign cloud's points/attributes, counts and shift/scale are unchanged.
- Source clouds and all other intended scene state remain unchanged. The expected
  parent/child relationship change is not an integrity failure. GUI selection
  changes must be recorded or normalized before comparing snapshots.
- Overlay status still reports `active: true`, the SAME group ID, and now
  `clear_safe: true`.

`active: false` is NOT evidence of recovery. It could mean the group was deleted,
unloaded or no longer owned. A new clone elsewhere is NOT the same-cloud test.
If another foreign descendant remains, clear must stay blocked until it is moved
out without deletion; do not silently ignore it.

## Retry and finish

Call `fit.overlay.clear`. Require `cleared: true`, then verify that the managed
group and its overlays are gone, but the SAME foreign cloud remains under the
ordinary destination with unchanged data. The source remains unchanged. Call clear
again and verify the idempotent no-op without scene mutation.

Do not delete the foreign cloud to make the result pass. Leave the destination and
foreign cloud visible as evidence, or close the disposable program without saving
after evidence is recorded. A failure must preserve the evidence and remain
FAIL/BLOCKED; do not perform speculative cleanup.

Report only this retest: runtime baseline SHA, checkout SHA, process and DLL hash,
source/foreign/destination/managed IDs, before/after parent IDs, status transition,
retry-clear result, surviving foreign-cloud data comparison, and evidence path.
Separate a passed manual GUI gesture from an untested automated-drag capability.

Update issue #7 only with actual results. Keep it open while blocked. Do not merge
main on partial acceptance, and do not label the original Windows report a full
PASS retroactively. A successful new check completes its outstanding recovery gap;
other results remain attributed to their original tested runtime and report.
