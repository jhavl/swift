import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { MessageHub, buildModules, buildPage, resolveSpecifier, toText } from "./notebook.js";

const encoder = new TextEncoder();

// What a browser's blob URL is to the page: a short URL that serves the source,
// and can be imported. (A data: URL would do too, but each module's URL would
// then contain those of everything it imports, and these grow without bound.)
const scratch = mkdtempSync(join(tmpdir(), "swift-notebook-test-"));
let written = 0;
function fileUrl(source) {
  const path = join(scratch, `module${written++}.mjs`);
  writeFileSync(path, source);
  return pathToFileURL(path).href;
}

/** Files as Python sends them: path -> bytes. */
function fakeFiles(sources) {
  return Object.fromEntries(Object.entries(sources).map(([path, text]) => [path, encoder.encode(text)]));
}

/** The files Python sends for real: the same selection as swift/_notebook.py. */
function realFiles() {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const files = {};
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else files[relative(root, path)] = readFileSync(path);
    }
  };
  walk(join(root, "js"));
  walk(join(root, "style"));
  files["index.html"] = readFileSync(join(root, "index.html"));
  for (const path of Object.keys(files)) if (path.endsWith(".test.js")) delete files[path];
  return files;
}

test("resolveSpecifier resolves relative paths against the importing file", () => {
  assert.equal(resolveSpecifier("./shapes.js", "js/main.js"), "js/shapes.js");
  assert.equal(resolveSpecifier("./three.core.js", "js/vendor/build/three.module.js"), "js/vendor/build/three.core.js");
  assert.equal(resolveSpecifier("../utils/BufferGeometryUtils.js", "js/vendor/examples/jsm/loaders/GLTFLoader.js"),
    "js/vendor/examples/jsm/utils/BufferGeometryUtils.js");
});

test("resolveSpecifier maps three and its addons to the vendored copy", () => {
  assert.equal(resolveSpecifier("three", "js/scene.js"), "js/vendor/build/three.module.js");
  assert.equal(
    resolveSpecifier("three/addons/loaders/STLLoader.js", "js/shapes.js"),
    "js/vendor/examples/jsm/loaders/STLLoader.js",
  );
});

test("resolveSpecifier leaves anything else alone", () => {
  assert.equal(resolveSpecifier("fs", "js/main.js"), null);
  assert.equal(resolveSpecifier("https://example.com/x.js", "js/main.js"), null);
});

test("toText reads the kinds of binary a widget delivers", () => {
  const bytes = encoder.encode("héllo");
  assert.equal(toText(bytes), "héllo");
  assert.equal(toText(bytes.buffer), "héllo");
  assert.equal(toText(new DataView(bytes.buffer)), "héllo");
});

test("buildModules rewrites imports so the modules load and share instances", async () => {
  const files = fakeFiles({
    "js/main.js": `import { a } from "./a.js";\nimport { b } from './b.js';\nexport { c } from "./b.js";\nexport const r = [a, b];`,
    "js/a.js": `import { shared } from "./shared.js";\nexport const a = shared;`,
    "js/b.js": `import {\n  shared,\n} from "./shared.js";\nexport const b = shared;\nexport * from "./c.js";`,
    "js/c.js": `export const c = 3;`,
    "js/shared.js": `export const shared = { n: 1 };`,
  });

  const { urls, unresolved } = buildModules(files, "js/main.js", fileUrl);

  assert.deepEqual(unresolved, []);
  const main = await import(urls.get("js/main.js"));
  assert.equal(main.r[0], main.r[1], "one module instance, however it is imported");
  assert.equal(main.c, 3);
});

