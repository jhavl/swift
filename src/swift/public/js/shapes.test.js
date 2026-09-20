import assert from "node:assert/strict";
import { test } from "node:test";

// shapes.js references window.innerWidth/innerHeight at module top level
// (lineResolution, for LineMaterial's resolution uniform) -- harmless in a
// real browser, but nothing under Node provides `window` at all, and a
// static `import` is hoisted before any stubbing here would run. A dynamic
// import(), which isn't hoisted, lets `window` be stubbed first.
globalThis.window ??= { innerWidth: 0, innerHeight: 0 };
const { retrieveUrl } = await import("./shapes.js");

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
