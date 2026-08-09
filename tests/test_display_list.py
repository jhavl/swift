"""
Tests for Swift's display list -- __repr__()/show()'s per-object
description, and __getitem__() lookup by id or by name=.
"""

import pytest
import roboticstoolbox as rtb
import spatialgeometry as sg

from swift import Swift


def make_env():
    env = Swift()
    env.headless = True
    return env


def test_getitem_by_id_returns_the_same_object():
    env = make_env()
    shape = sg.Sphere(0.2)
    id_ = env.add_shape(shape)

    assert env[id_] is shape


def test_getitem_by_name_returns_the_same_object():
    env = make_env()
    shape = sg.Sphere(0.2)
    env.add_shape(shape, name="ball")

    assert env["ball"] is shape


def test_getitem_unnamed_object_not_reachable_by_any_name():
    env = make_env()
    env.add_shape(sg.Sphere(0.2))

    with pytest.raises(KeyError):
        env["ball"]


def test_getitem_missing_name_raises_keyerror():
    env = make_env()

    with pytest.raises(KeyError):
        env["nope"]


def test_getitem_removed_id_raises_keyerror():
    env = make_env()
    id_ = env.add_shape(sg.Sphere(0.2))
    env.remove(id_)

    with pytest.raises(KeyError):
        env[id_]


def test_getitem_out_of_range_id_raises_keyerror():
    env = make_env()

    with pytest.raises(KeyError):
        env[123]


def test_describe_uses_shape_repr_not_bare_type_name():
    env = make_env()
    shape = sg.Sphere(0.2)
    id_ = env.add_shape(shape)

    assert env._describe(id_, shape) == f"[{id_}] {shape!r}"


@pytest.mark.rtb
def test_repr_lists_robot_links_indented_under_the_assembly():
    env = make_env()
    panda = rtb.models.Panda()
    handle = env.add_robot(panda, name="panda")

    text = repr(env)

    assert f'"panda"' in text
    for link in panda.links:
        assert link.name in text
    # links appear after (indented under) their AssemblyHandle line
    assert text.index(panda.links[0].name) > text.index("AssemblyHandle")
