/**
 * Scene, camera, renderer, lighting and orbit-camera setup.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { resizeLines } from "./shapes.js";

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

function addShadowedLight(scene, x, y, z, color, intensity) {
  const light = new THREE.DirectionalLight(color, intensity);
  light.position.set(x, y, z);
  light.castShadow = true;

  const d = 1;
  light.shadow.camera.left = -d;
  light.shadow.camera.right = d;
  light.shadow.camera.top = d;
  light.shadow.camera.bottom = -d;
  light.shadow.camera.near = 1;
  light.shadow.camera.far = 4;
  light.shadow.bias = -0.002;

  scene.add(light);
}

/**
 * Creates the scene, camera, renderer and orbit controls, and mounts the
 * renderer's canvas into `#canvas`.
 *
 * @returns {{scene: THREE.Scene, camera: THREE.PerspectiveCamera, renderer: THREE.WebGLRenderer, controls: OrbitControls}}
 */
export function createScene() {
  const camera = new THREE.PerspectiveCamera(
    70,
    window.innerWidth / window.innerHeight,
    0.01,
    10
  );
  camera.position.set(0.2, 1.2, 0.7);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x787878);
  scene.fog = new THREE.Fog(0x787878, 2, 15);

  // preserveDrawingBuffer is required for canvas.toDataURL() (screenshot())
  // to see anything -- WebGL clears/swaps the drawing buffer after each
  // frame by default, so without this a screenshot taken between frames
  // captures a blank canvas.
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  // Without this, the canvas renders at 1 device pixel per CSS pixel and
  // gets upscaled by the browser -- soft/blurry on any HiDPI (Retina) display.
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;

  const div = document.getElementById("canvas");
  div.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target = new THREE.Vector3(0, 0, 0.2);
  controls.update();

  // DoubleSide -- materials are single-sided by default, which made the
  // ground invisible when the camera orbited below it. transparent must
  // be set for opacity (see the "ground_opacity" message) to have any
  // effect at all -- three.js ignores opacity on an opaque material.
  const groundMaterial = new THREE.MeshPhongMaterial({
    color: 0x4b4b4b,
    specular: 0x101010,
    side: THREE.DoubleSide,
    transparent: true,
  });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), groundMaterial);
  ground.receiveShadow = true;
  scene.add(ground);

  scene.add(new THREE.HemisphereLight(0x666666, 0x222233));
  addShadowedLight(scene, 1, 1, 1, 0xffffff, 1.35);
  addShadowedLight(scene, 0.5, 1, -1, 0xffffff, 1);

  const axesHelper = new THREE.AxesHelper(5);
  scene.add(axesHelper);

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    resizeLines(window.innerWidth, window.innerHeight);
  });

  return { scene, camera, renderer, controls, axesHelper, groundMaterial };
}
