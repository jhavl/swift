#!/usr/bin/env python
"""
Panda arm follows a target box, positioned by xyz sliders.

Moving the sliders moves the (visual-only) box; on every step the arm
runs resolved-rate motion control (p_servo) towards the box's current
pose, so it continuously "chases" wherever the box is.

Named sliders push their value into env.values; per-step callbacks
read from there and return the new pose/q -- there's no explicit
per-slider setter function, and no manual pose/q assignment in the
loop, env.step() drives everything.
"""
import numpy as np
import roboticstoolbox as rtb
import spatialgeometry as sg
import spatialmath as sm
from swift import Swift, Slider

env = Swift()
env.launch(realtime=True)
dt = 0.05

panda = rtb.models.Panda()
handle = env.add_robot(panda)
handle.q = panda.qr

SIDE = 0.05
X0, Y0, Z0 = 0.5, 0.0, 0.3  # initial target position; z is height above the floor

# The gripper points straight down at the target
target_orientation = sm.SE3.Rx(np.pi)

target = sg.Cuboid(
    [SIDE, SIDE, SIDE],
    pose=sm.SE3(X0, Y0, Z0 + SIDE / 2) * target_orientation,
    color=[0.2, 0.4, 1.0, 1.0],
)


def target_pose(t, values):
    return sm.SE3(values["x"], values["y"], values["z"] + SIDE / 2) * target_orientation


env.add_shape(target, callback=target_pose)


def track_target(t, values):
    v, _ = rtb.p_servo(panda.fkine(handle.q), target.T, gain=1.0, threshold=0.01)
    qd = np.linalg.pinv(panda.jacobe(handle.q)) @ v
    return handle.q + qd * dt


handle.callback = track_target

env.add_ui(Slider(min=0.2, max=0.7, step=0.01, value=X0, desc="Target X", unit="m"), name="x")
env.add_ui(Slider(min=-0.4, max=0.4, step=0.01, value=Y0, desc="Target Y", unit="m"), name="y")
env.add_ui(Slider(min=0.05, max=0.6, step=0.01, value=Z0, desc="Target Z", unit="m"), name="z")

while True:
    env.step(dt)
