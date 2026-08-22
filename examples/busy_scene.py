#!/usr/bin/env python
"""Render a scene with many objects using Swift."""
from pathlib import Path

import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift
import numpy as np

# The /retrieve/ mechanism (used for mesh files and ground_pattern texture
# paths) requires an absolute path -- derived from this script's own
# location, not the current working directory, so it works regardless of
# where you run it from.
ASSETS = Path(__file__).parent / "assets"

env = Swift()
env.launch(realtime=True, ground_pattern=str(ASSETS / "gravel.jpg"))

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.2)*SE3.RPY(45, 45, 0, unit="deg"), color=[0.2, 0.4, 1.0, 1.0])
sphere = sg.Sphere(0.3, pose=SE3(0.8, 0, 0.1), color=[0.2, 1.0, 0.4, 1.0])

print(str(box))
print(repr(box))

env.add_shape(box)
env.add_shape(sphere)

stack1 = sg.Sphere(0.3, pose=SE3(-0.5, -0.5, 0.3), color=[0.55, 0.55, 0.53, 1.0])  # granite
stack2 = sg.Cuboid([0.3, 0.3, 0.3], pose=SE3(-0.5, -0.5, 0.75), color=[0.44, 0.49, 0.53, 1.0])  # slate
stack3 = sg.Sphere(0.2, pose=SE3(-0.5, -0.5, 1.1), color=[0.72, 0.66, 0.52, 1.0])  # sandstone
stack4 = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(-0.5, -0.5, 1.4)*SE3.Rz(45, "deg"), color=[0.30, 0.29, 0.28, 1.0])  # basalt

env.add_shape(stack1)
env.add_shape(stack2)
env.add_shape(stack3)
env.add_shape(stack4)

print(stack1)
print(repr(stack1))

env.show()

# small cylinder and arrow
cyl = sg.Cylinder(0.15, 2.5, pose=SE3(0.5, 0.5, 1.25), color=[1.0, 0.4, 0.2, 0.9])
env.add_shape(cyl)

arrow = sg.Arrow(1, pose=SE3.Rx(-90, "deg") * SE3.Ry(45, "deg") * SE3(0, -0.6, 0.2), radius=0.01, color=[0.2, 0.4, 1.0, 1.0])
env.add_shape(arrow)

# large cyclinder half above ground
cyl = sg.Cylinder(1, 0.2, pose=SE3.Rx(90, "deg") *SE3(0.5, 0, 1.2), color=[1.0, 0.4, 0.2, 0.3])
env.add_shape(cyl)


mesh = sg.Mesh(str(ASSETS / "robot.glb"), pose=SE3(-0.5, 0.5, 0.42)*SE3.Rx(90, "deg"), color=[1.0, 1.0, 0.2, 1.0])
env.add(mesh)

s=0.15
mesh = sg.Mesh(str(ASSETS / "spitfire.glb"), scale=[s,s,s], pose=SE3(-0.5, 0, 2)*SE3.Rx(60, "deg"), color=[1.0, 0.4, 0.2, 1.0])
env.add(mesh)

points = []
for i in range(101):
    theta = i * 2 * np.pi / 100
    x = 0.7 * np.cos(theta)
    y = 0.7 * np.sin(theta)
    points.append((x, y, 0))

ring = sg.Path(np.array(points).T, radius=0.05, pose=SE3(0.5, 0.5,1.2)*SE3.Rx(45, "deg"), color=[1.0, 1.0, 0.2, 1.0])
env.add_shape(ring)

env.hold()  # keep the browser tab open