# Technical Debt

## `hold()` never noticed a browser disconnect while idle -- fixed 2026-08-02

Found live-testing the new `Axes`/`Arrow` rendering: kill the browser tab
while sitting in a plain `env.hold()` (nothing actively `step()`-ing), and
nothing happens -- no reaction even after 20+ seconds, requiring a manual
^C. This despite `hold()`'s own disconnect-timeout mechanism (PR #71/#75,
polling `SwiftSocket.USERS`) already existing and working correctly in
principle.

Root cause: `serve()`'s per-connection loop is `while self.run(): message
= await self.producer()`, and `producer()` was a plain blocking
`self.outq.get()` inside an `async def`. During an idle `hold()` nothing
is ever queued, so `producer()` never returns -- meaning `serve()` never
reaches its `except ConnectionClosed`/`finally: self.USERS.discard(...)`,
so `USERS` never gets cleaned up, so `hold()`'s `len(self.socket.USERS) >
0` check never sees it as empty. The disconnect-polling mechanism was
correct; it just never got fed the information it needed, for the single
most common usage pattern (add shapes, then just `hold()`).

**Fixed in two steps, both needed:**
1. `producer()` now does `await asyncio.to_thread(self.outq.get)` instead
   of blocking directly -- keeps the event loop itself responsive. Alone,
   this fixes nothing about *this* bug (nothing is watching the
   connection for closure regardless of whether the loop is blocked or
   not) -- confirmed by testing: still hung past 2 minutes with only this
   change.
2. `serve()`'s loop now races `producer()` against `websocket.
   wait_closed()` (`asyncio.wait(..., return_when=FIRST_COMPLETED)`) --
   whichever resolves first wins. A disconnect now gets noticed even
   while producer() is idle, not just the next time `serve()` happens to
   actively send/recv.

**A third, subtler issue found verifying the fix**: cancelling
`producer_task` when `wait_closed()` wins doesn't stop the underlying
blocking `self.outq.get()` call already running on its own
`asyncio.to_thread()` worker -- `queue.Queue` has no cancellation hook.
Left alone, that thread sits blocked forever and, since `to_thread()`'s
workers are deliberately non-daemon (stdlib default), keeps the whole
Python process alive indefinitely even after the script has otherwise
finished -- caught because the repro script never exited after `hold()`
returned and printed its result. Fixed by pushing a throwaway sentinel
into `outq` right before cancelling, unblocking the orphaned `.get()` the
same way a real message would.

Verified via a real (non-mocked) repro: a scripted client connects, waits
past `add_shape()`, then disconnects with nothing ever queued -- `hold()`
now returns in ~8s (vs. hanging past 2 minutes before either fix), and
the process now exits cleanly afterward. New test:
`test_swift_socket_notices_disconnect_even_while_idle`.

## `shapes.js` mesh loading: `.obj`/`.gltf`/`.glb`/`.ply` skip the local-file proxy `.dae`/`.stl` use

Found 2026-07-31, as a byproduct of checking whether `sg.Mesh()` can load
from a URL (it can't, reliably -- see below). `loadMesh()`
(`public/js/shapes.js:72`) handles mesh filenames two different ways
depending on extension:

- `.dae`/`.stl`: rewritten to `/retrieve<path>` -- swift's own backend
  HTTP route that reads an *absolute local filesystem path* off disk and
  serves the bytes back. There's a comment confirming this is the
  intended design: "Mesh filenames arrive as absolute filesystem paths
  ... not URLs".
- `.obj`/`.gltf`/`.glb`/`.ply`: **not** rewritten -- `part.filename` is
  passed straight to the three.js loader's `.load()`, which fetches it
  via the browser's own `fetch()`.

Since `fetch()` can't read an arbitrary local filesystem path, this looks
like `.obj`/`.gltf`/`.glb`/`.ply` meshes referenced by absolute local path
(the normal case -- e.g. URDF-referenced meshes from an installed
package) are currently broken for rendering, unless something not yet
traced compensates. Conversely, a real `https://...` URL would actually
work for those four formats specifically (accidental side effect of the
missing rewrite), but not for `.dae`/`.stl` (would get mangled by the
`/retrieve` prefix) and not for collision loading either -- spatialgeometry's
`Mesh._init_coal()` calls `trimesh.load(self.filename, force="mesh")`
without `allow_remote=True`, so trimesh refuses remote URLs there.

**Not fixed, not fully verified either way** -- found while answering a
question, not by reproducing the OBJ/GLTF rendering failure directly.
Worth an actual repro (add an OBJ-mesh example, confirm it fails to
render) before fixing, in case something elsewhere already compensates.

---

## `env.add(SwiftElement)` hung when `headless=True` -- fixed

