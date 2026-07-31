#!/usr/bin/env python
"""
@author Jesse Haviland
"""

from os import read
import numpy as np
import spatialmath as sm
from spatialgeometry import Shape
import time
from queue import Queue, Empty
import json
from swift import start_servers, SwiftElement, Button, Select
from swift.Handle import AssemblyHandle


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
        self._hold_timeout = 5
        # How long the *browser tab* waits after losing its connection to
        # this Python process before closing itself -- see launch()'s
        # browser_timeout=. None means never auto-close. Independent of
        # _hold_timeout: this fires from the browser side, so it still
        # applies even if this process was killed outright rather than
        # exiting through hold().
        self._browser_timeout = 5

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
            kind = "AssemblyHandle(robot)" if obj.robot is not None else "AssemblyHandle"
        else:
            kind = type(obj).__name__
        return f"[{i}] {kind}" + (f' "{name}"' if name else "")

    def __repr__(self):
        s = f"Swift backend, t = {self.sim_time}, scene:"

        for i, ob in enumerate(self.swift_objects):
            if ob is None:
                continue
            s += f"\n  {self._describe(i, ob)}"
        return s

    def show(self):
        """
        Print the current display list, for debugging.

        ``env.show()`` prints every object currently added to the scene
        (shapes, assemblies/robots, and UI elements) with its id, type,
        and name if one was given via ``name=`` at add time.
        """
        print(repr(self))
        for eid, el in self.elements.items():
            name = getattr(el, "name", None)
            print(f"  UI[{eid}] {type(el).__name__}" + (f' "{name}"' if name else ""))

    #
    #  Basic methods to do with the state of the external program
    #

    def launch(
        self,
        realtime: bool | float = False,
        headless: bool = False,
        rate: int = 60,
        browser: str | None = None,
        axes: bool = True,
        ground_opacity: float = 1.0,
        timeout: float | None = 5,
        browser_timeout: float | None = 5,
        **kwargs,
    ):
        """
        Launch the Swift Simulator

        ``env = launch(args)`` create a 3D scene in a running Swift instance as
        defined by args, and returns a reference to the backend.

        ``timeout`` and ``browser_timeout`` cover two different halves of
        the same disconnect: ``timeout`` is how long this Python process
        (specifically :meth:`hold`) keeps waiting once it notices the
        browser is gone; ``browser_timeout`` is how long the browser tab
        itself waits once it notices *this process* is gone before
        closing itself. Neither one can observe the other's side of a
        disconnect directly, so both exist and are set independently.

        :param realtime: Force the simulator to display no faster than real
            time, note that it may still run slower due to complexity.
            ``True`` is 1x speed; a float (e.g. ``0.5``) sets a specific
            wall-clock-per-sim-time multiplier (slow motion below 1.0);
            ``False`` runs uncapped.
        :type realtime: bool | float
        :param headless: Do not launch the graphical front-end of the
            simulator. Will still simulate the robot. Runs faster due to not
            needing to display anything.
        :type headless: bool
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
        :param timeout: how long :meth:`hold` keeps waiting, in seconds,
            after the browser tab disconnects before giving up and
            returning. ``None`` means wait indefinitely (the pre-2.1
            behaviour), defaults to 5
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
        self.headless = headless
        self.axes = axes
        self.ground_opacity = ground_opacity
        # Anchors realtime_speed's pacing clock (see step()) -- needed in
        # headless mode too, not just for rendering.
        self.last_time = time.time()

        if not self.headless:
            # A flag for our threads to monitor for when to quit
            self._run_thread = True
            self.socket, self.server = start_servers(
                self.outq,
                self.inq,
                self._servers_running,
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

            self._send_socket("browser_timeout", self._browser_timeout, expected=False)

    def _servers_running(self):
        return self._run_thread

    def _stop_threads(self):
        self._run_thread = False
        if not self.headless:
            self.socket.join(1)
        if not self._dev:
            self.server.join(1)

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

        """

        # Sim time is incremented first -- callbacks registered via
        # add_shape()/add_assembly()/add_robot()'s callback= see the *new*
        # t for this step, not the one before it.
        self.sim_time += dt
        t = self.sim_time
        values = self.values

        # Update local pose of objects. A registered callback(t, values)
        # -- returning an SE3 for a shape, or a q vector for an assembly/
        # robot -- takes over entirely for that object; otherwise fall
        # back to the existing velocity-integration/shape.v path.
        for i, obj in enumerate(self.swift_objects):
            if isinstance(obj, Shape):
                cb = self.shape_callbacks.get(i)
                if cb is not None:
                    obj.T = cb(t, values)
                else:
                    self._step_shape(obj, dt)
            elif isinstance(obj, AssemblyHandle):
                if obj.callback is not None:
                    obj.q = np.asarray(obj.callback(t, values), dtype=float)
                else:
                    self._step_assembly(obj, dt)

        # Update world transform of shapes (assemblies/robots render via
        # AssemblyHandle.part_poses(), a pure function of handle.q -- no
        # scene-graph propagation needed, see tech-debt.md)
        for obj in self.swift_objects:
            if isinstance(obj, Shape):
                obj._propogate_scene_tree()

        if self.realtime_speed:
            # Delay progress if we're running too quickly for the target
            # speed -- 0.5x should take twice as long (wall clock) per dt
            # of simulated time as 1x, 0.25x four times as long, etc.
            # Applies in headless mode too -- realtime pacing and
            # rendering are independent concerns; only the rendering
            # itself needs a live browser tab to skip.
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

    def close(self):
        """
        Close the graphics display

        ``env.close()`` gracefully disconnectes from the Swift visualizer
        referenced by ``env``.
        """

        self._send_socket("close", "0", False)
        self._stop_threads()

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
        shape._propogate_scene_tree()
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
            part._propogate_scene_tree()
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
        robot._propogate_scene_tree()
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

    def hold(self, timeout: float | None = None):
        """
        Block until the browser disconnects (or forever)

        Meant to sit at the end of a script: once your simulation loop
        finishes, the script would otherwise exit immediately, killing
        this process and disconnecting the browser tab mid-view. ``hold()``
        keeps this process (and so the tab) alive so you can keep looking
        at the final scene.

        Returns once the browser has been disconnected (tab closed,
        crashed, ...) for longer than ``timeout``, rather than holding
        forever regardless of whether there's still a tab to hold open for
        -- see :meth:`launch`'s ``timeout=``, which sets the default this
        method uses when called with no argument.

        :param timeout: seconds to keep waiting after the browser
            disconnects before giving up and returning; defaults to
            whatever :meth:`launch` was given (itself 5 by default).
            ``None`` waits forever, matching the pre-2.1 behaviour.
        :type timeout: float | None
        """

        if timeout is None:
            timeout = self._hold_timeout

        disconnected_since = None

        try:
            while True:
                time.sleep(1)

                if self.headless:
                    continue

                if len(self.socket.USERS) == 0:
                    if disconnected_since is None:
                        disconnected_since = time.time()
                    elif timeout is not None and time.time() - disconnected_since > timeout:
                        return
                else:
                    disconnected_since = None
        except KeyboardInterrupt:
            self.close()
            raise

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
        # mutated/cached world transform. See tech-debt.md.

    def _step_shape(self, shape, dt):

        if shape._changed:
            shape._changed = False
            id = self.swift_objects.index(shape)
            self._send_socket("shape_update", [id, shape.to_dict()])

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
            try:
                return self.inq.get(timeout=_REPLY_TIMEOUT)
            except Empty:
                raise TimeoutError(
                    "Swift browser tab stopped responding (no reply to "
                    f"'{code}' within {_REPLY_TIMEOUT}s) -- it may have been "
                    "closed, crashed, or dropped into a different window/"
                    "profile mid-drag. Call env.close() then env.launch() "
                    "again to reconnect."
                ) from None
        else:
            return "0"

    def _wait_mounted(self, id, count):
        """
        Block until the browser confirms every part of object ``id`` has
        finished loading (see shapes.js's ``SwiftObject``).

        A "shape_mounted" reply of ``1`` means loaded, ``0`` means still
        loading (poll again), and ``-1`` means at least one part's asset
        failed to load in the browser (bad path, unsupported/corrupt mesh
        format, ...) -- see ``shapes.js``'s ``onError`` handlers, which
        report failure this way rather than leaving this loop to poll
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
            status = int(self._send_socket("shape_mounted", [id, count]))
            if status == 1:
                return
            if status == -1:
                raise RuntimeError(
                    f"Swift failed to load one or more assets for object "
                    f"{id} -- check the browser's JavaScript console for "
                    "details (common causes: a bad mesh file path, or an "
                    "unsupported file format)"
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
