import assert from "node:assert/strict";
import { test } from "node:test";

import { Recorder } from "./recording.js";

// ccapture.js 2.x removed the gif worker script (gifenc is bundled into
// the UMD build directly) -- workersPath is now a no-op option that
// should no longer be passed at all (see the js/vendor/build.cjs change
// alongside this test, and jhavl/swift's ccapture.js 2.0.0 migration).
test("Recorder's CCapture options no longer include workersPath", (t) => {
  let capturedOptions = null;
  class FakeCCapture {
    constructor(options) {
      capturedOptions = options;
    }
    start() {}
    capture() {}
    stop() {}
    save() {}
  }
  const originalCCapture = globalThis.CCapture;
  globalThis.CCapture = FakeCCapture;
  t.after(() => {
    globalThis.CCapture = originalCCapture;
  });

  const recorder = new Recorder({});
  recorder.start(30, "test-recording", "gif");

  assert.ok(capturedOptions, "CCapture should have been constructed");
  assert.equal(capturedOptions.format, "gif");
  assert.equal(capturedOptions.framerate, 30);
  assert.equal(capturedOptions.name, "test-recording");
  assert.ok(!("workersPath" in capturedOptions), "workersPath is a no-op in ccapture.js 2.x and should not be passed");
});

test("Recorder still uses CCapture for png/jpg, not just gif", (t) => {
  let capturedOptions = null;
  class FakeCCapture {
    constructor(options) {
      capturedOptions = options;
    }
    start() {}
    capture() {}
    stop() {}
    save() {}
  }
  const originalCCapture = globalThis.CCapture;
  globalThis.CCapture = FakeCCapture;
  t.after(() => {
    globalThis.CCapture = originalCCapture;
  });

  const recorder = new Recorder({});
  recorder.start(30, "frame", "png");

  assert.equal(capturedOptions.format, "png");
});
