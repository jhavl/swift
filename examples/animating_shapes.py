# pip install swift-sim
import spatialgeometry as gm
from spatialmath import SE3
from swift import Swift
import math

env = Swift()
env.launch(realtime=True)

sphere = gm.Sphere(0.3, pose=SE3(0, 0, 0.3), color="red")

env.add(sphere)

for i in range(500):
    x = math.sin(i/20) * 0.5
    sphere.T = SE3.Trans(x, 0, 0.3)
    env.step(0.05)  # wait 0.05 seconds before next step