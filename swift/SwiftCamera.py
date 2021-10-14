#!/usr/bin/env python
"""
@author: Jesse Haviland
"""

from spatialmath import SE3
import spatialgeometry as sg
import numpy as np
import uuid


class Camera(sg.Shape):
    def __init__(
        self,
        width=None,
        height=None,
        fov=None,
        fy=None,
        fx=None,
        cy=None,
        cx=None,
        **kwargs
    ):
        super().__init__(stype="camera", **kwargs)

        self.width = width
        self.height = height
        self.fov = fov

        self._id = str(uuid.uuid4())
        print(self._id)

    def to_dict(self):
        """
        to_dict() returns the shapes information in dictionary form

        :returns: All information about the shape
        :rtype: dict
        """

        shape = super().to_dict()
        shape["width"] = self.width
        shape["height"] = self.height
        shape["fov"] = self.fov
        shape["id"] = self._id
        return shape
