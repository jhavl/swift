#!/usr/bin/env python
"""
@author Jesse Haviland
"""

from __future__ import annotations

import swift as sw
import websockets
import asyncio
from threading import Thread, Event
import webbrowser as wb
import json
import http.server
import socketserver
from pathlib import Path
import os
from queue import Empty
from http import HTTPStatus
import urllib
from importlib.metadata import version as _installed_version, PackageNotFoundError
from typing import Any, Callable


from queue import Queue

# Check for notebook support
try:
    from IPython.display import display
    from IPython.display import IFrame
    from IPython.display import HTML

    NB = True
except ImportError:
    NB = False

try:
    # Check if we are in Google Colab
    from google.colab.output import eval_js  # type: ignore

    COLAB = True
except ImportError:
    COLAB = False


def _check_js_version(handshake_msg: str) -> None:
    """
    Warn if the connecting browser tab's JS reports a different version
    than the currently-installed swift-sim package -- almost always a
    stale, browser-cached page from before an upgrade. comms.js's
    SWIFT_JS_VERSION is what makes this detectable at all: it's baked
    into that file's own source (patched to match pyproject.toml at
    release-build time -- see scripts/sync_js_version.py), so a stale
    cached copy keeps reporting whatever version was true when it was
    cached, not the current one.

    :param handshake_msg: the raw first message received over the
        websocket, expected to be JSON containing "js_version" -- a
        pre-version-reporting JS build just sends the bare string
        "Connected" instead, which fails to parse and is treated the
        same as "no version reported at all"
    """
    try:
        installed = _installed_version("swift-sim")
    except PackageNotFoundError:
        # Editable/dev install with no dist-info to compare against --
        # nothing meaningful to warn about.
        return

    js_version = None
    try:
        payload = json.loads(handshake_msg)
        if isinstance(payload, dict):
            js_version = payload.get("js_version")
    except (json.JSONDecodeError, TypeError):
        pass

    if js_version is None:
        print(
            "\nWarning: this browser tab appears to be running a very "
            "old, cached copy of Swift's JavaScript -- older than the "
            f"version that added version reporting -- while swift-sim "
            f"{installed} is installed. If anything looks broken, "
            "hard-refresh the browser tab (or open a new one).\n"
        )
    elif js_version != installed:
        print(
            f"\nWarning: this browser tab is running Swift JS v{js_version}, "
            f"but swift-sim v{installed} is installed -- likely a stale "
            "cached page. Hard-refresh the browser tab (or open a new "
            "one) to pick up the current version.\n"
        )


