"""
Tests for the comm transport's Python end (swift/_comm.py and Swift's comm
path), with a list standing in for the widget that carries messages to the
browser. No kernel, widget or browser is involved: what these pin down is the
wire format public/js/main.js depends on, and that nothing on this path
waits for a reply (see _comm.py for why).
"""

import json

import pytest
import spatialgeometry as sg
import spatialmath as sm

from swift import Swift
from swift._comm import CommBridge


def make_bridge():
    sent: list[dict] = []
    return CommBridge(sent.append), sent


def make_env():
    bridge, sent = make_bridge()
    env = Swift()
    env._attach_comm(bridge)
    return env, bridge, sent


def codes(sent):
    return [m["func"] for m in sent]


def test_send_pushes_func_and_data_and_replies_with_a_constant():
    bridge, sent = make_bridge()

    assert bridge.send("axes", False) == "0"
    assert sent == [{"func": "axes", "data": False}]


def test_shape_poses_returns_the_ui_events_since_the_last_call():
    bridge, _ = make_bridge()
    bridge.receive({"reply": {"event": "ui", "changes": {"3": 0.5}}})
    bridge.receive({"reply": {"event": "ui", "changes": {"4": True}}})

    assert json.loads(bridge.send("shape_poses", [])) == {"3": 0.5, "4": True}
    assert json.loads(bridge.send("shape_poses", [])) == {}


def test_connected_handshake_makes_the_bridge_ready():
    bridge, _ = make_bridge()
    assert not bridge.ready

    # the browser sends the same JSON string it sends over the websocket
    bridge.receive({"reply": json.dumps({"event": "connected", "js_hashes": None})})

    assert bridge.ready


def test_load_error_is_raised_once_by_the_next_send():
    bridge, _ = make_bridge()
    bridge.receive({"reply": {"event": "error", "id": 2, "code": -2, "reason": "bad mesh"}})

    with pytest.raises(RuntimeError, match="object 2.*bad mesh"):
        bridge.send("axes", True)
    bridge.send("axes", True)  # reported once, not on every call after


def test_close_does_not_raise_a_pending_load_error():
    bridge, sent = make_bridge()
    bridge.receive({"reply": {"event": "error", "id": 0, "code": -2, "reason": "bad mesh"}})

    bridge.send("close", "0")

    assert codes(sent) == ["close"]


@pytest.mark.parametrize("content", [{}, {"reply": 5}, {"reply": "not json"}, {"reply": {"event": "unknown"}}])
def test_receive_ignores_what_it_does_not_understand(content):
    bridge, _ = make_bridge()
    bridge.receive(content)
    assert not bridge.ready and bridge.error is None


def test_attach_comm_sends_the_initial_controls():
    _, _, sent = make_env()

    assert "element" in codes(sent)  # pause / speed controls
    assert codes(sent)[-1] == "browser_timeout"


def test_add_shape_assigns_the_id_in_python_and_does_not_wait():
    env, _, sent = make_env()
    sent.clear()

    box = sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3())
    first = env.add(box)
    second = env.add(sg.Cuboid([0.2, 0.2, 0.2], pose=sm.SE3()))

    assert (first, second) == (0, 1)
    assert codes(sent) == ["shape", "shape"]  # no shape_mounted poll
    assert sent[0]["data"]["id"] == 0 and sent[1]["data"]["id"] == 1
    assert sent[0]["data"]["parts"][0]["stype"] == "cuboid"


def test_the_load_error_a_browser_reports_is_raised_by_the_next_call():
    env, bridge, _ = make_env()
    env.add(sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3()))

    bridge.receive({"reply": {"event": "error", "id": 0, "code": -2, "reason": "failed to load STL file"}})

    with pytest.raises(RuntimeError, match="failed to load STL file"):
        env.add(sg.Cuboid([0.1, 0.1, 0.1], pose=sm.SE3()))


def test_ready_is_true_on_the_desktop_and_follows_the_bridge_in_a_notebook():
    assert Swift().ready is True

    env, bridge, _ = make_env()
    assert env.ready is False
    bridge.receive({"reply": json.dumps({"event": "connected", "js_hashes": None})})
    assert env.ready is True


def test_close_sends_close_and_starts_no_threads_to_stop():
    env, _, sent = make_env()

    env.close()

    assert codes(sent)[-1] == "close"
