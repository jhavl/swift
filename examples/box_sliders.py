#!/usr/bin/env python
"""Render a blue box, with sliders to control its x/y/z position.

The Z slider controls height above the floor (the box's bottom face),
not its centre -- so Z=0 always means "resting on the ground" and the
box can never clip through the floor, whatever the slider range.

Named sliders (name=...) push their value into env.values -- a
per-step callback reads them from there, so there's no need to write a
setter function per slider.
"""
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift, Slider

env = Swift()
env.launch(realtime=True, ground_opacity=0.5)

SIDE = 0.2
box = sg.Cuboid([SIDE, SIDE, SIDE], pose=SE3(0, 0, SIDE / 2), color=[0.2, 0.4, 1.0, 1.0])


def box_pose(t, values):
    # z is height above the floor, not the box centre
    print(values)
    return SE3(values["x"], values["y"], values["z"] + SIDE / 2)


env.add_shape(box, callback=box_pose)

env.add_ui(Slider(min=-0.5, max=0.5, step=0.01, value=0.0, label="Box X", unit="m"), name="x")
env.add_ui(Slider(min=-0.5, max=0.5, step=0.01, value=0.0, label="Box Y", unit="m"), name="y")
env.add_ui(Slider(min=0.0, max=0.6, step=0.01, value=0.0, label="Box Z", unit="m"), name="z")

while True:
    env.step(0.05)
