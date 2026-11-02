"""
Python end of Swift's comm transport, for notebooks where Python cannot listen
on a socket (Colab, JupyterLite/Pyodide) -- see ``public/js/comms.js``'s
``CommTransport`` for the browser end.

Messages to the browser are pushed through a ``send`` callable (the notebook
layer wires that to a widget). Nothing can be waited on: the kernel delivers
messages from the browser only between cells, so a reply never arrives while
a cell is running. Everything Swift.py used to wait for is therefore decided
here instead -- the reply to a message is a constant, and what the browser
reports back (that it started, a load error, UI input) is stored as it
arrives, to be picked up by the next call.

The browser's code starts a moment after the widget is displayed, so the first
messages can arrive before anything is listening, and are lost. Messages that
change the scene are therefore numbered, kept, and sent again when the browser
reports (``sync``) that it is listening and what it has seen; see
:class:`CommBridge`.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

from swift._assets import asset_key, mesh_files

# Mesh files are sent in pieces of this size: a message much larger than this can
# be refused by the notebook server (Jupyter's limit is 10 MiB)
_CHUNK = 1 << 20


def in_comm_environment() -> bool:
    """
    True where Python cannot listen on a socket the browser can reach, so
    Swift must use the comm transport: Pyodide (JupyterLite) and Colab.
    """
    import sys

    return sys.platform == "emscripten" or "google.colab" in sys.modules


# Messages that each replace the last one, so need no numbering or keeping: only
# the most recent is of interest to a viewer that has just started.
_LATEST_WINS = ("shape_poses", "sim_time")


class CommBridge:
    """
    Sends Swift's messages to the browser, and holds what the browser sends back.

    Every message is ``{"func": code, "data": data}``. Those that change the
    scene also carry ``"seq"``, counting from 1 without gaps, which lets the
    browser notice a gap (messages lost before it was listening) and ask for
    them again. Python keeps these until the browser first reports that it is
    listening; from then on nothing more can be lost and they are let go.

    :param send: pushes one message to the browser, with binary buffers if it has
        any (``send(msg)`` or ``send(msg, buffers)``); called from the thread
        that is running the user's code
    """

    def __init__(self, send: Callable[..., None]) -> None:
        self._send = send
        self._lock = threading.Lock()
        self._seq = 0
        # Numbered messages not yet known to have reached the browser, and the
        # latest of each kind in _LATEST_WINS; None once the browser has
        # reported that it is listening
        self._kept: list[tuple[dict[str, Any], list[bytes] | None]] | None = []
        self._latest: dict[str, dict[str, Any]] = {}
        self._files_sent: set[str] = set()
        #: True once the browser has reported that its viewer is running
        self.ready = False
        #: the first load error the browser reported, as a message, or None
        self.error: str | None = None
        # UI input since the last "shape_poses" message, {element id: data}
        self._ui: dict[str, Any] = {}

    def send(
        self, code: str, data: Any = None, buffers: list[bytes] | None = None
    ) -> str:
        """
        Push one message to the browser.

        :param code: the message's function name, as in the websocket protocol
        :param data: the message's payload
        :param buffers: binary data that goes with the message
        :returns: what the websocket transport's reply would have been: the
            UI events since the last call (JSON) for ``shape_poses``, else ``"0"``
        :raises RuntimeError: if the browser has reported a load error
        """
        if self.error is not None and code != "close":
            error, self.error = self.error, None
            raise RuntimeError(error)

        msg: dict[str, Any] = {"func": code, "data": data}
        with self._lock:
            if code in _LATEST_WINS:
                self._latest[code] = msg
            else:
                self._seq += 1
                msg["seq"] = self._seq
                if self._kept is not None:
                    self._kept.append((msg, buffers))
            self._deliver(msg, buffers)

        if code == "shape_poses":
            events, self._ui = self._ui, {}
            return json.dumps(events)
        return "0"

    def _deliver(self, msg: dict[str, Any], buffers: list[bytes] | None) -> None:
        if buffers:
            self._send(msg, buffers)
        else:
            self._send(msg)

    def send_files(self, filename: str) -> None:
        """
        Send the browser a mesh file, and the files it refers to, to be loaded
        in place of fetching them. Those already sent are not sent again.

        :param filename: the mesh file, as given to the mesh
        :raises FileNotFoundError: if the mesh file does not exist
        """
        for path in mesh_files(filename):
            key = asset_key(path)
            if key in self._files_sent:
                continue
            self._files_sent.add(key)
            data = path.read_bytes()
            starts = range(0, max(len(data), 1), _CHUNK)  # one piece, even if empty
            for index, start in enumerate(starts):
                piece = data[start:][:_CHUNK]
                info = {"path": key, "index": index, "count": len(starts)}
                self.send("asset", info, [piece])

    def receive(self, content: dict[str, Any]) -> None:
        """
        Handle one message from the browser, as ``{"reply": ...}``.

        :param content: the comm message's content; anything that is not a
            reply is ignored
        """
        reply = content.get("reply")
        if isinstance(reply, str):
            # the websocket-style handshake, a JSON string
            try:
                reply = json.loads(reply)
            except json.JSONDecodeError:
                return
        if not isinstance(reply, dict):
            return

        event = reply.get("event")
        if event == "connected":
            self.ready = True
        elif event == "sync":
            self._resend(int(reply.get("have", 0)))
        elif event == "error":
            if "message" in reply:
                self.error = str(reply["message"])
            else:
                self.error = f"Swift failed to load object {reply.get('id')}: {reply.get('reason')}"
        elif event == "ui":
            self._ui.update(reply.get("changes", {}))

    def _resend(self, have: int) -> None:
        """
        Send the browser what it has not seen: the numbered messages after the
        first ``have``, in order, then the latest of the others.

        :param have: how many numbered messages the browser has applied
        """
        with self._lock:
            if self._kept is None:
                if have < self._seq:
                    self.error = (
                        "the Swift viewer missed messages that can no longer be sent"
                    )
                return
            for msg, buffers in self._kept:
                if msg["seq"] > have:
                    self._deliver(msg, buffers)
            for msg in self._latest.values():
                self._deliver(msg, None)
            # the browser is listening now, so nothing more can be lost
            self._kept = None
