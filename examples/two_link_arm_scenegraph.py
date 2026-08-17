#!/usr/bin/env python
"""
A minimal 2-link, 2-revolute-joint "robot" built directly from two
elongated cuboids -- no roboticstoolbox.Robot involved.

This variant uses scene graph primitives.TwoLinkArm.part_poses(q) is a pure forward-kinematics function: given q,
it returns one world-frame pose per part. Passed straight to
env.add_assembly() along with its two parts, swift builds and owns the
handle -- the exact same AssemblyHandle env.add_robot() returns for an
rtb.Robot, just constructed from a bare function instead of a robot
model. That's the whole leap from this to a real robot: a kinematic
model with more than two links, and swift building the handle instead
of you calling add_assembly() by hand.
"""
import numpy as np
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift, Slider

env = Swift()
env.launch(realtime=True)

L1=0.3
L2=0.25
thickness=0.03

def cb(t, values):
    print(f"t={t:.2f}, q1={values['q1']:.2f}, q2={values['q2']:.2f}")

link1 = sg.Cuboid([L1, thickness, thickness], color=[0.8, 0.2, 0.2, 1.0])
link2 = sg.Cuboid([L2, thickness, thickness], color=[0.2, 0.4, 1.0, 1.0])

link2.scene_parent = link1

def cb1(t, values):
    return SE3.Rz(values["q1"]) * SE3.Tx(L1/2)

def cb2(t, values):
    return SE3.Tx(L1/2) * SE3.Rz(values["q2"]) * SE3.Tx(L2/2)

env.add_shape(link1, callback=cb1)
# env.add_shape(link1, callback=lambda *x: print(x))
env.add_shape(link2, callback=cb2)

    # def part_poses(self, q) -> list[SE3]:
    #     """World pose of each link, purely as a function of q. Each
    #     cuboid's local origin sits at its own proximal (joint) end, so
    #     Tx(length / 2) places its centre correctly."""
    #     joint1 = SE3.Rz(q[0])
    #     joint2 = joint1 * SE3.Tx(self.L1) * SE3.Rz(q[1])
    #     return [joint1 * SE3.Tx(self.L1 / 2), joint2 * SE3.Tx(self.L2 / 2)]

env.add_ui(Slider(lambda v: None, min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 1", unit="rad"), name="q1")
env.add_ui(Slider(lambda v: None, min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 2", unit="rad"), name="q2")

env.show()

while True:
    env.step(0.05)
