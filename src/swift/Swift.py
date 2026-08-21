#!/usr/bin/env python
"""
@author Jesse Haviland
"""

import os
import numpy as np
import spatialmath as sm
from spatialgeometry import Shape
import time
from queue import Queue, Empty
from threading import Event
import json
from swift import start_servers, SwiftElement, Button, Select
from swift.Handle import AssemblyHandle
from swift.Light import Light


def _se3_to_wire(T):
    """Matches spatialgeometry Shape.fk_dict()'s wire format: t + xyzw q."""
    return {"t": T.t.tolist(), "q": sm.base.r2q(T.R, order="xyzs").tolist()}


def _step_v_py(n, valid, dt, q, qd, qlim):
    q += qd * dt
    if valid:
        np.clip(q, qlim[0], qlim[1], out=q)


def _step_shape_py(dt, v, base, sT, sq):
    eps = 2.220446049250313e-16
    dv = v * dt
    theta = np.linalg.norm(dv[3:6])
    R = np.eye(3)
    if theta > 10 * eps:
        axis = dv[3:6] / theta
        sk = np.array(
            [
                [0, -axis[2], axis[1]],
                [axis[2], 0, -axis[0]],
                [-axis[1], axis[0], 0],
            ]
        )
        R += np.sin(theta) * sk + (1.0 - np.cos(theta)) * (sk @ sk)
    base[:3, :3] = R @ base[:3, :3]
    o = base[:3, 1].copy()
    a = base[:3, 2].copy()
    n = np.cross(o, a)
    o = np.cross(a, n)
    base[:3, 0] = n / np.linalg.norm(n)
    base[:3, 1] = o / np.linalg.norm(o)
    base[:3, 2] = a / np.linalg.norm(a)
    base[:3, 3] += dv[:3]


try:
    from swift.phys import step_v, step_shape
except ImportError:
    step_v = _step_v_py
    step_shape = _step_shape_py


# Options for the built-in realtime-speed control -- None means uncapped
# (run as fast as possible), otherwise a wall-clock-per-sim-time multiplier.
_REALTIME_SPEED_LABELS = ["Max", "1x", "0.5x", "0.25x"]
_REALTIME_SPEEDS = [None, 1.0, 0.5, 0.25]

# How long to wait for a reply to a message that expects one. The browser
# always replies synchronously -- even "shape_mounted" polls report
# load-in-progress rather than blocking on the load itself (see
# shapes.js:SwiftObject) -- so a hang past this means the tab has gone away
# (closed, crashed, or dropped into a different window/profile mid-drag,
# see bugs.md) rather than being legitimately busy.
_REPLY_TIMEOUT = 15

# How often _send_socket() re-checks for a server-detected disconnect while
# waiting for a reply -- short enough that a disconnect mid-wait (the
# common case during an active step() loop) ends the wait almost
# immediately, rather than only ever bailing out at _REPLY_TIMEOUT.
_DISCONNECT_POLL_INTERVAL = 0.05

rtb = None


def _import_rtb():  # pragma nocover
    import importlib

    global rtb
    try:
        rtb = importlib.import_module("roboticstoolbox")
    except ImportError:
        print("\nYou must install the python package roboticstoolbox-python\n")
        raise


