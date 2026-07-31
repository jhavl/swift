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

const daeLoader = new ColladaLoader();
const stlLoader = new STLLoader();
const objLoader = new OBJLoader();
const mtlLoader = new MTLLoader();
const vrmLoader = new VRMLLoader();
const pcdLoader = new PCDLoader();
const plyLoader = new PLYLoader();
const gltfLoader = new GLTFLoader();

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

function loadMesh(part, scene, cb) {
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

  const onError = (label) => (error) => console.error(`Error loading ${label} file`, error);
  const onProgress = (xhr) => {
    if (xhr.total) console.log(`${((xhr.loaded / xhr.total) * 100).toFixed(0)}% loaded`);
  };

  if (ext === "dae") {
    daeLoader.load(url, (collada) => {
      const mesh = collada.scene;
      setPose(mesh, part.t, part.q);
      mesh.traverse((child) => {
        if (child.isMesh) child.castShadow = true;
        else if (child.type === "PointLight") child.visible = false;
      });
      finish(part, mesh, scene, cb);
    });
  } else if (ext === "stl") {
    stlLoader.load(url, (geometry) => {
      const mesh = new THREE.Mesh(geometry, materialFor(part));
      mesh.scale.set(part.scale[0], part.scale[1], part.scale[2]);
      setPose(mesh, part.t, part.q);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      finish(part, mesh, scene, cb);
    });
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
    console.error(`Unsupported mesh extension: ${ext}`);
  }
}

function load(part, scene, cb) {
  if (part.stype === "mesh") loadMesh(part, scene, cb);
  else if (["cuboid", "box", "sphere", "cylinder"].includes(part.stype)) loadPrimitive(part, scene, cb);
  else console.error(`Unsupported shape type: ${part.stype}`);
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

    const cb = () => {
      this.loaded++;
    };
    for (const part of this.parts) load(part, scene, cb);
  }

  isMounted() {
    return this.loaded === this.parts.length;
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
      old.mesh.material?.dispose?.();
      old.mesh.geometry?.dispose?.();
      this.scene.remove(old.mesh);
      this.loaded--;
    }
    this.parts[index] = partData;
    load(partData, this.scene, () => {
      this.loaded++;
    });
  }

  remove(scene) {
    for (const part of this.parts) {
      if (!part.mesh) continue;
      part.mesh.material?.dispose?.();
      part.mesh.geometry?.dispose?.();
      scene.remove(part.mesh);
    }
  }
}
