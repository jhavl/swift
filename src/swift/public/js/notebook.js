/**
 * Swift's viewer inside a notebook (Colab, JupyterLite): the anywidget module
 * that shows the same page the desktop serves, in a frame of the cell's output.
 *
 * There is no web server to fetch the page from, so Python sends the files
 * (swift/_notebook.py: the widget's `files`, read from the installed package)
 * and this module builds the page from them in memory: the modules are given
 * blob URLs, with their imports rewritten to match, and the page is put in an
 * iframe's `srcdoc`. The page itself is public/index.html and js/main.js
 * unchanged, which find the comm channel to Python in
 * `window.swiftTransport` instead of opening a websocket.
 *
 * anywidget loads this module on its own, as a single file, so it cannot import
 * from the others; nothing here is shared with them, and the page is built
 * from the same files the desktop uses so the two cannot drift apart.
 */

const THREE = "js/vendor/build/three.module.js";
const THREE_ADDONS = "js/vendor/examples/jsm/";

const TEXT = new TextDecoder();

/**
 * The text of a file Python sent: a DataView (what a widget delivers a binary
 * trait as), an ArrayBuffer or a typed array.
 *
 * @param {ArrayBuffer|ArrayBufferView} data
 * @returns {string}
 */
export function toText(data) {
  return TEXT.decode(data);
}

/**
 * The path in the files that an import specifier refers to, or null for one
 * that is not ours to resolve.
 *
 * @param {string} spec the specifier, as written in the import
 * @param {string} from the path of the file that imports it
 * @returns {string|null}
 */
export function resolveSpecifier(spec, from) {
  if (spec === "three") return THREE;
  if (spec.startsWith("three/addons/")) return THREE_ADDONS + spec.slice("three/addons/".length);
  if (!spec.startsWith("./") && !spec.startsWith("../")) return null;

  const parts = from.split("/").slice(0, -1);
  for (const part of spec.split("/")) {
    if (part === "..") parts.pop();
    else if (part !== ".") parts.push(part);
  }
  return parts.join("/");
}

