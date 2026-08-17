# pip install swift-sim
import spatialgeometry as gm
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

ax = gm.Axes(1, pose=SE3.Trans(0.1,0.2, 0.3))

env.add(ax)
env.step()
env.hold()
