import assert from "node:assert/strict";
import { test } from "node:test";

import { hashAssets, isSwiftAsset, loadedAssetPaths, sha256Hex } from "./integrity.js";

const utf8 = (s) => new TextEncoder().encode(s).buffer;

// The standard SHA-256 test vector for "abc" -- the Python side compares
// against hashlib.sha256(...).hexdigest(), so agreement on a known value is
// what makes the two ends comparable at all.
test("sha256Hex matches the standard test vector, lowercase hex", async () => {
  assert.equal(
    await sha256Hex(utf8("abc")),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
  );
});

test("isSwiftAsset covers Swift's own page, stylesheet and modules only", () => {
  assert.equal(isSwiftAsset("index.html"), true);
  assert.equal(isSwiftAsset("style/index.css"), true);
  assert.equal(isSwiftAsset("js/main.js"), true);
  assert.equal(isSwiftAsset("js/shapes.js"), true);
});

test("isSwiftAsset excludes vendored code and icons", () => {
  assert.equal(isSwiftAsset("js/vendor/build/three.module.js"), false);
  assert.equal(isSwiftAsset("js/vendor/examples/jsm/loaders/STLLoader.js"), false);
  assert.equal(isSwiftAsset("icons/icons/dark/add.svg"), false);
  assert.equal(isSwiftAsset("favicon.ico"), false);
});

test("loadedAssetPaths picks Swift's files out of everything the page loaded", () => {
  const paths = loadedAssetPaths(
    [
      "http://localhost:52000/js/main.js",
      "http://localhost:52000/js/shapes.js",
      "http://localhost:52000/js/vendor/build/three.module.js",
      "http://localhost:52000/style/index.css",
      "http://localhost:52000/icons/icons/dark/add.svg",
      "https://cdn.example.com/js/other.js",
    ],
    "http://localhost:52000/?52001"
  );
  assert.deepEqual(paths, ["index.html", "js/main.js", "js/shapes.js", "style/index.css"]);
});

test("loadedAssetPaths always includes the page itself, and de-duplicates", () => {
  const paths = loadedAssetPaths(
    ["http://localhost:52000/js/main.js", "http://localhost:52000/js/main.js?v=2"],
    "http://localhost:52000/?52001"
  );
  assert.deepEqual(paths, ["index.html", "js/main.js"]);
});

test("loadedAssetPaths is relative to where the page was served from", () => {
  const paths = loadedAssetPaths(
    ["http://host/proxy/swift/js/main.js", "http://host/js/main.js"],
    "http://host/proxy/swift/?1"
  );
  assert.deepEqual(paths, ["index.html", "js/main.js"]);
});

test("hashAssets hashes each fetched file", async () => {
  const bodies = { "js/a.js": "abc", "js/b.js": "" };
  const hashes = await hashAssets(Object.keys(bodies), async (path) => new Response(bodies[path]));

  assert.equal(hashes["js/a.js"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  // SHA-256 of the empty string.
  assert.equal(hashes["js/b.js"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
});

test("hashAssets maps a failed fetch to null, not a rejection", async () => {
  const fetchFn = async (path) => {
    if (path === "js/gone.js") return new Response("nope", { status: 404 });
    if (path === "js/boom.js") throw new Error("network down");
    return new Response("abc");
  };
  const hashes = await hashAssets(["js/ok.js", "js/gone.js", "js/boom.js"], fetchFn);

  assert.equal(hashes["js/ok.js"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert.equal(hashes["js/gone.js"], null);
  assert.equal(hashes["js/boom.js"], null);
});

test("hashAssets returns null overall where crypto.subtle is unavailable", async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  Object.defineProperty(globalThis, "crypto", { value: {}, configurable: true });
  try {
    const hashes = await hashAssets(["js/a.js"], async () => new Response("abc"));
    assert.equal(hashes, null);
  } finally {
    if (original) Object.defineProperty(globalThis, "crypto", original);
    else delete globalThis.crypto;
  }
});
