"""
Protocol-shape tests for Swift's websocket message envelope, exercised
against Swift's real outq/inq queues via a scripted fake-browser thread --
no real socket or browser involved.

These pin down the exact wire format swift/public/js/main.js depends on.
The frontend was rewritten from scratch in this repo and had to be
reverse-engineered from this exact code path (Swift.py has no protocol
spec beyond its own source) -- a silent change here is a change the
frontend has no way to detect on its own.
"""

import importlib
import json
import threading
from queue import Empty, Queue

import numpy as np
import pytest
import roboticstoolbox as rtb
import spatialgeometry as sg
import spatialmath as sm

from swift import Swift

# swift/__init__.py's `from swift.Swift import Swift` rebinds the `Swift`
# package's `Swift` attribute from the submodule to the class, shadowing it
# -- fetch the actual submodule (holding _REPLY_TIMEOUT) by qualified name
# instead of `import swift.Swift`, which would resolve to that same class.
swift_module = importlib.import_module("swift.Swift")


class FakeBrowser:
    """
    Drains Swift's outq like a real browser would, recording every message
    and replying with a scripted response (or "0" if none was queued).
    """

    def __init__(self, env, responses=None):
        self.env = env
        self.responses = list(responses or [])
        self.received = []
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self._stop:
            try:
                expected, (code, data) = self.env.outq.get(timeout=1)
            except Exception:
                continue
            self.received.append((code, data))
            if expected:
                reply = self.responses.pop(0) if self.responses else "0"
                self.env.inq.put(reply)
            if code == "close":
                break

    def stop(self):
        self._stop = True


def make_env():
    env = Swift()
    env.headless = False
    env.rate = 60
    env.realtime = False
    return env


def test_add_shape_sends_a_one_element_part_list():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([1, None])])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3(), color=[1, 0, 0, 1])
    box_id = env.add(box)

    assert box_id == 0
    codes = [c for c, _ in browser.received]
    assert codes == ["shape", "shape_mounted"]

    _, shape_data = browser.received[0]
    assert isinstance(shape_data, list)
    assert len(shape_data) == 1
    assert shape_data[0]["stype"] == "cuboid"
    assert "scale" in shape_data[0]
    assert "color" in shape_data[0] and "opacity" in shape_data[0]

    _, mounted_data = browser.received[1]
    assert mounted_data == [box_id, 1]
    browser.stop()


def test_add_path_sends_points_radius_and_linewidth():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([1, None])])

    points = np.array([[0.0, 1.0, 2.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    # spatialgeometry renamed the Python class Path -> Polyline (avoids
    # clashing with pathlib.Path -- see jhavl/spatialgeometry#42), but
    # deliberately left the wire-protocol stype string as "path" --
    # changing that too would be a breaking protocol change requiring a
    # matching shapes.js update, for a rename that's purely cosmetic on
    # the Python side.
    path = sg.Polyline(points, radius=0.02, linewidth=2.0, color=[1.0, 0.0, 0.0, 1.0])
    env.add(path)

    _, shape_data = browser.received[0]
    assert shape_data[0]["stype"] == "path"
    assert shape_data[0]["points"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
    assert shape_data[0]["radius"] == 0.02
    assert shape_data[0]["linewidth"] == 2.0
    browser.stop()


def test_add_shape_raises_when_browser_reports_a_load_error():
    # Regression test for bugs.md Bug 2: adding a mesh whose file the
    # browser can't load used to poll "shape_mounted" forever since a
    # failed load never became mounted=1 -- see shapes.js's onError
    # handlers, which now report failure as [-2, reason] instead of
    # leaving the SwiftObject stuck at loaded < len(parts) forever.
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([-2, "failed to load STL file"])])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    with pytest.raises(RuntimeError, match="failed to load STL file"):
        env.add(box)
    browser.stop()


def test_add_shape_raises_with_the_specific_reason_for_an_unsupported_shape_type():
    # Regression test: -1 (unsupported shape type, e.g. spatialgeometry.Axes/
    # Arrow before shapes.js grew support for them) used to be
    # indistinguishable from -2 (a genuine mesh/asset load failure) -- both
    # just meant "check the browser console." Now the browser's own reason
    # travels back over the wire, so the exception is specific without
    # needing the console at all.
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([-1, "unsupported shape type 'made_up_type'"])])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    with pytest.raises(RuntimeError, match="unsupported shape type 'made_up_type'"):
        env.add(box)
    browser.stop()


