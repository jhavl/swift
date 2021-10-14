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

# from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
# from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
# import uuid
# import cv2
# import numpy as np

# relay = MediaRelay()


def start_servers(outq, inq, stop_servers, open_tab=True, browser=None, dev=False):
    # Start our websocket server with a new clean port
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
    socket_port = inq.get()

    if not dev:
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

        if open_tab:

            if browser is not None:
                try:
                    wb.get(browser).open_new_tab(
                        "http://localhost:" + str(server_port) + "/?" + str(socket_port)
                    )
                except wb.Error:
                    print(
                        "\nCould not open specified browser, " "using default instead\n"
                    )
                    wb.open_new_tab(
                        "http://localhost:" + str(server_port) + "/?" + str(socket_port)
                    )
            else:
                wb.open_new_tab(
                    "http://localhost:" + str(server_port) + "/?" + str(socket_port)
                )
    else:
        server = None

        wb.get(browser).open_new_tab(
            "http://localhost:" + str(3000) + "/?" + str(socket_port)
        )

    try:
        inq.get(timeout=10)
    except Empty:
        print("\nCould not connect to the Swift simulator \n")
        raise

    return socket, server


class SwiftSocket:
    def __init__(self, outq, inq, run):
        self.pcs = set()
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
                start_server = websockets.serve(self.serve, "localhost", port)
                self.loop.run_until_complete(start_server)
                started = True
            except OSError:
                port += 1

        self.inq.put(port)
        self.loop.run_forever()

    async def register(self, websocket):
        self.USERS.add(websocket)

    async def serve(self, websocket, path):

        # Initial connection handshake
        await (self.register(websocket))
        recieved = await websocket.recv()
        self.inq.put(recieved)

        # Now onto send, recieve cycle
        while self.run():
            message = await self.producer()
            expected = message[0]
            msg = message[1]
            await websocket.send(json.dumps(msg))
            await self.expect_message(websocket, expected)
        return

    async def expect_message(self, websocket, expected):
        if expected:
            recieved = await websocket.recv()
            # if recieved[0:15] == '{"type":"offer"':
            #     await self._connect(recieved, websocket)
            #     await self.expect_message(websocket, expected)
            # else:
            #     self.inq.put(recieved)
            self.inq.put(recieved)

    async def producer(self):
        data = self.outq.get()
        return data

    # async def _connect(self, recieved, websocket):
    #     params = json.loads(recieved)
    #     params = params["offer"]

    #     offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    #     pc = RTCPeerConnection()
    #     pc_id = "PeerConnection(%s)" % uuid.uuid4()
    #     self.pcs.add(pc)

    #     @pc.on("track")
    #     def on_track(track):
    #         print("Track %s received", track.kind)

    #         if track.kind == "video":
    #             pc.addTrack(VideoTransformTrack(relay.subscribe(track)))

    #     # handle offer
    #     await pc.setRemoteDescription(offer)

    #     # send answer
    #     answer = await pc.createAnswer()
    #     await pc.setLocalDescription(answer)
    #     await websocket.send(
    #         json.dumps(
    #             [
    #                 "offer",
    #                 {
    #                     "sdp": pc.localDescription.sdp,
    #                     "type": pc.localDescription.type,
    #                 },
    #             ]
    #         )
    #     )


# class VideoTransformTrack(MediaStreamTrack):
#     """
#     A video stream track that transforms frames from an another track.
#     """

#     kind = "video"

#     def __init__(self, track):
#         super().__init__()  # don't forget this!
#         self.track = track
#         self.count = 0

#     async def recv(self):
#         print("hellooooo")
#         frame = await self.track.recv()
#         im = frame.to_ndarray(format="bgr24")

#         cv2.imshow("camera", im)
#         cv2.waitKey(1)
#         self.count += 1
#         print(self.count)
#         return frame


class SwiftServer:
    def __init__(self, outq, inq, socket_port, run, verbose=False, custom_root=None):

        server_port = 52000
        self.inq = inq
        self.run = run

        root_dir = Path(sw.__file__).parent / "out"

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

            def do_POST(self):
                pass
                # print(self)
                # if self.path == "/offer":
                #     print("hello")

                #     length = int(self.headers.get("content-length"))
                #     params = json.loads(self.rfile.read(length))
                #     self._connect(params)

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
                    # print(f"Retrieving file: {self.path[10:]}")
                    self.path = urllib.parse.unquote(self.path[10:])
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
                with socketserver.TCPServer(("", server_port), Handler) as httpd:
                    self.inq.put(server_port)
                    connected = True

                    httpd.serve_forever()
            except OSError:
                server_port += 1
