#!/usr/bin/env python
"""
@author Jesse Haviland
"""

from os import read
import numpy as np
import spatialmath as sm
from spatialgeometry import Shape
import time
from queue import Queue
import json
from swift import start_servers, SwiftElement, Button
import phys

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

    :param realtime: Force the simulator to display no faster than real time,
        note that it may still run slower due to complexity
    :type realtime: bool
    :param display: Do not launch the graphical front-end of the simulator.
        Will still simulate the robot. Runs faster due to not needing to
        display anything.
    :type display: bool

    Example:

    .. code-block:: python
        :linenos:

        import roboticstoolbox as rtb

        robot = rtb.models.DH.Panda()  # create a robot

        pyplot = rtb.backends.Swift()   # create a Swift backend
        pyplot.add(robot)              # add the robot to the backend
        robot.q = robot.qz             # set the robot configuration
        pyplot.step()                  # update the backend and graphical view

    :references:

        - https://github.com/jhavl/swift

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

        # This holds all simulated objects within swift
        self.swift_objects = []

        # This is an option dict with the format id: {option: option_value}
        # to hold custom options for simulated objects
        self.swift_options = {}

        # Number of custom html elements added to page for id purposes
        self.elementid = 0

        # Frame skipped to keep at rate
        self._skipped = 1

        # Element dict which holds the callback functions for form updates
        self.elements = {}

        self.rendering = True
        self._notrenderperiod = 1
        self.recording = False
        self._laststep = time.time()

    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, new):
        self._rate = new
        self._period = 1 / new

    def __repr__(self):
        s = f"Swift backend, t = {self.sim_time}, scene:"

        for ob in self.swift_objects:
            s += f"\n  {ob.name}"
        return s

    #
    #  Basic methods to do with the state of the external program
    #

    def launch(self, realtime=False, headless=False, rate=60, browser=None, **kwargs):
        """
        Launch a graphical backend in Swift by default in the default browser
        or in the specified browser

        :param browser: browser to open in: one of
            'google-chrome', 'chrome', 'firefox', 'safari', 'opera'
            or see for full list
            https://docs.python.org/3.8/library/webbrowser.html#webbrowser.open_new
        :type browser: string

        ``env = launch(args)`` create a 3D scene in a running Swift instance as
        defined by args, and returns a reference to the backend.

        """

        self.browser = browser
        self.rate = rate
        self.realtime = realtime
        self.headless = headless

        if not self.headless:
            # The realtime, render and pause buttons
            self._add_controls()

            # A flag for our threads to monitor for when to quit
            self._run_thread = True
            self.socket, self.server = start_servers(
                self.outq,
                self.inq,
                self._servers_running,
                browser=browser,
                dev=self._dev,
            )
            self.last_time = time.time()

    def _servers_running(self):
        return self._run_thread

    def _stop_threads(self):
        self._run_thread = False
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

        # TODO how is the pose of shapes updated prior to step?

        for i, obj in enumerate(self.swift_objects):
            if isinstance(obj, Shape):
                self._step_shape(obj, dt)
            elif isinstance(obj, rtb.Robot):
                self._step_robot(obj, dt, self.swift_options[i]["readonly"])

        # Adjust sim time
        self.sim_time += dt

        if not self.headless:

            if render and self.rendering:

                if self.realtime:
                    # If realtime is set, delay progress if we are
                    # running too quickly
                    time_taken = time.time() - self.last_time
                    diff = (dt * self._skipped) - time_taken
                    self._skipped = 1

                    if diff > 0:
                        time.sleep(diff)

                    self.last_time = time.time()
                elif (time.time() - self._laststep) < self._period:
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

        self._send_socket("close", "0", False)
        self._stop_threads()
        self._init()
        self.launch(
            realtime=self.realtime,
            headless=self.headless,
            rate=self.rate,
            browser=self.browser,
        )

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

    def add(self, ob, show_robot=True, show_collision=False, readonly=False):
        """
        Add a robot to the graphical scene

        :param ob: the object to add
        :type ob: Robot or Shape
        :param show_robot: Show the robot visual geometry,
            defaults to True
        :type show_robot: bool, optional
        :param show_collision: Show the collision geometry,
            defaults to False
        :type show_collision: bool, optional
        :return: object id within visualizer
        :rtype: int
        :param readonly: If true, swif twill not modify any robot attributes,
            the robot is only nbeing displayed, not simulated,
            defaults to False
        :type readonly: bool, optional

        ``id = env.add(robot)`` adds the ``robot`` to the graphical
            environment.

        .. note::

            - Adds the robot object to a list of robots which will be updated
              when the ``step()`` method is called.

        """
        # id = add(robot) adds the robot to the external environment. robot
        # must be of an appropriate class. This adds a robot object to a
        # list of robots which will act upon the step() method being called.

        if isinstance(ob, Shape):
            if not self.headless:
                id = int(self._send_socket("shape", [ob.to_dict()]))

                while not int(self._send_socket("shape_mounted", [id, 1])):
                    time.sleep(0.1)

            else:
                id = len(self.swift_objects)

            self.swift_objects.append(ob)
            return int(id)
        elif isinstance(ob, SwiftElement):

            if ob._added_to_swift:
                raise ValueError("This element has already been added to Swift")

            ob._added_to_swift = True

            # id = 'customelement' + str(self.elementid)
            id = self.elementid
            self.elementid += 1
            self.elements[str(id)] = ob
            ob._id = id

            self._send_socket("element", ob.to_dict())
        elif isinstance(ob, rtb.ERobot):

            if ob.base is None:
                ob.base = sm.SE3()

            # ob._swift_readonly = readonly
            # ob._show_robot = show_robot
            # ob._show_collision = show_collision

            if not self.headless:
                robob = ob._to_dict(
                    show_robot=show_robot, show_collision=show_collision
                )
                id = self._send_socket("shape", robob)

                while not int(self._send_socket("shape_mounted", [id, len(robob)])):
                    time.sleep(0.1)

            else:
                id = len(self.swift_objects)

            self.swift_objects.append(ob)

            self.swift_options[int(id)] = {
                "show_robot": show_robot,
                "show_collision": show_collision,
                "readonly": readonly,
            }

            return int(id)

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

        if isinstance(id, rtb.ERobot) or isinstance(id, Shape):

            for i in range(len(self.swift_objects)):
                if self.swift_objects[i] is not None and id == self.swift_objects[i]:
                    idd = i
                    code = "remove"
                    self.swift_objects[idd] = None
                    break
        else:
            # Number corresponding to robot ID
            idd = id
            code = "remove"
            self.robots[idd] = None

        if idd is None:
            raise ValueError(
                "the id argument does not correspond with " "a robot or shape in Swift"
            )

        self._send_socket(code, idd)

    def hold(self):  # pragma: no cover
        """
        hold() keeps the browser tab open i.e. stops the browser tab from
        closing once the main script has finished.

        """

        while True:
            time.sleep(1)

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
                "You are already recording, you can only record one video" " at a time"
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
        else:
            raise ValueError(
                "You must call swift.start_recording(file_name) before trying"
                " to stop the recording"
            )

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

    def _step_robot(self, robot, dt, readonly):

        # robot = robot_object['ob']

        robot._set_link_fk(robot.q)

        if readonly or robot._control_type == "p":
            pass  # pragma: no cover

        elif robot._control_type == "v":

            phys.step_v(
                robot._n, robot._valid_qlim, dt, robot._q, robot._qd, robot._qlim
            )

            # _v(robot._q, robot._qd, dt, robot._qlim, robot._valid_qlim)

            # for i in range(robot.n):
            #     robot.q[i] += robot.qd[i] * (dt)

            #     if np.any(robot.qlim[:, i] != 0) and \
            #             not np.any(np.isnan(robot.qlim[:, i])):
            #         robot.q[i] = np.min([robot.q[i], robot.qlim[1, i]])
            #         robot.q[i] = np.max([robot.q[i], robot.qlim[0, i]])

        elif robot.control_type == "a":
            pass

        else:  # pragma: no cover
            # Should be impossible to reach
            raise ValueError(
                "Invalid robot.control_type. " "Must be one of 'p', 'v', or 'a'"
            )

    def _step_shape(self, shape, dt):

        phys.step_shape(dt, shape.v, shape._base, shape._sT, shape._sq)
        if shape.collision:
            shape._update_pyb()

        # shape._sT[:] = shape._wT @ shape._base
        # shape._sq[:] = sm.base.r2q(shape._sT[:3, :3], order="xyzs")

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
                elif isinstance(self.swift_objects[i], rtb.Robot):
                    msg.append(
                        [
                            i,
                            self.swift_objects[i]._fk_dict(
                                self.swift_options[i]["show_robot"],
                                self.swift_options[i]["show_collision"],
                            ),
                        ]
                    )

        events = self._send_socket("shape_poses", msg, True)
        return json.loads(events)

    def _send_socket(self, code, data=None, expected=True):
        msg = [expected, [code, data]]

        self.outq.put(msg)

        if expected:
            return self.inq.get()
        else:
            return "0"

    def _pause_control(self, paused):
        # Must hold it here until unpaused
        while paused:
            time.sleep(0.1)
            events = json.loads(self._send_socket("shape_poses", []))

            if "0" in events and not events["0"]:
                paused = False
            self.process_events(events)

    def _render_control(self, rendering):
        self.rendering = rendering

    def _time_control(self, realtime):
        self._skipped = 1
        self.realtime = not realtime

    def _add_controls(self):
        self._pause_button = Button(self._pause_control)
        self._time_button = Button(self._time_control)
        self._render_button = Button(self._render_control)

        self._pause_button._id = "0"
        self._time_button._id = "1"
        self._render_button._id = "2"
        self.elements["0"] = self._pause_button
        self.elements["1"] = self._time_button
        self.elements["2"] = self._render_button
        self.elementid += 3
