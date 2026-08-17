# pip install swift-sim
import spatialgeometry as gm
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

cube = gm.Cuboid([1, 2, 3], pose=SE3(0, 0, 0.5), color="blue")
sphere = gm.Sphere(0.3, pose=SE3(2, 0, 0.3), color="red")
gripper = gm.Mesh("../docs/figs/panda_hand.dae", pose=SE3.Rx(90, unit="deg"))

env.add(cube)
env.add(sphere)
env.add(gripper)
