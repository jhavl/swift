/**
 * Scene, camera, renderer, lighting and orbit-camera setup.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { resizeLines } from "./shapes.js";

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

const GROUND_SIZE = 40;
const GROUND_COLOR = 0x4b4b4b;

// Set by setGroundPattern(), read by updateGroundPatternPosition() -- see
// their doc comments below. No pattern active means no recentring, so the
// plain flat floor keeps its original fixed-at-the-origin behaviour exactly.
let groundTileWidth = null;
let groundTileHeight = null;

// A 2x2-pixel canvas, NearestFilter, repeated -- each pixel becomes one
// checker square when magnified with no interpolation. Cheapest possible
// seamless checkerboard, no drawing code needed beyond four pixels.
function makeCheckerTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 2;
  const ctx = canvas.getContext("2d");
  const light = [0x8c, 0x8c, 0x8c, 255];
  const dark = [0x2a, 0x2a, 0x2a, 255];
  const imageData = ctx.createImageData(2, 2);
  for (const [i, pixel] of [light, dark, dark, light].entries()) {
    imageData.data.set(pixel, i * 4);
  }
  ctx.putImageData(imageData, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  return texture;
}

// A single cell's border, drawn as a filled square with a stroked outline
// -- one repeat of this canvas is exactly one grid cell.
function makeGridTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#4b4b4b";
  ctx.fillRect(0, 0, size, size);
  ctx.strokeStyle = "#8a8a8a";
  ctx.lineWidth = 2;
  ctx.strokeRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

/**
 * Applies (or clears) a repeating pattern on the ground plane's material.
 *
 * @param {THREE.Mesh} ground
 * @param {THREE.Material} groundMaterial
 * @param {boolean|string} pattern false clears any pattern (back to the
 *   plain flat floor); true or "@tile" is a built-in checkerboard; "@grid"
 *   is a built-in grid; anything else is a /retrieve/-servable texture path.
 * @param {number} width x-extent of one tile, in metres -- the tile's
 *   height follows the source image's own aspect ratio for a custom
 *   texture (never distorted), or equals width for the built-ins (both
 *   are square by construction).
 */
export function setGroundPattern(ground, groundMaterial, pattern, width) {
  if (!pattern) {
    groundMaterial.map = null;
    groundMaterial.color.set(GROUND_COLOR);
    groundMaterial.needsUpdate = true;
    groundTileWidth = groundTileHeight = null;
    ground.position.set(0, 0, 0);
    return;
  }

  const applyRepeat = (texture, tileWidth, tileHeight) => {
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(GROUND_SIZE / tileWidth, GROUND_SIZE / tileHeight);
    groundMaterial.map = texture;
    // The material's own color multiplies the texture -- white leaves the
    // pattern's own colors (checker/grid/custom texture) unmodified;
    // GROUND_COLOR would otherwise mute/darken all of them identically.
    groundMaterial.color.set(0xffffff);
    groundMaterial.needsUpdate = true;
    groundTileWidth = tileWidth;
    groundTileHeight = tileHeight;
  };

  if (pattern === true || pattern === "@tile") {
    // One repeat of the 2x2-pixel canvas spans 2 squares per axis.
    applyRepeat(makeCheckerTexture(), width * 2, width * 2);
  } else if (pattern === "@grid") {
    applyRepeat(makeGridTexture(), width, width);
  } else {
    // Mirrors loadMesh()'s own /retrieve/ URL construction (shapes.js) --
    // same absolute-filesystem-path convention, same Windows adjustment.
    let filename = pattern;
    if (navigator.appVersion.indexOf("Win") !== -1) {
      filename = filename.slice(2);
    }
    const url = "/retrieve" + encodeURI(filename);
    new THREE.TextureLoader().load(
      url,
      (texture) => {
        const aspect = texture.image.height / texture.image.width;
        applyRepeat(texture, width, width * aspect);
      },
      undefined,
      // No Python-side wait to fail for ground_pattern (unlike add_shape()'s
      // shape_mounted poll) -- this is fire-and-forget, so a console error
      // is the only signal available for a bad path/unsupported format.
      (error) => console.error(`failed to load ground_pattern texture '${pattern}': ${error}`, error)
    );
  }
}

/**
 * Keeps the ground plane's (finite) extent centred under the camera, so
 * its edge is never reachable regardless of pan/zoom -- only meaningful
 * once a pattern is active (see setGroundPattern()): a flat, untextured
 * floor has no visible seam at its edge in the first place, so it's left
 * exactly where it's always been rather than paying for this every frame.
 *
 * Snapped to the nearest whole tile so recentring never visibly shifts
 * the pattern -- moving by an exact multiple of its own period looks
 * identical to not having moved at all.
 */