Found 2026-07-27 while headlessly smoke-testing `examples/two_link_arm.py`
(handle redesign work). `Swift.add()`'s `Shape`/`Robot` branches both
checked `if not self.headless` before doing any socket round-trip, but
the `SwiftElement` branch (`Slider`/`Button`/etc.) didn't --
`self._send_socket("element", ob.to_dict())` always used the default
`expected=True`, blocking on `self.inq.get()` forever since a headless
session never runs the socket thread that would reply.

**Fixed 2026-07-29** while adding headless tests for the new
`add_ui()` method (same gate the `Shape`/`Robot` branches -- now
`add_shape()`/`add_robot()` -- already had).

Same bug, same fix, found in `remove()` right after: its final
`self._send_socket(code, idd)` had no headless gate either. Also fixed
in passing: `remove()`'s int-id branch wrote to `self.robots[idd]`, an
attribute that doesn't exist anywhere else in the class (dead/broken
since some earlier refactor) -- should have been `self.swift_objects`,
now is.

---

## `phys.cpp` still uses raw CPython C API + setuptools.Extension, not nanobind

Unlike RTB's `fknm`/`frne` and spatialgeometry's `scene.cpp`, `phys.cpp`
(the `step_v`/`step_shape` physics extension) was never ported to
nanobind + scikit-build-core/CMake — it's still built via
`setuptools.Extension` in `setup.py`, with `PyArg_ParseTuple`/
`PyMethodDef`/`PyModuleDef` raw CPython API calls.

Discussed 2026-07-26: this is lower priority than the other two ports
were, because the reasons *they* needed it don't really apply here —
`phys.cpp` is just two stateless numerical functions operating
in-place on numpy array data (`PyArray_DATA`), with no persistent C++
objects or ownership to get wrong, and minimal boilerplate already.
It also already has a working pure-Python fallback
(`_step_v_py`/`_step_shape_py` in `Swift.py`, same facade pattern as
RTB's `fknm`), so it already degrades gracefully without the compiled
extension — including, presumably, under Pyodide/JupyterLite, without
needing a WASM-compatible build of `phys.cpp` at all.

**Proposed fix (low priority):** port to nanobind + scikit-build-core
for build-tooling consistency with `fknm`/`frne`/`scene_nb` across the
three repos — not because it fixes a real bug, just uniformity. Not
worth doing unless/until the other, actually-motivated tech-debt items
in this file are cleared first.

---

## Vendored Eigen (3.4.0, Aug 2021), untrimmed

`swift/core/Eigen/` vendors Eigen 3.4.0 in full (337 files) for
`phys.cpp` (the `step_v`/`step_shape` physics C extension). Latest
Eigen is 5.0.0 (Sept 2025) — a major version gap.

`spatialgeometry`'s vendored Eigen copy was trimmed 337 → 175 files
during its Coal migration (2026-07), since that code only needs
`Matrix4d`/`Vector4d`/`Map`/basic multiply — see
`spatialgeometry/tech-debt.md`. `phys.cpp`'s actual Eigen usage hasn't
been audited to see if the same trim applies; likely does, given
`step_v`/`step_shape`'s job (joint-limit clipping, small
rotation/cross-product math) doesn't obviously need anything beyond
Core. Not attempted this session. A version bump (3.4.0 → 5.0.0) is a
separate, higher-risk piece of work — see the RTB and spatialgeometry
tech-debt files for the const-correctness/CMake caveats that apply
equally here.

---

## Robot/Shape "instance handle" redesign (animation-loop API)

### Background

