******
Meshes
******

.. note::

    Draft. Figures and worked examples to follow.

A :class:`~spatialgeometry.Mesh` shape's ``filename`` is loaded in the
browser by Swift's JavaScript, using `three.js <https://threejs.org>`_'s
built-in loaders. Swift picks a loader based on the file's extension --
``shapes.js``'s ``loadMesh()`` is a simple dispatch on ``ext``.

For the broader picture -- mesh files are actually read by *two*
independent consumers (the browser, via Swift; and ``trimesh``/Coal, for
collision queries), each supporting a different set of formats, and *why*
you'd pick one format over another -- see spatialgeometry's own File
Formats page, published somewhere under
`<https://jhavl.github.io/spatialgeometry/>`_ (exact path TBD). That page
covers the format history, a capability comparison table, and the
"bundle" problem (a mesh plus its external texture/material files) in
detail; it isn't repeated here.

Formats Swift's JS can load
============================

.. list-table::
   :header-rows: 1
   :widths: 14 20 30

   * - Extension
     - three.js loader
     - Notes
   * - ``.dae``
     - ``ColladaLoader``
     - See :ref:`scene-graph-formats` below.
   * - ``.stl``
     - ``STLLoader``
     - No materials/scene structure -- see vertex-color note below.
   * - ``.obj`` (+ ``.mtl``)
     - ``OBJLoader`` + ``MTLLoader``
     - A missing ``.mtl`` is a **hard** failure in Swift.
   * - ``.gltf`` / ``.glb``
     - ``GLTFLoader``
     - Prefer ``.glb`` -- single file, no separate ``.bin``/image references to go missing.
   * - ``.ply``
     - ``PLYLoader``
     - See vertex-color note below.
   * - ``.wrl``
     - ``VRMLLoader``
     - Legacy VRML97.
   * - ``.pcd``
     - ``PCDLoader``
     - Point clouds -- rendered as points, not a surface.

All of these are fetched from disk via Swift's ``/retrieve/<absolute
path>`` HTTP route, which requires an **absolute** path -- ``Mesh(filename=...)``
and :meth:`~swift.Swift.Swift.launch`'s ``ground_pattern`` argument both
raise a ``ValueError`` immediately if given a relative one, rather than
letting it fail later as a confusing 404 in the browser console.

Vertex colors
--------------

STL and PLY carry no material/scene information at all, only geometry --
but both formats can carry a per-vertex color attribute. When a ``Mesh``
is constructed with no explicit ``color=``, Swift prefers whatever
per-vertex colors the loader parsed out of the file over the flat default
grey; an explicit ``color=`` always overrides them. This is
``use_vertex_colors`` in the wire protocol (``Mesh.to_dict()``) and
``materialFor()`` in ``shapes.js``.

.. _scene-graph-formats:

Scene-graph formats: DAE and glTF/GLB
--------------------------------------

Unlike STL/OBJ/PLY, COLLADA (``.dae``) and glTF/GLB can encode a full
scene graph -- multiple nodes, each with its own local transform, useful
for a multi-part rigid assembly (or a skinned/animated model). After
loading, that hierarchy isn't flattened: ``ColladaLoader``/``GLTFLoader``
hand back a live three.js ``Object3D`` tree with the original nodes and
local transforms intact.

Swift, however, only ever applies **one** pose to the root of whatever
was loaded -- see ``setPose()`` in ``shapes.js``, called once at load time
and again on every subsequent :meth:`~swift.Swift.Swift.step`. Nothing in Swift's Python/JS
bridge reaches into a mesh's internal nodes individually, and any
baked-in COLLADA/glTF animation or skinning is ignored entirely (the
loader just grabs the static bind pose). A DAE/glTF with internal
structure therefore renders as **one rigid multi-part object** in Swift --
you can move/rotate the whole thing as a unit, but not drive its internal
parts independently.

This is a different mechanism from Swift's actual articulated-robot
support (:meth:`~swift.Swift.Swift.add_robot` / ``AssemblyHandle``), where each link is its own
independent ``Shape`` and Python drives each one's pose separately every
step from forward kinematics. Don't reach for a single multi-node mesh
file as a way to represent something you need to actuate.

External textures
^^^^^^^^^^^^^^^^^^

A ``.dae`` file is plain XML text -- it doesn't embed image data inline. Its
``<library_images>`` block just points at texture files by relative path
(e.g. ``textures/diffuse.jpg``), so a textured COLLADA model is really a
small *bundle*: the ``.dae`` plus one or more JPEG/PNG files sitting
alongside it, the same idea as OBJ's separate ``.mtl`` (see below) except the
material *definitions* live inline in the XML and only the *images* are
external.

Treat the ``.dae`` and its texture files as one unit -- never move or rename
one without the other. The relative paths are resolved against wherever the
``.dae`` itself was loaded from:

* For collision, trimesh's COLLADA loader defaults to ``ignore_broken=True``,
  so a missing or unreachable texture image doesn't stop it extracting the
  geometry Coal needs -- textures are irrelevant to collision anyway.
