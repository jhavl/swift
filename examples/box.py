#!/usr/bin/env python
"""Render a single blue box -- the simplest possible Swift scene."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.1), color=[0.2, 0.4, 1.0, 1.0])
env.add_shape(box)

env.hold()  # keep the browser tab open
