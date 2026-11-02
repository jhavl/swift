"""
Swift's viewer in a notebook where Python cannot run a web server for it to
load from (Colab, JupyterLite/Pyodide).

Instead of a page served from a port, the viewer is a widget
(`anywidget <https://anywidget.dev>`_): Python sends it the files of the same
page the desktop serves, read from the installed package, and the widget builds
the page from them in a frame of the cell's output (``public/js/notebook.js``).
Messages then travel over the widget's comm channel, through
:class:`swift._comm.CommBridge`.
"""

from __future__ import annotations

import functools
import sys
import time
import uuid
from importlib import resources
from typing import TYPE_CHECKING, Any

from swift._comm import CommBridge

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

    from swift.Swift import Swift


def viewer_files() -> dict[str, bytes]:
    """
    The files of the viewer page, as the desktop serves them.

    :returns: path relative to ``public/`` -> contents; the page, its stylesheet
        and every script (including the vendored libraries), but not the tests
    """
    public = resources.files("swift") / "public"
    files: dict[str, bytes] = {}

    def add(directory: Traversable, prefix: str, suffix: str) -> None:
        for entry in directory.iterdir():
            path = prefix + entry.name
            if entry.is_dir():
                add(entry, path + "/", suffix)
            elif entry.name.endswith(suffix) and not entry.name.endswith(".test.js"):
                files[path] = entry.read_bytes()

    files["index.html"] = (public / "index.html").read_bytes()
    add(public / "style", "style/", ".css")
    add(public / "js", "js/", ".js")
    return files


@functools.cache
def _viewer_class() -> type:
    """The widget class; made on first use so that anywidget is needed only here."""
    import anywidget
    import traitlets

    class SwiftViewer(anywidget.AnyWidget):
        _esm = (resources.files("swift") / "public" / "js" / "notebook.js").read_text(
            encoding="utf-8"
        )
        # binary values travel as buffers, not as text
        files = traitlets.Dict().tag(sync=True)
        width = traitlets.Int(600).tag(sync=True)
        height = traitlets.Int(400).tag(sync=True)
        # says which widget is meant, to the two parts of the JavaScript that
        # each see only a wrapper of it (see notebook.js)
        viewer_id = traitlets.Unicode().tag(sync=True)

        @traitlets.default("viewer_id")
        def _viewer_id(self) -> str:
            return uuid.uuid4().hex

    return SwiftViewer


def _wait_for_colab_viewer(timeout: float = 10.0) -> None:
    """
    Wait until the page in the output frame is listening for messages.

    Colab can run JavaScript in the cell's output frame and wait for the
    answer, even in the middle of a cell, which no other notebook can; that is
    what makes it possible to say here whether the viewer is up, rather than
    leaving it to the next cell.

    :param timeout: seconds to wait
    :raises RuntimeError: if the page did not start in time
    """
    from google.colab import output

    ready = "Object.values(window.__swiftViewers || {}).some(v => v.ready)"
    deadline = time.monotonic() + timeout
    while not output.eval_js(ready):
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"The Swift viewer did not start within {timeout:g} s. Colab shows "
                "third-party widgets only after "
                "google.colab.output.enable_custom_widget_manager() has run (Swift "
                "calls it for you); if the cell output shows a widget error, "
                "restart the runtime and run the notebook again."
            )
        time.sleep(0.2)


def show_viewer(swift: Swift, width: int = 600, height: int = 400) -> Any:
    """
    Display the viewer in the current cell's output and connect ``swift`` to it.

    On Colab this waits until the viewer is running, and raises if it is not.
    Elsewhere (JupyterLite) the kernel can hear nothing from the viewer until
    the cell ends, so this returns at once and ``swift.ready`` turns true later;
    a failure of the viewer to start is raised by the next call into Swift.

    :param swift: the simulator to connect
    :param width: width of the viewer in the output, in pixels, or less if the
        output is narrower
    :param height: height of the viewer in the output, in pixels
    :returns: the display handle of the output, for clearing it again
    :raises ImportError: if anywidget is not installed
    """
    try:
        viewer_class = _viewer_class()
    except ImportError as error:
        raise ImportError(
            "Swift shows its viewer in this notebook using the anywidget package, "
            "which is not installed: pip install anywidget"
        ) from error

    from IPython.display import display

    on_colab = "google.colab" in sys.modules
    if on_colab:
        from google.colab import output

        # Colab shows third-party widgets only with this switched on
        output.enable_custom_widget_manager()

    viewer = viewer_class(files=viewer_files(), width=width, height=height)
    bridge = CommBridge(viewer.send)
    viewer.on_msg(lambda _widget, content, _buffers: bridge.receive(content))
    handle = display(viewer, display_id=True)

    if on_colab:
        _wait_for_colab_viewer()
    swift._attach_comm(bridge)
    return handle
