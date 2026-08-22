"""Render a mesh using Swift.  This object has has its vertical axis along the y-axis,
so we rotate it to z-up with the ``y_up=True`` argument to ``Mesh``."""
from pathlib import Path

import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

# The /retrieve/ mechanism (used for mesh files and ground_pattern texture
# paths) requires an absolute path -- derived from this script's own
# location, not the current working directory, so it works regardless of
# where you run it from.
ASSETS = Path(__file__).parent / "assets"

env = Swift()
env.launch(realtime=True, ground_opacity=0.2)

mesh = sg.Mesh(str(ASSETS / "robot.glb"), y_up=True)
env.add(mesh)
env.hold()