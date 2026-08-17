*************
Using Swift
*************

.. note::

    Draft. Figures and worked examples to follow.

This page covers day-to-day use of the Swift viewer itself -- the
provided example assets, ground plane options, the world axes, the
camera, and the lighting model. For mesh file formats and how a
``Mesh`` shape's file is actually loaded, see :doc:`mesh`.

Provided assets
==================

``examples/assets/`` ships a small set of CC-licensed meshes and
textures for use in example scripts and this documentation -- a
colourful robot, a cooked steak/chicken piece/plate, turf and gravel
ground textures, and a Spitfire model. Each file's title, author,
source, and license are recorded in ``examples/assets/README.md``; add
an entry there in the same format before using any new asset. CC0
assets need no attribution but are listed anyway, for provenance.

These are example/doc assets only -- ``examples/`` isn't packaged, so
they aren't installed alongside Swift itself.

Ground options
=================

The ground plane is a single finite ``PlaneGeometry`` (40 x 40 m by
default), controlled by two ``launch()`` parameters:

``ground_opacity``
    Opacity from 0 (invisible) to 1 (opaque, the default).

``ground_pattern`` / ``ground_pattern_width``
    ``False`` (default) is a plain flat floor. ``True`` or ``"@tile"``
    is a built-in checkerboard; ``"@grid"`` is a built-in grid; anything
    else is treated as an absolute path to an image file to tile as a
    texture. ``ground_pattern_width`` sets the x-extent of one tile, in
    metres -- a custom texture's tile *height* follows the source
    image's own aspect ratio, so it's never distorted.

Whenever a pattern is active, the ground plane recentres under the
camera every frame, snapped to a whole tile so the pattern never
visibly shifts -- this keeps its edge permanently out of reach
regardless of pan/zoom, giving the appearance of an infinite floor. The
plain flat floor has no visible edge to begin with, so it's left fixed
at the origin and skips this recentring entirely.

Global axes
==============

``launch(axes=True)`` (the default) shows a ``THREE.AxesHelper`` at the
world origin -- red/green/blue for x/y/z. Pass ``axes=False`` to hide it.
Swift's world ``+z`` is up (``THREE.Object3D.DEFAULT_UP`` is set
accordingly), matching the usual robotics convention.

Camera
========

The default camera is a perspective camera positioned off to one side
and slightly above the origin, oriented so the world ``+x`` axis reads
as screen-right (the usual convention) -- with ``+z`` up, this requires
the camera to sit on the ``-y`` side. It's driven by three.js's
``OrbitControls``, so the mouse/trackpad orbits, pans, and zooms it
interactively; nothing on the Python side needs to change for that.

For programmatic control, ``Swift.set_camera_pose(position, look_at)``
moves the camera to an explicit position and re-aims it at a point in
the scene, updating ``OrbitControls``' own target to match so
subsequent interactive orbiting pivots around the new point rather than
the old one.

Lighting model
=================

The scene uses three.js's ``MeshPhongMaterial`` throughout (specular
highlights, not a full PBR pipeline), lit by:

* A ``HemisphereLight`` (soft sky/ground fill light, no shadows).
* Two shadow-casting ``DirectionalLight``\ s, positioned on the same
  side of the scene as the camera -- if a light and the camera are on
  opposite sides, camera-facing surfaces end up in shadow. Moving the
  camera means moving these lights to match.

Shadow mapping is enabled on the renderer; the ground plane receives
shadows. A background fog (matching the scene's background colour)
fades distant objects rather than clipping them abruptly at the camera's
far plane.

Visual vs. collision geometry
================================

A robot's each ``Link`` carries *two* independent sets of shapes --
``geometry`` (what you look at) and ``collision`` (what's used for
distance/collision queries via spatialgeometry's ``CollisionShape``,
backed by `coal <https://github.com/coal-library/coal>`_) -- mirroring
URDF's own ``<visual>``/``<collision>`` split per link. The collision set
is often a coarser, cheaper proxy (a box/cylinder standing in for a
complex part) since collision checking needs to run fast and doesn't
care about visual fidelity.

``add()``/``add_robot()`` expose this directly as two independent
opacity knobs, ``robot_alpha`` and ``collision_alpha``. ``collision_alpha``
defaults to ``0`` (hidden) precisely because the collision proxy is
normally an ugly, redundant stand-in you don't want cluttering the
view -- turn it up when you specifically need to sanity-check that the
collision geometry actually matches where you think it is, e.g. while
debugging a planner or a self-collision check.