def start_servers(
    outq: Queue,
    inq: Queue,
    stop_servers: Callable[[], bool],
    disconnected: Event,
    open_tab: bool = True,
    browser: str | None = None,
) -> tuple[Thread, "SwiftSocket", Thread, "SwiftServer", Any]:
    # Warn up front, not just after a cold ~60s timeout with no context --
    # see jhavl/swift#45. Not a hard block: still attempts the connection
    # regardless, in case Colab's infrastructure has changed, or the user
    # wants to see it fail themselves.
    if COLAB:
        print(
            "\nHeads up: Colab is not currently a supported environment "
            "for Swift. Every connection attempt made during testing has "
            "failed (0/500 in isolated testing of Colab's own "
            "proxyPort() proxy alone, with no Swift code involved at "
            "all) -- see https://github.com/jhavl/swift/issues/45 for the "
            "full write-up. Attempting to connect anyway.\n"
        )

    # Start our websocket server with a new port
    socket = Thread(
        target=SwiftSocket,
        args=(
            outq,
            inq,
            stop_servers,
            disconnected,
        ),
        daemon=True,
    )
    socket.start()
    socket_port, socket_instance = inq.get()

    # Start a http server
    server = Thread(
        target=SwiftServer,
        args=(
            outq,
            inq,
            socket_port,
            stop_servers,
        ),
        daemon=True,
    )

    server.start()
    server_port, server_instance = inq.get()

    # Only set for browser="notebook" -- a DisplayHandle (from
    # display(..., display_id=True)) letting close() later blank out
    # specifically the cell that rendered the iframe, regardless of
    # which cell is executing when close() actually runs. A plain
    # IPython.display.clear_output() only affects whatever cell is
    # *currently* executing, which is normally a different, later one.
    notebook_handle = None

    if open_tab:
        if COLAB:
            colab_url = eval_js(f"google.colab.kernel.proxyPort({server_port})")
            url = colab_url + f"?{socket_port}"
        else:
            url = f"http://localhost:{server_port}/?{socket_port}"

        if browser is not None:
            if browser == "notebook":
                if not NB:
                    raise ImportError(
                        "\nCould not open in notebook mode, install ipython with 'pip"
                        " install ipython'\n"
                    )

                notebook_handle = display(
                    IFrame(
                        src=url,
                        width="600",
                        height="400",
                    ),
                    display_id=True,
                )
            else:
                try:
                    wb.get(browser).open_new_tab(url)
                except wb.Error:
                    print("\nCould not open specified browser, using default instead\n")
                    wb.open_new_tab(url)
        elif COLAB:
            # wb.open_new_tab() would try to open a browser on the
            # (headless, remote) Colab VM itself, not the user's actual
            # browser -- nothing would ever navigate to `url`. A
            # window.open() triggered via eval_js isn't a direct user
            # click either, so browsers commonly block it as a popup
            # (confirmed 2026-07-26 -- silent, no visible error, just
            # the same handshake timeout below). A clickable link always
            # bypasses popup blockers since it's a genuine user gesture.
            display(HTML(f'<a href="{url}" target="_blank">Click here to open Swift</a>'))
        else:
            wb.open_new_tab(url)

    # On Colab the tab only opens once the user manually clicks the
    # displayed link (see the COLAB branch above) rather than
    # auto-opening -- give them realistic time to notice and click it.
    handshake_timeout = 60 if COLAB else 10
    try:
        handshake_msg = inq.get(timeout=handshake_timeout)
    except Empty:
        if COLAB:
            print(
                "\nCould not connect to the Swift simulator. As warned "
                "above, Colab is not currently a supported environment "
                "for Swift -- see https://github.com/jhavl/swift/issues/45 "
                "for the full evidence. We do not have a single confirmed "
                "successful connection to point to (0/500 in isolated "
                "testing), so retrying is unlikely to help.\n"
            )
        else:
            print("\nCould not connect to the Swift simulator \n")
        raise

    _check_js_version(handshake_msg)

    return socket, socket_instance, server, server_instance, notebook_handle


