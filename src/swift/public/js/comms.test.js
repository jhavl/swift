import assert from "node:assert/strict";
import { test } from "node:test";

import { portFromLocation } from "./comms.js";

test("portFromLocation reads the port from the query string", (t) => {
  const originalWindow = globalThis.window;
  globalThis.window = { location: { search: "?53000" } };
  t.after(() => {
    globalThis.window = originalWindow;
  });

  assert.equal(portFromLocation(), 53000);
});

test("portFromLocation does not read from the pathname", (t) => {
  // Regression test: SwiftRoute.py's start_servers() builds the URL as
  // http://localhost:{server_port}/?{socket_port} -- the port is always in
  // the query string, never the path. The original public/js/index.js read
  // window.location.pathname here, which is always "/" for this URL shape
  // and so always parsed to NaN.
  const originalWindow = globalThis.window;
  globalThis.window = { location: { pathname: "/53000", search: "" } };
  t.after(() => {
    globalThis.window = originalWindow;
  });

  assert.ok(Number.isNaN(portFromLocation()));
});
