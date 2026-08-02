************
Introduction
************

.. TODO: expand this page with more detail.

Swift is a light-weight browser-based animation visualizer which provides
robotics-specific functionality for rapid prototyping of algorithms,
research, and education. Built using Python and Javascript, Swift is
cross-platform (Linux, macOS, and Windows).

Swift provides:

* visualisation of mesh objects (Collada, STL, OBJ, glTF/GLB, PLY, VRML/WRL,
  and PCD files) and primitive shapes;
* robot visualisation and simulation;
* interactive UI controls (sliders, buttons, and more) for driving a scene
  from the browser;
* recording and saving a video of the simulation;
* source code which can be read for learning and teaching.


Swift is the primary visualisation engine for the
`Robotics Toolbox for Python
<https://github.com/petercorke/robotics-toolbox-python>`_.
Through the Robotics Toolbox, Swift can visualise over 150 robot
models -- contemporary robots from Franka-Emika, Kinova, Universal Robotics,
Rethink, as well as classical robots such as the Puma 560 and the Stanford
arm.


Installation
============

::

    pip install swift-sim

Swift is normally installed as a dependency of `roboticstoolbox-python
<https://github.com/petercorke/robotics-toolbox-python>`_ rather than used
standalone::

    pip install roboticstoolbox-python

Swift requires Python 3.10 or later.


Quick start
===========

.. code-block:: python

    import roboticstoolbox as rtb
    from swift import Swift

    env = Swift()
    env.launch(realtime=True)

    panda = rtb.models.Panda()
    handle = env.add_robot(panda)
    handle.q = panda.qr

    env.hold()  # keep the browser tab open

This example isn't executed when these docs are built (it needs a browser
and a running websocket connection), so treat it as a starting point rather
than verified-working output.


Playback controls
==================

Every non-headless session shows a small panel bottom-left of the browser
view:

* a pause/play button (``||``/``▶``) -- also bound to the spacebar;
* a realtime-speed selector (``Max``/``1x``/``0.5x``/``0.25x``) -- ``1x``
  matches ``env.launch(realtime=True)``, ``Max`` matches the default
  (``realtime=False``, uncapped). ``env.launch(realtime=0.5)`` (a specific
  float, not just ``True``/``False``) sets an initial speed directly.

See `Swift's own README
<https://github.com/jhavl/swift#readme>`_ for a full set of worked
examples of increasing complexity -- moving shapes with sliders, robots
following an interactive target, programmatic pose trajectories, and
video recording -- and the :doc:`api` page for the full class reference.


Ending a session: :meth:`~swift.Swift.Swift.hold`, :meth:`~swift.Swift.Swift.run`, :meth:`~swift.Swift.Swift.close`
=====================================================================================================================

A script that just falls off the end after its simulation loop kills the
process immediately, taking the browser tab down with it. Three methods
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
which isn't the same thing once execution has moved past the ``launch()``
call. Leave ``clear_cell`` at its default (``False``) to keep the last
frame visible instead.

See ``docs/notebooks/swift.ipynb`` for a runnable version of this example.


Google Colab
============

Swift does not currently work on Google Colab. ``launch()`` detects a
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
