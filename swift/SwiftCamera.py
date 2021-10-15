#!/usr/bin/env python
"""
@author: Jesse Haviland
"""

from typing import Optional
from spatialmath import SE3
import spatialgeometry as sg
import numpy as np
import uuid

_mv = False

try:
    import machinevisiontoolbox as mv

    _mv = True
except ImportError:  # pragma nocover
    pass


class Camera(sg.Shape, object):
    def __init__(
        self,
        width: int,
        height: int,
        fov: Optional[float] = None,
        fy: Optional[float] = None,
        fx: Optional[float] = None,
        cy: Optional[float] = None,
        cx: Optional[float] = None,
        **kwargs
    ):
        super().__init__(stype="camera", **kwargs)

        self.width = width
        self.height = height
        self.fov = fov

        self._id = str(uuid.uuid4())

    def to_dict(self):
        """
        to_dict() returns the shapes information in dictionary form

        :returns: All information about the shape
        :rtype: dict
        """

        shape = super().to_dict()
        shape["width"] = self.width
        shape["height"] = self.height
        shape["fov"] = np.rad2deg(self.fov)
        shape["id"] = self._id
        return shape

    @classmethod
    def CentralCamera(cls, camera: mv.CentralCamera, **kwargs):
        K = camera.K

        height = camera.nv
        width = camera.nu

        fv = K[1, 1]
        fov = 2 * np.arctan(height / (2 * fv))

        return cls(
            width=width, height=height, fov=fov, cx=K[0, 2], cy=K[1, 2], **kwargs
        )
