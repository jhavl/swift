import spatialgeometry as gm
from spatialmath import SE3
from swift import Swift
import math

env = Swift()
env.launch(realtime=True)

# Every Shape *is* a SceneNode (Shape inherits from SceneNode) -- there's no
# separate wrapper node to create, just parent one shape to another directly.
cube = gm.Cuboid([1, 1, 1], color="blue", pose=SE3(0, 0, 0.5))
sphere1 = gm.Sphere(0.5, pose=SE3(1, 0, 0.3), color="red")
sphere2 = gm.Sphere(0.5, pose=SE3(0, 1, 0.3), color="green")

# sphere1.T and sphere2.T are now interpreted relative to cube, not the world.
sphere1.scene_parent = cube
sphere2.scene_parent = cube

env.add(cube)
env.add(sphere1)
env.add(sphere2)

for i in range(200):
    # The cube rotates about the z-axis and spirals outward
    cube.T = SE3.Rz(i/10) * SE3((i/50), 0, 0)

    env.step()