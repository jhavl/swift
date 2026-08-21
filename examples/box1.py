#!/usr/bin/env python
"""Render a single blue box -- the simplest possible Swift scene."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(ground_opacity=0.5)

box = sg.Cuboid([0.2, 0.2, 0.2], color="blue")
env.add_shape(box)

env.hold()  # keep the browser tab open