export function updateGroundPatternPosition(ground, cameraPosition) {
  if (groundTileWidth === null) return;
  ground.position.x = Math.round(cameraPosition.x / groundTileWidth) * groundTileWidth;
  ground.position.y = Math.round(cameraPosition.y / groundTileHeight) * groundTileHeight;
}

// Swift's default 3-light rig -- same shape (ltype/fields) as
// Light.to_dict() in Python's Light.py, so user-supplied lights (see
// setLights() below) go through the identical code path as these
// defaults. y is negated (-1, not +1) to match the camera's -y position
// set in createScene() below -- these lights need to stay on the
// camera's side of the scene, else the faces facing the camera end up
// in shadow.
const DEFAULT_LIGHTS = [
  { ltype: "hemisphere", sky_color: 0x666666, ground_color: 0x222233, intensity: 1 },
  { ltype: "directional", color: 0xffffff, intensity: 1.35, position: [1, -1, 1], target: [0, 0, 0], cast_shadow: true },
  { ltype: "directional", color: 0xffffff, intensity: 1, position: [0.5, -1, -1], target: [0, 0, 0], cast_shadow: true },
];

// Tuned to this scene's own ~1m scale, not user-adjustable (see
// DirectionalLight's docstring in Light.py) -- exposing these raw was
// deliberately deferred, see the tech-debt issue for the fuller lighting
// API this is the first cut of.
function applyDirectionalShadow(light) {
  const d = 1;
  light.shadow.camera.left = -d;
  light.shadow.camera.right = d;
  light.shadow.camera.top = d;
  light.shadow.camera.bottom = -d;
  light.shadow.camera.near = 1;
  light.shadow.camera.far = 4;
  light.shadow.bias = -0.002;
}

// One branch per Light subclass in Light.py -- ltype is that class's own
// `ltype` class attribute, sent verbatim over the wire.
function buildLight(cfg) {
  switch (cfg.ltype) {
    case "ambient":
      return new THREE.AmbientLight(cfg.color, cfg.intensity);
    case "hemisphere":
      return new THREE.HemisphereLight(cfg.sky_color, cfg.ground_color, cfg.intensity);
    case "directional": {
      const light = new THREE.DirectionalLight(cfg.color, cfg.intensity);
      light.position.set(...cfg.position);
      light.target.position.set(...cfg.target);
      if (cfg.cast_shadow) {
        light.castShadow = true;
        applyDirectionalShadow(light);
      }
      return light;
    }
    case "point": {
      const light = new THREE.PointLight(cfg.color, cfg.intensity, cfg.distance, cfg.decay);
      light.position.set(...cfg.position);
      light.castShadow = !!cfg.cast_shadow;
      return light;
    }
    case "spot": {
      const light = new THREE.SpotLight(cfg.color, cfg.intensity, cfg.distance, cfg.angle, cfg.penumbra, cfg.decay);
      light.position.set(...cfg.position);
      light.target.position.set(...cfg.target);
      light.castShadow = !!cfg.cast_shadow;
      return light;
    }
    default:
      console.error(`unknown light type '${cfg.ltype}'`);
      return null;
  }
}

/**
 * Replaces every light currently in the scene (`lights`, mutated in
 * place so callers keep the same reference) with a fresh set built from
 * `configs` -- see Swift.set_lights()/launch(lights=). A light with a
 * `.target` (directional/spot) needs that target added to the scene
 * separately, since three.js's own target defaults to being un-parented.
 *
 * @param {THREE.Scene} scene
 * @param {THREE.Light[]} lights current lights, mutated in place
 * @param {object[]} configs new light configs, Light.to_dict()'s shape
 */
export function setLights(scene, lights, configs) {
  for (const light of lights) {
    if (light.target) scene.remove(light.target);
    scene.remove(light);
  }
  lights.length = 0;

  for (const cfg of configs) {
    const light = buildLight(cfg);
    if (!light) continue;
    scene.add(light);
    if (light.target) scene.add(light.target);
    lights.push(light);
  }
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
  // Negative y puts the camera on the side that makes the world +x axis
  // (AxesHelper's red line) read as screen-right, matching the usual
  // convention -- with DEFAULT_UP = +z, a camera at +y looking back
  // toward the origin has its own right vector pointing -x.
  camera.position.set(0.2, -1.2, 0.7);

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
    color: GROUND_COLOR,
    specular: 0x101010,
    side: THREE.DoubleSide,
    transparent: true,
  });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(GROUND_SIZE, GROUND_SIZE), groundMaterial);
  ground.receiveShadow = true;
  scene.add(ground);

  const lights = [];
  setLights(scene, lights, DEFAULT_LIGHTS);

  const axesHelper = new THREE.AxesHelper(5);
  scene.add(axesHelper);

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    resizeLines(window.innerWidth, window.innerHeight);
  });

  return { scene, camera, renderer, controls, axesHelper, ground, groundMaterial, lights };
}
