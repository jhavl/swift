*************
Using Swift
*************

.. note::

    Draft. Figures and worked examples to follow.

This page covers day-to-day use of the Swift viewer itself -- the
provided example assets, ground plane options, the world axes, the
camera, and the lighting model. For mesh file formats and how a
``Mesh`` shape's file is actually loaded, see :doc:`mesh`.

Controlling the animation
=========================

.. _playback-controls:

Playback controls
-----------------

Every non-headless session shows a small panel bottom-left of the browser
view:

* a pause/play button (``||``/``▶``) -- also bound to the spacebar;
* a realtime-speed selector (``Max``/``1x``/``0.5x``/``0.25x``) -- ``1x``
  matches ``env.launch(realtime=True)``, ``Max`` matches the default
  (``realtime=False``, uncapped). ``env.launch(realtime=0.5)`` (a specific
  float, not just ``True``/``False``) sets an initial speed directly.


.. _viewpoint-control:

Viewpoint control
-----------------

The scene is navigated with the mouse, using three.js's standard
`OrbitControls <https://threejs.org/docs/#examples/en/controls/OrbitControls>`__:

.. list-table:: Mouse controls
   :header-rows: 1
   :widths: 30 70

   * - Control
     - Action
   * - Left button, drag
     - Rotate (orbit) the camera around the orbit target
   * - Right button, drag
     - Pan the camera and orbit target together
   * - Scroll wheel
     - Zoom in/out (dolly the camera towards/away from the orbit target)

The camera always looks at a fixed point in space called the *orbit target*
-- dragging with the left button rotates the camera around this point rather
than around the scene's origin. Swift sets the orbit target just above the
ground plane, at ``(0, 0, 0.2)``, so that rotating the view keeps your
shapes centred rather than swinging around the ground plane at ``z=0``.
Panning (right button or Ctrl/Cmd/Shift+left button) moves the orbit target itself, so subsequent
rotations pivot around wherever you've panned to.


.. _headless-operation:

Headless operation
===================

``env.launch(headless=True)`` -- or the ``SWIFT_HEADLESS`` environment
variable, which lets a CI environment or test harness force it globally
without every script passing the argument itself -- never opens a
browser tab at all. It's a step further than just hiding the window:
the websocket/HTTP servers themselves are never started, so there is no
client anywhere for Swift to talk to.

:meth:`~swift.Swift.Swift.step`'s pose computation runs exactly the
same either way -- a registered ``callback(t, values)`` still runs, and
so does the fallback velocity-integration path described in
:ref:`velocity-control` when there isn't one. A headless script is
typically just that fallback path, driven directly with nothing
rendered:

.. code-block:: python

    import roboticstoolbox as rtb
    from swift import Swift

    env = Swift()
    env.launch(headless=True)

    panda = rtb.models.Panda()
    handle = env.add_robot(panda)
    handle.qd = [0.1, 0, 0, 0, 0, 0, 0]

    for _ in range(100):
        env.step(0.05)

    print(handle.q)  # the integrated result -- nothing was ever drawn

This runs faster than the same script with a real browser tab attached,
purely because there's nothing to render or send over the network each
step.