* For display, Swift serves files from disk via a ``/retrieve/<absolute
  path>`` route, and three.js's ``ColladaLoader`` resolves each
  ``<init_from>`` path relative to the ``.dae``'s own URL. So as long as the
  image sits at the relative path the ``.dae`` expects, the browser's
  follow-up request for it resolves automatically -- no extra configuration
  needed, just keep the files together.
* A missing texture is a **soft** failure: the loader still finishes and the
  mesh still appears, just untextured (a grey/default material) -- it
  doesn't raise an error the way a missing/renamed ``.dae`` itself would. If
  a mesh looks untextured in Swift, check the browser console for a 404
  before suspecting anything else.

Other formats have a version of this same "bundle" problem:

* **OBJ** has it worse in one sense -- geometry (``.obj``) and materials
  (``.mtl``, itself referencing texture images) are always two separate
  files, never optional. Swift treats a missing ``.mtl`` as a **hard**
  failure (it's wired to the same error path as a missing mesh file), so
  you'll see an explicit load error rather than a silently untextured mesh.
  A texture image missing under a *present* ``.mtl`` behaves like COLLADA's
  soft-failure case above.
* **glTF** has it too, but only in the plain-text ``.gltf`` form, which can
  reference a separate ``.bin`` geometry buffer and separate image files.
  A missing ``.bin`` is a hard failure (there's no geometry to build without
  it); missing images are a soft failure, same as COLLADA. ``.glb`` sidesteps
  the whole issue by packing geometry, buffers, and images into one file --
  another reason to prefer it over ``.gltf`` when you control the export.
* **STL** and **PLY** are normally single, self-contained files with no
  companion assets, so this doesn't apply to them.

Left-handed meshes and odd-looking rendering
==============================================

STL, OBJ, and PLY carry no coordinate-system metadata at all -- no "up
axis", no handedness declaration (unlike glTF, which mandates Y-up, or
COLLADA, which has an explicit ``<up_axis>`` element). A mesh authored or
exported in a left-handed convention, or one that was mirrored (e.g. a
negative scale baked in during export), ends up with its triangle
winding order reversed relative to what three.js expects.

In Swift this shows up as odd-looking shading, or faces that seem to
disappear from the angle you'd expect to see them from: ``materialFor()``
in ``shapes.js`` builds a plain ``MeshPhongMaterial`` with no ``side``
set, which defaults to ``THREE.FrontSide`` -- back-facing triangles (as
three.js judges winding) are culled entirely. A mesh with reversed
winding throughout will appear inside-out.

**Dealing with it today:**

* If the symptom is really just an axis-convention mismatch (e.g. a
  Z-up export looking like it's lying on its side) rather than true
  mirroring, a corrective rotation on the shape's pose (``SE3.Rx``/``Ry``/``Rz``)
  is enough -- this doesn't touch winding at all.
* If the winding itself is reversed, a pose rotation can't fix it. Fix it
  upstream instead: most mesh tools have a "flip normals" / "recalculate
  normals" operation (Blender, MeshLab), or do it programmatically with
  ``trimesh`` (``mesh.invert()``) before ever pointing Swift at the file.
* There is currently no per-shape "render both sides" override in Swift
  to paper over this live -- see the implementor note below.

Y-up or Z-up meshes
===================

Typically in robotics applications the z-axis is "up", but
many mesh exporters default to y-up. Swift doesn't care which convention a mesh uses, as
long as you apply the right pose.  Spatial Geometry's ``Mesh`` shape has no notion of "up" so
vertices are passed through to the browser as-is.  If you have a mesh that is y-up, you can rotate it to z-up by
passing the ``y_up=True`` argument to the ``Mesh`` constructor, which applies a 90-degree rotation about the x-axis to the mesh's vertices.

Implementor notes
====================

**Adding a new mesh format.** ``loadMesh()`` in ``shapes.js`` dispatches
purely on file extension, one ``else if (ext === "...")`` branch per
format, each following the same shape: call the loader with the
``/retrieve``-prefixed ``url``, build a ``THREE.Mesh`` (or use the
loader's own scene/group) in the success callback, call ``finish(part,
mesh, scene, cb)``, and wire up ``onProgress``/``onError(label)``. To add
a format: instantiate the relevant three.js loader (many live under
``three/addons/loaders/``) alongside the existing ones near the top of
``shapes.js``, add a matching branch in ``loadMesh()``, and update the
table above. If the format should also be usable for collision, check
whether ``trimesh`` already supports it too (spatialgeometry's
``CollisionShape`` side) -- no Python-side extension allowlist needs
updating either way, since ``Mesh`` doesn't validate extensions itself.

**Handling handedness more robustly.** Rather than requiring every user
to notice and manually fix reversed winding, ``materialFor()`` could
default loaded-mesh materials to ``THREE.DoubleSide`` instead of leaving
``side`` unset. three.js's shader flips the interpolated normal for
back-facing triangles under ``DoubleSide``, which corrects the
*lighting* as well as visibility -- not just a workaround for missing
faces. The tradeoff is a minor render-cost increase (every triangle's
back face becomes eligible for rasterization) for every loaded mesh, not
just the ones that need it; worth revisiting if this keeps coming up in
practice.