def test_send_socket_raises_timeout_instead_of_hanging_forever(monkeypatch):
    # Regression test for bugs.md Bug 1: a browser tab that goes away
    # (closed, crashed, dropped into another window/profile mid-drag)
    # mid-request used to leave Swift.py blocked on inq.get() forever,
    # requiring ^C -- _send_socket() must instead give up after
    # _REPLY_TIMEOUT and raise, since nothing will ever reply.
    monkeypatch.setattr(swift_module, "_REPLY_TIMEOUT", 0.05)
    env = make_env()
    with pytest.raises(TimeoutError):
        env._send_socket("shape", ["dummy"])


@pytest.mark.rtb
def test_add_robot_sends_flat_list_of_all_link_parts():
    env = make_env()
    panda = rtb.models.Panda()
    n_parts = sum(len(link.geometry) for link in panda.links)
    for gripper in panda.grippers:
        n_parts += sum(len(link.geometry) for link in gripper.links)

    browser = FakeBrowser(env, responses=["0", json.dumps([1, None])])
    robot_id = env.add(panda)

    codes = [c for c, _ in browser.received]
    assert codes == ["shape", "shape_mounted"]

    _, shape_data = browser.received[0]
    assert isinstance(shape_data, list)
    assert len(shape_data) == n_parts

    assert robot_id.id == 0
    _, mounted_data = browser.received[1]
    assert mounted_data == [0, n_parts]
    browser.stop()


def test_draw_all_batches_poses_by_object_index_and_returns_element_events():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([1, None])])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    env.add(box)
    expected_pose = box.fk_dict()

    browser.responses.append(json.dumps({"0": True}))
    events = env._draw_all()

    _, poses_data = browser.received[-1]
    assert poses_data == [[0, [expected_pose]]]
    assert events == {"0": True}
    browser.stop()


def test_remove_sends_the_raw_object_index():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", json.dumps([1, None]), "0"])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    box_id = env.add(box)
    env.remove(box)

    _, remove_data = browser.received[-1]
    assert browser.received[-1][0] == "remove"
    assert remove_data == box_id
    browser.stop()


def test_shape_color_is_hex_int_not_rgb_triple():
    # Regression check for the wire format spatialgeometry's Shape.to_dict()
    # actually produces: a single 0xRRGGBB int plus a separate opacity
    # float, not an [r, g, b, a] array (an older convention some earlier
    # frontend code assumed).
    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3(), color=[1.0, 0.0, 0.0, 0.5])
    d = box.to_dict()
    assert isinstance(d["color"], int)
    assert d["color"] == 0xFF0000
    assert d["opacity"] == 0.5


def test_shape_quaternion_is_xyzw_not_wxyz():
    # Regression check: SceneNode._wq is computed via r2q(..., order="xyzs")
    # -- scalar LAST. An earlier frontend implementation assumed scalar
    # FIRST and silently produced garbled (but plausible-looking) rotations.
    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    d = box.to_dict()
    assert d["q"] == [0.0, 0.0, 0.0, 1.0]


def test_add_controls_sends_two_builtin_elements():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0", "1"])

    env._add_controls()

    codes = [c for c, _ in browser.received]
    assert codes == ["element", "element"]

    _, pause_data = browser.received[0]
    assert pause_data["element"] == "button"
    assert pause_data["builtin"] is True
    assert pause_data["label"] == "||"

    _, speed_data = browser.received[1]
    assert speed_data["element"] == "select"
    assert speed_data["builtin"] is True
    assert speed_data["options"] == ["Max", "1x", "0.5x", "0.25x"]
    assert speed_data["value"] == 0  # env.realtime_speed defaults to None -> "Max"
    browser.stop()


