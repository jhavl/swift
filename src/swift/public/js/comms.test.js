import assert from "node:assert/strict";
import { test } from "node:test";

import { CommTransport, portFromLocation } from "./comms.js";

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

function fakeModel() {
  const handlers = [];
  return {
    sent: [],
    on(name, cb) {
      assert.equal(name, "msg:custom");
      handlers.push(cb);
    },
    send(content) {
      this.sent.push(content);
    },
    deliver(msg) {
      handlers.forEach((cb) => cb(msg));
    },
  };
}

test("CommTransport dispatches {func, data} messages and ignores others", () => {
  const model = fakeModel();
  const transport = new CommTransport(model);
  const got = [];
  transport.onMessage((func, data) => got.push([func, data]));

  model.deliver({ func: "axes", data: true });
  model.deliver({ unrelated: 1 });
  model.deliver(null);

  assert.deepEqual(got, [["axes", true]]);
});

test("CommTransport sends replies wrapped as {reply}, and expects none from Python", () => {
  const model = fakeModel();
  const transport = new CommTransport(model);

  transport.send({ event: "connected" });

  assert.deepEqual(model.sent, [{ reply: { event: "connected" } }]);
  assert.equal(transport.expectsReplies, false);
});

test("CommTransport calls onOpen without a connection step", async () => {
  const transport = new CommTransport(fakeModel());
  await new Promise((resolve) => transport.onOpen(resolve));
});
