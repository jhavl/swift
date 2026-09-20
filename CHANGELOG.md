# Changelog

Notable changes to this project are documented in this file. swift has
never kept a changelog before, so this covers everything since the last
PyPI release, v1.1.0 (2023-04-30) — effectively three years of accumulated
work on the `future` branch, now merged into `main`, plus everything since.

## [2.0.1] - 2026-09-20

### New

- **Python 3.14 support**: `cp314` wheels are built and the test suite now
  runs on every supported version, 3.10 through 3.14 (it previously only ran
  on 3.12). `requires-python` is unchanged (`>=3.10`).

### Changed

- **Swift no longer depends on `roboticstoolbox` in any way.** The
  dependency runs one way only (RTB depends on swift). `Swift()` previously
  imported RTB at construction and raised `ImportError` without it; it now
  constructs and works standalone, and `add()`/`remove()` recognize a robot
  by its interface rather than by RTB's type. Behavior with RTB installed is
  unchanged, and `remove()` now also works for robots that aren't `ERobot`.
- **Screen recording** moved to `ccapture.js` 2.0.0. The API swift uses is
  unchanged; its GIF encoder is now bundled, so the separate
  `gif.worker.js` is gone.

### Fixed

- **Meshes and textures failed to load on Windows** (#152): a Windows path's
  backslashes were escaped by `encodeURI()`, producing a URL that never
  reached the server's `/retrieve/` route. Backslashes are now converted
  before the drive letter is stripped. The same fix applies to
  `ground_pattern` textures, which had their own copy of this logic.
- **Meshes failed to load when the server runs under WSL** with a Windows
  browser: whether to strip a drive letter was decided from the browser's
  OS, so POSIX paths like `/home/...` were mangled. It is now decided from
  the path itself. Thanks to @tmbkr for diagnosing this (#157).

### Internal

- The Python test job no longer installs `roboticstoolbox`; robot-shaped
  tests use a stand-in, and a session-wide guard blocks any RTB import.
  Nine tests that were previously excluded everywhere now run.
- New end-to-end test of the `/retrieve` route (spatialgeometry, the JS
  URL builder and the real server) on Linux and Windows.
- Wheel and sdist builds now run as a dry run on pull requests that touch
  the build configuration; only a published release uploads to PyPI (a
  manual run of the workflow previously would have published).

## [2.0.0] - 2026-08-23

### Breaking

- **Package moved to a `src/swift/` layout** (was a flat `swift/` package).
- **Frontend rebuilt as modern ES modules**, replacing the old bundled JS.
- **Requires NumPy 2** (`numpy>=2.0`) — the compiled `phys` extension is
  rebuilt against the NumPy 2 ABI; the v1.1.0 wheels on PyPI were built
  against NumPy 1 and genuinely crash under NumPy 2 (confirmed directly:
  real `ImportError` on import, not a theoretical incompatibility).
- **`add_robot()`/`add_assembly()` now return an `AssemblyHandle`** owning
  `q`/`qd` state, replacing direct mutation of the robot object passed in —
  a more functional style. See the updated README quickstart.
- **Per-step rendering now calls `Robot.fkine_geometry(q)` directly**
  instead of mutating the shared `SceneNode` scene graph every frame —
  faster, and doesn't require a robot to carry live scene-graph state to
  animate it.
- **Dead WebRTC/RTC code removed** — was unused, never fully worked.
- Tracks `spatialgeometry`'s `Path` → `Polyline` rename and its `update()`
  method (replacing the deprecated `_propogate_scene_tree()` alias).
- **`swift.SwiftElement` module renamed to `swift.Elements`** (the file and
  the `SwiftElement` class inside it shared a name, which confused static
  type checkers into resolving `SwiftElement` as the submodule rather than
  the class). Only affects code importing directly from the submodule path
  (`from swift.SwiftElement import ...`) — the normal `from swift import
  Slider, Label, ...` top-level import is unaffected.

### New

- `swift.__version__`.
- `SWIFT_HEADLESS` environment variable as `launch()`'s headless default.
- Richer `show()`/`__repr__()`, plus `__getitem__()` lookup by shape id or
  name.
- Configurable scene lights: `launch(lights=)` / `set_lights()`.
- Tiled ground plane: `launch(ground_pattern=, ground_pattern_width=,
  ground_opacity=)`.
- Render support for `spatialgeometry.Ellipsoid`, `Axes`/`Arrow`, and
  `Polyline` (a line through waypoints), and `Mesh`'s new `y_up`
  correction and own vertex colors when no explicit color is given.
- `launch(axes=)` toggle, `Slider(precision=)` (default 3).
- Two independent disconnect timeouts: `launch(timeout=, browser_timeout=)`.
- Detects and warns on a stale browser-cached JS version.
- Overhauled browser/notebook connection lifecycle — a `close()` that
  actually closes, `run()`, and Colab-specific diagnostics.
- `Slider`'s `cb` callback is now optional — a named slider read via
  `env.values` in a shape/assembly callback no longer needs a throwaway
  `lambda v: None` just to satisfy the constructor.
- `Label(compact=True)` — a tighter margin/font-size for several labels
  stacked close together (e.g. a multi-line live readout), without a
  shared CSS change affecting every other `Label`.
- Pressing `s` anywhere in the browser tab (outside a text input) saves a
  screenshot — the same mechanism as `env.screenshot()`, without a Python
  round-trip.
- Full Python 3.10+ type hints across the public API (`Swift`, the UI
  elements, `AssemblyHandle`, `Light` and subclasses).
- Documentation is now actually built and published — see
  https://jhavl.github.io/swift/ (a GitHub Pages deploy workflow existed
  in name only before this; the site had never had a successful build).
  Includes a full rewritten introduction/tutorial, a copy-to-clipboard
  button on every code example, and per-parameter type rendering in the
  API reference.

### Deprecated

- **`desc=`/`.desc` renamed to `label=`/`.label`** across every UI element
  (`Slider`, `Label`, `Button`, `Select`, `Checkbox`, `Radio`) — `desc`
  still works identically, but now raises a `DeprecationWarning` pointing
  at `label`.

### Fixed

A large cluster of rendering, lifecycle, and connection-handling bugs:

- **`SwiftServer`'s HTTP thread never stopped, leaking every shape ever
  added** — the most significant fix in this release; long-running
  processes using swift accumulated this leak continuously.
- `Swift.py` could hang forever on a browser disconnect or a failed mesh
  load; `hold()` never noticed a browser disconnect while idle;
  `producer()` is now disconnect-detectable via `asyncio.to_thread`.
- Mesh loaders (`obj`/`gltf`/`ply`/`wrl`/`pcd`) fetched raw filesystem
  paths — a real correctness/security issue, not just a style one.
- Cylinder primitive rendered along the wrong axis (Y instead of Z); arrow
  head radius was halved, leaving a barely-flared head; the ground plane
  now renders double-sided.
- Default camera position had +x on the wrong side of the screen;
  directional lights repositioned to match.
- Callback-driven shapes never sent color/scale/opacity updates.
- `Slider.onInput()` reported its value as a string, not a number.
- `realtime_speed` wasn't honoured in headless mode.
- `launch()`'s own `timeout=` default silently overrode `_init()`'s.
- Relative `mesh`/`ground_pattern` paths now raise a clear `ValueError`
  instead of failing silently.
- webm recording switched to the browser's native `MediaRecorder`.
- Colab tab-opening, HTTP caching on the local dev server, and the static
  server's threading model (`ThreadingTCPServer`) all fixed.
- Various wire-protocol bugs; added a pause/speed control panel.
- The legacy `robot.q`/`robot.qd` direct-mutation path never wrote the
  handle's own velocity integration back to the robot model — a control
  loop reading `robot.q` back after `env.step()` (a common pattern, e.g.
  RTB's own README `p_servo` example) saw a permanently stale value and
  never converged.
- A disconnect arriving while `_send_socket()` was mid-wait for a reply
  could still fall through to the full 15s `_REPLY_TIMEOUT` instead of
  returning almost immediately.
- `run()` now lets a disconnect detected mid-`step()` crash out as a plain
  traceback, instead of a confusing, inconsistent handling path depending
  on exactly where the disconnect landed.
- Wheels now build against `manylinux_2_28` (was an older, narrower
  manylinux tag) — matches current PyPI/pip tooling expectations.
