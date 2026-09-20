"""
Swift must work with roboticstoolbox (RTB) unimportable.

The dependency is strictly one way: RTB depends on swift, never the reverse.
tests/conftest.py blocks the import for the whole session; these tests
confirm the block is in effect and that swift's public entry points still
work under it -- so a regression (an ``import roboticstoolbox`` creeping
back into swift's source) fails here, on any machine, whether or not RTB is
installed.

What this does not cover: that swift works *with* a real RTB robot. That is
verified by RTB's own CI, which installs swift and runs its Swift-backend
tests (see tests/fake_robot.py).
"""

import pytest

from swift import Swift
from tests.fake_robot import FakeRobot


def test_roboticstoolbox_is_unimportable_in_this_suite():
    # If this fails the guard in conftest.py is gone, and every other test's
    # "no RTB" property is unverified.
    with pytest.raises(ImportError):
        import roboticstoolbox  # noqa: F401


def test_swift_constructs_and_adds_a_robot_without_rtb():
    env = Swift()
    env.headless = True
    handle = env.add(FakeRobot())  # dispatched by interface, not by RTB type
    assert handle.robot is not None
    env.remove(handle.robot)  # found by identity, no RTB type check
    assert env.swift_objects[handle.id] is None