test("buildModules gives three, addons and relative imports the same module", async () => {
  const files = fakeFiles({
    "js/main.js": `import * as T from "three";\nimport { x } from "three/addons/x.js";\nexport { T, x };`,
    "js/vendor/build/three.module.js": `import { core } from "./three.core.js";\nexport const three = core;`,
    "js/vendor/build/three.core.js": `export const core = "core";`,
    "js/vendor/examples/jsm/x.js": `import { three } from "three";\nexport const x = three + "!";`,
  });

  const { urls } = buildModules(files, "js/main.js", fileUrl);
  const main = await import(urls.get("js/main.js"));

  assert.equal(main.T.three, "core");
  assert.equal(main.x, "core!");
});

test("buildModules reports an import of a file that was not sent, and leaves it as written", () => {
  const files = fakeFiles({ "js/main.js": `import { z } from "./missing.js";` });

  const { urls, unresolved } = buildModules(files, "js/main.js", (s) => s);

  assert.deepEqual(unresolved, ["js/main.js: ./missing.js"]);
  assert.match(urls.get("js/main.js"), /"\.\/missing\.js"/);
});

test("buildModules refuses a circular import", () => {
  const files = fakeFiles({
    "js/main.js": `import "./a.js";`,
    "js/a.js": `import "./main.js";`,
  });
  assert.throws(() => buildModules(files, "js/main.js", fileUrl), /circular/);
});

test("the files Python sends form a complete module graph", async () => {
  const files = realFiles();

  const { urls, unresolved } = buildModules(files, "js/main.js", fileUrl);

  assert.deepEqual(unresolved, []);
  // all of Swift's own modules and the loaders they use are in it...
  for (const path of ["js/comms.js", "js/shapes.js", "js/scene.js", "js/vendor/build/three.core.js"]) {
    assert.ok(urls.has(path), `${path} reached`);
  }
  // ...and it is loadable: shapes.js pulls in three and every loader
  globalThis.window ??= { innerWidth: 1, innerHeight: 1 }; // read when shapes.js loads
  const shapes = await import(urls.get("js/shapes.js"));
  assert.equal(typeof shapes.SwiftObject, "function");
});

