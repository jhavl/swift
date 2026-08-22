# Changelog

Notable changes to this project are documented in this file. This is the
first entry — swift has never kept a changelog before, so this covers
everything since the last PyPI release, v1.1.0 (2023-04-30), effectively
three years of accumulated work on the `future` branch, now merged into
`main`.

## [2.0.0] - 2026-08-17

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
