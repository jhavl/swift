/**
 * Loading and pose updates for scene objects.
 *
 * Swift.py's protocol has no separate "robot" concept on the wire: adding a
 * robot just sends a flat list of its link geometries, each in the same
 * per-part dict shape a lone Shape uses (spatialgeometry's Shape.to_dict()):
 * {stype, t, q, v, color, opacity, ...type-specific fields}. A Shape is the
 * one-part case of the same list. `q` is [w, x, y, z] -- THREE.Quaternion's
 * constructor is (x, y, z, w), so it's always passed as
 * (q[1], q[2], q[3], q[0]). `color` is a 0xRRGGBB int, `opacity` a 0-1 float.
 */

import * as THREE from "three";
import { ColladaLoader } from "three/addons/loaders/ColladaLoader.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { MTLLoader } from "three/addons/loaders/MTLLoader.js";
import { VRMLLoader } from "three/addons/loaders/VRMLLoader.js";
import { PCDLoader } from "three/addons/loaders/PCDLoader.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";

const daeLoader = new ColladaLoader();
const stlLoader = new STLLoader();
const objLoader = new OBJLoader();
const mtlLoader = new MTLLoader();
const vrmLoader = new VRMLLoader();
const pcdLoader = new PCDLoader();
const plyLoader = new PLYLoader();
const gltfLoader = new GLTFLoader();

// LineMaterial (used for Arrow's radius=0 shaft and, later, Path) renders
// screen-space-width lines via a resolution uniform it needs kept in sync
// with the canvas size -- unlike everything else here, it doesn't pick this
// up automatically. scene.js's resize handler calls resizeLines() with the
// new canvas size; every LineMaterial ever created gets its own resolution
// updated in place (copying into a material's Vector2 doesn't establish a
// live reference back to this one).
const lineResolution = new THREE.Vector2(window.innerWidth, window.innerHeight);
const lineMaterials = [];

export function resizeLines(width, height) {
  lineResolution.set(width, height);
  for (const material of lineMaterials) material.resolution.copy(lineResolution);
}

function setPose(object3d, t, q) {
  object3d.position.set(t[0], t[1], t[2]);
  // q is already [x, y, z, w] -- spatialgeometry's SceneNode._wq is computed
  // via spatialmath's r2q(..., order="xyzs"), which is also THREE.Quaternion's
  // native constructor order, so no reordering is needed (unlike the old
  // public/js/lib.js, which reordered assuming [w, x, y, z] -- that must have
  // matched an older, since-changed version of this wire format).
  object3d.quaternion.set(q[0], q[1], q[2], q[3]);
}

function materialFor(part) {
  return new THREE.MeshPhongMaterial({
    color: part.color,
    specular: 0x111111,
    shininess: 200,
    transparent: true,
    opacity: part.opacity,
  });
}

function finish(part, mesh, scene, cb) {
  scene.add(mesh);
  part.mesh = mesh;
  cb();
}

/**
 * Frees GPU resources for anything `finish()` handed to a scene -- a plain
 * THREE.Mesh (material/geometry directly on it), a helper with its own
 * dispose() (AxesHelper, ArrowHelper), or one of this module's own
 * multi-child Groups (Arrow's shaft+cone, Axes' three per-axis arrows --
 * see makeArrow()/loadAxes(), which tag every child needing disposal onto
 * userData.disposables since Group itself owns no geometry/material).
 */
function disposeChild(child) {
  child.material?.dispose?.();
  child.geometry?.dispose?.();
  // LineMaterial instances (Arrow's radius=0 shaft) are tracked in
  // lineMaterials so resizeLines() can keep their resolution uniform
  // current -- forgetting to untrack here would leak one entry per Arrow
  // ever created, for the life of the page.
  const idx = lineMaterials.indexOf(child.material);
  if (idx !== -1) lineMaterials.splice(idx, 1);
}

function disposeMesh(object) {
  if (typeof object.dispose === "function") {
    object.dispose();
    return;
  }
  disposeChild(object);
  for (const child of object.userData.disposables ?? []) disposeChild(child);
}

function loadPrimitive(part, scene, cb) {
  let geometry;
  if (part.stype === "cuboid" || part.stype === "box") {
    geometry = new THREE.BoxGeometry(part.scale[0], part.scale[1], part.scale[2]);
  } else if (part.stype === "sphere") {
    geometry = new THREE.SphereGeometry(part.radius, 64, 64);
  } else if (part.stype === "cylinder") {
    geometry = new THREE.CylinderGeometry(part.radius, part.radius, part.length, 32);
  }
  const mesh = new THREE.Mesh(geometry, materialFor(part));
  setPose(mesh, part.t, part.q);
  finish(part, mesh, scene, cb);
}

