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
    browser = FakeBrowser(env, responses=["0", "1"])

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


def test_add_shape_raises_when_browser_reports_a_load_error():
    # Regression test for bugs.md Bug 2: adding a mesh whose file the
    # browser can't load used to poll "shape_mounted" forever since a
    # failed load never became mounted=1 -- see shapes.js's onError
    # handlers, which now report failure as -1 instead of leaving the
    # SwiftObject stuck at loaded < len(parts) forever.
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "-1"])

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    with pytest.raises(RuntimeError, match="failed to load"):
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


def test_add_robot_sends_flat_list_of_all_link_parts():
    env = make_env()
    panda = rtb.models.Panda()
    n_parts = sum(len(link.geometry) for link in panda.links)
    for gripper in panda.grippers:
        n_parts += sum(len(link.geometry) for link in gripper.links)

    browser = FakeBrowser(env, responses=["0", "1"])
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
    browser = FakeBrowser(env, responses=["0", "1"])

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
    browser = FakeBrowser(env, responses=["0", "1", "0"])

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
    assert pause_data["desc"] == "||"

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
    assert env._pause_button.desc == "||"

    # Simulate a second click arriving while the pause loop below is
    # polling, by scripting its next shape_poses reply to report element
    # "0" (the pause button) as changed -- process_events() then recurses
    # back into _pause_control via the button's own cb, which is what
    # actually unblocks the loop (see the comment on _pause_control).
    browser.responses.append(json.dumps({"0": True}))

    env._pause_control(None)  # the first click

    assert env._paused is False
    assert env._pause_button.desc == "||"
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
