#!/usr/bin/env python
"""
@author Jesse Haviland
"""


# import numpy as np
# import spatialmath as sm
# import time
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


def start_servers(outq, inq, open_tab=True, browser=None):

    # Start our websocket server with a new clean port
    socket = Thread(
        target=SwiftSocket, args=(outq, inq, ), daemon=True)
    socket.start()
    socket_port = inq.get()

    # Start a http server
    server = Thread(
        target=SwiftServer, args=(outq, inq, socket_port, ), daemon=True)
    server.start()
    server_port = inq.get()

    if open_tab:

        if browser is not None:
            try:
                wb.get(browser).open_new_tab(
                    'http://localhost:'
                    + str(server_port)
                    + '/'
                    + str(socket_port))
            except wb.Error:
                print(
                    '\nCould not open specified browser, '
                    'using default instead\n')
                wb.open_new_tab(
                    'http://localhost:'
                    + str(server_port)
                    + '/'
                    + str(socket_port))
        else:
            wb.open_new_tab(
                'http://localhost:'
                + str(server_port)
                + '/'
                + str(socket_port))

        try:
            inq.get(timeout=10)
        except Empty:
            print('\nCould not connect to the Swift simulator \n')
            raise


class SwiftSocket:

    def __init__(self, outq, inq):
        self.outq = outq
        self.inq = inq
        self.USERS = set()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        started = False
        port = 51480

        while not started and port < 62000:
            try:
                start_server = websockets.serve(self.serve, "localhost", port)
                loop.run_until_complete(start_server)
                started = True
            except OSError:
                port += 1

        self.inq.put(port)
        loop.run_forever()

    async def register(self, websocket):
        self.USERS.add(websocket)

    async def serve(self, websocket, path):

        # Initial connection handshake
        await(self.register(websocket))
        recieved = await websocket.recv()
        self.inq.put(recieved)

        # Now onto send, recieve cycle
        while True:
            message = await self.producer()
            await websocket.send(json.dumps(message))

            recieved = await websocket.recv()
            self.inq.put(recieved)

    async def producer(self):
        data = self.outq.get()
        return data


class SwiftServer:

    def __init__(self, outq, inq, socket_port, verbose=False):

        server_port = 52000
        self.inq = inq

        root_dir = Path(sw.__file__).parent / 'public'
        # os.chdir(Path.home())
        os.chdir(Path.home().anchor)

        class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                if verbose:
                    http.server.SimpleHTTPRequestHandler.log_message(
                                                        self, format, *args)
                else:
                    pass

            def do_POST(self):
                print(self)

            def do_GET(self):

                # home = str(Path.home())

                if self.path == '/':
                    self.send_response(301)

                    self.send_header(
                        'Location', 'http://localhost:'
                        + str(server_port)
                        + '/'
                        + str(socket_port))

                    self.end_headers()
                    return

                if self.path == '/' + str(socket_port):
                    self.path = str(root_dir / 'index.html')

                elif self.path.endswith('css') or self.path.endswith('js') \
                        or self.path.endswith('map'):
                    self.path = str(root_dir) + str(Path(self.path))

                self.path = str(Path(self.path))

                # if self.path.lower().startswith(home.lower()):
                #     self.path = self.path[len(home):]
                # elif self.path.lower().startswith(home.lower()[2:]):
                #     self.path = self.path[len(home)-2:]

                self.path = Path(self.path).as_posix()

                return http.server.SimpleHTTPRequestHandler.do_GET(self)

        Handler = MyHttpRequestHandler

        connected = False

        while not connected and server_port < 62000:
            try:
                with socketserver.TCPServer(
                            ("", server_port), Handler) as httpd:
                    self.inq.put(server_port)
                    connected = True

                    httpd.serve_forever()
            except OSError:
                server_port += 1
