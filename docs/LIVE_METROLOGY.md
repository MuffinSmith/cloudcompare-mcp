# Live interactive metrology

Version 0.7.0 adds the first interactive metrology layer to qMCPBridge.

The design goal is to let an assistant operate the visible CloudCompare viewport,
capture exact geometry picks, inspect point attributes, and make simple measurements
without modifying scan geometry.

## Interactive picking

`start_live_picking` registers a CloudCompare picking listener on the active 3D
viewport. The caller can optionally:

- stop automatically after a chosen number of accepted picks
- restrict accepted picks to a list of entity IDs
- request exclusive use of CloudCompare's picking hub

The picking session records point-cloud points and mesh-triangle picks. Each pick
contains:

- pick index within the current session
- source entity ID/name/type
- CloudCompare item index
- screen click coordinates
- native-local 3D position
- CloudCompare global 3D position
- global shift and scale where applicable
- point RGB, normal and scalar-field values for real point-cloud points
- triangle index and barycentric coordinates for mesh picks

`get_live_picks` can be called while picking is active. `clear_live_picks`
clears the captured list without leaving picking mode. `stop_live_picking`
unregisters the listener and returns the final pick list.

A session also auto-stops when `max_picks` is reached.

## Exact point inspection

`inspect_live_point` reads one standalone point-cloud point by zero-based point
index and returns the same native/global position and attribute information used
for interactive point picks.

This is useful for repeatable tests and for inspecting a point after a prior pick
has revealed its entity/index.

## Measurements

`measure_live_picked_distance` measures the Euclidean distance between two
captured picks using their CloudCompare global coordinates. It also returns:

- XYZ delta
- absolute XYZ delta
- XY distance

By default it uses the two latest picks; explicit session pick indexes can be
supplied.

`measure_live_picked_angle` measures the three-point A-B-C angle, with B as the
vertex. It returns the angle in degrees/radians and both leg lengths. By default
it uses the three latest picks.

## Units

CloudCompare coordinates are still unit-neutral at the bridge layer. Distances are
reported in native coordinate units. The bridge does not silently claim
millimeters, inches or meters.

## Safety

Interactive metrology is read-only with respect to scan geometry:

- picking registers only a listener with CloudCompare's picking hub
- no labels, markers or result geometry are inserted into the DB tree
- point inspection reads source arrays only
- distance/angle calculations operate on stored pick coordinates

qMCPBridge explicitly stops any active metrology listener when the plugin detaches
from the application, so closing/restarting CloudCompare during a test should not
leave persistent picking state.

## Current limits

This first layer intentionally does not yet create persistent measurement labels,
fit primitives, or generate sections.

Planned next layers after native acceptance:

- optional visible non-destructive pick/measurement overlays
- plane fitting
- circle/hole fitting
- cylinder/shaft fitting
- cross-section extraction and dimensional analysis
