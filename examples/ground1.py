"""Render a cube on a textured ground plane."""
import math
from pathlib import Path

from spatialgeometry import Cuboid
from spatialmath import SE3, SO3
from swift import Swift

# The /retrieve/ mechanism (used for mesh files and ground_pattern texture
# paths) requires an absolute path -- derived from this script's own
# location, not the current working directory, so it works regardless of
# where you run it from.
ASSETS = Path(__file__).parent / "assets"

env = Swift()
env.launch(realtime=True, ground_pattern="@tile")

box = Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.1*math.sqrt(3))*SE3(SO3.RotatedVector([0,0,1], [1,1,1])), color="blue")

env.add_shape(box)
env.hold()