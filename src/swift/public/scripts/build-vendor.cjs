#!/usr/bin/env node
/**
 * Refreshes js/vendor/ from the npm dependencies declared in package.json.
 *
 * Run `npm ci && npm run build:vendor` after bumping a version in
 * package.json, then commit the result -- this is a maintainer-side tool,
 * not a build step end users need. The output is committed to git so
 * installing/using swift-sim never requires Node.js.
 *
 * Vendors only the specific examples/jsm modules ("three/addons/" via
 * the import map in index.html) that ENTRY_POINTS below -- and their
 * transitive imports, resolved automatically by walking `from "./..."`
 * statements -- actually reach, rather than three's whole examples/ tree
 * (hundreds of files this app never uses). The transitive set shifts
 * between three.js releases as loaders gain/drop shared utility imports
 * (confirmed happening: 10 files at 0.125.0, 15 at 0.185.1) -- so this
 * is computed fresh each run instead of hand-maintained, specifically to
 * not silently drift the way a hardcoded list would.
 *
 * If you add an import of a *new* examples/jsm module to app code (not
 * already reachable from an existing entry point), add it to
 * ENTRY_POINTS below too, or this script won't know to vendor it.
 *
 * three.js dropped its classic UMD global-script build somewhere after
 * r125 (ESM-only now, via three.module.js) -- nothing to vendor there
 * beyond the one file; the import map in index.html points "three" at it.
 */

const fs = require("fs");
const path = require("path");

const ROOT = __dirname + "/..";
const NODE_MODULES = ROOT + "/node_modules";
const VENDOR = ROOT + "/js/vendor";
const JSM_SRC = `${NODE_MODULES}/three/examples/jsm`;
const JSM_DEST = `${VENDOR}/examples/jsm`;

const ENTRY_POINTS = [
  "controls/OrbitControls.js",
  "loaders/ColladaLoader.js",
  "loaders/GLTFLoader.js",
  "loaders/MTLLoader.js",
  "loaders/OBJLoader.js",
  "loaders/PCDLoader.js",
  "loaders/PLYLoader.js",
  "loaders/STLLoader.js",
  "loaders/VRMLLoader.js",
];

function copyFile(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  console.log(`  ${path.relative(ROOT, dest)}`);
}

/** Resolves the transitive closure of relative `from "..."` imports. */
function resolveTransitiveImports(entryRelPaths) {
  const importRe = /from\s+["']([^"']+)["']/g;
  const visited = new Set();

  function visit(relPath) {
    if (visited.has(relPath)) return;
    const absPath = path.join(JSM_SRC, relPath);
    if (!fs.existsSync(absPath)) {
      throw new Error(`examples/jsm file not found: ${relPath} (three.js version bump renamed/removed it?)`);
    }
    visited.add(relPath);

    const text = fs.readFileSync(absPath, "utf8");
    for (const match of text.matchAll(importRe)) {
      const importPath = match[1];
      if (!importPath.startsWith(".")) continue; // bare specifier, e.g. "three"
      const depAbs = path.resolve(path.dirname(absPath), importPath);
      const depRel = path.relative(JSM_SRC, depAbs);
      visit(depRel);
    }
  }

  for (const entry of entryRelPaths) visit(entry);
  return [...visited].sort();
}

console.log("three.js build (three.module.js):");
copyFile(`${NODE_MODULES}/three/build/three.module.js`, `${VENDOR}/build/three.module.js`);
// three.module.js re-exports the WebGL/WebGPU-shared classes from here --
// split out of the single-file build as of three.js's WebGPU renderer work.
copyFile(`${NODE_MODULES}/three/build/three.core.js`, `${VENDOR}/build/three.core.js`);

console.log("CCapture:");
copyFile(
  `${NODE_MODULES}/ccapture.js/build/CCapture.all.min.js`,
  `${VENDOR}/build/CCapture.all.min.js`
);
// gif.worker.js is only shipped under src/, not build/, but
// CCapture.all.min.js's webm/gif encoders load it at runtime as a Worker
// script (workersPath option in recording.js) -- without it, recording
// starts and produces a valid-looking but empty (frameless) output file,
// silently: the Worker fails to load and nothing else surfaces the error.
copyFile(
  `${NODE_MODULES}/ccapture.js/src/gif.worker.js`,
  `${VENDOR}/build/gif.worker.js`
);

const jsmFiles = resolveTransitiveImports(ENTRY_POINTS);
console.log(`examples/jsm (${ENTRY_POINTS.length} entry points, ${jsmFiles.length} files including transitive imports):`);
for (const f of jsmFiles) {
  copyFile(`${JSM_SRC}/${f}`, `${JSM_DEST}/${f}`);
}

// Remove anything vendored previously that's no longer part of the
// resolved set (a renamed/dropped transitive dependency, e.g.
// VRMLoader.js -> VRMLLoader.js between 0.125.0 and 0.185.1).
if (fs.existsSync(JSM_DEST)) {
  const vendored = fs
    .readdirSync(JSM_DEST, { recursive: true, withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => path.relative(JSM_DEST, path.join(e.parentPath ?? e.path, e.name)));
  const keep = new Set(jsmFiles);
  for (const f of vendored) {
    if (!keep.has(f)) {
      fs.rmSync(path.join(JSM_DEST, f));
      console.log(`  removed stale: js/vendor/examples/jsm/${f}`);
    }
  }
}

console.log("\nDone. Review `git status`/`git diff` before committing.");
