#!/usr/bin/env python
"""Render a set of axes."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

axes = sg.Axes(1, pose=SE3(0.2, 0.3, 0.4), arrows=True, radius=0.01)
env.add_shape(axes)

env.hold()  # keep the browser tab open