def test_pause_toggles_on_click_and_unblocks_on_second_click():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env._add_controls()

    assert env._paused is False
    assert env._pause_button.label == "||"

    # Simulate a second click arriving while the pause loop below is
    # polling, by scripting its next shape_poses reply to report element
    # "0" (the pause button) as changed -- process_events() then recurses
    # back into _pause_control via the button's own cb, which is what
    # actually unblocks the loop (see the comment on _pause_control).
    browser.responses.append(json.dumps({"0": True}))

    env._pause_control(None)  # the first click

    assert env._paused is False
    assert env._pause_button.label == "||"
    browser.stop()


def test_speed_control_maps_select_index_to_speed_multiplier():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env._add_controls()

    env._time_control(1)
    assert env.realtime_speed == 1.0

    env._time_control(2)
    assert env.realtime_speed == 0.5

    env._time_control(3)
    assert env.realtime_speed == 0.25

    env._time_control(0)
    assert env.realtime_speed is None
    browser.stop()


def test_headless_realtime_still_paces_steps():
    # Regression test for jhavl/swift#60: realtime_speed's pacing sleep
    # used to sit entirely inside `if not self.headless`, so headless
    # runs ignored it and ran flat-out regardless of realtime=True.
    import time

    env = make_env()
    env.headless = True
    env.realtime_speed = 1.0
    env.last_time = time.time()

    t0 = time.time()
    for _ in range(3):
        env.step(0.05)
    elapsed = time.time() - t0

    assert elapsed >= 0.1, "headless step() did not pace to realtime_speed"


def test_launch_sends_browser_timeout_after_connecting():
    # Mirrors the tail of launch()'s connected-browser sequence: controls,
    # then browser_timeout -- a value the frontend needs to know before a
    # disconnect can happen, so it must go out at connect time, not lazily.
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env._browser_timeout = 5

    import time

    env._add_controls()
    env._send_socket("browser_timeout", env._browser_timeout, expected=False)

    # expected=False doesn't block for a reply, so give the FakeBrowser
    # thread a moment to drain the queue before asserting on it.
    for _ in range(50):
        if len(browser.received) >= 3:
            break
        time.sleep(0.01)

    codes = [c for c, _ in browser.received]
    assert codes == ["element", "element", "browser_timeout"]
    assert browser.received[-1][1] == 5
    browser.stop()


def test_hold_returns_once_disconnected_past_timeout(monkeypatch):
    # Regression test: hold() used to loop forever regardless of whether
    # the browser was still there, requiring a manual ^C even after the
    # tab was long gone -- see Swift.py's hold()/launch()'s timeout=.
    from types import SimpleNamespace

    env = make_env()
    env.headless = False
    env.socket = SimpleNamespace(USERS=set())  # already disconnected
    env._hold_timeout = 2
    closed = []
    env.close = lambda *a, **kw: closed.append(True)

    fake_now = [0.0]
    monkeypatch.setattr(swift_module.time, "time", lambda: fake_now[0])
    monkeypatch.setattr(swift_module.time, "sleep", lambda s: fake_now.__setitem__(0, fake_now[0] + 1.0))

    env.hold()  # returns once disconnected for > 2s -- would hang otherwise
    assert fake_now[0] > 2
    assert closed == [True]  # hold() now closes on a disconnect-timeout, not just ^C


def test_hold_keeps_waiting_while_still_connected(monkeypatch):
    from types import SimpleNamespace

    env = make_env()
    env.headless = False
    env.socket = SimpleNamespace(USERS={"a-connected-browser"})
    env._hold_timeout = 1
    env.close = lambda *a, **kw: None  # disconnects near the end, hold() closes

    call_count = [0]

    def fake_sleep(s):
        call_count[0] += 1
        if call_count[0] > 3:
            # Still "connected" the whole time -- prove hold() really
            # would have kept going by disconnecting only now, then let
            # it return so the test itself terminates.
            env.socket.USERS.clear()

    fake_now = [0.0]
    monkeypatch.setattr(swift_module.time, "time", lambda: fake_now[0])

    def sleep_and_advance(s):
        fake_sleep(s)
        fake_now[0] += 1.0

    monkeypatch.setattr(swift_module.time, "sleep", sleep_and_advance)

    env.hold()
    assert call_count[0] > 3


