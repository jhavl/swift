"""
Tests for AssemblyHandle -- the per-instance joint state env.add_robot()/
env.add_assembly() return, and (for a robot handle) its backward-compat
bridge for the deprecated pattern of mutating robot.q/robot.qd directly.
See tech-debt.md.
"""

import warnings

import numpy as np
import pytest
import roboticstoolbox as rtb
import spatialgeometry as sg
from spatialmath import SE3

from swift import Swift, AssemblyHandle


def make_env():
    env = Swift()
    env.headless = True
    return env


def test_add_robot_returns_a_handle_with_independent_state():
    env = make_env()
    panda = rtb.models.Panda()

    handle1 = env.add_robot(panda)
    handle2 = env.add_robot(panda)

    assert isinstance(handle1, AssemblyHandle)
    assert handle1.robot is panda
    assert handle2.robot is panda

    handle1.q = panda.qr
    handle2.q = panda.qz

    assert not np.array_equal(handle1.q, handle2.q)


def test_setting_handle_q_drives_part_poses():
    env = make_env()
    panda = rtb.models.Panda()
    handle = env.add_robot(panda)

    handle.q = panda.qz
    poses_zero = handle.part_poses()

    handle.q = panda.qr
    poses_ready = handle.part_poses()

    assert not np.allclose(poses_zero[-1].t, poses_ready[-1].t)


def test_legacy_direct_mutation_still_works_but_warns_once():
    env = make_env()
    panda = rtb.models.Panda()
    handle = env.add_robot(panda)

    with pytest.warns(DeprecationWarning):
        panda.q = panda.qr
        handle._sync_legacy()

    assert np.array_equal(handle.q, panda.q)

    # Second legacy mutation: state still adopted, but no further warning.
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        panda.q = panda.qz
        handle._sync_legacy()
    assert len(record) == 0
    assert np.array_equal(handle.q, panda.q)


def test_new_style_usage_never_warns():
    env = make_env()
    panda = rtb.models.Panda()
    handle = env.add_robot(panda)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        handle.q = panda.qr
        handle._sync_legacy()
    assert len(record) == 0


def test_control_mode_validation():
    env = make_env()
    panda = rtb.models.Panda()
    handle = env.add_robot(panda)

    handle.control_mode = "p"
    assert handle.control_mode == "p"

    with pytest.raises(ValueError):
        handle.control_mode = "bogus"


def test_add_assembly_bare_fk_no_robot():
    env = make_env()

    link1 = sg.Cuboid([0.3, 0.03, 0.03])
    link2 = sg.Cuboid([0.25, 0.03, 0.03])

    def fk(q):
        j1 = SE3.Rz(q[0])
        j2 = j1 * SE3.Tx(0.3) * SE3.Rz(q[1])
        return [j1 * SE3.Tx(0.15), j2 * SE3.Tx(0.125)]

    handle = env.add_assembly(fk, [link1, link2], q0=[0.0, 0.0])

    assert isinstance(handle, AssemblyHandle)
    assert handle.robot is None
    assert handle.control_mode == "p"  # bare assemblies default to position control

    handle.q = np.array([np.pi / 2, 0.0])
    poses = handle.part_poses()
    assert len(poses) == 2
    assert np.allclose(poses[0].t, [0, 0.15, 0], atol=1e-9)


def test_add_assembly_velocity_mode_needs_a_robot():
    env = make_env()
    link1 = sg.Cuboid([0.1, 0.1, 0.1])
    handle = env.add_assembly(lambda q: [SE3()], [link1], q0=[0.0])
    handle.control_mode = "v"

    with pytest.raises(ValueError):
        env._step_assembly(handle, 0.05)


def test_assembly_callback_drives_q_each_step():
    env = make_env()
    link1 = sg.Cuboid([0.1, 0.1, 0.1])

    calls = []

    def callback(t, values):
        calls.append((t, dict(values)))
        return [t]

    handle = env.add_assembly(lambda q: [SE3.Tx(q[0])], [link1], q0=[0.0], callback=callback)

    env.step(0.1)
    assert handle.q[0] == pytest.approx(0.1)
    env.step(0.1)
    assert handle.q[0] == pytest.approx(0.2)
    assert [t for t, _ in calls] == [pytest.approx(0.1), pytest.approx(0.2)]


def test_shape_callback_drives_pose_each_step():
    env = make_env()
    box = sg.Cuboid([0.1, 0.1, 0.1])
    env.add_shape(box, callback=lambda t, values: SE3.Tx(t))

    env.step(0.1)
    assert np.allclose(np.array(box.T)[:3, 3], [0.1, 0, 0])


def test_named_slider_pushes_into_values():
    from swift.SwiftElement import Slider

    env = make_env()
    slider = Slider(lambda v: None, min=0, max=10, value=3)
    env.add_ui(slider, name="q1")

    assert env.values["q1"] == 3
    slider.value = 7
    assert env.values["q1"] == 7

    # Browser-driven updates (process_events -> element.update()) bypass
    # the value property setter -- must still push, or dragging a slider
    # in the browser would never reach a per-step callback's `values`.
    slider.update(9)
    assert env.values["q1"] == 9


def test_show_does_not_raise(capsys):
    env = make_env()
    box = sg.Cuboid([0.1, 0.1, 0.1])
    env.add_shape(box, name="my box")
    panda = rtb.models.Panda()
    env.add_robot(panda, name="panda")

    env.show()
    out = capsys.readouterr().out
    assert "my box" in out
    assert "panda" in out