test("buildPage turns index.html into a page with nothing left to fetch", () => {
  const files = realFiles();

  const { html, unresolved } = buildPage(files, fileUrl, "7");

  assert.deepEqual(unresolved, []);
  assert.doesNotMatch(html, /importmap/);
  assert.doesNotMatch(html, /\.\/js\/|src="js\/|href="\.\/style/);
  assert.match(html, /<style>[\s\S]*\.sidenav/);
  assert.match(html, /__swiftViewers\["7"\]/);
  assert.match(html, /new CommTransport\(viewer\.channel\)/);
  assert.match(html, /<script type="module" src="file:/);
  // the elements main.js looks for
  for (const id of ["canvas", "fps", "sim-time", "sidenav", "control-panel"]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
});

test("buildPage says so when index.html has changed shape", () => {
  const files = realFiles();
  files["index.html"] = encoder.encode("<html><body>different</body></html>");

  assert.throws(() => buildPage(files, fileUrl, "1"), /index\.html no longer contains/);
});

function makeHub() {
  const syncs = [];
  const seen = [];
  const hub = new MessageHub((have) => syncs.push(have));
  hub.attach((msg) => seen.push(msg));
  return { hub, syncs, seen };
}

const numbered = (seq, func = "shape") => ({ func, data: seq, seq });

test("start asks for everything sent before the hub was listening", () => {
  const { hub, syncs } = makeHub();
  hub.start();
  assert.deepEqual(syncs, [0]);
});

test("numbered messages are applied in order, once", () => {
  const { hub, seen } = makeHub();
  hub.receive(numbered(1));
  hub.receive(numbered(2));
  hub.receive(numbered(2)); // sent again
  hub.receive(numbered(3));
  assert.deepEqual(seen.map((m) => m.seq), [1, 2, 3]);
});

test("a gap is not applied, asks for a resend once, and is filled when the resend comes", () => {
  const { hub, syncs, seen } = makeHub();
  hub.receive(numbered(1));
  hub.receive(numbered(4)); // 2 and 3 were lost
  hub.receive(numbered(5));
  assert.deepEqual(seen.map((m) => m.seq), [1]);
  assert.deepEqual(syncs, [1]);

  for (const seq of [2, 3, 4, 5, 6]) hub.receive(numbered(seq)); // the resend, then live
  assert.deepEqual(seen.map((m) => m.seq), [1, 2, 3, 4, 5, 6]);

  hub.receive(numbered(9)); // a new gap asks again
  assert.deepEqual(syncs, [1, 6]);
});

test("a hub that has just started asks once even when live messages arrive first", () => {
  const { hub, syncs, seen } = makeHub();
  hub.start();
  hub.receive(numbered(3));
  assert.deepEqual(syncs, [0]);
  assert.deepEqual(seen, []);

  for (const seq of [1, 2, 3, 4]) hub.receive(numbered(seq));
  assert.deepEqual(seen.map((m) => m.seq), [1, 2, 3, 4]);
});

test("messages without a number are passed on as they come", () => {
  const { hub, seen } = makeHub();
  hub.receive({ func: "shape_poses", data: 1 });
  hub.receive(numbered(5)); // a gap...
  hub.receive({ func: "shape_poses", data: 2 }); // ...does not hold back the latest poses
  assert.deepEqual(seen.map((m) => m.data), [1, 2]);
});

test("messages that arrive before the page is listening are held, the latest of each kind", () => {
  const hub = new MessageHub(() => {});
  hub.receive(numbered(1));
  hub.receive({ func: "shape_poses", data: "old" });
  hub.receive({ func: "shape_poses", data: "new" });
  hub.receive(numbered(2));

  const seen = [];
  hub.attach((msg) => seen.push(msg));
  assert.deepEqual(seen.map((m) => m.data), [1, "new", 2]);

  hub.receive(numbered(3));
  assert.equal(seen.length, 4);
});

test("anything that is not a Swift message is ignored", () => {
  const { hub, seen } = makeHub();
  hub.receive(null);
  hub.receive({ other: 1 });
  assert.deepEqual(seen, []);
});


function assetHub() {
  const made = [];
  const revoked = [];
  const hub = new MessageHub(
    () => {},
    (pieces) => {
      made.push(pieces);
      return `blob:${made.length}`;
    },
    (url) => revoked.push(url),
  );
  const seen = [];
  hub.attach((msg) => seen.push(msg));
  return { hub, made, revoked, seen };
}

const piece = (seq, path, index, count, text) => [
  { func: "asset", data: { path, index, count }, seq },
  [encoder.encode(text)],
];

test("a mesh file sent in pieces is put together, and not passed on to the page", () => {
  const { hub, made, seen } = assetHub();
  hub.receive(...piece(1, "/a/arm.stl", 0, 2, "ab"));
  assert.equal(hub.assets.size, 0);
  hub.receive(...piece(2, "/a/arm.stl", 1, 2, "cd"));

  assert.equal(hub.assets.get("/a/arm.stl"), "blob:1");
  assert.deepEqual(made[0].map(toText), ["ab", "cd"]);
  assert.deepEqual(seen, []);
});

test("a mesh file sent again after a gap is not made twice", () => {
  const { hub, made } = assetHub();
  hub.receive(...piece(1, "/a/arm.stl", 0, 1, "ab"));
  hub.receive(...piece(1, "/a/arm.stl", 0, 1, "ab"));
  assert.equal(made.length, 1);
});

test("files held are let go of when the widget goes", () => {
  const { hub, revoked } = assetHub();
  hub.receive(...piece(1, "/a/arm.stl", 0, 1, "ab"));
  hub.dispose();
  assert.deepEqual(revoked, ["blob:1"]);
  assert.equal(hub.assets.size, 0);
});

test("buildPage gives the page the files held for it", () => {
  const { html } = buildPage(realFiles(), fileUrl, "3");
  assert.match(html, /window\.swiftAssets = viewer\.assets/);
});