Discussed 2026-07-26 while planning the Swift frontend rebuild's
successor Python API. The current animation-loop pattern —
`env.add(robot)`, then mutate `robot.q` directly and call `env.step()`
in a loop — makes `roboticstoolbox.Robot` carry live simulation state
(`.q`, and transitively `SceneNode`/`_propogate_scene_tree()` world-
transform bookkeeping), which is exactly the drift
`desiderata.md` (RTB repo) already documents as unwanted ("Stateless
over stateful... no internal state arrays such as a persistent `.q`").

### Direction agreed (not yet implemented)

`env.add()` should return a lightweight, Swift-owned instance handle
that carries the live per-simulation state (`q`, plausibly `base`/
`tool`) instead of the robot model itself carrying it. Both a Shape
handle and a Robot handle satisfy a shared minimal contract — something
like `part_poses() -> list[SE3]` — trivial for a Shape (its own pose,
one part), computed via *pure* FK (`fkine`/`fkine_all(q)`, not
`SceneNode`) for a Robot (N parts, one per link/gripper geometry).
Proposed as a `typing.Protocol` owned by `swift` itself, not a shared
base class, since `Robot` (roboticstoolbox) and `Shape`
(spatialgeometry) are unrelated classes from separate packages.

Default `env.add(robot)` holds a *reference* to the model (cheap,
common case); an opt-in `env.add(robot, clone=True)` would deep-copy
the kinematic structure for the case where one shared model needs
multiple independently-placed instances (e.g. stamping out several
copies with different `base` poses in a loop) — though if `base` also
ends up living on the handle rather than the model (open question, see
below), that specific use case may not need `clone=True` at all.

**Open, deliberately unresolved:** whether `base`/`tool` belong on the
model (part of the robot's kinematic definition — genuinely true for
some fixed-pedestal-mounted robots) or on the handle (an instance-
placement concern, like `q`) needs answering before this can be
implemented. See the matching entry in `roboticstoolbox-python`'s
`tech-debt.md` ("`Robot`/`Link` mix kinematic-model state with
scene-graph/rendering state") — the two repos' redesigns are coupled
and should land together.

**Partial progress (2026-07-26):** implemented the narrow-scope slice
of this. `Swift.py`'s per-step rendering hot path (`_draw_all()`/
`_step_robot()`) now calls RTB's new `Robot.fkine_geometry(robot.q,
robot_alpha, collision_alpha)` (added to `roboticstoolbox-python`,
verified bit-for-bit against the old `SceneNode` path including
gripper joints and base offsets) instead of `_update_link_tf()`/
`_propogate_scene_tree()` -- so the actual per-frame rendering no
longer depends on the scene-graph mutation machinery at all. Confirmed
working live (two robots + gripper fingers + a moving shape, ~90s run).

**Handle implemented (2026-07-27):** `env.add(robot)` now returns a
`RobotHandle` (`swift/Handle.py`) that owns `q`, `qd`, and
`control_mode` for that instance -- the `roboticstoolbox.Robot` passed
in stays a plain, shareable kinematic model, used functionally
(`panda.fkine(handle.q)`, `panda.jacobe(handle.q)`). `_step_robot()`/
`_draw_all()` operate on the handle; `handle.part_poses()` is the
zero-argument `SwiftPart` contract (also defined in `Handle.py`) that
calls through to `robot.fkine_geometry(handle.q, ...)`.
`examples/two_link_arm.py` demonstrates a non-RTB object (`ArmHandle`)
satisfying the same `SwiftPart` contract by hand.

Backward compatibility: mutating `robot.q`/`robot.qd`/`robot.control_mode`
directly (the old pattern, handle never touched) still works --
`RobotHandle._sync_legacy()` detects the model's state diverging from a
snapshot taken at the last sync, adopts it, and emits one
`DeprecationWarning` per handle. This is deliberately *not* a generic
RTB-wide deprecation of `Robot.q`/`Robot.qd` (those remain first-class,
heavily used elsewhere in RTB for plotting/dynamics/etc.) -- only
swift's old animation-loop reliance on them is deprecated.

Still open, deliberately out of scope for this pass: `base`/`tool`
remain on the model, not the handle (`fkine_geometry()` reads
`self.base` internally); `env.add(robot, clone=True)` for multiple
independently-placed instances of one shared model is not implemented
(though two `RobotHandle`s over one model already have independent
`q`/`qd`, so simple multi-instance cases work today, just without a
convenience clone); gripper `.q` is still read directly off the
`Gripper` object inside `fkine_geometry()`, not handle-owned; `Shape`
does not get a matching `ShapeHandle` -- unlike `Robot`, `Shape` was
never a shared model with conflated instance state, so `env.add(shape)`
still returns a plain `int` id. The two repos' redesigns remain
coupled -- see the matching entry in `roboticstoolbox-python`'s
`tech-debt.md`.

**Investigated 2026-07-29, decided not to pursue:** `_se3_to_wire()`
(`Swift.py`) uses `sm.base.r2q` (spatialmath, pure Python) to convert
each part's rotation to the wire-format quaternion, once per geometry
part per step. Looked into a C-accelerated replacement:

- `roboticstoolbox.ets.fknm.r2q()` is not just unused in RTB (grepped --
  no internal caller) but currently **broken**: its Python wrapper is
  `def r2q(R): return _c_r2q(R)`, a one-argument call, but the real
  nanobind binding requires two (`r2q(r_in, q_out)`, writing into a
  caller-supplied output array) -- calling it as documented raises
  `TypeError`. Never exercised, presumably added speculatively for
  Swift's benefit and never actually wired up or tested.
- Swift's own `swift/core/phys.cpp` already contains a byte-for-byte
  copy of the same `_r2q` C++ algorithm (line ~393), compiled into the
  shipping `phys.cpython-*.so`, but never registered in `physMethods[]`
  -- fully dead, not Python-callable today. No dependency on RTB would
  be needed to use it.
- Benchmarked the algorithm anyway (via RTB's raw `_fknm_c.r2q`, calling
  it correctly, as a stand-in for the identical swift copy): ~23x faster
  per call than `sm.base.r2q` (0.17us vs 4.0us, 200k calls, output
  verified identical for the tested input). At that cost a 15-part robot
  at 60fps spends ~3.6ms/sec total in `r2q` today -- not a measured
  bottleneck for a scene with one or two robots, but linear in
  part-count x robot-count x framerate.

**Decided against pursuing further.** Two reasons: (1) not an actual
bottleneck yet, per the above; (2) more importantly, `_r2q`'s sign-
disambiguation logic (the "transfer sign from rotation element
differences" branch, handling the standard quaternion-from-rotation-
matrix corner cases -- near-identity, near-180 degree rotations, etc.)
is exactly the kind of code that's fiddly to get right at the
boundaries, and `spatialmath.base.r2q`'s pure-Python implementation has
been revised over time to fix such corner cases. It's unclear which
version of that logic the vendored C++ copy (identical in both this
repo and RTB's `linalg.cpp`) reflects, or whether it predates fixes the
Python version has since picked up. Trusting it without a solid corner-
case test suite (near-identity rotation, 180-degree rotations about each
axis, rotations that trip each sign branch, etc., diffed numerically
against `sm.base.r2q` for every case) would risk silently reintroducing
whatever the Python side already fixed. Not worth that testing effort
for a currently-nonexistent bottleneck. If this ever needs revisiting,
start from that test suite, not from the existing C++ code.

**Follow-up check (2026-07-30):** while confirming `spatialmath.base.r2q`'s
current algorithm (Cayley's method) matches the dormant C++ copies
above -- it does, identical variable-for-variable -- found that
spatialgeometry's *own* `scene_nb.cpp` r2q (used live, every single
`_propogate_scene_tree()` call, unlike the two dormant copies above) is
a **third, different** algorithm entirely: Shepperd's method
(four-case branching on which diagonal element is largest), not
Cayley's method. That one had never been checked against the Python
reference. Verified numerically now: identity, 90/180/179.99-degree
rotations about each axis, near-identity, and two arbitrary compound
rotations -- all match `sm.base.r2q` to `1.67e-16` (float64 epsilon),
modulo the expected `q`/`-q` sign ambiguity. So the actually-live r2q in
this stack is independently confirmed correct, despite using a
different algorithm than everything else discussed above.

**Assembly API generalization (2026-07-29):** the handle described above
is no longer robot-specific. `RobotHandle` is now `AssemblyHandle`
(`swift/Handle.py`), constructed from a `pose_fn(q) -> list[SE3]`
callable plus initial `q` -- `robot=` is optional, only set (and only
then does `_sync_legacy()` do anything) when the handle wraps an actual
`rtb.Robot`. A bare assembly (no robot) defaults to `control_mode="p"`
since it has no `qlim`/joint-count to integrate `qd` against.

`Swift.add()`'s single `isinstance` if/elif tree is now four explicit
methods -- `add_shape()`, `add_ui()`, `add_assembly(fk, parts, q0=,
callback=, name=)`, `add_robot(robot, callback=, name=, ...)` -- each
returning something specific (`add_assembly`/`add_robot` both return an
`AssemblyHandle`, same class either way). `env.add()` still exists,
dispatching to these by type, kept only for backward compatibility --
new code should call the explicit method. `examples/two_link_arm.py`
now calls `add_assembly()` directly instead of hand-writing an
`ArmHandle` (the old `SwiftPart`-conformance-by-hand version is gone --
swift builds the handle for you now, for both a bare `fk` and an
`rtb.Robot`).

Two more additions land with this: a per-step **callback** --
`callback=lambda t, values: ...`, set via `add_shape()`/`add_assembly()`/
`add_robot()` or `handle.callback = ...` -- invoked each `env.step()`,
returning the new pose (shape) or `q` (assembly/robot), so a scene can
run off a plain `while True: env.step(dt)` loop with no per-step
mutation written by hand. And named UI elements (`add_ui(el,
name=...)`) push their `.value` into `env.values` on every change --
including browser-driven changes via `element.update()`, which bypasses
the `value` property setter and needed its own push call added
(`SwiftElement._notify_value_changed()`) -- available to any callback as
`values[name]`, removing the need for a `def set_x(x): ...` setter
function per slider. `env.show()` prints the current display list
(shapes/assemblies/robots/UI elements, with id and name) for debugging.

**Design idea, not started (2026-07-29): time slider / recorded playback.**
Since a per-step callback is `(t, values) -> pose_or_q`, and `env` already
owns `t`, a *pure* callback (`box_orbit`'s `orbit(t, values)`, no reference
to prior state) can be scrubbed for free -- re-evaluate it at any `t`,
correct by construction. A *stateful* one (`panda_ik_sliders`'s
`track_target`, which returns `handle.q + qd * dt`) can't: its output is a
recurrence over the assembly's entire history, not a closed-form function
of `t` alone, so jumping to an arbitrary `t` without having walked the path
gives the wrong answer.

Proposed fix, not a new mechanism: record `(t, q)` per assembly/robot
handle (and `(t, pose)` for a plain shape's callback output) as the
simulation runs forward normally -- cheap, since `q` is small and
`part_poses(q)` is already pure and cheap to re-derive for display. A time
slider then seeks/interpolates into that recording rather than
re-invoking any callback for past time. Same shape of feature as the
existing `start_recording()`/`stop_recording()` video capture, recording
state instead of pixels -- likely opt-in and bounded for the same reason
(an unbounded per-step buffer for a long interactive session isn't free).

Two things to pin down before this becomes a real design: (1) passive
scrub-and-look (safe, is exactly what recording `q` gives you) versus
scrub-back-and-*resume*-live-simulation-from-there (not generally safe --
a fancier controller could carry state beyond `handle.q` that recording
`q` alone wouldn't capture, e.g. an integrator/history term); (2) whether
recording is always-on, or explicitly started like video recording.

**Follow-up not done:** Playwright (headless browser automation) as an
automated replacement for this session's live, manual
screenshot-and-console back-and-forth debugging -- would let CI (or a
single local command) catch console errors, failed network requests,
and blank/broken renders automatically instead of needing a human to
open DevTools and describe what they see. Discussed but not installed
in this environment or wired into `swift`'s test suite.

---

## Google Colab support: not currently working, no fix planned for now

### Background

README.md claims the `vision` extra's WebRTC support "allows Swift to
be run on Google Colab." Investigated 2026-07-26, after dropping
WebRTC entirely in the frontend rebuild, by actually running
`examples/teach_swift.py` on a real Colab notebook (installing RTB/
spatialgeometry/swift from git branches, since none of the three had a
current PyPI release at the time).

Found and fixed three real, confirmed, comms-mode-independent bugs in
`SwiftRoute.py`'s Colab path (none of which were about WebRTC/video at
all):

1. `start_servers()` computed `colab_url` correctly via `eval_js`
   (Colab's JS bridge), but then fell through to the shared
   `wb.open_new_tab(url)` call -- Python's desktop `webbrowser`
   module, which tries to open a browser on the (headless, remote)
   Colab VM itself. Nothing ever navigated the user's actual browser
   to the URL.
2. The first fix (`eval_js(f'window.open("{url}")')`) hit two further
   problems: browsers commonly block a `window.open()` triggered this
   way as a popup (not a direct user click), and even with the popup
   allowed through, `eval_js` raised `MessageError: DataCloneError`
   trying to structured-clone `window.open()`'s return value (a JS
   `Window` object) back to Python -- browsers explicitly disallow
   cloning `Window`/DOM objects. Fixed by displaying a clickable HTML
   link instead (`display(HTML(...))`) -- a genuine click always
   bypasses popup blockers, and nothing round-trips through `eval_js`.
   Also extended the post-open handshake wait from 10s to 60s for
   Colab, since opening now requires the user to notice and click a
   link rather than happening automatically.
3. `SwiftServer`'s static/HTTP server used a plain, single-threaded
   `socketserver.TCPServer` -- switched to `ThreadingTCPServer`, since
   a proxying layer in front of it may hold open or make concurrent
   requests while establishing its tunnel, which a single-threaded
   server can't handle without stalling the real request.

After all three fixes, the initial request through
`google.colab.kernel.proxyPort()` still failed. Original
back-and-forth testing showed two different failure *symptoms* across
identical steps (sometimes a 404 on `favicon.ico` with the actual page
still blank, sometimes the request never completing at all -- no
status, no response headers, indistinguishable from a hang); ruled out
browser caching as the cause (tested in a private/incognito window,
same result either way).

**Update 2026-08-02 -- quantified, not just "sometimes fails."** Ran a
minimal, Swift-independent isolation test (no roboticstoolbox, no
websocket, just a bare `http.server` returning "OK" behind
`proxyPort()`, hit with 500 consecutive requests, 3s timeout each,
0.5s between attempts): **0 successes in 500 attempts** (mostly 404,
a handful of read-timeouts). Do not have a single confirmed successful
`proxyPort()` connection to point to, from any test run, on any
`browser=` mode, ever. "Unreliable"/"intermittent" as used in the
original write-up above overclaimed -- that implies occasional
success, which we have no evidence for. What we actually have evidence
for is: fails every time tried, with inconsistent failure symptoms
(pointing at Colab's proxy infrastructure rather than a deterministic
bug in this code -- see googlecolab/colabtools#4270, #3308, #4738 for
the documented pattern, though none of those are the current issue).

### A second, separate, structural bug found the same day -- NOT the root cause of the above, but real and worth fixing eventually

`public/js/main.js` hardcodes the live data connection as
`ws://localhost:${port}/` (see `comms.js`'s `WebSocketTransport`).
Only the *initial HTML page load* gets routed through
`google.colab.kernel.proxyPort()` (see `colab_url` above); the
WebSocket URL never does -- it's passed through as a query-string
port number and reconnected to literally as `localhost` on whatever
machine is running the browser. On Colab that's the user's own local
machine, not the remote VM Swift's process actually runs on, so even
a *perfectly reliable* `proxyPort()` wouldn't be enough on its own --
the initial page could load fine and the WebSocket would still try to
reach a port with nothing listening on it.

