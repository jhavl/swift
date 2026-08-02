#!/usr/bin/env python
"""
@author Jesse Haviland
"""

import swift as sw
import websockets
import asyncio
from threading import Thread
import webbrowser as wb
import json
import http.server
import socketserver
from pathlib import Path
import os
from queue import Empty
from http import HTTPStatus
import urllib


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


def start_servers(
    outq: Queue,
    inq: Queue,
    stop_servers,
    open_tab: bool = True,
    browser: str | None = None,
):
    # Warn up front, not just after a cold ~60s timeout with no context --
    # see tech-debt.md's "Google Colab support" section. Not a hard block:
    # still attempts the connection regardless, in case Colab's
    # infrastructure has changed, or the user wants to see it fail
    # themselves.
    if COLAB:
        print(
            "\nHeads up: Colab is not currently a supported environment "
            "for Swift. Every connection attempt made during testing has "
            "failed (0/500 in isolated testing of Colab's own "
            "proxyPort() proxy alone, with no Swift code involved at "
            "all) -- see tech-debt.md's 'Google Colab support' section "
            "for the full write-up. Attempting to connect anyway.\n"
        )

    # Start our websocket server with a new port
    socket = Thread(
        target=SwiftSocket,
        args=(
            outq,
            inq,
            stop_servers,
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
    server_port = inq.get()

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
        inq.get(timeout=handshake_timeout)
    except Empty:
        if COLAB:
            print(
                "\nCould not connect to the Swift simulator. As warned "
                "above, Colab is not currently a supported environment "
                "for Swift -- see tech-debt.md's 'Google Colab support' "
                "section for the full evidence. We do not have a single "
                "confirmed successful connection to point to (0/500 in "
                "isolated testing), so retrying is unlikely to help.\n"
            )
        else:
            print("\nCould not connect to the Swift simulator \n")
        raise

    return socket, socket_instance, server, notebook_handle


class SwiftSocket:
    def __init__(self, outq, inq, run):
        self.run = run
        self.outq = outq
        self.inq = inq
        self.USERS = set()
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

    async def _start_server(self, port: int):
        # websockets>=11 requires serve() to be created from a running loop.
        self._server = await websockets.serve(self.serve, "localhost", port)

    def stop(self):
        # call_soon_threadsafe -- run_forever() is executing on a
        # different thread than whichever one calls stop().
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def register(self, websocket):
        self.USERS.add(websocket)

    async def serve(self, websocket, path=None):
        # Initial connection handshake
        await self.register(websocket)
        try:
            recieved = await websocket.recv()
            self.inq.put(recieved)

            # Now onto send, recieve cycle
            while self.run():
                message = await self.producer()
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

    async def expect_message(self, websocket, expected):
        if expected:
            recieved = await websocket.recv()
            self.inq.put(recieved)

    async def producer(self):
        data = self.outq.get()
        return data


class SwiftServer:
    def __init__(self, outq, inq, socket_port, run, verbose=False, custom_root=None):
        server_port = 52000
        self.inq = inq
        self.run = run

        root_dir = Path(sw.__file__).parent / "public"

        class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super(MyHttpRequestHandler, self).__init__(
                    *args, directory=str(root_dir), **kwargs
                )

            def log_message(self, format, *args):
                if verbose:
                    http.server.SimpleHTTPRequestHandler.log_message(
                        self, format, *args
                    )
                else:
                    pass

            def do_GET(self):
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

            def send_file_via_real_path(self):
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
                    self.inq.put(server_port)
                    connected = True

                    httpd.serve_forever()
            except OSError:
                server_port += 1
