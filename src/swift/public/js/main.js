import { createScene } from "./scene.js";
import { SwiftObject } from "./shapes.js";
import { Slider, Button, Label, Select, Checkbox, Radio } from "./ui.js";
import { WebSocketTransport, portFromLocation } from "./comms.js";
import { Recorder } from "./recording.js";
import { FPS, SimTime } from "./hud.js";

const { scene, camera, renderer, controls, axesHelper } = createScene();

const fps = new FPS(document.getElementById("fps"));
const simTime = new SimTime(document.getElementById("sim-time"));
const recorder = new Recorder();

/**
 * Swift.py's `swift_objects` list, mirrored index-for-index -- both robots
 * and shapes are added as one flat list of parts, addressed by the same
 * index space (see shapes.js's module docstring for the wire protocol).
 * @type {Array<SwiftObject|null>}
 */
const objects = [];
const uiElements = [];

const UI_CLASSES = { slider: Slider, button: Button, label: Label, select: Select, checkbox: Checkbox, radio: Radio };

function saveScreenshot(fileName) {
  const link = document.createElement("a");
  link.download = `${fileName}.png`;
  link.href = renderer.domElement.toDataURL("image/png");
  link.click();
}

// launch()'s _add_controls() always adds Pause/Realtime/Render as the
// first three elements, right after connecting and before any user code
// runs -- so id 0 is reliably the pause button. Space just simulates a
// click on it, reusing the exact same click -> "changed" -> shape_poses
// response path a mouse click would take.
window.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.target.tagName === "INPUT") return;
  const pauseButton = uiElements.find((el) => el.id === 0);
  if (pauseButton?.button) {
    e.preventDefault();
    pauseButton.button.click();
  }
});

const transport = new WebSocketTransport(`ws://localhost:${portFromLocation()}/`);

transport.onOpen(() => {
  transport.send("Connected");
  requestAnimationFrame(animate);
});

transport.onClose(() => {
  if (recorder.active) recorder.stop();
  // window.close() silently no-ops on a tab the browser didn't consider
  // script-opened, which is the common case here -- so don't rely on it
  // to clean up the now-stale sidenav controls, do that directly instead.
  if (recorder.autoclose) setTimeout(() => window.close(), 5000);

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
      transport.send(objects[id].isMounted() ? 1 : 0);
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
    case "camera_pose": {
      camera.position.set(...data.t);
      camera.lookAt(...data.look_at);
      controls.target.set(...data.look_at);
      controls.update();
      break;
    }
    case "screenshot": {
      saveScreenshot(data[0]);
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
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
  recorder.captureFrame(renderer.domElement);
  fps.frame();
}
