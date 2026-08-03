*********
Internals
*********

This page explains what actually happens underneath ``env.launch()`` --
threads, sockets, queues, and the wire protocol. Nothing here is public
API; it exists so anyone extending Swift or chasing a bug doesn't have to
rediscover the architecture from scratch (which is exactly how this page
came to be written).


Processes, threads, and where they live
========================================

A non-headless session is **one Python process**, **one browser tab**,
and **three threads** inside the Python process:

.. code-block:: text

    Python process (your script)
    │
    ├── Main thread
    │     runs your script: add_shape(), step(), hold(), ...
    │     owns outq / inq (see below)
    │
    ├── SwiftServer thread (daemon)
    │     a socketserver.ThreadingTCPServer serving static files
    │     (swift/public/*) and the "/retrieve/<path>" passthrough
    │     route for local mesh files -- plain HTTP, port 52000+
    │
    └── SwiftSocket thread (daemon)
          owns its own asyncio event loop (asyncio.new_event_loop() +
          run_forever()) running a websockets server -- port 53000+
          this is where the real-time protocol lives

                                    ▲
                                    │ WebSocket (SwiftSocket)
                                    │ HTTP, once, for the initial
                                    │ page load (SwiftServer)
                                    ▼
                              Browser tab
                        (public/js/*.js, three.js)

Two separate servers, two separate ports, on purpose: the HTTP server's
job (serve ``index.html``/JS/vendor files once, then serve occasional
``/retrieve/<path>`` mesh requests) is completely different traffic from
the WebSocket's job (a continuous, low-latency, bidirectional message
stream for every shape update, every step, every UI interaction). Mixing
them onto one server/port would work, but there's no reason to couple
two unrelated concerns.

Both background threads are daemon threads, but that alone does **not**
mean they exit when your script does -- see `Shutdown`_ below. Getting
this wrong (before it was fixed) is exactly what caused the nanobind
leak documented in `jhavl/swift#92
<https://github.com/jhavl/swift/issues/92>`_: a thread that never
terminates keeps everything it can reach alive for the rest of the
process's life, GC or no GC.


The wire protocol
==================

``self.outq`` / ``self.inq`` (both a plain thread-safe ``queue.Queue``)
are the *only* channel between the main thread and ``SwiftSocket``'s
event-loop thread. Everything crosses through them -- there is no other
shared state.

- **``outq``**: Python → browser. ``Swift._send_socket(code, data,
  expected=True)`` puts ``(expected, (code, data))`` onto ``outq``.
  ``SwiftSocket.producer()`` (running on the event-loop thread) takes it
  off, JSON-encodes it, and sends it over the WebSocket.
- **``inq``**: browser → Python. Every reply from the browser (and the
  very first message of the initial handshake) gets put onto ``inq``.
  If ``expected=True``, ``_send_socket()`` blocks on ``inq.get(timeout=
  _REPLY_TIMEOUT)`` (15s) waiting for it; ``expected=False`` is
  fire-and-forget (e.g. per-step pose updates that don't need
  acknowledgement).

A message is always ``[code, data]`` -- a short string identifying what
it is, plus a JSON-serialisable payload. ``main.js``'s ``onMessage``
switch statement is the browser-side source of truth for every ``code``
that exists; there is no other protocol spec. A few worth knowing by
name:

- ``"shape"`` -- add an object (a flat list of per-part dicts, one
  entry per link for a robot, one entry total for a lone shape). Reply:
  the new object's id.
- ``"shape_mounted"`` -- poll whether an object finished loading in the
  browser (see `Loading and the shape_mounted protocol`_ below).
- ``"shape_poses"`` -- the per-step batch pose update every
  :meth:`~swift.Swift.Swift.step` call sends.
- ``"element"`` -- add a UI element (:class:`~swift.SwiftElement.SwiftElement`
  subclass).
- ``"close"`` -- sent once, right before the Python side tears its
  threads down (see `Shutdown`_).


Loading and the ``shape_mounted`` protocol
============================================

Adding a shape/robot is two round trips, not one: the ``"shape"``
message hands the browser a part list and gets back an id immediately
(construction is synchronous), but *loading* each part's actual asset
(a mesh file, or building primitive/``Axes``/``Arrow`` geometry) happens
asynchronously in the browser. :meth:`~swift.Swift.Swift._wait_mounted`
polls ``"shape_mounted"`` in a loop until it's done:

.. code-block:: text

    reply = [code, detail]

    code ==  1   mounted -- stop polling, return
    code ==  0   still loading -- sleep 0.1s, poll again
    code == -1   unsupported shape type -- raise RuntimeError(detail)
    code == -2   asset/mesh load failed -- raise RuntimeError(detail)

``detail`` is the browser's own diagnostic string (e.g. ``"unsupported
shape type 'axes'"``, or the underlying loader error for a bad mesh
path) -- it travels back over the wire specifically so the Python-side
exception can say exactly what went wrong, rather than a generic
"check the browser's JavaScript console" (which used to be the only
option; see ``shapes.js``'s ``load()``/``SwiftObject`` for where ``code``
and ``detail`` actually get decided).


Connection lifecycle
======================

1. ``launch()`` starts both background threads (``start_servers()``),
   opens (or displays a link/iframe for) the browser tab, and blocks on
   the initial handshake (``inq.get(timeout=handshake_timeout)``) --
   this is the "Could not connect to the Swift simulator" timeout if
   nothing ever connects.
2. Once connected, ``launch()`` sends the initial ``axes``/
   ``ground_opacity``/``browser_timeout`` state and adds the built-in
   pause/realtime-speed controls.
3. Your script runs -- ``add_shape()``/``add_robot()``/``step()``/
   ``hold()``/``run()`` etc., all going through ``outq``/``inq``.
4. Something ends the session -- see `Shutdown`_.


Disconnect detection
======================

``SwiftSocket.USERS`` is a ``set`` of currently-connected websocket
objects (really just 0 or 1 in normal use -- one browser tab).
:meth:`~swift.Swift.Swift.hold`/:meth:`~swift.Swift.Swift.run` poll
``len(self.socket.USERS) > 0`` once a second to decide whether the
browser is still there.

Getting ``USERS`` cleaned up *promptly* when the tab actually closes
took real work, and is worth understanding if you're ever debugging
something in this area again. ``SwiftSocket.serve()``'s per-connection
loop is, conceptually:

.. code-block:: python

    while self.run():
        message = await self.producer()   # next thing to send
        await websocket.send(json.dumps(message))
        await self.expect_message(websocket, expected)

The naive version of ``producer()`` is a **blocking**
``self.outq.get()`` -- fine when something is actively being sent every
frame (:meth:`step`), but during a plain :meth:`hold` with nothing
actively stepping, *nothing is ever queued*. A blocking call inside an
``async def``, with nothing to wait on, doesn't just block that one
coroutine -- since asyncio is cooperative and single-threaded per event
loop, it blocks the *entire event loop*, so nothing else on that loop
(including noticing the browser disconnected) gets a chance to run
either. The fix has two parts, both necessary:

1. ``producer()`` runs the blocking ``outq.get()`` via
   ``asyncio.to_thread()`` instead of calling it directly -- this makes
   the *await* itself non-blocking, freeing the event loop while
   nothing is queued.
2. That alone isn't sufficient -- nothing was *watching* the connection
   for closure either way. ``serve()``'s loop now races ``producer()``
   against ``websocket.wait_closed()`` (``asyncio.wait(...,
   return_when=FIRST_COMPLETED)``); whichever resolves first wins. A
   disconnect now gets noticed the moment it happens, not just the next
   time ``serve()`` happens to actively send/recv (which, during an idle
   :meth:`hold`, might be never).

One more subtlety: cancelling the ``producer()`` task when
``wait_closed()`` wins does **not** stop the underlying blocking
``outq.get()`` already running on its ``to_thread()`` worker --
``queue.Queue`` has no cancellation hook. Left alone, that thread sits
blocked forever, and since ``to_thread()``'s workers are deliberately
**non-daemon** (so work is never silently abandoned), it would keep the
whole *process* alive indefinitely, even after your script has
otherwise finished. The fix pushes a throwaway sentinel value into
``outq`` right before cancelling, unblocking the orphaned ``.get()`` the
same way a real message would.

Once ``USERS`` is empty, :meth:`hold`/:meth:`run` see it on their next
1-second poll, wait out ``timeout`` (see the table in
:meth:`~swift.Swift.Swift.launch`'s docstring), print ``"Swift browser
tab closed."``, and call :meth:`~swift.Swift.Swift.close`.


Shutdown
=========

:meth:`~swift.Swift.Swift.close` (called explicitly, or automatically by
:meth:`hold`/:meth:`run` on a disconnect-timeout or ``^C``) does three
things:

1. ``self._send_socket("close", "0", False)`` -- tell the browser it's
   over (fire-and-forget).
2. ``self.socket.stop()`` -- ``self.loop.call_soon_threadsafe(self.loop
   .stop)``, from the calling thread, since ``run_forever()`` is
   executing on a *different* thread than whichever one calls
   :meth:`close`.
3. ``self.server.stop()`` -- ``self.httpd.shutdown()``. Easy to assume
   this doesn't matter ("it's just a static file server, it isn't
   holding anything interesting") -- it was, in fact, exactly what was
   keeping every shape ever added alive for the rest of the process's
   life. ``socketserver.BaseServer.serve_forever()`` never returns on
   its own; nothing ever called ``shutdown()`` before this fix.
   ``threading.Thread.run()`` only clears the arguments it was started
   with (``self._target``/``_args``/``_kwargs``) *after* the target
   function returns -- since ``serve_forever()`` never returned, the
   wrapping ``Thread`` object kept those start arguments alive forever.
   One of them is a bound method of the ``Swift`` instance itself
   (``self._servers_running``, passed as the ``run`` callback to *both*
   ``SwiftSocket`` and ``SwiftServer``) -- so that single, easy-to-miss
   reference kept the whole environment (every shape, every scene-graph
   node) alive indefinitely, regardless of how gracefully everything
   else shut down. See `jhavl/swift#92
   <https://github.com/jhavl/swift/issues/92>`_ for the full
   investigation.

Both ``.stop()`` calls are followed by a bounded ``.join(1)`` in
``_stop_threads()`` -- by design a best-effort wait, not a guarantee;
a still-running thread after ``close()`` returns is itself worth
investigating rather than assuming is fine.


Where to look next
====================

- `GitHub issues labeled tech-debt
  <https://github.com/jhavl/swift/issues?q=label%3Atech-debt>`_ -- the
  incident log behind most of the above: what broke, how it was found,
  exact fixes (closed issues are the ones already fixed). This page is
  the steady-state architecture; those issues are the history of
  getting here.
- ``src/swift/SwiftRoute.py`` -- ``SwiftSocket``/``SwiftServer``,
  ``start_servers()``.
- ``src/swift/public/js/main.js`` -- the browser-side ``onMessage``
  switch statement, the actual protocol source of truth.
- ``src/swift/public/js/shapes.js`` -- per-shape loading/rendering,
  ``SwiftObject``, the ``load()``/error-code logic behind
  ``shape_mounted``.
