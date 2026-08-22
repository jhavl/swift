#!/usr/bin/env python
"""
A minimal 2-link, 2-revolute-joint "robot" built directly from two
elongated cuboids -- no roboticstoolbox.Robot involved.

TwoLinkArm.part_poses(q) is a pure forward-kinematics function: given q,
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


class TwoLinkArm:
    """A pure kinematic model: two links, two revolute joints about z."""

    def __init__(self, L1=0.3, L2=0.25, thickness=0.03):
        self.L1 = L1
        self.L2 = L2
        self.link1 = sg.Cuboid([L1, thickness, thickness], color=[0.8, 0.2, 0.2, 1.0])
        self.link2 = sg.Cuboid([L2, thickness, thickness], color=[0.2, 0.4, 1.0, 1.0])

    def part_poses(self, q) -> list[SE3]:
        """World pose of each link, purely as a function of q. Each
        cuboid's local origin sits at its own proximal (joint) end, so
        Tx(length / 2) places its centre correctly."""
        joint1 = SE3.Rz(q[0])
        joint2 = joint1 * SE3.Tx(self.L1) * SE3.Rz(q[1])
        return [joint1 * SE3.Tx(self.L1 / 2), joint2 * SE3.Tx(self.L2 / 2)]


arm = TwoLinkArm()
handle = env.add_assembly(
    arm.part_poses,
    [arm.link1, arm.link2],
    q0=[0.0, 0.0],
    callback=lambda t, values: [values["q1"], values["q2"]],
)

env.add_ui(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 1", unit="rad"), name="q1")
env.add_ui(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 2", unit="rad"), name="q2")

while True:
    env.step(0.05)
