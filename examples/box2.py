#!/usr/bin/env python
"""Render a single blue box and specify its pose."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(ground_pattern="@tile")

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.2)*SE3.RPY(45, 45, 0, unit="deg"), color="blue")
env.add_shape(box)

env.hold()  # keep the browser tab open
