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
"""

from __future__ import annotations

import json
from typing import Any, Callable


def in_comm_environment() -> bool:
    """
    True where Python cannot listen on a socket the browser can reach, so
    Swift must use the comm transport: Pyodide (JupyterLite) and Colab.
    """
    import sys

    return sys.platform == "emscripten" or "google.colab" in sys.modules


class CommBridge:
    """
    Sends Swift's messages to the browser, and holds what the browser sends back.

    :param send: pushes one message, ``{"func": code, "data": data}``, to the
        browser; called from the thread that is running the user's code
    """

    def __init__(self, send: Callable[[dict[str, Any]], None]) -> None:
        self._send = send
        #: True once the browser has reported that its viewer is running
        self.ready = False
        #: the first load error the browser reported, as a message, or None
        self.error: str | None = None
        # UI input since the last "shape_poses" message, {element id: data}
        self._ui: dict[str, Any] = {}

    def send(self, code: str, data: Any = None) -> str:
        """
        Push one message to the browser.

        :param code: the message's function name, as in the websocket protocol
        :param data: the message's payload
        :returns: what the websocket transport's reply would have been: the
            UI events since the last call (JSON) for ``shape_poses``, else ``"0"``
        :raises RuntimeError: if the browser has reported a load error
        """
        if self.error is not None and code != "close":
            error, self.error = self.error, None
            raise RuntimeError(error)

        self._send({"func": code, "data": data})

        if code == "shape_poses":
            events, self._ui = self._ui, {}
            return json.dumps(events)
        return "0"

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
        elif event == "error":
            self.error = f"Swift failed to load object {reply.get('id')}: {reply.get('reason')}"
        elif event == "ui":
            self._ui.update(reply.get("changes", {}))
