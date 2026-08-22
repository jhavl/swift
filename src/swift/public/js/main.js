import { createScene, setGroundPattern, updateGroundPatternPosition, setLights } from "./scene.js";
import { SwiftObject } from "./shapes.js";
import { Slider, Button, Label, Select, Checkbox, Radio } from "./ui.js";
import { WebSocketTransport, portFromLocation, SWIFT_JS_VERSION } from "./comms.js";
import { Recorder } from "./recording.js";
import { FPS, SimTime } from "./hud.js";
import { saveScreenshot, timestampedScreenshotName } from "./screenshot.js";

const { scene, camera, renderer, controls, axesHelper, ground, groundMaterial, lights } = createScene();

const fps = new FPS(document.getElementById("fps"));
const simTime = new SimTime(document.getElementById("sim-time"));
const recorder = new Recorder(renderer.domElement);

/**
 * Swift.py's `swift_objects` list, mirrored index-for-index -- both robots
 * and shapes are added as one flat list of parts, addressed by the same
 * index space (see shapes.js's module docstring for the wire protocol).
 * @type {Array<SwiftObject|null>}
 */
const objects = [];
const uiElements = [];

const UI_CLASSES = { slider: Slider, button: Button, label: Label, select: Select, checkbox: Checkbox, radio: Radio };

// Seconds to wait after losing the connection before self-closing the tab
// -- set by the "browser_timeout" message, sent right after launch()
// connects (see Swift.py's launch(browser_timeout=)). null means never.
let autoCloseDelay = null;

// launch()'s _add_controls() always adds Pause/Realtime/Render as the
// first three elements, right after connecting and before any user code
// runs -- so id 0 is reliably the pause button. Space just simulates a
// click on it, reusing the exact same click -> "changed" -> shape_poses
// response path a mouse click would take.
window.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;

  if (e.code === "Space") {
    const pauseButton = uiElements.find((el) => el.id === 0);
    if (pauseButton?.button) {
      e.preventDefault();
      pauseButton.button.click();
    }
  } else if (e.code === "KeyS" && !e.ctrlKey && !e.metaKey && !e.altKey) {
    // Bare 's' -- Ctrl/Cmd+S is left alone so it still triggers the
    // browser's own "Save Page As", rather than fighting it.
    saveScreenshot(renderer.domElement, timestampedScreenshotName());
  }
});

const transport = new WebSocketTransport(`ws://localhost:${portFromLocation()}/`);

// Guards animate()'s requestAnimationFrame chain -- otherwise it reschedules
// itself forever regardless of connection state, rendering a static scene
// and updating the FPS counter at full framerate indefinitely after
// disconnect for no reason (found testing the notebook embedding path,
// where the tab commonly can't self-close -- see browser_timeout's docs).
let connected = false;

transport.onOpen(() => {
  // Plain JSON, not one of main.js's own [func, data] wire-protocol
  // pairs -- this is the very first message, before Python's read loop
  // has even started dispatching those; SwiftRoute.py's start_servers()
  // reads it directly to check this tab's JS version against the
  // installed package's, so it can warn about a stale browser cache
  // rather than something more confusing further down the line.
  transport.send(JSON.stringify({ event: "connected", js_version: SWIFT_JS_VERSION }));
  connected = true;
  requestAnimationFrame(animate);
});

transport.onClose(() => {
  connected = false;
  if (recorder.active) recorder.stop();
  // window.close() silently no-ops on a tab the browser didn't consider
  // script-opened, which is the common case here -- so don't rely on it
  // to clean up the now-stale sidenav controls, do that directly instead.
  // recorder.autoclose is only false mid-GIF-save (the user still needs
  // the tab to trigger that download), independent of autoCloseDelay.
  if (recorder.autoclose && autoCloseDelay !== null) {
    setTimeout(() => window.close(), autoCloseDelay * 1000);
  }

  const sidenav = document.getElementById("sidenav");
  sidenav.innerHTML = "";
  sidenav.style.display = "none";

  const controlPanel = document.getElementById("control-panel");
  controlPanel.innerHTML = "";
  controlPanel.style.display = "none";

  const banner = document.createElement("div");
  banner.className = "disconnected-banner";
  banner.textContent = "Disconnected";
  document.body.appendChild(banner);
});

transport.onMessage((func, data) => {
  switch (func) {
    case "shape": {
      const id = objects.length;
      objects.push(new SwiftObject(scene, data));
      transport.send(id);
      break;
    }
    case "shape_mounted": {
      const [id, _count] = data;
      const obj = objects[id];
      // A non-zero code (-1 unsupported shape type, -2 asset/mesh load
      // failed -- see shapes.js's load()) tells Swift.py's poll loop to
      // stop and raise with the specific reason, rather than retry
      // forever -- see SwiftObject.hasError()/errorCode()/errorReason()
      // and Swift._wait_mounted().
      const reply = obj.hasError() ? [obj.errorCode, obj.errorReason] : [obj.isMounted() ? 1 : 0, null];
      transport.send(reply);
      break;
    }
    case "remove": {
      objects[data]?.remove(scene);
      renderer.renderLists.dispose();
      objects[data] = null;
      transport.send(0);
      break;
    }
    case "shape_update": {
      const [id, partData] = data;
      objects[id].updatePart(0, partData);
      transport.send(0);
      break;
    }
    case "shape_poses": {
      for (const [i, poses] of data) {
        objects[i]?.setPoses(poses);
      }

      const changes = {};
      for (const el of uiElements) {
        if (el.changed) {
          changes[el.id] = el.data;
          el.changed = false;
        }
      }
      transport.send(JSON.stringify(changes));
      break;
    }
    case "element": {
      const Cls = UI_CLASSES[data.element];
      if (Cls) uiElements.push(new Cls(data));
      transport.send(0);
      break;
    }
    case "update_element": {
      const el = uiElements.find((e) => e.id === data.id);
      el?.update(data);
      break;
    }
    case "sim_time": {
      simTime.display(parseFloat(data));
      break;
    }
    case "axes": {
      axesHelper.visible = data;
      break;
    }
    case "browser_timeout": {
      autoCloseDelay = data;
      break;
    }
    case "ground_opacity": {
      groundMaterial.opacity = data;
      break;
    }
    case "ground_pattern": {
      setGroundPattern(ground, groundMaterial, data.pattern, data.width);
      break;
    }
    case "lights": {
      setLights(scene, lights, data);
      break;
    }
    case "camera_pose": {
      camera.position.set(...data.t);
      camera.lookAt(...data.look_at);
      controls.target.set(...data.look_at);
      controls.update();
      break;
    }
    case "screenshot": {
      saveScreenshot(renderer.domElement, data[0]);
      transport.send(0);
      break;
    }
    case "start_recording": {
      const [framerate, name, format] = data;
      recorder.start(parseFloat(framerate), name, format);
      transport.send(0);
      break;
    }
    case "stop_recording": {
      recorder.stop();
      setTimeout(() => transport.send(0), 5000);
      break;
    }
    case "close": {
      // Connection teardown itself (see transport.onClose above) does the
      // real cleanup; this message is just Python's heads-up before it.
      break;
    }
    default:
      console.error(`Unknown message: ${func}`);
  }
});

function animate() {
  if (!connected) return; // freeze on the last frame instead of looping forever
  requestAnimationFrame(animate);
  updateGroundPatternPosition(ground, camera.position);
  renderer.render(scene, camera);
  recorder.captureFrame(renderer.domElement);
  fps.frame();
}
