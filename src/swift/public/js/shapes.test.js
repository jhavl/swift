import assert from "node:assert/strict";
import { test } from "node:test";

// shapes.js references window.innerWidth/innerHeight at module top level
// (lineResolution, for LineMaterial's resolution uniform) -- harmless in a
// real browser, but nothing under Node provides `window` at all, and a
// static `import` is hoisted before any stubbing here would run. A dynamic
// import(), which isn't hoisted, lets `window` be stubbed first.
globalThis.window ??= { innerWidth: 0, innerHeight: 0 };
const { retrieveUrl, loadAxes } = await import("./shapes.js");

// Regression test for jhavl/swift#152: a Windows path's backslashes must be
// converted to forward slashes *before* the drive-letter strip, not after --
// otherwise the constructed URL has no literal '/' between "/retrieve" and
// the rest, fails SwiftRoute.py's self.path.startswith("/retrieve/") check,
// and 404s.
test("retrieveUrl converts a Windows path's backslashes and strips the drive letter", (t) => {
  const url = retrieveUrl("C:\\Users\\test\\meshes\\panda_link0.stl");
  assert.equal(url, "/retrieve/Users/test/meshes/panda_link0.stl");
});

// spatialgeometry now serializes Mesh filenames with forward slashes
// (Mesh.to_dict()), so a Windows server sends "C:/Users/..." -- the drive
// letter must still be recognized and stripped.
test("retrieveUrl strips the drive letter from a forward-slash Windows path", (t) => {
  const url = retrieveUrl("C:/Users/test/meshes/panda_link0.stl");
  assert.equal(url, "/retrieve/Users/test/meshes/panda_link0.stl");
});

test("retrieveUrl handles a Windows path with mixed separators", (t) => {
  const url = retrieveUrl("C:\\Users/test\\meshes/panda_link0.stl");
  assert.equal(url, "/retrieve/Users/test/meshes/panda_link0.stl");
});

// jhavl/swift#157: the decision must not depend on the browser's OS. A
// swift server running in WSL sends POSIX paths to a Windows browser, and
// stripping the "first two characters" of "/home/..." breaks them.
test("retrieveUrl leaves a POSIX path unaffected (e.g. WSL server, Windows browser)", (t) => {
  const url = retrieveUrl("/home/test/meshes/panda_link0.stl");
  assert.equal(url, "/retrieve/home/test/meshes/panda_link0.stl");
});

test("retrieveUrl only treats a leading drive letter as one", (t) => {
  // A colon elsewhere in a POSIX path is not a drive letter.
  const url = retrieveUrl("/data/a:/b.stl");
  assert.equal(url, "/retrieve/data/a:/b.stl");
});

test("retrieveUrl URI-encodes characters that need it", (t) => {
  const url = retrieveUrl("C:\\My Meshes\\arm link.stl");
  assert.equal(url, "/retrieve/My%20Meshes/arm%20link.stl");
});

// spatialgeometry.Axes: color is null when none was given (X red / Y green /
// Z blue), else one color overriding all three axes in either style.
const axesPart = (extra) => ({
  stype: "axes",
  t: [0, 0, 0],
  q: [0, 0, 0, 1],
  length: 1,
  radius: 0,
  linewidth: 1,
  arrows: false,
  color: null,
  opacity: 1,
  ...extra,
});

function loaded(part) {
  loadAxes(part, { add() {} }, () => {});
  return part.mesh;
}

// AxesHelper's per-vertex colors: two vertices per axis, 3 floats each.
const lineColors = (mesh) => {
  const a = mesh.geometry.attributes.color.array;
  return [0, 6, 12].map((i) => Array.from(a.slice(i, i + 3)));
};

// One color per arrow; the shaft is a Line2 or a Mesh, and either way the
// material's color is the one that matters.
const arrowColors = (group) => group.children.map((arrow) => arrow.children[0].material.color.getHex());

test("Axes with no color is red/green/blue in line style", (t) => {
  const c = lineColors(loaded(axesPart({})));
  assert.deepEqual(c, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
});

test("Axes with no color is red/green/blue in arrow style", (t) => {
  assert.deepEqual(arrowColors(loaded(axesPart({ arrows: true }))), [0xff0000, 0x00ff00, 0x0000ff]);
});

test("Axes color overrides all three axes in line style", (t) => {
  const c = lineColors(loaded(axesPart({ color: 0xff00ff })));
  assert.deepEqual(c, [[1, 0, 1], [1, 0, 1], [1, 0, 1]]);
});

test("Axes color overrides all three axes in arrow style, line and tube shafts", (t) => {
  for (const radius of [0, 0.02]) {
    const mesh = loaded(axesPart({ arrows: true, radius, color: 0xff00ff }));
    assert.deepEqual(arrowColors(mesh), [0xff00ff, 0xff00ff, 0xff00ff]);
  }
});
