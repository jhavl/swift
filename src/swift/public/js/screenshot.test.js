import assert from "node:assert/strict";
import { test } from "node:test";

import { saveScreenshot, timestampedScreenshotName } from "./screenshot.js";

test("timestampedScreenshotName matches swift-YYYY-MM-DD_HH-MM-SS, no colons", (t) => {
  const name = timestampedScreenshotName();
  assert.match(name, /^swift-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$/);
});

test("saveScreenshot encodes the canvas as a PNG and clicks a download link", (t) => {
  const originalDocument = globalThis.document;
  let created;
  globalThis.document = {
    createElement: () => {
      created = { clicked: false, click() { this.clicked = true; } };
      return created;
    },
  };
  t.after(() => {
    globalThis.document = originalDocument;
  });

  const canvas = { toDataURL: (type) => `data:${type};base64,stub` };
  saveScreenshot(canvas, "swift-2026-08-22_10-00-00");

  assert.equal(created.download, "swift-2026-08-22_10-00-00.png");
  assert.equal(created.href, "data:image/png;base64,stub");
  assert.equal(created.clicked, true);
});
