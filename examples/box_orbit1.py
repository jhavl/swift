#!/usr/bin/env python
"""
Programmatic pose control: a box orbits the origin on a circle of
radius 3*W (W = box width), while the plane of that circle slowly
tilts about the x-axis.

T(t) = SE3.Rx(t/10) * SE3.Rz(t) * SE3.Tx(3*W)

Tx(3W) places the box at the orbit radius; Rz(t) spins it around the
circle; Rx(t/10), applied last (so in the world frame), tilts the
whole orbital plane about x -- ten times slower than the orbit itself.

A per-step callback computes and returns the pose directly -- swift
owns t and calls it each env.step(), so there's no manual box.T
assignment in the loop.
"""
import spatialgeometry as sg
import spatialmath as sm
import numpy as np
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True, ground_opacity=0.5)

W = 0.1 # size of the box
box = sg.Cuboid([W, W, W], color="blue")
env.add_shape(box)

# animate
dt = 0.02   # time step, 50 fps
for t in np.arange(0, 20, dt):  # run for 5 seconds
    print(f"t = {t:.2f}")
    box.T = sm.SE3.Rx(t / 10) * sm.SE3.Rz(t) * sm.SE3.Tx(3 * W)
    env.step(dt)
env.hold()  # keep the browser tab open