import assert from "node:assert/strict";
import { test } from "node:test";

// shapes.js references window.innerWidth/innerHeight at module top level
// (lineResolution, for LineMaterial's resolution uniform) -- harmless in a
// real browser, but nothing under Node provides `window` at all, and a
// static `import` is hoisted before any stubbing here would run. A dynamic
// import(), which isn't hoisted, lets `window` be stubbed first.
globalThis.window ??= { innerWidth: 0, innerHeight: 0 };
const { meshRetrieveUrl } = await import("./shapes.js");

// Regression test for jhavl/swift#152: a Windows mesh path's backslashes
// must be converted to forward slashes *before* the drive-letter strip,
// not after -- otherwise the constructed URL has no literal '/' between
// "/retrieve" and the rest, fails SwiftRoute.py's
// self.path.startswith("/retrieve/") check, and 404s.
test("meshRetrieveUrl converts a Windows path's backslashes and strips the drive letter", (t) => {
  const url = meshRetrieveUrl("C:\\Users\\test\\meshes\\panda_link0.stl", true);
  assert.equal(url, "/retrieve/Users/test/meshes/panda_link0.stl");
});

test("meshRetrieveUrl leaves a POSIX path unaffected", (t) => {
  const url = meshRetrieveUrl("/home/test/meshes/panda_link0.stl", false);
  assert.equal(url, "/retrieve/home/test/meshes/panda_link0.stl");
});
