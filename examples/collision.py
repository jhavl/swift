#!/usr/bin/env python
"""Render a single blue box -- the simplest possible Swift scene."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift
from swift.SwiftElement import Slider

env = Swift()
env.launch(realtime=True, ground_opacity=0.1)

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0), color=[0.2, 0.4, 1.0, 1.0]) # blue box at origin
env.add_shape(box)


def sphere_pose(t, values):
    # print(values)
    return SE3(values["x"], 0, 0)

sphere = sg.Sphere(0.1, pose=SE3(0.5, 0, 0.1), color=[0.2, 1.0, 0.4, 1.0]) # green sphere
env.add_shape(sphere, callback=sphere_pose)

env.add_ui(Slider(lambda v: None, min=-2, max=2, step=0.01, value=0.0, desc="Sphere X", unit="m"), name="x")


while True:
    env.step(0.05)
    d, p1, p2 = box.closest_point(sphere)
    if d < 0.1:
        # print(f"Collision detected: distance={d:.3f}, p1={p1}, p2={p2}")
        box.color = [1.0, 0.2, 0.2, 1.0]  # change box color to red
        sphere.color = [1.0, 0.2, 0.2, 1.0]  # change sphere color to red
    else:
        box.color = [0.2, 0.4, 1.0, 1.0]  # change box color back to blue
        sphere.color = [0.2, 1.0, 0.4, 1.0]  # change sphere color back to green