The likely fix, if this is ever revisited: also proxy the socket port
(`eval_js(f"google.colab.kernel.proxyPort({socket_port})")`) and use
the returned URL (rewritten `wss://`) instead of a hardcoded
`ws://localhost`, the same way the HTTP server URL already works --
*assuming* Colab's proxy supports the WebSocket upgrade handshake,
which is untested. **Not implemented. No fix planned right now** (see
Decision below) -- documented so a future attempt doesn't have to
rediscover it, and so "found the bug" isn't mistaken for "fixed the
bug."

### Ruled out: reviving WebRTC

An AI assistant (Gemini, consulted 2026-08-02) suggested this class of
restriction is why WebRTC support originally existed in this codebase,
and that reviving it might be worth prioritizing. Checked, not taken
on faith: (a) its cited source is about `BroadcastChannel`, a
same-page iframe-to-iframe messaging API -- unrelated to
WebSocket-to-backend connectivity, doesn't actually support the claim;
(b) per `0d122d1`'s own commit message (already on `future`, predates
this investigation), the removed WebRTC code was "an unmodified copy
of aiortc's own bundled example server (webcam capture +
cartoon/edge/rotate video transform)... genuinely webcam/mic capture
from the browser, not three.js scene streaming" -- dead demo
boilerplate, never adapted for Swift's actual pose-streaming use case,
no evidence it was ever meant to route around a Colab-specific
restriction. Not reconsidering WebRTC on this basis.

