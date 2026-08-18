#!/usr/bin/env python
"""Render a Franka-Emika Panda in its ready joint configuration."""
import roboticstoolbox as rtb
from swift import Swift

env = Swift()
env.launch(realtime=True)

panda = rtb.models.Panda()
handle = env.add_robot(panda)
handle.q = panda.qr

env.hold()  # keep the browser tab open