class SwiftSocket:
    def __init__(self, outq: Queue, inq: Queue, run: Callable[[], bool], disconnected: Event) -> None:
        self.run = run
        self.outq = outq
        self.inq = inq
        # Set the instant either race below (this loop's send side, or
        # expect_message()'s reply side) notices the browser is gone --
        # lets Swift._send_socket()'s blocked inq.get() bail out well
        # before _REPLY_TIMEOUT, instead of it being the only bound.
        self.disconnected = disconnected
        self.USERS: set[Any] = set()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        started = False

        port = 53000
        while not started and port < 62000:
            try:
                self.loop.run_until_complete(self._start_server(port))
                started = True
            except OSError:
                port += 1

        # self, not just the port, so the calling thread can actually stop
        # this event loop later (see stop()) -- start_servers() previously
        # only ever handed the caller the wrapping Thread, which has no
        # way to reach into a *different* thread's running event loop.
        self.inq.put((port, self))
        self.loop.run_forever()

    async def _start_server(self, port: int) -> None:
        # websockets>=11 requires serve() to be created from a running loop.
        self._server = await websockets.serve(self.serve, "localhost", port)

    def stop(self) -> None:
        # call_soon_threadsafe -- run_forever() is executing on a
        # different thread than whichever one calls stop().
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def register(self, websocket: Any) -> None:
        self.USERS.add(websocket)

    async def serve(self, websocket: Any, path: str | None = None) -> None:
        # Initial connection handshake
        await self.register(websocket)
        try:
            recieved = await websocket.recv()
            self.inq.put(recieved)

            # Now onto send, recieve cycle
            while self.run():
                # producer() can wait a long time (nothing queued during a
                # plain hold() with nothing actively step()-ing) -- racing
                # it against wait_closed() means a disconnect gets noticed
                # even while idle, instead of only the next time this code
                # actively tries to send/recv (which, during an idle
                # hold(), might be never). Without this, USERS never gets
                # cleaned up for an idle connection, which silently
                # defeats hold()'s own disconnect-timeout polling.
                producer_task = asyncio.ensure_future(self.producer())
                closed_task = asyncio.ensure_future(websocket.wait_closed())
                done, _ = await asyncio.wait(
                    [producer_task, closed_task], return_when=asyncio.FIRST_COMPLETED
                )
                if closed_task in done:
                    producer_task.cancel()
                    # Cancelling the *await* doesn't stop the underlying
                    # blocking self.outq.get() call already running on its
                    # own worker thread (queue.Queue has no cancellation
                    # hook) -- left alone, that thread sits blocked
                    # forever, and since asyncio.to_thread()'s workers are
                    # deliberately non-daemon (stdlib default, to avoid
                    # silently abandoning work), it would keep the whole
                    # process alive indefinitely even after this script
                    # has otherwise finished. A throwaway value unblocks
                    # it the same way a real message would; nothing is
                    # left to consume the result, so its value doesn't
                    # matter.
                    self.outq.put((False, ("__disconnect_sentinel__", None)))
                    self.disconnected.set()
                    raise websockets.exceptions.ConnectionClosed(None, None)
                closed_task.cancel()
                message = producer_task.result()
                expected = message[0]
                msg = message[1]
                await websocket.send(json.dumps(msg))
                await self.expect_message(websocket, expected)
        except websockets.exceptions.ConnectionClosed:
            # Browser tab closed (or connection otherwise dropped) mid-run
            # -- not an error, just the end of this session. websockets
            # would otherwise log this as a failed connection handler,
            # full traceback and all.
            pass
        finally:
            self.USERS.discard(websocket)
        return

    async def expect_message(self, websocket: Any, expected: bool) -> None:
        if not expected:
            return

        # Race against wait_closed() the same way serve()'s send side
        # does above -- otherwise a disconnect while waiting for the
        # browser's reply (the common case during an active step() loop,
        # where the server spends nearly all its time right here) isn't
        # noticed until Swift._send_socket()'s own _REPLY_TIMEOUT
        # fallback gives up, up to _REPLY_TIMEOUT seconds later instead
        # of near-instantly. See jhavl/swift#125.
        recv_task = asyncio.ensure_future(websocket.recv())
        closed_task = asyncio.ensure_future(websocket.wait_closed())
        done, _ = await asyncio.wait(
            [recv_task, closed_task], return_when=asyncio.FIRST_COMPLETED
        )
        if closed_task in done:
            recv_task.cancel()
            self.disconnected.set()
            raise websockets.exceptions.ConnectionClosed(None, None)
        closed_task.cancel()
        recieved = recv_task.result()
        self.inq.put(recieved)

    async def producer(self) -> Any:
        # self.outq.get() is a genuine blocking call (a plain thread-safe
        # queue.Queue, shared with the synchronous Python-thread side --
        # can't just swap in asyncio.Queue without breaking that side's
        # ordinary .put()/.get()). Awaiting it directly here would block
        # this whole event-loop thread for however long nothing's queued
        # -- which is most of the time during a plain hold() with nothing
        # actively step()-ing -- starving the loop of any chance to notice
        # the underlying connection closed. asyncio.to_thread() runs the
        # blocking .get() on a worker thread and genuinely suspends this
        # coroutine while waiting, so the event loop stays free to detect
        # a closed connection (and cancel this await) in the meantime.
        return await asyncio.to_thread(self.outq.get)