### A more promising direction, if Colab is ever revisited: `eval_js`/`register_callback` instead of a raw WebSocket

Read the actual notebook behind the Gemini citation above directly
(not just the text snippet Gemini quoted) to check what
`google.colab.output` genuinely offers, since the specific claim
didn't hold up but the general area seemed worth checking properly:

- `google.colab.output.eval_js(js)` -- blocking call from Python,
  evaluates JS "within the context of the outputframe of the current
  cell" and returns the result (resolves Promises too). Already
  proven partially reliable in this codebase's own existing Colab
  path -- it's exactly what fetches `colab_url` via `proxyPort()`
  today.
- `google.colab.output.register_callback(name, fn)` /
  `google.colab.kernel.invokeFunction()` (JS side) -- lets JS in a
  cell's outputframe call back into Python, for "trusted" outputs
  (executed within the current session).
- Both are Colab's own first-class, documented bridge specifically
  across the kernel <-> outputframe boundary -- confirmed sandboxed
  ("the output of each cell is hosted in a separate iframe sandbox")
  -- rather than a generic port-forwarding proxy never hardened for
  this kind of interactive back-and-forth.

This is architecturally more promising than trying to route the raw
WebSocket through `proxyPort()` (the fix noted above): `eval_js`/
`register_callback` are Colab's actual supported mechanism for this
exact problem, not a workaround of a mechanism built for something
else. It would mean a genuine third transport implementation --
`comms.js`'s `WebSocketTransport` already has a docstring anticipating
exactly this kind of second transport (originally imagined as
postMessage/pyodide), so this wouldn't be fighting the existing
architecture -- paired with a parallel Python-side route module using
`eval_js`/`register_callback` instead of `websockets`/`http.server`.

