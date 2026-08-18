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
from swift import Swift

env = Swift()
env.launch(realtime=True)

W = 0.1
box = sg.Cuboid([W, W, W], color=[0.2, 0.4, 1.0, 1.0])


def orbit(t, values):
    return sm.SE3.Rx(t / 10) * sm.SE3.Rz(t) * sm.SE3.Tx(3 * W)


env.add_shape(box, callback=orbit)

dt = 0.02
while True:
    env.step(dt)
