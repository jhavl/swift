"""
Configurable scene lights for Swift -- see Swift.set_lights() and
launch()'s lights= parameter.

These are swift-specific, not spatialgeometry Shapes: a light has no
collision geometry and no meaning outside Swift's own three.js scene, so
this deliberately doesn't reuse spatialgeometry's Shape/pose machinery.
"""

from __future__ import annotations

import math

from spatialgeometry.geom.Shape import ArrayLike
from spatialmath.base.argcheck import getvector


def _to_hex(rgb: ArrayLike) -> int:
    r, g, b = (int(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return (r << 16) + (g << 8) + b


class Light:
    """
    Base class for a light in Swift's scene.

    :param color: light color, defaults to white
    :type color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype: str = ""

    def __init__(self, color: ArrayLike = (1.0, 1.0, 1.0), intensity: float = 1.0) -> None:
        self.color = color
        self.intensity = intensity

    def to_dict(self) -> dict:
        """
        :returns: this light's information, in wire-protocol form
        """
        return {
            "ltype": self.ltype,
            "color": _to_hex(self.color),
            "intensity": self.intensity,
        }


class AmbientLight(Light):
    """
    Uniform light added equally to every surface regardless of position
    or orientation -- no position, casts no shadows.

    :param color: light color, defaults to white
    :type color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype = "ambient"


class HemisphereLight(Light):
    """
    Soft light that gradates between one color from above (sky) and
    another from below (ground) -- no position, casts no shadows.

    :param sky_color: color from above, defaults to white
    :type sky_color: ArrayLike
    :param ground_color: color from below, defaults to white
    :type ground_color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype = "hemisphere"

    def __init__(
        self,
        sky_color: ArrayLike = (1.0, 1.0, 1.0),
        ground_color: ArrayLike = (1.0, 1.0, 1.0),
        intensity: float = 1.0,
    ) -> None:
        super().__init__(color=sky_color, intensity=intensity)
        self.ground_color = ground_color

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["sky_color"] = d.pop("color")
        d["ground_color"] = _to_hex(self.ground_color)
        return d


class DirectionalLight(Light):
    """
    Parallel light rays from a fixed direction (``position`` towards
    ``target``), e.g. sunlight -- the key/fill lights in Swift's default
    rig are both this type.

    Shadow quality (the shadow camera's frustum and bias) is tuned
    internally to Swift's default scene scale and isn't user-adjustable
    -- only whether this light casts a shadow at all.

    :param position: where the light is, defaults to (1, -1, 1)
    :type position: ArrayLike
    :param target: point the light points at, defaults to the origin
    :type target: ArrayLike
    :param cast_shadow: whether this light casts shadows, defaults to True
    :param color: light color, defaults to white
    :type color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype = "directional"

    def __init__(
        self,
        position: ArrayLike = (1.0, -1.0, 1.0),
        target: ArrayLike = (0.0, 0.0, 0.0),
        cast_shadow: bool = True,
        color: ArrayLike = (1.0, 1.0, 1.0),
        intensity: float = 1.0,
    ) -> None:
        super().__init__(color=color, intensity=intensity)
        self.position = getvector(position, 3)
        self.target = getvector(target, 3)
        self.cast_shadow = cast_shadow

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["position"] = self.position.tolist()
        d["target"] = self.target.tolist()
        d["cast_shadow"] = self.cast_shadow
        return d


class PointLight(Light):
    """
    Light radiating equally in all directions from a point, falling off
    with distance -- e.g. a bare bulb.

    :param position: where the light is, defaults to (1, -1, 1)
    :type position: ArrayLike
    :param distance: distance at which intensity reaches zero, 0 means
        no limit, defaults to 0
    :param decay: how quickly intensity falls off with distance,
        defaults to 2 (physically realistic inverse-square)
    :param cast_shadow: whether this light casts shadows, defaults to False
    :param color: light color, defaults to white
    :type color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype = "point"

    def __init__(
        self,
        position: ArrayLike = (1.0, -1.0, 1.0),
        distance: float = 0.0,
        decay: float = 2.0,
        cast_shadow: bool = False,
        color: ArrayLike = (1.0, 1.0, 1.0),
        intensity: float = 1.0,
    ) -> None:
        super().__init__(color=color, intensity=intensity)
        self.position = getvector(position, 3)
        self.distance = distance
        self.decay = decay
        self.cast_shadow = cast_shadow

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["position"] = self.position.tolist()
        d["distance"] = self.distance
        d["decay"] = self.decay
        d["cast_shadow"] = self.cast_shadow
        return d


class SpotLight(Light):
    """
    A cone of light from a point, aimed at a target -- e.g. a spotlight
    or flashlight.

    :param position: where the light is, defaults to (1, -1, 1)
    :type position: ArrayLike
    :param target: point the light points at, defaults to the origin
    :type target: ArrayLike
    :param angle: half-angle of the light's cone, in radians, defaults
        to pi/6 (three.js's own default)
    :param penumbra: fraction of the cone that's a soft falloff edge
        rather than full intensity, from 0 to 1, defaults to 0
    :param distance: distance at which intensity reaches zero, 0 means
        no limit, defaults to 0
    :param decay: how quickly intensity falls off with distance,
        defaults to 2 (physically realistic inverse-square)
    :param cast_shadow: whether this light casts shadows, defaults to False
    :param color: light color, defaults to white
    :type color: ArrayLike
    :param intensity: light intensity, defaults to 1.0
    """

    ltype = "spot"

    def __init__(
        self,
        position: ArrayLike = (1.0, -1.0, 1.0),
        target: ArrayLike = (0.0, 0.0, 0.0),
        angle: float = math.pi / 6,
        penumbra: float = 0.0,
        distance: float = 0.0,
        decay: float = 2.0,
        cast_shadow: bool = False,
        color: ArrayLike = (1.0, 1.0, 1.0),
        intensity: float = 1.0,
    ) -> None:
        super().__init__(color=color, intensity=intensity)
        self.position = getvector(position, 3)
        self.target = getvector(target, 3)
        self.angle = angle
        self.penumbra = penumbra
        self.distance = distance
        self.decay = decay
        self.cast_shadow = cast_shadow

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["position"] = self.position.tolist()
        d["target"] = self.target.tolist()
        d["angle"] = self.angle
        d["penumbra"] = self.penumbra
        d["distance"] = self.distance
        d["decay"] = self.decay
        d["cast_shadow"] = self.cast_shadow
        return d