class Swift:
    """
    Graphical backend using Swift

    Swift is a web app built on three.js. It supports many 3D graphical
    primitives including meshes, boxes, ellipsoids and lines. It can render
    Collada objects in full color.

    Examples
    --------
    .. code-block:: python
        :linenos:

        import roboticstoolbox as rtb

        robot = rtb.models.DH.Panda()  # create a robot

        pyplot = rtb.backends.Swift()   # create a Swift backend
        pyplot.add(robot)              # add the robot to the backend
        robot.q = robot.qz             # set the robot configuration
        pyplot.step()                  # update the backend and graphical view

    """

    def __init__(self, _dev=False):
        self.outq = Queue()
        self.inq = Queue()

        self._dev = _dev

        if rtb is None:
            _import_rtb()

        self._init()

    def _init(self):
        """
        A private initialization method to make relaunching easy
        """

        # This is the time that has been simulated according to step(dt)
        self.sim_time = 0.0

        # This holds all simulated objects within swift (Shape instances
        # directly, assemblies/robots wrapped in an AssemblyHandle -- see
        # Handle.py)
        self.swift_objects = []

        # Debug/display names, keyed by the same id as swift_objects --
        # not stored on the objects themselves (Shape isn't swift's to
        # extend). Set via the name= kwarg on any add_*() method.
        self.swift_names: dict[int, str] = {}

        # Per-step pose callbacks for plain shapes, keyed by swift_objects
        # index -- see add_shape(..., callback=...). AssemblyHandle carries
        # its own .callback directly since it's swift's own class.
        self.shape_callbacks = {}

        # Current value of every named UI element with a .value, kept
        # current by each element pushing into this dict on change (see
        # SwiftElement._notify_value_changed()) rather than being
        # rescanned each step -- passed to per-step callbacks as `values`.
        self.values: dict[str, object] = {}

        # Number of custom html elements added to page for id purposes
        self.elementid = 0

        # Frame skipped to keep at rate
        self._skipped = 1

        # Element dict which holds the callback functions for form updates
        self.elements = {}

        self.headless = False
        self.rendering = True
        self._notrenderperiod = 1
        self.recording = False
        self._laststep = time.time()
        self._paused = False
        # None means uncapped (run as fast as possible); otherwise a
        # multiplier on wall-clock time per unit of simulated time -- 1.0
        # matches real time, 0.5 is half speed (slow motion), etc.
        self.realtime_speed = None
        self.axes = True
        self.ground_opacity = 1.0
        # How long hold() keeps waiting after the browser disconnects
        # before giving up -- see launch()'s timeout= and hold(). None
        # means wait forever (the old behaviour).
        self._hold_timeout = 1
        # How long the *browser tab* waits after losing its connection to
        # this Python process before closing itself -- see launch()'s
        # browser_timeout=. None means never auto-close. Independent of
        # _hold_timeout: this fires from the browser side, so it still
        # applies even if this process was killed outright rather than
        # exiting through hold().
        self._browser_timeout = 5
        # Set by launch(browser="notebook") -- see close()'s clear_cell=.
        self._notebook_display_handle = None
        # Set by SwiftSocket the instant a disconnect is detected server-
        # side -- lets _send_socket()'s wait bail out well before
        # _REPLY_TIMEOUT. Cleared again at the top of launch(), not
        # recreated -- close()/launch() (the documented reconnect path)
        # don't call _init() again, so the same Event persists and must
        # be explicitly re-armed rather than left set from a prior
        # session's disconnect.
        self._disconnected = Event()

    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, new):
        self._rate = new
        self._period = 1 / new

    def _describe(self, i, obj):
        name = self.swift_names.get(i)
        if isinstance(obj, AssemblyHandle):
            if obj.robot is not None:
                kind = f"AssemblyHandle(robot={obj.robot.name!r}, links={len(obj.robot.links)})"
            else:
                kind = "AssemblyHandle"
        else:
            kind = repr(obj)
        return f"[{i}] {kind}" + (f' "{name}"' if name else "")

    def __repr__(self):
        s = f"Swift backend, t = {self.sim_time}, scene:"

        for i, ob in enumerate(self.swift_objects):
            if ob is None:
                continue
            s += f"\n  {self._describe(i, ob)}"
            if isinstance(ob, AssemblyHandle) and ob.robot is not None:
                for link in ob.robot.links:
                    counts = []
                    if len(link.geometry):
                        counts.append(f"{len(link.geometry)} geometry")
                    if len(link.collision):
                        counts.append(f"{len(link.collision)} collision")
                    suffix = f" ({', '.join(counts)})" if counts else ""
                    s += f"\n      {link.name}{suffix}"
        return s

    def __getitem__(self, key):
        """
        Retrieve a previously-added shape/robot/assembly by id or name.

        ``env[3]`` retrieves by the id returned from ``add_shape()`` etc.
        ``env["gripper"]`` retrieves by the ``name=`` given at add time --
        only objects actually given a name are reachable this way.

        :param key: the object's id, or its ``name=``
        :type key: int | str
        :raises KeyError: no object exists under ``key`` (never named,
            already removed, or an out-of-range id)
        """
        if isinstance(key, str):
            for i, name in self.swift_names.items():
                if name == key and self.swift_objects[i] is not None:
                    return self.swift_objects[i]
            raise KeyError(f"no object named {key!r}")

        try:
            obj = self.swift_objects[key]
        except IndexError:
            obj = None
        if obj is None:
            raise KeyError(f"no object with id {key!r} (removed, or never existed)")
        return obj

    def show(self):
        """
        Print the current display list, for debugging.

        ``env.show()`` prints every object currently added to the scene
        (shapes, assemblies/robots, and UI elements) with its id, a
        ``repr()`` of the object itself, and its name if one was given
        via ``name=`` at add time -- an assembly/robot also lists its
        links, indented, with their geometry/collision shape counts. The
        pause/realtime-speed controls _add_controls() adds to every
        launch() aren't user-added UI, so they're excluded here too.

        Any named object, or any object by its id, can also be
        retrieved directly with ``env[name]`` / ``env[id]`` -- see
        :meth:`__getitem__`.
        """
        print(repr(self))
        for eid, el in self.elements.items():
            if el.builtin:
                continue
            name = getattr(el, "name", None)
            print(f"  UI[{eid}] {type(el).__name__}" + (f' "{name}"' if name else ""))

    #
    #  Basic methods to do with the state of the external program
    #

    def launch(
        self,
        realtime: bool | float = False,
        headless: bool | None = None,
        rate: int = 60,
        browser: str | None = None,
        axes: bool = True,
        ground_opacity: float = 1.0,
        ground_pattern: bool | str = False,
        ground_pattern_width: float = 1.0,
        lights: list[Light] | None = None,
        timeout: float | None = 1,
        browser_timeout: float | None = 5,
        **kwargs,
    ):
        """
        Launch the Swift Simulator

        ``env = launch(args)`` create a 3D scene in a running Swift instance as
        defined by args, and returns a reference to the backend.

        .. warning::

            The scene's lights are fixed in world space and never move on
            their own -- including in response to :meth:`set_camera_pose`.
            Moving the camera far enough from its default position can
            leave every camera-facing surface in shadow, since the
            default lights are positioned specifically to match that
            default camera position. Use ``lights=``/:meth:`set_lights`
            to reposition them to match, if needed.

        ``timeout`` and ``browser_timeout`` cover two independent,
        opposite-direction halves of the same disconnect -- worth
        spelling out in full, since the two are easy to mix up:

        ========================  ================================  ================================
        Parameter                 *Who* is waiting                   *For what*
        ========================  ================================  ================================
        ``timeout``                This Python process, inside        The browser tab to still be there
                                    :meth:`hold`/:meth:`run`
        ``browser_timeout``        The browser tab (JavaScript)       This Python process to still be
                                                                       alive
        ========================  ================================  ================================

        Concretely:

        * Close the **browser tab** -- ``timeout`` (default 1 second) is
          how long :meth:`hold`/:meth:`run` keep polling before giving
          up, printing ``"Swift browser tab closed."``, calling
          :meth:`close`, and returning. Actual wall-clock latency is
          ``timeout`` plus up to ~1 second of polling granularity --
          about 2 seconds with the default.
        * Kill **this Python process** (or it crashes) -- ``browser_timeout``
          (default 5 seconds) is how long the browser tab waits before
          closing itself. Python can't run any code to reconnect a dead
          process, so this side needs its own, independently-configured
          timer running entirely in the browser.

        Neither side can observe the other's half of a disconnect
        directly -- the browser can't poll a dead Python process, and a
        killed Python process can't run any code at all -- which is why
        two separate parameters exist rather than one. Either can be set
        to ``None`` for "wait forever" on that side. See
        :doc:`internals` for the full mechanism (threads, sockets,
        exactly what "the browser is gone" means internally).

        :param realtime: Force the simulator to display no faster than real
            time, note that it may still run slower due to complexity.
            ``True`` is 1x speed; a float (e.g. ``0.5``) sets a specific
            wall-clock-per-sim-time multiplier (slow motion below 1.0);
            ``False`` runs uncapped.
        :type realtime: bool | float
        :param headless: Do not launch the graphical front-end of the
            simulator. Will still simulate the robot. Runs faster due to not
            needing to display anything. ``None`` (default) falls back to
            the ``SWIFT_HEADLESS`` environment variable (headless if set to
            any non-empty value), then ``False`` if that's also unset --
            lets a test harness or CI environment force headless mode
            globally without every calling script having to pass
            ``headless=True`` itself.
        :type headless: bool | None
        :param rate: The rate (Hz) at which the simulator will be run,
            defaults to 60Hz
        :type rate: int
        :param browser: browser to open in: one of 'google-chrome', 'chrome',
            'firefox', 'safari', 'opera' or see for full list
            https://docs.python.org/3/library/webbrowser.html#webbrowser.open_new
        :type browser: str | None
        :param axes: Show the world-frame axes helper at the origin,
            defaults to True
        :type axes: bool
        :param ground_opacity: Opacity of the ground plane, from 0
            (invisible) to 1 (opaque), defaults to 1
        :type ground_opacity: float
        :param ground_pattern: Repeating pattern on the ground plane.
            ``False`` (default) is a plain flat floor. ``True`` or
            ``"@tile"`` is a built-in checkerboard; ``"@grid"`` is a
            built-in grid. Anything else is treated as an absolute path
            to an image file to tile as a texture -- its tile height
            follows the image's own aspect ratio (never distorted); see
            ``ground_pattern_width``. Whenever a pattern is active, the
            ground plane recentres under the camera every frame (snapped
            to a whole tile, so the pattern never visibly shifts) so its
            edge is never reachable regardless of pan/zoom -- skipped
            entirely for the plain flat floor, which has no visible edge
            to begin with.
        :type ground_pattern: bool | str
        :param ground_pattern_width: x-extent of one tile, in metres.
            Only meaningful when ``ground_pattern`` is set, defaults to 1.
        :type ground_pattern_width: float
        :param lights: custom scene lights, replacing Swift's default
            3-light rig entirely -- there is no way to add to the
            defaults, only replace them outright. ``None`` (default)
            keeps the default rig unchanged. See :meth:`set_lights` to
            change lights again after launch.
        :type lights: list[Light] | None
        :param timeout: how long :meth:`hold` keeps waiting, in seconds,
            after the browser tab disconnects before giving up and
            returning. ``None`` means wait indefinitely (the pre-2.1
            behaviour), defaults to 1
        :type timeout: float | None
        :param browser_timeout: how long the *browser tab* waits, in
            seconds, after losing its connection to this process before
            closing itself. ``None`` means never auto-close, defaults to
            5. Independent of ``timeout`` -- this fires browser-side, so
            it still applies if this process is killed outright rather
            than exiting through :meth:`hold`. Only takes effect on a
            tab the browser considers script-opened; on a normally
            user-opened tab (the common case) ``window.close()`` is a
            silent no-op and the tab is left showing a "Disconnected"
            banner instead.
        :type browser_timeout: float | None

        """

        self.browser = browser
        self.rate = rate
        self._hold_timeout = timeout
        self._browser_timeout = browser_timeout
        if isinstance(realtime, bool):
            self.realtime_speed = 1.0 if realtime else None
        else:
            self.realtime_speed = float(realtime)
        if headless is None:
            headless = bool(os.environ.get("SWIFT_HEADLESS"))
        self.headless = headless
        self.axes = axes
        self.ground_opacity = ground_opacity
        if (
            isinstance(ground_pattern, str)
            and ground_pattern not in ("@tile", "@grid")
            and not os.path.isabs(ground_pattern)
        ):
            raise ValueError(
                f"ground_pattern={ground_pattern!r} is a relative path, but "
                "Swift serves custom textures from an absolute path on disk "
                "(via the same mechanism as Mesh filenames) -- pass an "
                "absolute path, e.g. str(Path(__file__).parent / "
                f"{ground_pattern!r})"
            )
        self.ground_pattern = ground_pattern
        self.ground_pattern_width = ground_pattern_width
        self.lights = lights
        # Anchors realtime_speed's pacing clock (see step()) -- needed in
        # headless mode too, not just for rendering.
        self.last_time = time.time()

        if not self.headless:
            # A flag for our threads to monitor for when to quit
            self._run_thread = True
            self._disconnected.clear()
            self.socket_thread, self.socket, self.server_thread, self.server, self._notebook_display_handle = start_servers(
                self.outq,
                self.inq,
                self._servers_running,
                self._disconnected,
                browser=browser,
            )

            # The realtime, render and pause buttons -- added after the
            # browser has connected, since sending them any earlier would
            # block waiting for a reply from a client that isn't there yet.
            self._add_controls()

            if not self.axes:
                self._send_socket("axes", False, expected=False)

            if self.ground_opacity != 1.0:
                self._send_socket("ground_opacity", self.ground_opacity, expected=False)

            if self.ground_pattern:
                self._send_socket(
                    "ground_pattern",
                    {"pattern": self.ground_pattern, "width": self.ground_pattern_width},
                    expected=False,
                )

            if self.lights is not None:
                self.set_lights(self.lights)

            self._send_socket("browser_timeout", self._browser_timeout, expected=False)

    def _servers_running(self):
        return self._run_thread

    def _stop_threads(self):
        self._run_thread = False
        if not self.headless:
            # Setting _run_thread above only ends serve()'s per-connection
            # message loop -- SwiftSocket.loop.run_forever() itself never
            # checks it and would otherwise keep the thread (and the bound
            # port) alive forever, regardless. stop() actually tells that
            # event loop to return.
            self.socket.stop()
            self.socket_thread.join(1)
        if not self._dev and not self.headless:
            # server.stop() (httpd.shutdown()) is what actually lets
            # serve_forever() return -- without it, Thread.run() never
            # reaches its own cleanup of the arguments it was started
            # with, one of which is a bound method of this Swift
            # instance. That single un-cleared reference, from a thread
            # that runs for the rest of the process's life, is what was
            # keeping every shape ever added (and this env itself) alive
            # long after close() returned -- see jhavl/swift#92.
            self.server.stop()
            self.server_thread.join(1)

    def step(self, dt=0.05, render=True):
        """
        Update the graphical scene

        :param dt: time step in seconds, defaults to 0.05
        :type dt: int, optional
        :param render: render the change in Swift. If True, this updates the
            pose of the simulated robots and objects in Swift.
        :type dt: bool, optional

        ``env.step(args)`` triggers an update of the 3D scene in the Swift
        window referenced by ``env``.

        .. note::

            - Each robot in the scene is updated based on
              their control type (position, velocity, acceleration, or torque).
            - Upon acting, the other three of the four control types will be
              updated in the internal state of the robot object.
            - The control type is defined by the robot object, and not all
              robot objects support all control types.
            - Execution is blocked for the specified interval

        :seealso: :meth:`run` for repeatedly calling this in a loop with
            disconnect-awareness built in, instead of hand-writing
            ``while True: env.step(dt)``.

        """

        try:
            # Sim time is incremented first -- callbacks registered via
            # add_shape()/add_assembly()/add_robot()'s callback= see the
            # *new* t for this step, not the one before it.
            self.sim_time += dt
            t = self.sim_time
            values = self.values

            # Update local pose of objects. A registered callback(t, values)
            # -- returning an SE3 for a shape, or a q vector for an
            # assembly/robot -- takes over entirely for that object;
            # otherwise fall back to the existing velocity-integration/
            # shape.v path.
            for i, obj in enumerate(self.swift_objects):
                if isinstance(obj, Shape):
                    cb = self.shape_callbacks.get(i)
                    if cb is not None:
                        obj.T = cb(t, values)
                        self._send_shape_update_if_changed(obj)
                    else:
                        self._step_shape(obj, dt)
                elif isinstance(obj, AssemblyHandle):
                    if obj.callback is not None:
                        obj.q = np.asarray(obj.callback(t, values), dtype=float)
                    else:
                        self._step_assembly(obj, dt)

            # Update world transform of shapes (assemblies/robots render via
            # AssemblyHandle.part_poses(), a pure function of handle.q --
            # no scene-graph propagation needed, see jhavl/swift#85)
            for obj in self.swift_objects:
                if isinstance(obj, Shape):
                    obj.update()

            if self.realtime_speed:
                # Delay progress if we're running too quickly for the
                # target speed -- 0.5x should take twice as long (wall
                # clock) per dt of simulated time as 1x, 0.25x four times
                # as long, etc. Applies in headless mode too -- realtime
                # pacing and rendering are independent concerns; only the
                # rendering itself needs a live browser tab to skip. This
                # sleep is also where most of a realtime-paced script's
                # wall-clock time between step() calls actually goes --
                # which is why ^C is caught around this whole method, not
                # just here: it's overwhelmingly likely to land inside
                # this call, not a caller's own sleep (if it even has one).
                time_taken = time.time() - self.last_time
                diff = (dt * self._skipped) / self.realtime_speed - time_taken
                self._skipped = 1

                if diff > 0:
                    time.sleep(diff)

                self.last_time = time.time()

            if not self.headless:

                if render and self.rendering:

                    if not self.realtime_speed and (time.time() - self._laststep) < self._period:
                        # Only render at 60 FPS
                        self._skipped += 1
                        return

                    self._laststep = time.time()

                    self._step_elements()

                    events = self._draw_all()
                    # print(events)

                    # Process GUI events
                    self.process_events(events)

                elif not self.rendering:
                    if (time.time() - self._laststep) < self._notrenderperiod:
                        return
                    self._laststep = time.time()
                    events = json.loads(self._send_socket("shape_poses", [], True))
                    self.process_events(events)

                # print(events)
                # else:
                #     for i in range(len(self.robots)):
                #         self.robots[i]['ob'].fkine_all(self.robots[i]['ob'].q)

                self._send_socket("sim_time", self.sim_time, expected=False)
        except KeyboardInterrupt:
            # ^C is the normal, expected way to end an interactive session
            # here, not an error -- exit quietly rather than a traceback,
            # regardless of what loop construct the caller wrote (a bare
            # `while True: env.step(dt)` gets this for free, not just
            # hold()/run(), which also catch it independently for the
            # part of their own loops spent outside step()).
            print("\nInterrupted, closing.")
            self.close()
            raise SystemExit

    def reset(self):
        """
        Reset the graphical scene

        ``env.reset()`` triggers a reset of the 3D scene in the Swift window
        referenced by ``env``. It is restored to the original state defined by
        ``launch()``.

        """

        self.restart()

    def restart(self):
        """
        Restart the graphics display

        ``env.restart()`` triggers a restart of the Swift view referenced by
        ``env``. It is closed and relaunched to the original state defined by
        ``launch()``.

        """

        prior_speed = self.realtime_speed
        prior_axes = self.axes
        prior_timeout = self._hold_timeout
        prior_browser_timeout = self._browser_timeout

        self._send_socket("close", "0", False)
        self._stop_threads()
        self._init()
        self.launch(
            headless=self.headless,
            rate=self.rate,
            browser=self.browser,
            axes=prior_axes,
            timeout=prior_timeout,
            browser_timeout=prior_browser_timeout,
        )
        self.realtime_speed = prior_speed

    def close(self, clear_cell: bool = False):
        """
        Close the graphics display

        ``env.close()`` gracefully disconnectes from the Swift visualizer
        referenced by ``env``.

        :param clear_cell: if launched with ``browser="notebook"``, blank
            out the cell that rendered the iframe instead of leaving its
            last frame visible (the default -- matches prior behaviour).
            No effect for any other ``browser=`` mode, or if the iframe's
            cell was never displayed (e.g. still headless).
        :type clear_cell: bool
        """

        self._send_socket("close", "0", False)
        self._stop_threads()

        if clear_cell and self._notebook_display_handle is not None:
            # Lazy import -- IPython is optional, only actually needed if
            # a notebook display handle was ever created in the first
            # place (browser="notebook" already requires it be installed).
            from IPython.display import HTML

            self._notebook_display_handle.update(HTML(""))

    #
    #  Methods to interface with the robots created in other environemnts
    #

    def add(self, ob, robot_alpha=1.0, collision_alpha=0.0, readonly=False, name=None):
        """
        Add an object to the graphical scene

        .. deprecated:: 2.0

            Kept for backward compatibility. Prefer the explicit
            :meth:`add_shape`, :meth:`add_ui`, :meth:`add_assembly`, or
            :meth:`add_robot` -- one entry point per kind of thing, no
            type-checking required.

        :param ob: the object to add
        :type ob: Robot, Shape, or SwiftElement
        :param robot_alpha: Robot visual opacity. If 0, then the geometries
            are invisible, defaults to 1.0
        :type robot_alpha: bool, optional
        :param collision_alpha: Robot collision visual opacity. If 0, then
            the geometries defaults to 0.0
        :type collision_alpha: float, optional
        :param readonly: If true, swift will not modify any robot attributes,
            the robot is only being displayed, not simulated,
            defaults to False
        :type readonly: bool, optional
        :param name: optional debug/display name, see :meth:`show`
        :type name: str | None
        :return: for a ``Shape``, its object id within the visualizer; for
            a ``Robot``, an :class:`~swift.Handle.AssemblyHandle` owning
            that instance's live joint state; for a ``SwiftElement``, the
            element itself
        :rtype: int | AssemblyHandle | SwiftElement
        """

        if isinstance(ob, Shape):
            return self.add_shape(ob, name=name)
        elif isinstance(ob, SwiftElement):
            return self.add_ui(ob, name=name)
        elif isinstance(ob, rtb.Robot):
            return self.add_robot(
                ob,
                robot_alpha=robot_alpha,
                collision_alpha=collision_alpha,
                readonly=readonly,
                name=name,
            )

    def add_shape(self, shape, callback=None, name=None):
        """
        Add a single shape to the graphical scene

        :param shape: the shape to add
        :type shape: Shape
        :param callback: optional per-step pose callback ``(t, values) ->
            SE3``, called each ``env.step()`` instead of the default
            velocity/``shape.v``-driven update -- see :meth:`step`
        :type callback: Callable[[float, dict], SE3] | None
        :param name: optional debug/display name, see :meth:`show`
        :type name: str | None
        :return: the shape's object id within the visualizer
        :rtype: int

        ``id = env.add_shape(shape)`` adds ``shape`` to the graphical
        environment and returns its id.
        """
        filename = getattr(shape, "filename", None)
        if isinstance(filename, str) and not os.path.isabs(filename):
            raise ValueError(
                f"{type(shape).__name__}(filename={filename!r}) is a "
                "relative path, but Swift serves mesh files from an "
                "absolute path on disk -- pass an absolute path, e.g. "
                f"str(Path(__file__).parent / {filename!r})"
            )
        shape.update()
        shape._added_to_swift = True
        if not self.headless:
            id = int(self._send_socket("shape", [shape.to_dict()]))
            self._wait_mounted(id, 1)

        else:
            id = len(self.swift_objects)

        self.swift_objects.append(shape)
        if name is not None:
            self.swift_names[int(id)] = name
        if callback is not None:
            self.shape_callbacks[int(id)] = callback
        return int(id)

    def add_ui(self, element, name=None):
        """
        Add a UI element (Slider, Button, ...) to the graphical scene

        :param element: the element to add
        :type element: SwiftElement
        :param name: optional name, collected into the ``values`` dict
            per-step callbacks receive -- see :meth:`step`. Only elements
            with a ``.value`` attribute (e.g. ``Slider``, ``Select``)
            contribute a value.
        :type name: str | None
        :return: the element itself
        :rtype: SwiftElement

        ``env.add_ui(element)`` adds ``element`` to the sidebar.
        """
        if element._added_to_swift:
            raise ValueError("This element has already been added to Swift")

        element._added_to_swift = True
        element.name = name

        if name is not None and hasattr(element, "value"):
            element._on_change = lambda v, name=name: self.values.__setitem__(name, v)
            self.values[name] = element.value

        id = self.elementid
        self.elementid += 1
        self.elements[str(id)] = element
        element._id = id

        if not self.headless:
            self._send_socket("element", element.to_dict())
        return element

    def add_assembly(self, fk, parts, q0=None, callback=None, readonly=False, name=None):
        """
        Add an assembly of parts driven by a pure forward-kinematics function

        :param fk: pure function mapping this assembly's current ``q`` to
            one world-frame :class:`~spatialmath.SE3` pose per entry in
            ``parts``, in the same order
        :type fk: Callable[[ArrayLike], list[SE3]]
        :param parts: the shapes making up this assembly, in the order
            ``fk`` returns poses for
        :type parts: list[Shape]
        :param q0: initial configuration, defaults to an empty array (set
            ``handle.q`` before the first :meth:`step` if ``fk`` needs
            one)
        :type q0: ArrayLike | None
        :param callback: optional per-step callback ``(t, values) -> q``,
            called each ``env.step()`` to compute the new ``q`` directly
            -- see :meth:`step`
        :type callback: Callable[[float, dict], ArrayLike] | None
        :param readonly: if True, swift will not advance this assembly's
            ``q`` itself, defaults to False
        :type readonly: bool
        :param name: optional debug/display name, see :meth:`show`
        :type name: str | None
        :return: a handle owning this assembly's live joint state
        :rtype: AssemblyHandle

        ``handle = env.add_assembly(fk, parts)`` adds ``parts`` to the
        graphical environment as one unit, positioned each step by
        ``fk(handle.q)``.
        """
        for part in parts:
            part.update()
            part._added_to_swift = True

        if not self.headless:
            parts_dict = [p.to_dict() for p in parts]
            id = int(self._send_socket("shape", parts_dict))
            self._wait_mounted(id, len(parts_dict))

        else:
            id = len(self.swift_objects)

        handle = AssemblyHandle(
            fk, np.zeros(0) if q0 is None else q0, readonly=readonly,
            name=name, callback=callback,
        )
        handle.id = int(id)
        self.swift_objects.append(handle)
        if name is not None:
            self.swift_names[int(id)] = name

        return handle

    def add_robot(self, robot, robot_alpha=1.0, collision_alpha=0.0, readonly=False, callback=None, name=None):
        """
        Add an ``rtb.Robot`` to the graphical scene

        :param robot: the robot to add
        :type robot: roboticstoolbox.Robot
        :param robot_alpha: Robot visual opacity. If 0, then the geometries
            are invisible, defaults to 1.0
        :type robot_alpha: bool, optional
        :param collision_alpha: Robot collision visual opacity. If 0, then
            the geometries defaults to 0.0
        :type collision_alpha: float, optional
        :param readonly: If true, swift will not modify any robot attributes,
            the robot is only being displayed, not simulated,
            defaults to False
        :type readonly: bool, optional
        :param callback: optional per-step callback ``(t, values) -> q``,
            see :meth:`add_assembly`
        :type callback: Callable[[float, dict], ArrayLike] | None
        :param name: optional debug/display name, see :meth:`show`
        :type name: str | None
        :return: a handle owning this robot instance's live joint state
        :rtype: AssemblyHandle

        ``handle = env.add_robot(robot)`` adds ``robot`` to the graphical
        environment and returns a handle. ``robot`` itself stays a plain
        kinematic model -- drive it with ``handle.q``/``handle.qd``
        (mutating ``robot.q``/``robot.qd`` directly still works, but is
        deprecated, see :class:`~swift.Handle.AssemblyHandle`).
        """
        robot._update_link_tf()
        robot.update()
        robot._qlim = robot.qlim

        if not self.headless:
            robob = robot._to_dict(
                robot_alpha=robot_alpha, collision_alpha=collision_alpha
            )
            id = int(self._send_socket("shape", robob))
            self._wait_mounted(id, len(robob))

        else:
            id = len(self.swift_objects)

        handle = AssemblyHandle(
            lambda q: robot.fkine_geometry(q, robot_alpha, collision_alpha),
            robot.q, robot=robot, readonly=readonly, name=name, callback=callback,
        )
        handle.id = int(id)
        self.swift_objects.append(handle)
        if name is not None:
            self.swift_names[int(id)] = name

        return handle

    def remove(self, id):
        """
        Remove a robot/shape from the graphical scene

        ``env.remove(robot)`` removes the ``robot`` from the graphical
            environment.

        :param id: the id of the object as returned by the ``add`` method,
            or the instance of the object
        :type id: Int, Robot or Shape
        """

        # ob to remove
        idd = None
        code = None

        if isinstance(id, AssemblyHandle):
            idd = id.id
            code = "remove"
            self.swift_objects[idd] = None
        elif isinstance(id, rtb.ERobot) or isinstance(id, Shape):

            for i in range(len(self.swift_objects)):
                obj = self.swift_objects[i]
                if obj is None:
                    continue
                if obj is id or (isinstance(obj, AssemblyHandle) and obj.robot is id):
                    idd = i
                    code = "remove"
                    self.swift_objects[idd] = None
                    break
        else:
            # Number corresponding to swift_objects index
            idd = id
            code = "remove"
            self.swift_objects[idd] = None

        if idd is None:
            raise ValueError(
                "the id argument does not correspond with a robot or shape in Swift"
            )

        if not self.headless:
            self._send_socket(code, idd)

    def hold(self, duration: float | None = None, timeout: float | None = None):
        """
        Block for up to ``duration`` seconds (or indefinitely)

        Meant to sit at the end of a script: once your simulation loop
        finishes, the script would otherwise exit immediately, killing
        this process and disconnecting the browser tab mid-view. ``hold()``
        keeps this process (and so the tab) alive so you can keep looking
        at the final scene -- for a fixed amount of time if ``duration``
        is given, or until interrupted (^C) or the browser disconnects
        for longer than ``timeout`` otherwise.

        ``duration`` is an unconditional cap -- it elapses regardless of
        whether the browser is still connected, unlike ``timeout``, which
        only ever starts counting *after* a disconnect. ``hold(5)`` reads
        as "hold for 5 seconds" and does exactly that; it will still
        return early if the browser goes away first.

        :param duration: seconds to hold for, regardless of connection
            state; ``None`` (default) holds indefinitely, bounded only
            by ``timeout``/^C
        :type duration: float | None
        :param timeout: seconds to keep waiting after the browser
            disconnects before giving up and returning early; defaults
            to whatever :meth:`launch` was given (itself 1 by default).
            ``None`` never gives up on a disconnect (still stops at
            ``duration``, if given).
        :type timeout: float | None
        """

        if timeout is None:
            timeout = self._hold_timeout

        start_time = time.time()
        disconnected_since = None

        try:
            while duration is None or (time.time() - start_time) < duration:
                time.sleep(1)
                disconnected_since, expired = self._check_disconnected(disconnected_since, timeout)
                if expired:
                    print("\nSwift browser tab closed.")
                    self.close()
                    return
        except KeyboardInterrupt:
            # ^C is the normal, expected way to end an interactive session
            # here, not an error -- exit quietly rather than a traceback.
            # SystemExit (not a plain return) so any code after this call
            # doesn't keep running -- matches step()'s own handling of
            # the same interrupt, since ^C landing inside a step() call
            # this method makes (run()) is otherwise handled differently
            # depending on exactly where it lands, which would be a
            # confusing inconsistency.
            print("\nInterrupted, closing.")
            self.close()
            raise SystemExit

    def _check_disconnected(self, disconnected_since, timeout):
        """
        Shared disconnect-timeout bookkeeping for hold() and run().

        :param disconnected_since: ``time.time()`` the browser was first
            seen disconnected, or ``None`` if it wasn't (yet)
        :type disconnected_since: float | None
        :param timeout: seconds of continuous disconnection before
            ``expired`` becomes True; ``None`` never expires
        :type timeout: float | None
        :return: updated ``disconnected_since``, and whether ``timeout``
            has now been exceeded (headless never expires -- there's no
            browser to disconnect from)
        :rtype: tuple[float | None, bool]
        """
        if self.headless or len(self.socket.USERS) > 0:
            return None, False
        if disconnected_since is None:
            return time.time(), False
        expired = timeout is not None and time.time() - disconnected_since > timeout
        return disconnected_since, expired

    def run(self, duration: float | None = None, dt: float = 0.05, timeout: float | None = None):
        """
        Repeatedly call :meth:`step` until ``duration`` (sim-time seconds)
        has elapsed, stopping early if the browser disconnects for longer
        than ``timeout`` -- the same disconnect-timeout ``hold()`` uses,
        and defaulting to the same :meth:`launch`'s ``timeout=`` value.

        ``env.run()`` is the loop most scripts would otherwise hand-write
        as ``while True: env.step(dt); time.sleep(dt)`` at the end of a
        script, with hold()'s disconnect-awareness built in instead of
        looping forever after the browser is long gone.

        :param duration: sim-time seconds to run for; ``None`` runs until
            disconnected (or forever, if ``timeout`` is also ``None``)
        :type duration: float | None
        :param dt: time step passed to each :meth:`step` call, defaults
            to 0.05
        :type dt: float
        :param timeout: seconds to keep running after the browser
            disconnects before giving up and returning; defaults to
            whatever :meth:`launch` was given (itself 1 by default).
            ``None`` never gives up on a disconnect (still stops at
            ``duration``, if given).
        :type timeout: float | None

        :seealso: :meth:`step` for a single manual update, if you need
            finer control than a bounded/unbounded loop gives you.
        """

        if timeout is None:
            timeout = self._hold_timeout

        start_time = self.sim_time
        disconnected_since = None

        try:
            while duration is None or (self.sim_time - start_time) < duration:
                self.step(dt)
                time.sleep(dt)
                disconnected_since, expired = self._check_disconnected(disconnected_since, timeout)
                if expired:
                    print("\nSwift browser tab closed.")
                    self.close()
                    return
        except KeyboardInterrupt:
            # ^C is the normal, expected way to end an interactive session
            # here, not an error -- exit quietly rather than a traceback.
            # SystemExit (not a plain return) so any code after this call
            # doesn't keep running -- matches step()'s own handling of
            # the same interrupt, since ^C landing inside a step() call
            # this method makes (run()) is otherwise handled differently
            # depending on exactly where it lands, which would be a
            # confusing inconsistency.
            print("\nInterrupted, closing.")
            self.close()
            raise SystemExit

    def start_recording(self, file_name, framerate, format="webm"):
        """
        Start recording the canvas in the Swift simulator

        :param file_name: The file name for which the video will be saved as
        :type file_name: string
        :param framerate: The framerate of the video - to be timed correctly,
            this should equalt 1 / dt where dt is the time supplied to the
            step function
        :type framerate: float
        :param format: This is the format of the video, one of 'webm', 'gif',
            'png', or 'jpg'
        :type format: string

        ``env.start_recording(file_name)`` starts recording the simulation
            scene and will save it as file_name once
            ``env.start_recording(file_name)`` is called
        """

        valid_formats = ["webm", "gif", "png", "jpg"]

        if format not in valid_formats:
            raise ValueError("Format can one of 'webm', 'gif', 'png', or 'jpg'")

        if not self.recording:
            self._send_socket("start_recording", [framerate, file_name, format])
            self.recording = True
        else:
            raise ValueError(
                "You are already recording, you can only record one video at a time"
            )

    def stop_recording(self):
        """
        Start recording the canvas in the Swift simulator. This is optional
        as the video will be automatically saved when the python script exits

        ``env.stop_recording()`` stops the recording of the simulation, can
            only be called after ``env.start_recording(file_name)``
        """

        if self.recording:
            self._send_socket("stop_recording")
            self.recording = False
        else:
            raise ValueError(
                "You must call swift.start_recording(file_name) before trying"
                " to stop the recording"
            )

    def screenshot(self, file_name="swift_snap"):
        """
        Save a screenshot of the current Swift frame as a png file

        :param file_name: The file name for which the screenshot will be saved as
        :type file_name: string

        ``env.screenshot(file_name)`` saves a screenshot and downloads it as file_name
        """

        if file_name.endswith(".png"):
            file_name = file_name[:-4]

        self._send_socket("screenshot", [file_name])

    def process_events(self, events):
        """
        Process the event queue from Swift, this invokes the callback functions
        from custom elements added to the page. If using custom elements
        (for example `add_slider`), use this function in your event loop to
        process updates from Swift.
        """
        # events = self._send_socket('check_elements')
        for event in events:
            self.elements[event].update(events[event])
            self.elements[event].cb(events[event])

    def set_camera_pose(self, position, look_at):
        """
        Swift.set_camera_pose(position, look_at) will set the camera
        position and orientation of the camera within the swift scene.
        The camera is located at location and is oriented to look at a
        point in space defined by look_at. Note that the camera is
        oriented with the positive z-axis.

        .. warning::

            The scene's lights do not move with the camera -- they're
            fixed in world space, positioned to match the *default*
            camera position set at launch. Moving the camera far enough
            away with this method can leave every camera-facing surface
            in shadow. Use :meth:`set_lights` to reposition them to
            match, if needed.

        :param position: The desired position of the camera
        :type position: 3 vector (list or ndarray)
        :param look_at: A point in the scene in which the camera will look at
        :type look_at: 3 vector (list or ndarray)
        """

        # if isinstance(pose, sm.SE3):
        #     pose = pose.A

        # if look_at is None:
        #     q = r2q(pose[:3, :3], order="xyzs").tolist()
        # else:
        #     q = None

        if isinstance(position, np.ndarray):
            position = position.tolist()

        if isinstance(look_at, np.ndarray):
            look_at = look_at.tolist()

        transform = {
            "t": position,
            "look_at": look_at,
        }

        self._send_socket("camera_pose", transform, False)

    def set_lights(self, lights: list[Light]) -> None:
        """
        Replace the scene's current lights.

        ``env.set_lights(lights)`` replaces every light currently in the
        scene -- including Swift's own default rig, if it's still
        active -- with ``lights``. There is no way to add or remove a
        single light individually; the whole rig is always replaced as
        one unit. Call again with the same lights given to
        :meth:`launch` to restore them after temporarily using
        something else.

        :param lights: the new set of lights, replacing every light
            currently in the scene
        """
        self.lights = lights
        if not self.headless:
            self._send_socket("lights", [light.to_dict() for light in lights], expected=False)

    def _step_assembly(self, handle, dt):

        handle._sync_legacy()

        if handle.readonly or handle.control_mode == "p":
            pass  # pragma: no cover

        elif handle.control_mode == "v":

            if handle.robot is None:
                raise ValueError(
                    "control_mode='v' needs a robot's qlim/joint count to "
                    "integrate against -- only available on a handle from "
                    "add_robot(), not a bare add_assembly() handle. Drive "
                    "handle.q directly, or use a callback, instead."
                )

            robot = handle.robot
            step_v(robot._n, robot._valid_qlim, dt, handle.q, handle.qd, robot._qlim)
            handle._push_legacy()

        elif handle.control_mode == "a":
            pass

        else:  # pragma: no cover
            # Should be impossible to reach
            raise ValueError(
                "Invalid handle.control_mode. Must be one of 'p', 'v', or 'a'"
            )

        # No _update_link_tf()/_propogate_scene_tree() call here -- _draw_all()
        # computes geometry poses via AssemblyHandle.part_poses(), a pure
        # function of handle.q, rather than reading the scene-graph's
        # mutated/cached world transform. See jhavl/swift#85.

    def _send_shape_update_if_changed(self, shape):
        # A shape's @update-decorated setters (color, opacity, scale, ...)
        # only flip shape._changed -- this is the one place that turns that
        # flag into an actual "shape_update" message. Must run for every
        # shape every step, callback-driven or not (see step()'s caller in
        # the cb-is-not-None branch) -- it used to only run from within
        # _step_shape(), which callback-driven shapes never reach, so a
        # callback shape's color/scale/opacity changes were silently
        # dropped forever, even though its pose kept updating fine via the
        # callback's own SE3 return value.
        if shape._changed:
            shape._changed = False
            id = self.swift_objects.index(shape)
            self._send_socket("shape_update", [id, shape.to_dict()])

    def _step_shape(self, shape, dt):

        self._send_shape_update_if_changed(shape)

        step_shape(
            dt, shape.v, shape._SceneNode__T, shape._SceneNode__wT, shape._SceneNode__wq
        )
        if shape.collision:
            shape._update_coal()

    def _step_elements(self):
        """
        Check custom HTML elements to see if any have been updated, if there
        are any updates, send them through to Swift.
        """

        for element in self.elements:
            if self.elements[element]._changed:
                self.elements[element]._changed = False
                self._send_socket(
                    "update_element", self.elements[element].to_dict(), False
                )

    def _draw_all(self):
        """
        Sends the transform of every simulated object in the scene
        Recieves bacl a list of events which has occured
        """

        msg = []

        for i in range(len(self.swift_objects)):
            if self.swift_objects[i] is not None:
                if isinstance(self.swift_objects[i], Shape):
                    msg.append([i, [self.swift_objects[i].fk_dict()]])
                elif isinstance(self.swift_objects[i], AssemblyHandle):
                    handle = self.swift_objects[i]
                    handle._sync_legacy()
                    poses = handle.part_poses()
                    msg.append([i, [_se3_to_wire(T) for T in poses]])

        events = self._send_socket("shape_poses", msg, True)
        return json.loads(events)

    def _send_socket(self, code, data=None, expected=True):
        msg = [expected, [code, data]]

        self.outq.put(msg)

        if expected:
            # Poll in short slices rather than one blocking
            # inq.get(timeout=_REPLY_TIMEOUT) -- so a disconnect
            # SwiftSocket notices mid-wait (see SwiftRoute.py's
            # expect_message()) ends this well before the full timeout,
            # instead of _REPLY_TIMEOUT being the only possible bound.
            start = time.time()
            while True:
                try:
                    return self.inq.get(timeout=_DISCONNECT_POLL_INTERVAL)
                except Empty:
                    elapsed = time.time() - start
                    if self._disconnected.is_set() or elapsed >= _REPLY_TIMEOUT:
                        raise TimeoutError(
                            "Swift browser tab stopped responding (no "
                            f"reply to '{code}' after {elapsed:.1f}s) -- "
                            "it may have been closed, crashed, or dropped "
                            "into a different window/profile mid-drag. "
                            "Call env.close() then env.launch() again to "
                            "reconnect."
                        ) from None
        else:
            return "0"

    def _wait_mounted(self, id, count):
        """
        Block until the browser confirms every part of object ``id`` has
        finished loading (see shapes.js's ``SwiftObject``).

        A "shape_mounted" reply is ``[code, detail]`` (see shapes.js's
        ``load()``/``SwiftObject``): ``[1, None]`` means loaded, ``[0,
        None]`` means still loading (poll again), ``[-1, reason]`` means
        the shape type itself isn't one ``load()`` recognises at all, and
        ``[-2, reason]`` means a genuine asset load failure (bad path,
        unsupported/corrupt mesh format). Either failure stops this loop
        and raises with the browser's own reason instead of polling
        forever with no way to tell the caller why (bugs.md, Bug 2).

        :param id: the object's id, as returned by the preceding "shape"
            message
        :type id: int
        :param count: number of parts the object has, for the browser-side
            log/protocol payload only -- the mounted check itself compares
            against the part list ``id`` was created with
        :type count: int
        """
        while True:
            status, detail = json.loads(self._send_socket("shape_mounted", [id, count]))
            if status == 1:
                return
            if status == -1:
                raise RuntimeError(f"Swift failed to load object {id}: {detail}")
            if status == -2:
                raise RuntimeError(
                    f"Swift failed to load object {id}: {detail} -- check "
                    "the browser's JavaScript console for the full error"
                )
            time.sleep(0.1)

    def _pause_control(self, _):
        # Button's cb() contract is "argument can be disregarded" -- the
        # click carries no state of its own, so pause/resume is tracked
        # here and just flipped on each click. A second click, arriving
        # while the loop below is polling, recurses back into this same
        # method (via process_events -> cb) and flips it back to False,
        # which is what breaks the outer loop.
        self._paused = not self._paused
        self._pause_button.desc = "▶" if self._paused else "||"
        # The loop below bypasses the normal step()/_step_elements() path
        # entirely (it only polls shape_poses directly), so the icon
        # change above would otherwise sit queued and unsent for as long
        # as we're paused -- flush it immediately instead.
        self._step_elements()
        while self._paused:
            time.sleep(0.1)
            events = json.loads(self._send_socket("shape_poses", []))
            self.process_events(events)

    def _time_control(self, index):
        self._skipped = 1
        self.realtime_speed = _REALTIME_SPEEDS[int(index)]

    def _add_controls(self):
        self._pause_button = Button(self._pause_control, desc="||")
        self._pause_button.builtin = True
        self.add_ui(self._pause_button)

        # self.realtime_speed may be an arbitrary float set directly via
        # launch(realtime=<float>) rather than one of the dropdown presets
        # -- fall back to "Max" in the display without touching the actual
        # (still fully respected) speed.
        try:
            speed_index = _REALTIME_SPEEDS.index(self.realtime_speed)
        except ValueError:
            speed_index = 0
        speed_select = Select(
            self._time_control, desc="Speed", options=_REALTIME_SPEED_LABELS, value=speed_index
        )
        speed_select.builtin = True
        self.add_ui(speed_select)