/**
 * spatialgeometry.Arrow: a shaft (cylinder if radius > 0, otherwise a
 * screen-space-width line via LineMaterial) plus a cone head. radius and
 * linewidth are mutually exclusive -- radius > 0 always wins, matching
 * Arrow's own Python-side docstring.
 *
 * @param {number} color 0xRRGGBB
 * @returns {THREE.Object3D} local +Z is the arrow's direction, tip at
 *   `length` -- callers position/orient this however they need (setPose(),
 *   or a parent group for Axes' per-axis rotation).
 */
function makeArrow(length, radius, linewidth, headLength, headRadius, color) {
  const group = new THREE.Group();
  const headLen = length * headLength;
  const headWidth = headLen * headRadius;
  const shaftLen = Math.max(0.0001, length - headLen);

  let shaft;
  if (radius > 0) {
    const geometry = new THREE.CylinderGeometry(radius, radius, shaftLen, 16);
    // CylinderGeometry is centred on Y with the app's default axis -- shift
    // so the base sits at the origin, then rotate Y-up into Z-forward to
    // match spatialgeometry's Arrow (+Z) convention.
    geometry.translate(0, shaftLen / 2, 0);
    geometry.rotateX(Math.PI / 2);
    shaft = new THREE.Mesh(geometry, new THREE.MeshPhongMaterial({ color, specular: 0x111111, shininess: 200 }));
  } else {
    const positions = [0, 0, 0, 0, 0, shaftLen];
    const lineGeometry = new LineGeometry();
    lineGeometry.setPositions(positions);
    const material = new LineMaterial({ color, linewidth, worldUnits: false });
    material.resolution.copy(lineResolution);
    shaft = new Line2(lineGeometry, material);
    lineMaterials.push(material); // kept in sync on resize -- see scene.js
  }
  group.add(shaft);

  const coneGeometry = new THREE.ConeGeometry(headWidth / 2, headLen, 16);
  coneGeometry.translate(0, headLen / 2, 0);
  coneGeometry.rotateX(Math.PI / 2);
  const cone = new THREE.Mesh(coneGeometry, new THREE.MeshPhongMaterial({ color, specular: 0x111111, shininess: 200 }));
  cone.position.z = shaftLen;
  group.add(cone);

  group.userData.disposables = [shaft, cone];
  return group;
}

function loadArrow(part, scene, cb) {
  const arrow = makeArrow(part.length, part.radius, part.linewidth, part.head_length, part.head_radius, part.color);
  setPose(arrow, part.t, part.q);
  finish(part, arrow, scene, cb);
}

const _AXIS_COLORS = [0xff0000, 0x00ff00, 0x0000ff]; // X red, Y green, Z blue
const _AXIS_ROTATIONS = [
  new THREE.Euler(0, Math.PI / 2, 0), // +Z -> +X
  new THREE.Euler(-Math.PI / 2, 0, 0), // +Z -> +Y
  new THREE.Euler(0, 0, 0), // +Z -> +Z, no rotation needed
];

function loadAxes(part, scene, cb) {
  let axes;
  if (part.arrows) {
    axes = new THREE.Group();
    for (let i = 0; i < 3; i++) {
      const arrow = makeArrow(part.length, part.radius, part.linewidth, 0.2, 0.2, _AXIS_COLORS[i]);
      arrow.setRotationFromEuler(_AXIS_ROTATIONS[i]);
      axes.add(arrow);
    }
    axes.userData.disposables = axes.children.flatMap((a) => a.userData.disposables);
  } else {
    axes = new THREE.AxesHelper(part.length);
  }
  setPose(axes, part.t, part.q);
  finish(part, axes, scene, cb);
}