What doesn't work headless: anything that needs an actual connected
browser tab has nowhere to go. That rules out screenshots and movie
recording (there's no canvas to capture), interactive UI elements and
sliders, and mouse camera control. :meth:`~swift.Swift.Swift.hold` and
:meth:`~swift.Swift.Swift.run`'s disconnect-timeout logic doesn't apply
either -- there's no browser tab to disconnect from, so both block for
their full requested ``duration`` (or forever, if none was given)
rather than ever detecting a "disconnect".


.. _velocity-control:

Velocity control
=================

Any shape, assembly, or robot with no registered ``callback=`` falls
back to a per-step velocity integration instead of staying put -- this
is what ``shape.v``/``handle.qd`` actually drive, and it runs on every
call to :meth:`~swift.Swift.Swift.step`, headless or not (see
:ref:`headless-operation`).

For an assembly or robot handle, this is governed by
``handle.control_mode`` (``"p"``, ``"v"``, or ``"a"`` -- defaults to
``"v"`` for a robot added via :meth:`~swift.Swift.Swift.add_robot`; see
:class:`~swift.Handle.AssemblyHandle`):

* ``"p"`` (position) -- ``handle.q`` is read directly each step;
  nothing is integrated. This is effectively what a registered
  ``callback=`` gives you too, since its return value is written
  straight to ``handle.q``. A bare assembly (added via
  :meth:`~swift.Swift.Swift.add_assembly`, with no robot behind it) has
  no joint limits to integrate against, so it defaults to ``"p"``
  instead of ``"v"`` -- drive it with a callback, or set ``handle.q``
  directly.
* ``"v"`` (velocity) -- each step, ``handle.q`` is advanced by simple
  Euler integration, ``q += handle.qd * dt``, then clipped to the
  robot's own joint limits if it has any.
* ``"a"`` (acceleration) -- reserved for future use. :meth:`step`
  currently takes no action in this mode, so ``handle.q`` stays fixed
  regardless of ``handle.qd`` unless you also register a ``callback=``
  (which bypasses ``control_mode`` entirely).

A plain ``Shape`` (added via ``add_shape()``, no callback) follows the
same idea through ``shape.v``: a 6-vector twist
``[vx, vy, vz, wx, wy, wz]``, integrated each step into the shape's
pose -- linear velocity added directly to its position, angular
velocity applied as a small rotation about its own instantaneous axis
(via Rodrigues' rotation formula), not as three independent per-axis
Euler-angle updates.

Either way, this integration genuinely happens inside :meth:`step`
itself -- not something spatialgeometry or the browser computes -- so
it's exactly as available headless as it is with a real browser tab
attached; only the final render is what gets skipped.



Snapshots
==========

Pressing ``s`` anywhere in the browser tab (outside a text input) saves a
screenshot of the current view, named ``swift-YYYY-MM-DD_HH-MM-SS.png`` --
the same mechanism as :meth:`~swift.Swift.Swift.screenshot`, just without a
Python round-trip.

From a script, call :meth:`~swift.Swift.Swift.screenshot` directly to
capture a frame at a specific point in a simulation, with a file name of
your choosing::

    env.step(dt)
    env.screenshot("my_snapshot")

Either way, the image is a PNG of exactly what the canvas is showing at
that instant -- there's no way to capture at a resolution different from
the browser window's current size. Like the hotkey, this triggers a
regular browser download; it lands wherever your browser normally saves
downloads, not a path you can choose from Python.


Movies
=======

:meth:`~swift.Swift.Swift.start_recording` and
:meth:`~swift.Swift.Swift.stop_recording` capture a video of the scene
as it animates::

    env.start_recording("my_movie", framerate=1 / dt)
    for t in np.arange(0, 5, dt):
        box.T = SE3.Rz(t)
        env.step(dt)
    env.stop_recording()

``framerate`` should match ``1 / dt`` so the saved video plays back at
the same speed the simulation ran -- pass whatever ``dt`` you're already
using in your :meth:`step` calls. ``stop_recording()`` is optional:
if you never call it, the recording is saved automatically once the
script exits (via :meth:`hold`/:meth:`run`/^C, or the process just
ending).

Four formats are available via ``start_recording(..., format=...)``:

* ``"webm"`` (the default) uses the browser's own ``MediaRecorder`` --
  broadly supported, no extra download step; the file saves itself the
  same way a screenshot does.
* ``"gif"``, ``"png"``, and ``"jpg"`` all go through a bundled capture
  library (CCapture) instead. ``"gif"`` in particular needs the browser
  tab to stay open after the simulation ends so you can trigger its own
  save step -- Swift won't auto-close the tab while a GIF capture is
  still pending, even if you've set a ``timeout`` on :meth:`hold`.

:meth:`~swift.Swift.Swift.step` or :meth:`~swift.Swift.Swift.run`?
====================================================================

:meth:`~swift.Swift.Swift.run` is a convenience wrapper around :meth:`~swift.Swift.Swift.step` that runs a simulation loop for you, so you don't have to write your own ``while True:`` loop.
Both notice if the browser tab disappears mid-call -- but :meth:`step` just raises a ``TimeoutError`` after Swift's fixed internal reply timeout (15s), while :meth:`run` (see the next section) polls for a disconnect explicitly and gives up gracefully after its own configurable ``timeout``, printing a message and closing the connection instead of raising.


Ending a session: :meth:`~swift.Swift.Swift.hold`, :meth:`~swift.Swift.Swift.run`, :meth:`~swift.Swift.Swift.close`
=====================================================================================================================

A script that just falls off the end after its simulation loop ends will kill the
owning process immediately, which will take the browser tab down with it. Three methods
manage that:

* :meth:`~swift.Swift.Swift.hold` blocks -- for a fixed ``duration``, or
  until interrupted -- so the final frame stays visible. It's disconnect-
  aware: if the browser tab goes away, it gives up after ``timeout``
  seconds rather than hanging forever.
* :meth:`~swift.Swift.Swift.run` is :meth:`step` wrapped in the loop most
  scripts would otherwise hand-write themselves (``while True:
  env.step(dt)``), with the same disconnect-awareness as :meth:`hold`.
* :meth:`~swift.Swift.Swift.close` gracefully disconnects and stops
  Swift's background threads. Called automatically by :meth:`hold` and
  :meth:`run` on ^C, so a script using either doesn't need its own
  ``try``/``except KeyboardInterrupt`` to exit cleanly.

All three are interrupt-safe: pressing ^C during :meth:`step`,
:meth:`hold`, or :meth:`run` closes the connection and exits quietly
(no traceback) rather than raising -- ^C is treated as the normal way
to end an interactive session, not an error.


Notebook operation
===================

``env.launch(browser="notebook")`` renders inline in the current cell's
output via :class:`IPython.display.IFrame`, instead of opening a separate
browser tab -- useful in Jupyter/JupyterLab. Combined with
:meth:`~swift.Swift.Swift.hold` and
:meth:`~swift.Swift.Swift.close`'s ``clear_cell`` option:

.. code-block:: python

    import roboticstoolbox as rtb
    from swift import Swift

    env = Swift()
    env.launch(browser="notebook")

    panda = rtb.models.Panda()
    handle = env.add_robot(panda)
    handle.q = panda.qr
    env.step()

    env.hold(5)               # show the result for 5 seconds
    env.close(clear_cell=True)  # then blank this cell's output

``close(clear_cell=True)`` blanks specifically the cell that rendered the
iframe, regardless of which cell is executing when ``close()`` runs --
plain ``clear_output()`` only ever affects the currently-executing cell,
which isn't the same thing once execution has moved past the :meth:`launch`
call. Leave ``clear_cell`` at its default (``False``) to keep the last
frame visible instead.

See ``docs/notebooks/swift.ipynb`` for a runnable version of this example.


Scene graph and data structures
================================

Shapes, primitives, and pose representation (:class:`~spatialgeometry.Shape`
and its subclasses -- ``Cuboid``, ``Sphere``, mesh loaders, and so on, each
positioned by an :class:`~spatialmath.SE3`) come from `spatialgeometry
<https://github.com/jhavl/spatialgeometry>`_, a separate package. Swift
doesn't reimplement any of that -- a shape you build with spatialgeometry is
exactly what you hand to :meth:`~swift.Swift.Swift.add_shape` or pack into an
assembly.

Spatialgeometry also owns its *own* scene graph: every ``Shape`` is a
``SceneNode``, backed by a small C++ ``Node`` object that propagates a
parent's world transform down to its children (``_propogate_scene_tree()``).
That machinery still runs for a plain shape driven by a velocity
(``shape.v``, stepped by :meth:`~swift.Swift.Swift.step`) -- but it is
*not* what positions an assembly or a robot. For those, Swift computes every
part's world pose itself, each step, as a pure function of the assembly's
current ``q`` (see :class:`~swift.Handle.AssemblyHandle`), and sends the
result straight to the browser without touching spatialgeometry's
propagation path at all.

So: the geometric vocabulary -- shapes, transforms, primitive types -- is
spatialgeometry's. The animation-loop *mechanism* that decides what pose an
assembly or robot has right now, and how it gets there, is Swift's own.


Google Colab
============

Swift does not currently work on Google Colab. :meth:`launch` detects a
Colab environment and prints a warning up front, before attempting to
connect, but still tries anyway in case that changes.

Two independent problems, neither fixed as of this writing:

* Colab proxies a notebook's outputs through
  ``google.colab.kernel.proxyPort()``, which was found to fail
  consistently (0 successes across 500 isolated test attempts) --
  unrelated to Swift, and outside this repo's control.
* Separately, Swift's websocket connection is never routed through that
  proxy at all (it's hardcoded to ``ws://localhost``), so even if
  ``proxyPort()`` worked, the websocket handshake specifically would
  still fail.

See ``tech-debt.md``'s "Google Colab support" section for the full
investigation, including what was ruled out (reviving WebRTC) and the
more promising direction if this is ever revisited (``eval_js``/
``register_callback`` instead of a raw websocket).

Design philosophy
==================

A few decisions, arrived at over a long design discussion during this
project's 2.0 rebuild, shape the API described above:

* **Stateless over stateful.** Kinematics is computed as a pure function of
  an explicit ``q`` -- :meth:`Robot.fkine_geometry() <roboticstoolbox.robot.Robot.Robot.fkine_geometry>`
  for a real robot, or a bare ``fk(q) -> list[SE3]`` for anything else --
  rather than read from mutated, cached state. This mirrors
  `roboticstoolbox`'s own "stateless over stateful" aspiration, applied to
  the rendering path specifically.
* **One place for live state.** A model (an ``rtb.Robot``, or any object with
  an ``fk(q)``) stays plain and shareable -- it carries no live simulation
  state of its own. The one thing that's genuinely per-instance --
  ``q``/``qd``/``control_mode`` -- lives on a handle
  (:class:`~swift.Handle.AssemblyHandle`) that Swift owns and steps.
* **One handle, regardless of source.** :meth:`~swift.Swift.Swift.add_robot`
  and :meth:`~swift.Swift.Swift.add_assembly` return the exact same handle
  class. An ``rtb.Robot`` is just one particular, convenient way to produce
  the ``fk(q)`` an assembly needs -- there's no separate, parallel code path
  for "real robots" versus anything else.
* **Passive data isn't the same as live state.** A component referencing
  static, descriptive data -- a robot link knowing which shapes represent
  it, for instance -- isn't "stateful" in any sense worth avoiding. What
  matters is whether something *mutates cached results in place* as a side
  effect of rendering. Swift's assembly path avoids that; it doesn't avoid
  a ``Link`` knowing what it looks like.
* **Callbacks over hand-written loops.** Any shape, assembly, or robot can
  take a per-step ``callback(t, values) -> pose_or_q``, and named UI
  elements push their value into ``env.values`` as they change. Together
  these remove the imperative ``while True: ...; env.step(dt)`` boilerplate
  -- and the per-slider setter function -- from the common case, while the
  explicit, manual form keeps working for anything a callback doesn't fit.
* **Deprecate, don't break.** Superseded patterns -- mutating ``robot.q``
  directly instead of using a handle, calling ``env.add()`` instead of the
  explicit ``add_shape()``/``add_ui()``/``add_assembly()``/``add_robot()`` --
  keep working. They're flagged as superseded, not removed.



Provided assets
==================

``examples/assets/`` ships a small set of CC-licensed meshes and
textures for use in example scripts and this documentation -- a
colorful robot, a cooked steak/chicken piece/plate, turf and gravel
ground textures, and a Spitfire model. Each file's title, author,
source, and licence are recorded in ``examples/assets/README.md``; add
an entry there in the same format before using any new asset. CC0
assets need no attribution but are listed anyway, for provenance.

These are example/doc assets only -- ``examples/`` isn't packaged, so
they aren't installed alongside Swift itself.

Ground options
=================

The ground plane is a single finite ``PlaneGeometry`` (40 x 40 m by
default), controlled by two ``launch()`` parameters:

``ground_opacity``
    Opacity from 0 (invisible) to 1 (opaque, the default).

``ground_pattern`` / ``ground_pattern_width``
    ``False`` (default) is a plain flat floor. ``True`` or ``"@tile"``
    is a built-in checkerboard; ``"@grid"`` is a built-in grid; anything
    else is treated as an absolute path to an image file to tile as a
    texture. ``ground_pattern_width`` sets the x-extent of one tile, in
    metres -- a custom texture's tile *height* follows the source
    image's own aspect ratio, so it's never distorted.

Whenever a pattern is active, the ground plane recentres under the
camera every frame, snapped to a whole tile so the pattern never
visibly shifts -- this keeps its edge permanently out of reach
regardless of pan/zoom, giving the appearance of an infinite floor. The
plain flat floor has no visible edge to begin with, so it's left fixed
at the origin and skips this recentring entirely.

Global axes
==============

``launch(axes=True)`` (the default) shows a ``THREE.AxesHelper`` at the
world origin -- red/green/blue for x/y/z. Pass ``axes=False`` to hide it.
Swift's world ``+z`` is up (``THREE.Object3D.DEFAULT_UP`` is set
accordingly), matching the usual robotics convention.

Camera
========

The default camera is a perspective camera positioned off to one side
and slightly above the origin, oriented so the world ``+x`` axis reads
as screen-right (the usual convention) -- with ``+z`` up, this requires
the camera to sit on the ``-y`` side. It's driven by three.js's
``OrbitControls``, so the mouse/trackpad orbits, pans, and zooms it
interactively; nothing on the Python side needs to change for that.

For programmatic control, ``Swift.set_camera_pose(position, look_at)``
moves the camera to an explicit position and re-aims it at a point in
the scene, updating ``OrbitControls``' own target to match so
subsequent interactive orbiting pivots around the new point rather than
the old one.

Lighting model
=================

The scene uses three.js's ``MeshPhongMaterial`` throughout (specular
highlights, not a full PBR pipeline), lit by:

* A ``HemisphereLight`` (soft sky/ground fill light, no shadows).
* Two shadow-casting ``DirectionalLight``\ s, positioned on the same
  side of the scene as the camera -- if a light and the camera are on
  opposite sides, camera-facing surfaces end up in shadow. Moving the
  camera means moving these lights to match.

Shadow mapping is enabled on the renderer; the ground plane receives
shadows. A background fog (matching the scene's background color)
fades distant objects rather than clipping them abruptly at the camera's
far plane.

Visual vs. collision geometry
================================

Each robot ``Link`` carries *two* independent sets of shapes --
``geometry`` (what you look at) and ``collision`` (what's used for
distance/collision queries via spatialgeometry's ``CollisionShape``,
backed by `coal <https://github.com/coal-library/coal>`_) -- mirroring
URDF's own ``<visual>``/``<collision>`` split per link. The collision set
is often a coarser, cheaper proxy (a box/cylinder standing in for a
complex part) since collision checking needs to run fast and doesn't
care about visual fidelity.

``add()``/``add_robot()`` expose this directly as two independent
opacity knobs, ``robot_alpha`` and ``collision_alpha``. ``collision_alpha``
defaults to ``0`` (hidden) precisely because the collision proxy is
normally an ugly, redundant stand-in you don't want cluttering the
view -- turn it up when you specifically need to sanity-check that the
collision geometry actually matches where you think it is, e.g. while
debugging a planner or a self-collision check.