Open question before committing to this: `eval_js` is a blocking
round-trip through the kernel comm channel, and Swift's `step()` loop
wants up to 60Hz pose updates -- unknown whether that holds up at
that frequency without prototyping it; Colab-specific throttling of
the update rate might be necessary regardless of transport.

**Not being pursued now** -- a genuine refactor, and Colab isn't a
currently-supported target (see Decision below) -- but worth
recording as the credible direction rather than starting from zero if
this ever gets revisited.

### Decision: no Colab support for now

Not investing further here without new evidence. `launch()` now
detects Colab at the start of `start_servers()` and prints a clear
warning up front (before attempting anything, not just after a 60s
timeout) rather than letting a user hit a cold "could not connect"
after a long wait with no context. It still attempts the connection
regardless -- not a hard block -- in case Colab's infrastructure
changes, or a user wants to see the failure for themselves.

### Status

Not resolved, not currently being worked on. The three original fixes
are real, confirmed improvements worth keeping regardless (any Colab
user who does get through gets further than before), but Colab is not
a supported environment right now -- both known issues (`proxyPort()`
reliability, outside this repo's control; the un-proxied WebSocket,
inside this repo's control but unfixed) would need addressing, and
neither is planned.

### `browser="notebook"` (inline iframe) tested on Colab too -- same failure

Tested 2026-08-02 via `docs/notebooks/swift.ipynb`, using
`launch(browser="notebook")` (renders inline via `IPython.display.IFrame`)
instead of the tab-opening path. Structurally this sidesteps one whole
class of problem the tab path has to work around -- an `<iframe>` is a
normal DOM element, not a `window.open()` call, so it was never at risk
of Colab's popup blocking. Didn't help: same "Could not connect to the
Swift simulator" handshake timeout as the tab path, i.e. the initial
page load through `proxyPort()` itself didn't complete. Consistent
with the conclusion above -- the failure is in `proxyPort()` (and
separately, the un-proxied WebSocket), not in anything about *how* the
resulting URL gets opened, so tab vs iframe doesn't change the
outcome. Confirmed locally (both plain browser tab and the notebook
iframe) that the underlying code is otherwise correct.

---

## JupyterLite / Pyodide transport (not yet designed against, just not blocked)

`swift/public/js/comms.js`'s `WebSocketTransport` class deliberately
exposes a minimal `{onOpen, onMessage, onClose, send}` interface
specifically so a second transport implementation (postMessage /
BroadcastChannel, for the case where Python runs in-browser via
Pyodide and a real `localhost` socket server can't exist) could be
added later without touching `main.js`. See
`roboticstoolbox-python/SWIFT-MPL-SPLIT.md`'s Phase E for the earlier
framing of this same problem ("JupyterLite runs Python in-browser...
localhost Python server assumptions do not hold").

See also `FUTURE-NO-MICROSERVER.md` for the broader version of this
problem — replacing not just the comms channel but also the
`/retrieve/` local-filesystem asset passthrough with hosted HTTPS
delivery, with JupyterLite as one of several motivating contexts.

No design work has gone into the actual transport swap or how
`SwiftRoute.py`'s server-thread model would need to change for a
Pyodide context — this is purely "the seam exists," not "the seam has
been thought through."

---

## CI modernization not yet started

- `swift`'s test matrix is minimal (no cross-OS/Python-version coverage
  comparable to RTB's `ci.yml`).
- `.github/workflows/cibuildwheel.yml`'s publish workflow predates
  this session's work and hasn't been re-audited against it.

Not blocking anything currently, just not yet done — flagged so it
isn't forgotten once the current frontend-rebuild work is committed.

---

## `ci/python-tests` depends on an unreleased `roboticstoolbox-python` branch

`.github/workflows/python-tests.yml` originally pinned
`roboticstoolbox-python~=1.0.0` (a leftover from before swift-sim's 2.0
rewrite). That pin restricts pip to RTB 1.0.x, which in turn pins
`spatialgeometry~=1.0.0` -- an old, pre-nanobind-migration release that
*is* genuinely compiled against the legacy NumPy 1.x C-API and hard-crashes
under NumPy 2.x at import time. This looked, initially, like a NumPy-2
compatibility bug in spatialgeometry's *current* published wheel -- it
isn't; spatialgeometry 1.2.0 (current latest) is nanobind-based
(`nb::ndarray<>`) and has no NumPy ABI dependency at all (confirmed via
`otool -L` against the actual wheel: no NumPy symbols). The old pin was
just quietly forcing an old, unrelated spatialgeometry version to be
installed alongside it.

Fixing the stale pin surfaced a second, real issue: `tests/` exercises
`Robot.fkine_geometry(q)`, which doesn't exist on *any* released RTB --
it only exists on `feat/fkine-geometry`
(`petercorke/robotics-toolbox-python`, commit `8dbb44e2`, pushed
2026-08-02). `ci/python-tests` now installs RTB directly from that branch
via `pip install git+https://...@feat/fkine-geometry`, the same idea as
installing swift-sim itself from source (see the next workflow step).

**Follow-up**: once `feat/fkine-geometry` merges to RTB's `main` and a new
RTB version is released to PyPI, switch `python-tests.yml` back to a normal
version pin instead of the git branch reference.

---

## `spatialgeometry.scene._Node` nanobind leak on every Swift session -- fixed 2026-08-02

Superseded two earlier, incorrect hypotheses (both investigated and ruled
out this session): "`_fknm_c` object creation from a background thread"
(an RTB-side mechanism that doesn't actually apply here -- this repo has
no `_fknm_c` involvement at all) and "daemon thread abandoned mid-frame
at interpreter shutdown" (disproven directly: headless -- zero threads --
never leaked; a fully graceful `close()` with no interruption still
leaked; `gc.collect()` couldn't reclaim it even with `env`/`box` explicitly
deleted, ruling out a plain abandoned-thread or reference-cycle
explanation).

### Actual root cause

`SwiftServer`'s HTTP thread (`SwiftRoute.py`) called `httpd.serve_forever()`
but nothing ever called `httpd.shutdown()` -- so that thread ran for the
rest of the process's life, regardless of `close()`. `threading.Thread.run()`
only clears the arguments it was started with (`self._target`/`_args`/
`_kwargs`) *after* the target function returns -- since `serve_forever()`
never returned, the wrapping `Thread` object kept those arguments alive
forever, one of which is a bound method of the `Swift` instance itself
(`self._servers_running`, passed as `run` to both `SwiftSocket` *and*
`SwiftServer`). That single un-cleared reference kept the entire `env`
alive -- `swift_objects` (every shape ever added), and so every shape's
`_Node`, for the process's whole lifetime, regardless of whether `close()`
had been called or how gracefully.

This is not a `nanobind`/`spatialgeometry` bug -- nanobind's leak report
was accurate the whole time; the object genuinely was still alive and
reachable from a live thread's own retained call arguments, which is
exactly the case `gc` correctly refuses to collect (it isn't garbage).

Confirmed via a real (non-mocked) repro: `env.server_thread.is_alive()`
stayed `True` indefinitely after `close()` returned; `gc.get_referrers()`
on the leaked object traced straight back through `env.__dict__` to the
bound-method arguments retained by the never-finished `Thread.run()` call.

Separately, `SwiftSocket`'s own thread (the websocket side) does
terminate correctly -- `producer()`'s `self.outq.get()` is a genuine
blocking (non-`await`ed) `queue.Queue.get()` inside an `async def`, which
blocks the whole event-loop thread for however long it takes the next
`outq` item to arrive (up to the full `join(1)` timeout in the worst
case) -- a real, separate inefficiency worth fixing (e.g. a sentinel
value or switching to `asyncio.Queue`), but not the leak's cause.

### Fix

`SwiftServer` now stores `self.httpd` and exposes a `stop()` method
(`self.httpd.shutdown()`), mirroring `SwiftSocket.stop()`. `start_servers()`
now returns the actual `SwiftServer` instance (not just the wrapping
`Thread`), the same pattern already used for `SwiftSocket`. `Swift.
_stop_threads()` calls `self.server.stop()` before joining
`self.server_thread`. Verified fixed via the same repro: `_Node` no
longer appears in nanobind's leak report, `env` is reclaimed by a single
`gc.collect()` pass after `del env, box`, and both threads report
`is_alive() == False` after `close()` returns.

---

## Recording: webm works (native MediaRecorder), gif captures but doesn't download

### Background

Found and partly fixed 2026-07-26 producing example recordings for the
README. `recording.js`'s `Recorder` class used CCapture
(`js/vendor/build/CCapture.all.min.js`) for every format. Two separate
bugs found:

1. **webm was completely broken** — CCapture's webm encoder mux-es
   per-frame WebP images (`canvas.toDataURL("image/webp")`), which
   Safari has never supported from a canvas — fails silently there
   ("WebP not supported" / "Couldn't decode WebP frame" in console),
   producing a 243-byte (effectively empty) file every time regardless
   of recording length. **Fixed**: webm now uses the browser's native
   `MediaRecorder` API (`canvas.captureStream()` +
   `new MediaRecorder(stream, {mimeType: "video/webm"})`) instead of
   CCapture — no WebP involved, confirmed producing real multi-MB
   files. gif/png/jpg are unaffected by this specific bug (their
   CCapture encoders don't go through WebP) and still use CCapture.
2. **`Swift.stop_recording()` never reset `self.recording = False`**
   — found via the same testing: a second `start_recording()` call in
   the same session always raised `"You are already recording"`, even
   though the first recording had genuinely already stopped. Fixed
   (`Swift.py`).
3. Separately: `gif.worker.js` (needed by CCapture's gif/webm encoders,
   loaded at runtime as a Worker script) was never vendored — only
   shipped under `ccapture.js`'s `src/`, not `build/`, so
   `build-vendor.cjs` never copied it. Fixed (vendor script + rerun).

**Still broken, not yet fixed**: after fix #3, GIF encoding genuinely
runs (confirmed via CCapture's `display: true` status overlay showing
real frame counts, e.g. "CCapture gif | 640 frames | 00:00:32"), but
`.save()` never triggers an actual browser download — no file ever
appears, and there's no visible save/download control in that overlay
to click either (it's a status readout, not an interactive dialog).
Not root-caused: could be an async encoding step that never completes,
or a broken/no-op internal call to whatever download helper CCapture
normally uses (the vendored bundle does contain its own `download()`
helper, similar in shape to what was hand-rolled for the webm fix).

### Proposed fix

Either root-cause CCapture's gif save path specifically (would need to
step through the minified bundle or find an unminified source), or
replace it the same way webm was replaced — record a `MediaRecorder`
webm as before and convert to gif via an external tool/service, or
find a modern maintained gif-encoding library to vendor instead of
`ccapture.js` (unmaintained, last released ~2017, predates
`MediaRecorder` being universal). The latter is probably the more
durable fix long-term, consistent with the "modern, no framework,
current dependencies" direction the rest of this rebuild took —
`ccapture.js` itself is the same vintage as the old WebP-era workaround
webm just moved away from.