function loadMesh(part, scene, cb, errCb) {
  const ext = part.filename.split(".").pop().toLowerCase();

  // Mesh filenames arrive as absolute filesystem paths (e.g. rtbdata's
  // installed location), not URLs -- SwiftServer.do_GET only serves those
  // through its "/retrieve/<path>" passthrough route, everything else is
  // resolved against swift/public/ as the static root.
  let filename = part.filename;
  if (navigator.appVersion.indexOf("Win") !== -1) {
    filename = filename.slice(2);
  }
  const url = "/retrieve" + encodeURI(filename);

  // Every loader below must be given this (or call errCb() directly on an
  // unsupported/malformed input) -- Swift.py's add_shape()/add_assembly()/
  // add_robot() poll "shape_mounted" in a loop that only terminates on
  // load-complete or load-failed (see SwiftObject.hasError() in this file
  // and Swift._wait_mounted() in Swift.py); a swallowed error here means
  // that poll spins forever with no way for the caller to find out why.
  const onError = (label) => (error) => {
    const reason = `failed to load ${label} file '${part.filename}': ${error}`;
    console.error(reason, error);
    errCb(-2, reason);
  };
  const onProgress = (xhr) => {
    if (xhr.total) console.log(`${((xhr.loaded / xhr.total) * 100).toFixed(0)}% loaded`);
  };

  if (ext === "dae") {
    daeLoader.load(
      url,
      (collada) => {
        const mesh = collada.scene;
        setPose(mesh, part.t, part.q);
        mesh.traverse((child) => {
          if (child.isMesh) child.castShadow = true;
          else if (child.type === "PointLight") child.visible = false;
        });
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("Collada")
    );
  } else if (ext === "stl") {
    stlLoader.load(
      url,
      (geometry) => {
        const mesh = new THREE.Mesh(geometry, materialFor(part));
        mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
        setPose(mesh, part.t, part.q);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("STL")
    );
  } else if (ext === "obj") {
    mtlLoader.load(
      part.filename.slice(0, part.filename.length - 3) + "mtl",
      (materials) => {
        materials.preload();
        objLoader.setMaterials(materials);
        objLoader.load(
          part.filename,
          (object) => {
            object.traverse((child) => {
              if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
              }
            });
            object.scale.set(part.scale[0], part.scale[1], part.scale[2]);
            setPose(object, part.t, part.q);
            finish(part, object, scene, cb);
          },
          onProgress,
          onError("obj")
        );
      }
    );
  } else if (ext === "gltf" || ext === "glb") {
    gltfLoader.load(
      part.filename,
      (gltf) => {
        const mesh = gltf.scene;
        mesh.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
        setPose(mesh, part.t, part.q);
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("GLTF")
    );
  } else if (ext === "ply") {
    plyLoader.load(
      part.filename,
      (geometry) => {
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, materialFor(part));
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
        setPose(mesh, part.t, part.q);
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("PLY")
    );
  } else if (ext === "wrl") {
    vrmLoader.load(
      part.filename,
      (mesh) => {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
        setPose(mesh, part.t, part.q);
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("VRML")
    );
  } else if (ext === "pcd") {
    pcdLoader.load(
      part.filename,
      (mesh) => {
        mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
        setPose(mesh, part.t, part.q);
        finish(part, mesh, scene, cb);
      },
      onProgress,
      onError("PCD")
    );
  } else {
    const reason = `unsupported mesh extension '${ext}' (${part.filename})`;
    console.error(reason);
    errCb(-2, reason);
  }
}

function load(part, scene, cb, errCb) {
  if (part.stype === "mesh") loadMesh(part, scene, cb, errCb);
  else if (["cuboid", "box", "sphere", "cylinder"].includes(part.stype)) loadPrimitive(part, scene, cb);
  else if (part.stype === "axes") loadAxes(part, scene, cb);
  else if (part.stype === "arrow") loadArrow(part, scene, cb);
  else {
    const reason = `unsupported shape type '${part.stype}'`;
    console.error(reason);
    errCb(-1, reason);
  }
}

/**
 * One entry in Swift's `swift_objects` list -- either a lone Shape (one
 * part) or a Robot (one part per link/gripper geometry). Both are added,
 * posed and removed identically since the wire protocol treats them the
 * same way (see module docstring).
 */
export class SwiftObject {
  /**
   * @param {THREE.Scene} scene
   * @param {Array<object>} parts flat list of shape dicts
   */
  constructor(scene, parts) {
    this.scene = scene;
    this.parts = parts;
    this.loaded = 0;
    this.failed = 0;
    // First failure's code/reason -- see load()'s two error paths
    // (-1 unsupported shape type, -2 asset/mesh load failed). Kept as
    // the *first* one seen: with several parts, only one reason is ever
    // surfaced to Swift.py's exception, and the first is the most
    // actionable/deterministic choice.
    this.errorCode = null;
    this.errorReason = null;

    const cb = () => {
      this.loaded++;
    };
    const errCb = (code, reason) => {
      this.failed++;
      if (this.errorCode === null) {
        this.errorCode = code;
        this.errorReason = reason;
      }
    };
    for (const part of this.parts) load(part, scene, cb, errCb);
  }

  isMounted() {
    return this.loaded === this.parts.length;
  }

  /** True once any part has failed to load -- see load()'s error paths. */
  hasError() {
    return this.failed > 0;
  }

  setPoses(poses) {
    for (let i = 0; i < this.parts.length; i++) {
      const mesh = this.parts[i].mesh;
      if (mesh) setPose(mesh, poses[i].t, poses[i].q);
    }
  }

  /** Handles "shape_update" -- a Shape's geometry/color/etc changed, not just its pose. */
  updatePart(index, partData) {
    const old = this.parts[index];
    if (old.mesh) {
      disposeMesh(old.mesh);
      this.scene.remove(old.mesh);
      this.loaded--;
    }
    this.parts[index] = partData;
    load(
      partData,
      this.scene,
      () => {
        this.loaded++;
      },
      (code, reason) => {
        this.failed++;
        if (this.errorCode === null) {
          this.errorCode = code;
          this.errorReason = reason;
        }
      }
    );
  }

  remove(scene) {
    for (const part of this.parts) {
      if (!part.mesh) continue;
      disposeMesh(part.mesh);
      scene.remove(part.mesh);
    }
  }
}
