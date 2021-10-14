#!/usr/bin/env python
"""
@author: Jesse Haviland
"""

from spatialmath import SE3
import numpy as np


class SwiftCamera:
    def __init__(
        self,
        width=None,
        height=None,
        fov=None,
        fy=None,
        fx=None,
        cy=None,
        cx=None,
        base=None,
        shape=None,
    ):

        self.width = width
        self.height = height
        self.fov = fov
