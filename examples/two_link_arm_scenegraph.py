#!/usr/bin/env python
"""
A minimal 2-link, 2-revolute-joint "robot" built directly from two elongated cuboids --
no roboticstoolbox.Robot involved.

This variant uses scene graph primitives.  Each link is a child of the previous link, so
moving the first link moves the second link too.  The scene graph is built by setting
the ``scene_parent`` attribute of each child shape to its parent shape.
"""
import numpy as np
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift, Slider

env = Swift()
env.launch(realtime=True)

L1, L2, thickness = 0.3, 0.25, 0.03

link1 = sg.Cuboid([L1, thickness, thickness], color="red")
link2 = sg.Cuboid([L2, thickness, thickness], color="blue")

link2.scene_parent = link1

env.add_shape(link1, callback=lambda t, values: SE3.Rz(values["q1"]) * SE3.Tx(L1/2))
env.add_shape(link2, callback=lambda t, values: SE3.Tx(L1/2) * SE3.Rz(values["q2"]) * SE3.Tx(L2/2))

env.add_ui(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, label="Joint 1", unit="rad"), name="q1")
env.add_ui(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, label="Joint 2", unit="rad"), name="q2")

env.show()

print(link1.tree())  # prints the scene graph tree for debugging

env.run(dt=0.02) # run forever at 50 fps
