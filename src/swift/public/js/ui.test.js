import assert from "node:assert/strict";
import { test } from "node:test";

import { Slider } from "./ui.js";

// A real HTMLInputElement's .value getter always returns a string, no
// matter what type was assigned to it -- this stub replicates exactly that
// coercion (and nothing else) so the test actually exercises the same
// string-vs-number trap the real DOM sets, instead of trivially passing
// because a plain stub property kept whatever type was assigned.
function stubElement() {
  let value = "";
  return {
    style: {},
    innerHTML: "",
    addEventListener() {},
    insertAdjacentHTML() {},
    getElementsByTagName: () => [],
    get value() {
      return String(value);
    },
    set value(v) {
      value = v;
    },
  };
}

test("Slider reports a numeric .data, not the DOM's stringified value", (t) => {
  const originalDocument = globalThis.document;
  globalThis.document = { getElementById: () => stubElement() };
  t.after(() => {
    globalThis.document = originalDocument;
  });

  // Regression test: Slider.onInput() set this.data = this.slider.value
  // directly -- since HTMLInputElement.value is always a string, this.data
  // silently became "0.3" instead of 0.3. update() (and so onInput()) runs
  // once at construction time, so the bug showed up on the very first
  // event.py callback even if no slider was ever touched.
  const slider = new Slider({
    id: 0,
    desc: "Box X",
    unit: "m",
    precision: 2,
    value: 0.3,
    step: 0.01,
    min: -0.5,
    max: 0.5,
  });

  assert.equal(typeof slider.data, "number");
  assert.equal(slider.data, 0.3);
});
