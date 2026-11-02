// Mesh, material and texture files in a notebook. There is no server to fetch
// them from, so Python sends each file ahead of the shape that uses it (see
// swift/_assets.py) and notebook.js makes a blob URL for it. A loader still asks
// for "/retrieve/<path>", as it does on the desktop; the URL modifier installed
// here answers that request with the blob. Anything it does not hold is left
// alone, and fails to load, which is reported like any other load error.

/**
 * The name a file goes by in the notebook, from the URL a loader asks for: the
 * path with forward slashes, no drive letter and no "." or ".." parts. Python
 * names the files it sends the same way (asset_key() in swift/_assets.py), and
 * the two must agree.
 *
 * @param {string} url the URL asked for, "/retrieve" and a path, or a path
 *   relative to a file's own directory resolved against one
 * @returns {string}
 */
export function assetKey(url) {
  let path = url.replace(/^\/retrieve/, "");
  try {
    path = decodeURI(path);
  } catch {
    // not valid percent-encoding: take it as it is
  }
  path = path.replace(/\\/g, "/").replace(/^[A-Za-z]:/, "");

  const parts = [];
  for (const part of path.split("/")) {
    if (part === "..") parts.pop();
    else if (part !== "." && part !== "") parts.push(part);
  }
  return "/" + parts.join("/");
}

/**
 * Make a loading manager answer requests for files held in `assets`.
 *
 * @param {{setURLModifier: Function}} manager e.g. THREE.DefaultLoadingManager,
 *   which every loader in shapes.js and scene.js uses
 * @param {Map<string, string>} assets asset key -> URL to load it from
 */
export function installAssetUrls(manager, assets) {
  manager.setURLModifier((url) => {
    if (url.startsWith("data:") || url.startsWith("blob:")) return url;
    return assets.get(assetKey(url)) ?? url;
  });
}
