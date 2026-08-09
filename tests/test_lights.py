"""
Tests for the configurable lighting API -- Light subclasses' to_dict(),
and the "lights" wire message from launch(lights=)/set_lights().
"""

import importlib

import pytest

from swift import AmbientLight, DirectionalLight, HemisphereLight, Light, PointLight, SpotLight, Swift

swift_module = importlib.import_module("swift.Swift")

from tests.test_protocol import FakeBrowser, _wait_for_received  # noqa: E402


def make_env():
    env = Swift()
    env.headless = False
    env.rate = 60
    env.realtime = False
    return env


def test_ambient_light_to_dict():
    assert AmbientLight(color=[1.0, 0.5, 0.0], intensity=0.5).to_dict() == {
        "ltype": "ambient",
        "color": 0xFF7F00,
        "intensity": 0.5,
    }


def test_hemisphere_light_to_dict():
    d = HemisphereLight(sky_color=[1.0, 1.0, 1.0], ground_color=[0.0, 0.0, 0.0], intensity=0.8).to_dict()
    assert d == {
        "ltype": "hemisphere",
        "sky_color": 0xFFFFFF,
        "ground_color": 0x000000,
        "intensity": 0.8,
    }


def test_directional_light_to_dict():
    d = DirectionalLight(
        position=[1.0, -1.0, 1.0], target=[0.0, 0.0, 0.5], cast_shadow=True, color=[1, 1, 1], intensity=1.35
    ).to_dict()
    assert d == {
        "ltype": "directional",
        "color": 0xFFFFFF,
        "intensity": 1.35,
        "position": [1.0, -1.0, 1.0],
        "target": [0.0, 0.0, 0.5],
        "cast_shadow": True,
    }


def test_point_light_to_dict():
    d = PointLight(position=[0.6, -0.6, 1.0], distance=5.0, decay=2.0, cast_shadow=False, color=[1, 0, 0]).to_dict()
    assert d == {
        "ltype": "point",
        "color": 0xFF0000,
        "intensity": 1.0,
        "position": [0.6, -0.6, 1.0],
        "distance": 5.0,
        "decay": 2.0,
        "cast_shadow": False,
    }


def test_spot_light_to_dict():
    d = SpotLight(position=[1, 1, 1], target=[0, 0, 0], angle=0.4, penumbra=0.1, cast_shadow=True).to_dict()
    assert d["ltype"] == "spot"
    assert d["angle"] == 0.4
    assert d["penumbra"] == 0.1
    assert d["cast_shadow"] is True


def test_set_lights_sends_serialized_lights():
    env = make_env()
    browser = FakeBrowser(env)

    lights = [AmbientLight(intensity=0.3), PointLight(position=[1, 0, 0])]
    env.set_lights(lights)
    _wait_for_received(browser, 1)

    assert browser.received[-1][0] == "lights"
    assert browser.received[-1][1] == [light.to_dict() for light in lights]
    browser.stop()


def test_set_lights_does_nothing_when_headless():
    env = make_env()
    env.headless = True

    # No browser/socket at all in headless mode -- this must not attempt
    # to send anything (would raise/hang if it tried), but env.lights
    # should still be updated.
    lights = [AmbientLight()]
    env.set_lights(lights)
    assert env.lights is lights


def test_launch_lights_none_sends_nothing():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    env.lights = None

    env._add_controls()
    if env.lights is not None:
        env.set_lights(env.lights)

    codes = [c for c, _ in browser.received]
    assert "lights" not in codes
    browser.stop()


def test_launch_lights_sent_when_given():
    env = make_env()
    browser = FakeBrowser(env, responses=["0", "0"])
    lights = [DirectionalLight()]
    env.lights = lights

    env._add_controls()
    if env.lights is not None:
        env.set_lights(env.lights)

    _wait_for_received(browser, 3)
    codes = [c for c, _ in browser.received]
    assert codes == ["element", "element", "lights"]
    assert browser.received[-1][1] == [lights[0].to_dict()]
    browser.stop()
