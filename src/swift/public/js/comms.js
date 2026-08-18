/**
 * Live update transport. WebSocketTransport is the only implementation
 * today (desktop/local use), but callers only depend on the small
 * {onMessage, send, onClose} interface below -- a postMessage/
 * BroadcastChannel transport (for running under Pyodide/JupyterLite,
 * where no real socket can be opened) can be added later as a second
 * implementation of the same interface, without changing main.js.
 *
 * Wire protocol: each message is a JSON-encoded [func, data] pair sent
 * from Python. The browser always sends a response back after handling
 * one (an id, 0, or a JSON blob depending on func) -- see main.js's
 * dispatch table.
 */

// Patched in place to match pyproject.toml's `version` before every
// release build -- see scripts/sync_js_version.py, run as a step in
// .github/workflows/cibuildwheel.yml, so this can never drift out of
// sync via a forgotten manual bump. The value checked in here is only
// what a local editable install/dev checkout sees.
//
// Baked directly into this source file (not injected at serve time) so
// that a *stale, browser-cached* copy of this exact file still reports
// whatever version was true when it was cached -- that's the whole
// point: SwiftRoute.py's start_servers() compares this against the
// currently-installed package version at connection time, so a browser
// tab running old cached JS against a freshly-upgraded install gets a
// clear warning instead of silently misbehaving.
export const SWIFT_JS_VERSION = "2.0.0";

export class WebSocketTransport {
  /** @param {string} url */
  constructor(url) {
    this.ws = new WebSocket(url);
  }

  onOpen(cb) {
    this.ws.onopen = cb;
  }

  onMessage(cb) {
    this.ws.onmessage = (event) => {
      const [func, data] = JSON.parse(event.data);
      cb(func, data);
    };
  }

  onClose(cb) {
    this.ws.onclose = cb;
  }

  send(data) {
    this.ws.send(typeof data === "string" ? data : JSON.stringify(data));
  }
}

/**
 * Reads the port Swift's Python side encodes in the page URL, e.g.
 * `http://localhost:52000/?53000` (SwiftRoute.py's start_servers) -- the
 * socket port is the query string, not a path segment. (The original
 * public/js/index.js read window.location.pathname here, which is always
 * "/" for this URL shape and so always parsed to NaN -- never caught
 * because that app was never actually the one being served.)
 */
export function portFromLocation() {
  return parseInt(window.location.search.slice(1), 10);
}