// `import x from "a"`, `import {a, b} from "a"`, `import "a"`, `export * from "a"`
// and `export {a} from "a"`: the prefix, the quote and the specifier. Only at the
// start of a line, so that an example in a comment is not mistaken for an import.
const IMPORT_RE = /^([ \t]*(?:import|export)\b[^'"`;]*?\bfrom\s*|[ \t]*import\s*)(["'])([^"']+)\2/gm;

/**
 * Give each module a URL of its own, with its imports rewritten to the URLs
 * of the modules they refer to (dependencies first), so that modules can be
 * loaded without a server to resolve their relative paths.
 *
 * @param {Object<string, ArrayBuffer|ArrayBufferView>} files path -> contents
 * @param {string} entry the path of the module to start from
 * @param {(source: string) => string} makeUrl a URL that serves the source
 * @returns {{urls: Map<string, string>, unresolved: string[]}} the URL of every
 *   module reached, and the imports that named a file we were not sent
 *   (these are left as written, and fail when the module is loaded)
 */
export function buildModules(files, entry, makeUrl) {
  const urls = new Map();
  const unresolved = [];
  const loading = new Set();

  function load(path) {
    if (urls.has(path)) return urls.get(path);
    if (loading.has(path)) throw new Error(`circular import involving ${path}`);
    loading.add(path);

    const source = toText(files[path]).replace(IMPORT_RE, (match, before, quote, spec) => {
      const target = resolveSpecifier(spec, path);
      if (target === null) return match;
      if (!(target in files)) {
        unresolved.push(`${path}: ${spec}`);
        return match;
      }
      return `${before}${quote}${load(target)}${quote}`;
    });

    loading.delete(path);
    const url = makeUrl(source);
    urls.set(path, url);
    return url;
  }

  if (!(entry in files)) throw new Error(`${entry} was not sent`);
  load(entry);
  return { urls, unresolved };
}

/**
 * Turn index.html into a page that loads the modules built by
 * buildModules(), and hands main.js the comm channel to Python.
 *
 * @param {Object<string, ArrayBuffer|ArrayBufferView>} files path -> contents
 * @param {(source: string) => string} makeUrl a URL that serves the source
 * @param {string} viewerId the key of this viewer in the opener's
 *   `window.__swiftViewers`, where the page finds its channel
 * @returns {{html: string, unresolved: string[]}}
 */
export function buildPage(files, makeUrl, viewerId) {
  const { urls, unresolved } = buildModules(files, "js/main.js", makeUrl);

  let html = toText(files["index.html"]);
  const swap = (pattern, replacement) => {
    if (!pattern.test(html)) throw new Error(`index.html no longer contains ${pattern}; update buildPage()`);
    html = html.replace(pattern, () => replacement);
  };

  // blob: scripts are not allowed by the page's own policy (script-src 'self')
  swap(
    /<meta http-equiv="Content-Security-Policy"[^>]*>/,
    `<meta http-equiv="Content-Security-Policy" content="script-src 'unsafe-inline' blob:; object-src 'none';">`,
  );
  // every module is imported by its URL, so there is nothing for an import map to do
  swap(/<script type="importmap">[\s\S]*?<\/script>/, "");
  swap(/<link rel="stylesheet" href="\.\/style\/index\.css">/, `<style>${toText(files["style/index.css"])}</style>`);
  swap(
    /<script src="js\/vendor\/build\/ccapture\.umd\.min\.js"><\/script>/,
    `<script src="${makeUrl(toText(files["js/vendor/build/ccapture.umd.min.js"]))}"></script>`,
  );
  // the channel is made from the comms.js that main.js imports (the same
  // module, by URL), before main.js runs
  swap(
    /<script type="module" src="js\/main\.js"><\/script>/,
    `<script type="module">
      import { CommTransport } from "${urls.get("js/comms.js")}";
      const viewer = window.parent.__swiftViewers["${viewerId}"];
      window.swiftAssets = viewer.assets;
      window.swiftTransport = new CommTransport(viewer.channel);
    </script>
    <script type="module" src="${urls.get("js/main.js")}"></script>`,
  );

  return { html, unresolved };
}

/**
 * Receives Python's messages, in order, and passes them to the page once it is
 * listening.
 *
 * The first messages Python sends can arrive before this module has loaded
 * and be lost. Messages that change the scene are numbered 1, 2, 3, ... by
 * Python; a hole in the numbers means that happened, so the hub asks Python
 * (`requestSync`) to send again from the first one it has not seen, and
 * ignores what comes meanwhile. Messages that replace one another (`seq`
 * absent) need no such care; only the latest matters.
 */
export class MessageHub {
  /**
   * @param {(have: number) => void} requestSync tells Python how many numbered messages we have applied
   * @param {(pieces: ArrayBufferView[]) => string} makeUrl a URL that serves a file's bytes
   * @param {(url: string) => void} revokeUrl lets go of a URL made by makeUrl
   */
  constructor(
    requestSync,
    makeUrl = (pieces) => URL.createObjectURL(new Blob(pieces)),
    revokeUrl = (url) => URL.revokeObjectURL(url),
  ) {
    this.requestSync = requestSync;
    this.makeUrl = makeUrl;
    this.revokeUrl = revokeUrl;
    this.assets = new Map(); // key of a file Python sent (see assets.js) -> its URL
    this.pieces = new Map(); // key -> the pieces of a file that has not all arrived
    this.next = 1; // the number of the message we expect next
    this.syncing = false;
    this.queue = []; // messages that arrived before the page was listening
    this.sink = null;
    this.setAside = 0; // numbered messages that arrived after a gap, to be sent again
    this.repeated = 0; // numbered messages that arrived again after being applied
  }

  /** Say we are listening, and ask for anything sent before we were. */
  start() {
    this.syncing = true;
    this.requestSync(0);
  }

  /**
   * @param {{func: string, data: any, seq?: number}} msg
   * @param {ArrayBufferView[]} [buffers] binary data sent with the message
   */
  receive(msg, buffers) {
    if (!msg || msg.func === undefined) return;

    if (msg.seq !== undefined) {
      if (msg.seq < this.next) {
        this.repeated += 1; // a message we have already applied, sent again
        return;
      }
      if (msg.seq > this.next) {
        this.setAside += 1;
        // some were lost; ask once, and wait for them to be sent again
        if (!this.syncing) {
          this.syncing = true;
          this.requestSync(this.next - 1);
        }
        return;
      }
      this.next += 1;
      this.syncing = false;
    } else {
      this.queue = this.queue.filter((m) => m.seq !== undefined || m.func !== msg.func);
    }

    if (msg.func === "asset") {
      this.addPiece(msg.data, buffers);
      return;
    }
    if (this.sink) this.sink(msg);
    else this.queue.push(msg);
  }

  // Mesh files arrive in pieces, in order (the messages are numbered); the page
  // is told nothing, it finds the file by its key once a loader asks for it
  addPiece({ path, count }, buffers) {
    const pieces = this.pieces.get(path) ?? [];
    pieces.push(buffers[0]);
    if (pieces.length < count) {
      this.pieces.set(path, pieces);
      return;
    }
    this.pieces.delete(path);
    this.assets.set(path, this.makeUrl(pieces));
  }

  /** Let go of the files held. */
  dispose() {
    this.assets.forEach((url) => this.revokeUrl(url));
    this.assets.clear();
  }

  /** @param {(msg: object) => void} sink called with each message, from now on */
  attach(sink) {
    this.sink = sink;
    const queued = this.queue;
    this.queue = [];
    queued.forEach(sink);
  }
}

// One hub per widget, shared by initialize() and render(): anywidget hands each
// of them its own wrapper of the model, so the widget's `viewer_id` (made by
// Python, and the same in both) is what says which hub is meant.
const hubs = new Map();

export default {
  initialize({ model }) {
    const id = model.get("viewer_id");
    const hub = new MessageHub((have) => model.send({ reply: { event: "sync", have } }));
    hubs.set(id, hub);
    model.on("msg:custom", (msg, buffers) => hub.receive(msg, buffers));
    hub.start();
    return () => {
      hubs.delete(id);
      hub.dispose();
    };
  },

  render({ model, el }) {
    const viewerId = model.get("viewer_id");
    const hub = hubs.get(viewerId);
    const win = el.ownerDocument.defaultView;
    const urls = [];
    const makeUrl = (source) => {
      const url = URL.createObjectURL(new Blob([source], { type: "text/javascript" }));
      urls.push(url);
      return url;
    };

    let page;
    try {
      page = buildPage(model.get("files"), makeUrl, viewerId);
    } catch (error) {
      const message = `Swift viewer failed to start: ${error.message}`;
      el.textContent = message;
      model.send({ reply: { event: "error", message } });
      return;
    }
    if (page.unresolved.length > 0) console.warn("Swift: imports not found:", page.unresolved);

    // what the page gets as its CommTransport's model, and what Python's
    // launch() looks at (through eval_js on Colab) to see that the page is up
    const viewer = {
      hub, // for looking at in the browser's console
      assets: hub.assets, // the page's mesh files
      ready: false,
      channel: {
        on: (_event, listener) => {
          hub.attach(listener);
          viewer.ready = true;
        },
        send: (msg) => model.send(msg),
      },
    };
    (win.__swiftViewers ??= {})[viewerId] = viewer;

    const frame = el.ownerDocument.createElement("iframe");
    frame.style.cssText = `width: ${model.get("width")}px; max-width: 100%; height: ${model.get("height")}px; border: 0;`;
    frame.srcdoc = page.html;
    el.replaceChildren(frame);

    return () => {
      delete win.__swiftViewers[viewerId];
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  },
};
