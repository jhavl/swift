"""Render a scene with all the CollisionShape objects."""
from pathlib import Path

from spatialgeometry import Cuboid, Sphere, Cylinder, Ellipsoid, Mesh
from spatialmath import SE3
from swift import Swift
import numpy as np

# The /retrieve/ mechanism (used for mesh files and ground_pattern texture
# paths) requires an absolute path -- derived from this script's own
# location, not the current working directory, so it works regardless of
# where you run it from.
ASSETS = Path(__file__).parent / "assets"

env = Swift()
env.launch(realtime=True, ground_opacity=0.5)

def pose(i, n):
    """Return a pose for the i'th object in a grid of n objects."""
    theta = 2 * np.pi * i / n
    x = 0.5 * np.cos(theta)
    y = 0.5 * np.sin(theta) 
    return SE3(x, y, 0)

box = Cuboid([0.2, 0.2, 0.2], color="blue", pose=pose(0, 5))
sphere = Sphere(0.3, color="green", pose=pose(1, 5))
cylinder = Cylinder(0.15, 0.5, color="red", pose=pose(2, 5))
ellipsoid = Ellipsoid([0.2, 0.3, 0.4], color="yellow", pose=pose(3, 5))
mesh = Mesh(str(ASSETS / "robot.glb"), y_up=True, pose=pose(4, 5))

env.add_shape(box)
env.add_shape(sphere)
env.add_shape(cylinder)
env.add_shape(ellipsoid)
env.add_shape(mesh)

env.hold()  # keep the browser tab open