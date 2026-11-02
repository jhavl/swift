import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

globalThis.window ??= { innerWidth: 1, innerHeight: 1 }; // read when shapes.js loads
const { retrieveUrl } = await import("./shapes.js");
const { assetKey, installAssetUrls } = await import("./assets.js");

// The names Python gives the files it sends: tests/test_assets.py reads the same table
const here = dirname(fileURLToPath(import.meta.url));
const { cases } = JSON.parse(readFileSync(join(here, "../../../../tests/data/asset_keys.json"), "utf8"));

for (const { path, key } of cases) {
  test(`the browser names a file as Python does: ${path}`, () => {
    // what a loader asks for a mesh file, which is what Python sent under `key`
    assert.equal(assetKey(retrieveUrl(path)), key);
  });
}

test("a texture beside a mesh is named the same however its path is written in the mesh file", () => {
  const base = "/retrieve/home/user/my%20meshes/";
  assert.equal(assetKey(base + "paint.png"), "/home/user/my meshes/paint.png");
  assert.equal(assetKey(base + "paint%20one.png"), "/home/user/my meshes/paint one.png");
  assert.equal(assetKey(base + "paint one.png"), "/home/user/my meshes/paint one.png");
  assert.equal(assetKey(base + "../tex/paint.png"), "/home/user/tex/paint.png");
  assert.equal(assetKey(base + "./paint.png"), "/home/user/my meshes/paint.png");
});

test("a name that is not valid percent-encoding is taken as it is", () => {
  assert.equal(assetKey("/retrieve/home/user/100%/a.png"), "/home/user/100%/a.png");
});

function fakeManager() {
  const manager = { modifier: null, setURLModifier(fn) { this.modifier = fn; } };
  return manager;
}

test("requests for files that were sent are answered with their blobs", () => {
  const manager = fakeManager();
  installAssetUrls(manager, new Map([["/home/user/arm.stl", "blob:1"]]));

  assert.equal(manager.modifier(retrieveUrl("/home/user/arm.stl")), "blob:1");
});

test("requests for anything else are left alone", () => {
  const manager = fakeManager();
  installAssetUrls(manager, new Map([["/home/user/arm.stl", "blob:1"]]));

  assert.equal(manager.modifier("/retrieve/home/user/other.stl"), "/retrieve/home/user/other.stl");
  assert.equal(manager.modifier("data:image/png;base64,AAAA"), "data:image/png;base64,AAAA");
  assert.equal(manager.modifier("blob:2"), "blob:2");
});

test("three's own loading manager can be given the modifier", async () => {
  const THREE = await import("three");
  installAssetUrls(THREE.DefaultLoadingManager, new Map([["/a/b.stl", "blob:9"]]));
  assert.equal(THREE.DefaultLoadingManager.resolveURL("/retrieve/a/b.stl"), "blob:9");
  THREE.DefaultLoadingManager.setURLModifier(undefined);
});
