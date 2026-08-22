#!/usr/bin/env python
"""Box and slider controlled sphere, demonstrate collision detection."""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift
from swift.Elements import Slider, Label

env = Swift()
env.launch(realtime=True, ground_opacity=0.1)

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0), color="blue") # blue box at origin
env.add_shape(box)


def sphere_pose(t, values):
    # print(values)
    return SE3(values["x"], 0, 0)

sphere = sg.Sphere(0.1, pose=SE3(0.5, 0, 0.1), color="green") # green sphere
env.add_shape(sphere, callback=sphere_pose)

env.add_ui(Slider(lambda v: None, min=-2, max=2, step=0.01, value=0.5, desc="Sphere X", unit="m"), name="x")
env.add_ui((distance := Label("")), name="label")

while True:
    env.step(0.05)
    d, p1, p2 = box.closest_point(sphere)
    distance.desc = f"Distance: {d:.3f}"
    if d < 0.1:
        # print(f"Collision detected: distance={d:.3f}, p1={p1}, p2={p2}")
        box.color = "red"  # change box color to red
        sphere.color = "red"  # change sphere color to red
    else:
        box.color = "blue"  # change box color back to blue
        sphere.color = "green"  # change sphere color back to green