class SwiftServer:
    def __init__(
        self,
        outq: Queue,
        inq: Queue,
        socket_port: int,
        run: Callable[[], bool],
        verbose: bool = False,
        custom_root: str | None = None,
    ) -> None:
        server_port = 52000
        self.inq = inq
        self.run = run

        root_dir = Path(sw.__file__).parent / "public"

        class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super(MyHttpRequestHandler, self).__init__(
                    *args, directory=str(root_dir), **kwargs
                )

            def log_message(self, format: str, *args: Any) -> None:
                if verbose:
                    http.server.SimpleHTTPRequestHandler.log_message(
                        self, format, *args
                    )
                else:
                    pass

            def end_headers(self) -> None:
                # This server's process (and the port it's bound to) never
                # outlives one Python session, so there's no real caching
                # benefit -- only the risk of a browser silently serving a
                # stale cached JS/mesh file across a dev-session file edit
                # (hit repeatedly in practice: scene.js and ui.js each
                # served stale after an on-disk fix, only noticed because
                # the fix appeared to have no effect).
                self.send_header("Cache-Control", "no-store")
                http.server.SimpleHTTPRequestHandler.end_headers(self)

            def do_GET(self) -> None:
                if self.path == "/":
                    self.send_response(301)

                    self.send_header(
                        "Location",
                        "http://localhost:"
                        + str(server_port)
                        + "/?"
                        + str(socket_port),
                    )

                    self.end_headers()
                    return
                elif self.path == "/?" + str(socket_port):
                    self.path = "index.html"
                elif self.path.startswith("/retrieve/"):
                    # print(f"Retrieving file: {self.path[9:]}")
                    self.path = urllib.parse.unquote(self.path[9:])
                    self.send_file_via_real_path()
                    return

                self.path = Path(self.path).as_posix()

                try:
                    http.server.SimpleHTTPRequestHandler.do_GET(self)
                except BrokenPipeError:
                    # After killing this error will pop up but it's of no use
                    # to the user
                    pass

            def send_file_via_real_path(self) -> None:
                try:
                    f = open(self.path, "rb")
                except OSError:
                    self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                    return None
                ctype = self.guess_type(self.path)
                try:
                    fs = os.fstat(f.fileno())
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-type", ctype)
                    self.send_header("Content-Length", str(fs[6]))
                    self.send_header(
                        "Last-Modified", self.date_time_string(fs.st_mtime)
                    )
                    self.end_headers()
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()

        Handler = MyHttpRequestHandler

        connected = False

        while not connected and server_port < 62000:
            try:
                # ThreadingTCPServer, not plain TCPServer: a single-
                # threaded server can only serve one connection at a
                # time, and a proxying layer in front of it (e.g. Colab's
                # google.colab.kernel.proxyPort()) may hold open or make
                # concurrent requests while establishing its tunnel --
                # with a single-threaded server that can stall the real
                # navigation request behind an unrelated one, with no
                # visible error on either side.
                with socketserver.ThreadingTCPServer(("", server_port), Handler) as httpd:
                    httpd.daemon_threads = True
                    self.httpd = httpd
                    self.inq.put((server_port, self))
                    connected = True

                    httpd.serve_forever()
            except OSError:
                server_port += 1

    def stop(self) -> None:
        # serve_forever() never returns on its own (nothing ever called
        # shutdown() before this) -- Thread.run() (which called
        # SwiftServer(...), which is blocked inside serve_forever()) never
        # reaches its own internal cleanup of self._target/_args/_kwargs
        # as a result, so the wrapping Thread object keeps alive whatever
        # was passed as this class's `run` callback for the whole process
        # lifetime -- in practice, a bound method of the Swift instance
        # itself, keeping the entire env (and every shape ever added)
        # alive long after close() returns. shutdown() must be called
        # from a different thread than the one running serve_forever()
        # (Python's own requirement), which is always true here -- this
        # is called from the thread that called close().
        self.httpd.shutdown()