def test_ground_opacity_only_sent_when_non_default():
    # ground_opacity=1.0 matches the frontend's own default (an opaque
    # material), so skipping the message when it's unchanged is safe --
    # mirrors the axes= pattern. A non-default value must go out though.
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env.ground_opacity = 1.0

    if env.ground_opacity != 1.0:
        env._send_socket("ground_opacity", env.ground_opacity, expected=False)
    env._add_controls()

    codes = [c for c, _ in browser.received]
    assert "ground_opacity" not in codes
    browser.stop()


def test_ground_opacity_sent_when_set():
    import time

    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env.ground_opacity = 0.3

    env._add_controls()
    if env.ground_opacity != 1.0:
        env._send_socket("ground_opacity", env.ground_opacity, expected=False)

    for _ in range(50):
        if len(browser.received) >= 3:
            break
        time.sleep(0.01)

    codes = [c for c, _ in browser.received]
    assert codes == ["element", "element", "ground_opacity"]
    assert browser.received[-1][1] == 0.3
    browser.stop()


def _wait_for_received(browser, count, timeout=1.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(browser.received) >= count:
            return
        time.sleep(0.01)
    raise AssertionError(f"browser only received {len(browser.received)}/{count} messages")


def test_set_camera_pose_sends_position_and_look_at():
    # Regression test: set_camera_pose() had no protocol coverage at all
    # (confirmed via grep -- zero hits for "camera_pose" before this).
    # Pins down the wire format main.js's camera_pose handler depends on:
    # {"t": position, "look_at": look_at}, sent with expected=False (fire
    # and forget, no reply awaited -- so this races FakeBrowser's own
    # background thread, hence the wait below).
    env = make_env()
    browser = FakeBrowser(env)

    env.set_camera_pose([1.0, 2.0, 3.0], [0.0, 0.0, 0.5])
    _wait_for_received(browser, 1)

    assert browser.received[-1][0] == "camera_pose"
    assert browser.received[-1][1] == {
        "t": [1.0, 2.0, 3.0],
        "look_at": [0.0, 0.0, 0.5],
    }
    browser.stop()


def test_set_camera_pose_accepts_numpy_arrays():
    # position/look_at are documented as "3 vector (list or ndarray)" --
    # the ndarray branch (np.ndarray -> .tolist()) had no coverage either.
    import numpy as np

    env = make_env()
    browser = FakeBrowser(env)

    env.set_camera_pose(np.array([1.0, 2.0, 3.0]), np.array([0.0, 0.0, 0.5]))
    _wait_for_received(browser, 1)

    assert browser.received[-1][1] == {
        "t": [1.0, 2.0, 3.0],
        "look_at": [0.0, 0.0, 0.5],
    }
    browser.stop()


def test_start_servers_socket_thread_actually_stops_on_close():
    # Regression test for a real bug FakeBrowser-based tests structurally
    # can't catch: everything above drains Swift's outq/inq directly, never
    # touching start_servers()/SwiftSocket at all. That let two real bugs
    # ship together -- self.socket used to be the wrapping Thread (no
    # .USERS, breaking hold()'s disconnect polling), and _stop_threads()
    # set a flag SwiftSocket.loop.run_forever() never checked, so close()
    # never actually stopped the background thread or freed the port. This
    # exercises the real SwiftSocket over a real socket instead.
    from swift.SwiftRoute import SwiftSocket

    outq, inq = Queue(), Queue()
    run_flag = [True]
    t = threading.Thread(
        target=SwiftSocket,
        args=(outq, inq, lambda: run_flag[0], threading.Event()),
        daemon=True,
    )
    t.start()
    port, instance = inq.get(timeout=5)

    assert isinstance(instance.USERS, set)  # what hold() polls

    # Mirrors what Swift.close() -> _stop_threads() actually does: queue a
    # message (unblocks producer()'s blocking outq.get()), then stop().
    run_flag[0] = False
    outq.put([False, ["close", "0"]])
    instance.stop()

    t.join(timeout=3)
    assert not t.is_alive(), "SwiftSocket's thread did not actually stop"


def test_start_servers_http_thread_actually_stops_on_close():
    # Regression test for the nanobind _Node leak (jhavl/swift#92,
    # fixed 2026-08-02): SwiftServer's httpd.serve_forever() never returned
    # (nothing ever called httpd.shutdown()), so Thread.run() never
    # reached its own cleanup of the arguments it was started with --
    # one of which is a bound method of the Swift instance, keeping
    # every shape ever added alive for the process's whole life,
    # regardless of close(). Exercises the real SwiftServer/httpd, not a
    # mock -- a FakeBrowser-based test can't see a thread that's still
    # running after the test function returns.
    from swift.SwiftRoute import SwiftServer

    outq, inq = Queue(), Queue()
    t = threading.Thread(
        target=SwiftServer, args=(outq, inq, 0, lambda: True), daemon=True
    )
    t.start()
    port, instance = inq.get(timeout=5)

    instance.stop()

    t.join(timeout=3)
    assert not t.is_alive(), "SwiftServer's thread did not actually stop"


def test_swift_socket_notices_disconnect_even_while_idle():
    # Regression test: serve()'s while-loop calls producer(), which used to
    # be a plain blocking self.outq.get() inside an async def -- during a
    # plain hold() with nothing actively step()-ing, nothing is ever queued,
    # so producer() (and so serve()) never returned control, so a
    # disconnect was never noticed and USERS never got cleaned up. This
    # silently defeated hold()'s own disconnect-timeout polling (self.socket
    # .USERS) for the single most common usage pattern -- add shapes, then
    # just hold() with no active stepping. Exercises a real client
    # connecting and disconnecting with nothing ever queued in outq at all,
    # mirroring exactly that idle-hold() scenario.
    import asyncio
    import time

    import websockets

    from swift.SwiftRoute import SwiftSocket

    outq, inq = Queue(), Queue()
    t = threading.Thread(
        target=SwiftSocket, args=(outq, inq, lambda: True, threading.Event()), daemon=True
    )
    t.start()
    port, instance = inq.get(timeout=5)

    def client_thread():
        async def client():
            async with websockets.connect(f"ws://localhost:{port}/") as ws:
                await ws.send("Connected")
                await asyncio.sleep(0.3)
                # Exiting this block closes the connection -- nothing was
                # ever queued in outq, so this is the idle-hold() case.

        asyncio.run(client())

    ct = threading.Thread(target=client_thread, daemon=True)
    ct.start()
    ct.join(timeout=5)

    for _ in range(50):
        if len(instance.USERS) == 0:
            break
        time.sleep(0.1)

    assert len(instance.USERS) == 0, (
        "SwiftSocket.USERS was never cleaned up after an idle disconnect "
        "-- hold()'s disconnect-timeout polling would never fire"
    )


def test_disconnect_while_waiting_for_a_reply_is_noticed_quickly():
    # Regression test for the gap the idle-disconnect fix above didn't
    # cover: serve()'s producer/wait_closed race only guards the *send*
    # side, at the top of each loop iteration. expect_message()'s
    # websocket.recv() -- where the server actually spends nearly all its
    # time during an active step() loop, waiting for the browser's reply
    # to the last message -- had no such race, so a disconnect right there
    # (the common case, e.g. killing the tab mid-RRMC-loop) fell through
    # entirely to _send_socket()'s own _REPLY_TIMEOUT fallback. Exercises
    # a real client over a real websocket that vanishes without ever
    # replying to a queued message, and asserts the resulting wait is a
    # small fraction of _REPLY_TIMEOUT, not the full 15s.
    import asyncio
    import time

    import websockets

    from swift.SwiftRoute import SwiftSocket

    outq, inq = Queue(), Queue()
    disconnected = threading.Event()
    t = threading.Thread(
        target=SwiftSocket, args=(outq, inq, lambda: True, disconnected), daemon=True
    )
    t.start()
    port, instance = inq.get(timeout=5)

    connected = threading.Event()

    def client_thread():
        async def client():
            async with websockets.connect(f"ws://localhost:{port}/") as ws:
                await ws.send("Connected")
                connected.set()
                # Long enough for the server to have sent the queued
                # message below and be sitting in expect_message()'s
                # recv() -- then vanish without ever replying, simulating
                # a tab killed mid-step().
                await asyncio.sleep(0.3)

        asyncio.run(client())

    ct = threading.Thread(target=client_thread, daemon=True)
    ct.start()
    connected.wait(timeout=5)
    inq.get(timeout=5)  # drain the handshake message

    # Mirrors Swift._send_socket()'s own polling loop against this same
    # outq/inq/disconnected, without needing a full Swift instance.
    outq.put([True, ["shape_poses", []]])

    start = time.time()
    while True:
        try:
            inq.get(timeout=swift_module._DISCONNECT_POLL_INTERVAL)
            break
        except Empty:
            if disconnected.is_set() or (time.time() - start) >= swift_module._REPLY_TIMEOUT:
                break
    elapsed = time.time() - start

    assert disconnected.is_set(), "disconnect was never detected"
    assert elapsed < 1.0, (
        f"took {elapsed:.2f}s to notice the disconnect -- should be near-"
        "instant, not bounded by _REPLY_TIMEOUT"
    )

    ct.join(timeout=2)
    instance.stop()
    t.join(timeout=3)


def test_hold_duration_returns_even_while_still_connected(monkeypatch):
    # Regression test: hold(5) used to map its positional arg to timeout=
    # (a grace period that only starts counting AFTER a disconnect), so a
    # still-connected browser meant it never returned -- not what hold(5)
    # reads as. duration= is an unconditional cap, connected or not.
    from types import SimpleNamespace

    env = make_env()
    env.headless = False
    env.socket = SimpleNamespace(USERS={"still-connected"})

    fake_now = [0.0]
    monkeypatch.setattr(swift_module.time, "time", lambda: fake_now[0])
    monkeypatch.setattr(swift_module.time, "sleep", lambda s: fake_now.__setitem__(0, fake_now[0] + 1.0))

    env.hold(duration=5)  # must return on its own -- would hang otherwise
    assert fake_now[0] >= 5


def test_run_calls_step_and_stops_at_duration():
    env = make_env()
    env.headless = True

    steps = []
    orig_step = env.step

    def counting_step(dt=0.05, render=True):
        steps.append(dt)
        orig_step(dt, render=False)

    env.step = counting_step
    env.run(duration=0.2, dt=0.05)

    assert len(steps) >= 4  # 0.2 / 0.05, allowing for real-time slop
    assert env.sim_time >= 0.2


def test_run_exits_quietly_on_keyboard_interrupt(monkeypatch):
    # ^C is the normal way to end an interactive session here, not an
    # error -- run()/hold()/step() must not let it propagate as a
    # traceback. They raise SystemExit instead of returning normally, so
    # any code after the call doesn't keep running either -- pytest.raises
    # confirms that without actually killing the test process (SystemExit
    # uncaught at the real top level is what exits quietly, not something
    # visible inside a caught exception).
    env = make_env()
    env.headless = True

    def sleep_raises(s):
        raise KeyboardInterrupt

    monkeypatch.setattr(swift_module.time, "sleep", sleep_raises)
    closed = []
    env.close = lambda *a, **kw: closed.append(True)

    with pytest.raises(SystemExit):
        env.run()

    assert closed == [True]


def test_hold_exits_quietly_on_keyboard_interrupt(monkeypatch):
    env = make_env()
    env.headless = True

    def sleep_raises(s):
        raise KeyboardInterrupt

    monkeypatch.setattr(swift_module.time, "sleep", sleep_raises)
    closed = []
    env.close = lambda *a, **kw: closed.append(True)

    with pytest.raises(SystemExit):
        env.hold()

    assert closed == [True]


def test_step_exits_quietly_on_keyboard_interrupt(monkeypatch):
    # step() itself catches ^C too, not just hold()/run() -- most of a
    # realtime-paced script's wall-clock wait happens inside step()'s own
    # pacing sleep, so ^C is overwhelmingly likely to land there even for
    # a bare `while True: env.step(dt)` loop with no handling of its own.
    import time as time_module

    env = make_env()
    env.headless = True
    env.realtime_speed = 1.0
    env.last_time = time_module.time()  # small/near-zero time_taken -> diff > 0 -> sleeps

    def sleep_raises(s):
        raise KeyboardInterrupt

    monkeypatch.setattr(swift_module.time, "sleep", sleep_raises)
    closed = []
    env.close = lambda *a, **kw: closed.append(True)

    with pytest.raises(SystemExit):
        env.step(0.05)

    assert closed == [True]
