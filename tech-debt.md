# Technical Debt

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

**Not done now** — this session's Swift work (frontend rebuild, wire
protocol, control panel) was deliberately built against the *current*
stateful-`robot.q` API, but using the pure-FK-computation path
underneath where practical, so it doesn't have to be re-architected
when this lands.

---

## Google Colab support: real bugs fixed, but `proxyPort()` itself appears unreliable

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
`google.colab.kernel.proxyPort()` still fails **intermittently** --
same code, same steps, sometimes a 404 (on `favicon.ico`, harmless)
with the actual page still blank, sometimes the request never
completes at all (no status, no response headers, indistinguishable
from a hang). Ruled out browser caching as the cause (tested in a
private/incognito window, same intermittent failure). The
inconsistency itself -- identical steps producing different outcomes
-- points at Colab's proxy infrastructure rather than a deterministic
bug in this code, consistent with a documented history of `proxyPort`
reliability issues (e.g. googlecolab/colabtools#4270, #3308, #4738 --
the last of these was from 2024, already closed, not the current
issue, but establishes the pattern).

### Implication for the WebRTC decision

Confirmed this isn't a reason to reconsider dropping WebRTC: RTC would
only have replaced the *data channel* after the page loads. The
observed failure is in the *initial page load* through `proxyPort()`
itself, before any comms-mode-specific code runs -- RTC wouldn't have
helped with what's actually breaking.

### Status

Not resolved. The three fixes above are real, confirmed improvements
worth keeping regardless (any Colab user gets further than before),
but further progress needs either reproducing this outside of live
back-and-forth debugging (a throwaway minimal `proxyPort()` Colab
notebook with no Swift involved, to isolate whether *any* custom local
server behaves reliably through it) or accepting Colab support as
presently unreliable for reasons outside this repo's control.

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

## `_fknm_c` background-thread nanobind leak affects every Swift session

Fully written up in `roboticstoolbox-python/tech-debt.md` under
"`_fknm_c` (nanobind) leaks `_ETObj`/`_ETSObj` when created from a
background thread" — root-caused there to fknm object creation
specifically from a non-main thread, not call volume. Directly
relevant here since Swift's stepping/rendering machinery always runs
on a background thread, so any script using the Swift backend is a
candidate to print the `nanobind: leaked N instances!` messages at
interpreter shutdown (seen throughout this session's E2E test output).
Confirmed cosmetic (a shutdown-time diagnostic) in every session this
work generated, but not confirmed to rule out real memory growth in a
long-running process — see the RTB entry for the open question and
repro.
