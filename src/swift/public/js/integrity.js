// Reports a SHA-256 of each of Swift's own files this page loaded, so the
// Python side can tell whether the browser is running the same code the
// server has on disk -- e.g. a stale copy held by a caching proxy, or a file
// edited on disk mid-session. Sent in the very first websocket message; see
// SwiftRoute._check_js_assets(), which recomputes the same hashes from the
// files and warns, naming any that differ.
//
// Content hashes rather than a version string: nothing to bump or keep in
// sync at release time, it works in editable/dev checkouts, and it also
// catches a changed file whose version didn't change. Only Swift's own files
// are covered -- js/vendor/ (three.js and friends) is pinned and verified
// against the lockfile by vendor-check.yml, and is nearly all of the bytes.

/**
 * Whether a path (relative to the served public/ root) is one of Swift's own
 * files -- the page, its stylesheet, and its top-level modules. js/vendor/
 * (a subdirectory) and the icons are deliberately excluded.
 *
 * @param {string} path
 * @returns {boolean}
 */
export function isSwiftAsset(path) {
  return path === "index.html" || path === "style/index.css" || /^js\/[^/]+\.js$/.test(path);
}

/**
 * The Swift-owned files a page loaded, as paths relative to the directory the
 * page itself was served from. Always includes "index.html" (the page).
 *
 * @param {string[]} resourceUrls URLs of everything the page loaded
 * @param {string} baseHref the directory URL the page was served from
 * @returns {string[]} sorted, de-duplicated relative paths
 */
export function loadedAssetPaths(resourceUrls, baseHref) {
  const base = new URL(".", baseHref).href;
  const paths = new Set(["index.html"]);
  for (const url of resourceUrls) {
    const href = new URL(url, base).href.split(/[?#]/)[0];
    if (!href.startsWith(base)) continue;
    const path = href.slice(base.length);
    if (isSwiftAsset(path)) paths.add(path);
  }
  return [...paths].sort();
}

/**
 * Lowercase hex SHA-256 of some bytes, or null where the browser doesn't
 * provide it (crypto.subtle only exists in secure contexts: https, or
 * localhost -- not a plain-http LAN address).
 *
 * @param {ArrayBuffer} buffer
 * @returns {Promise<string|null>}
 */
export async function sha256Hex(buffer) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const digest = new Uint8Array(await subtle.digest("SHA-256", buffer));
  return [...digest].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// How many files are fetched at once. SwiftServer is a ThreadingTCPServer with
// Python's default listen backlog of 5, and Windows refuses (ECONNREFUSED)
// connections beyond that queue rather than holding them, so an unbounded
// burst loses fetches there. Browsers cap connections per host at about this
// anyway, but a runtime with no such cap (Node, in the integration test) does
// not.
const MAX_CONCURRENT_FETCHES = 4;

/**
 * Hash each path by fetching it, a few at a time. A path whose fetch fails
 * maps to null ("couldn't check"), which the Python side ignores rather than
 * reporting as stale.
 *
 * @param {string[]} paths
 * @param {(path: string) => Promise<Response>} fetchFn
 * @returns {Promise<Object<string, string|null>|null>} path -> hash, or null
 *   overall if hashing isn't available in this browser
 */
export async function hashAssets(paths, fetchFn) {
  if (!globalThis.crypto?.subtle) return null;
  const hashes = {};
  let next = 0;
  const worker = async () => {
    while (next < paths.length) {
      const path = paths[next++];
      try {
        const response = await fetchFn(path);
        hashes[path] = response.ok ? await sha256Hex(await response.arrayBuffer()) : null;
      } catch {
        hashes[path] = null;
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT_FETCHES, paths.length) }, worker));
  return Object.fromEntries(paths.map((path) => [path, hashes[path]]));
}

let cached = null;

/**
 * Hashes of the Swift files this page loaded (browser only). Computed once,
 * at load time, and remembered -- the point is what this page *started* with,
 * not whatever the server would serve now. Never rejects and never takes
 * more than a few seconds: null means "couldn't check", not "stale".
 *
 * @returns {Promise<Object<string, string|null>|null>}
 */
export function computeAssetHashes() {
  if (!cached) {
    const base = document.baseURI;
    const urls = performance.getEntriesByType("resource").map((entry) => entry.name);
    const work = hashAssets(loadedAssetPaths(urls, base), (path) => fetch(new URL(path, base)));
    const timeout = new Promise((resolve) => setTimeout(() => resolve(null), 3000));
    cached = Promise.race([work, timeout]).catch(() => null);
  }
  return cached;
}
