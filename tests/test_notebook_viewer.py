"""
Tests for showing the viewer in a notebook where Python cannot run a web
server (swift/_notebook.py): which files are sent, the widget that carries
them, and launch() choosing this path. A fake widget stands in for the one
that would be displayed; whether the page then really starts in a browser is
covered by running a notebook (see claude-notes/notebook-transport-plan.md),
not here.
"""

import sys
import types
from pathlib import Path

import pytest

import swift._notebook as nb
from swift import Swift
from swift._comm import CommBridge

PUBLIC = Path(nb.__file__).parent / "public"


class FakeViewer:
    """Records what the real widget would be given and sent."""

    def __init__(self, files, width, height):
        self.files = files
        self.width = width
        self.height = height
        self.sent: list[dict] = []
        self.handlers = []

    def send(self, content):
        self.sent.append(content)

    def on_msg(self, handler):
        self.handlers.append(handler)

    def reply(self, content):
        for handler in self.handlers:
            handler(self, content, [])


@pytest.fixture
def fake_display(monkeypatch):
    """Replace the widget class and IPython's display; return what display was given."""
    shown = []
    monkeypatch.setattr(nb, "_viewer_class", lambda: FakeViewer)

    def display(obj, display_id=None):
        shown.append(obj)
        return "handle"

    import IPython.display

    monkeypatch.setattr(IPython.display, "display", display)
    return shown


def test_viewer_files_are_the_page_the_desktop_serves():
    files = nb.viewer_files()

    assert files["index.html"] == (PUBLIC / "index.html").read_bytes()
    assert files["style/index.css"] == (PUBLIC / "style" / "index.css").read_bytes()
    for path in ("js/main.js", "js/comms.js", "js/vendor/build/three.module.js"):
        assert files[path] == (PUBLIC / path).read_bytes()
    assert all(isinstance(data, bytes) for data in files.values())


def test_viewer_files_leave_out_tests_and_build_tools():
    files = nb.viewer_files()

    assert not [p for p in files if p.endswith(".test.js")]
    assert not [p for p in files if "node_modules" in p or p.endswith(".json")]


def test_viewer_files_include_every_script_the_page_loads():
    on_disk = {
        str(p.relative_to(PUBLIC))
        for p in (PUBLIC / "js").rglob("*.js")
        if not p.name.endswith(".test.js")
    }
    assert on_disk <= set(nb.viewer_files())


def test_show_viewer_connects_swift_and_returns_the_display_handle(fake_display):
    env = Swift()

    handle = nb.show_viewer(env, width=500, height=300)

    assert handle == "handle"
    (viewer,) = fake_display
    assert (viewer.width, viewer.height) == (500, 300)
    assert "index.html" in viewer.files
    assert env._comm is not None
    # launching's first messages have gone to the widget
    assert viewer.sent and viewer.sent[0]["func"] == "element"


def test_replies_from_the_widget_reach_the_bridge(fake_display):
    env = Swift()
    nb.show_viewer(env)
    (viewer,) = fake_display
    assert not env.ready

    viewer.reply({"reply": {"event": "connected"}})

    assert env.ready


def test_a_sync_request_from_the_widget_is_answered(fake_display):
    env = Swift()
    nb.show_viewer(env)
    (viewer,) = fake_display
    sent_before = len(viewer.sent)

    viewer.reply({"reply": {"event": "sync", "have": 0}})

    # everything that changes the scene is sent again (the first, an "element", among it)
    assert len(viewer.sent) > sent_before
    assert viewer.sent[sent_before]["seq"] == 1


def test_show_viewer_says_how_to_fix_a_missing_anywidget(monkeypatch):
    def missing():
        raise ImportError("No module named 'anywidget'")

    monkeypatch.setattr(nb, "_viewer_class", missing)

    with pytest.raises(ImportError, match="pip install anywidget"):
        nb.show_viewer(Swift())


def test_launch_uses_the_viewer_widget_where_no_server_can_run(
    monkeypatch, fake_display
):
    monkeypatch.setattr(sys.modules["swift.Swift"], "in_comm_environment", lambda: True)
    env = Swift()

    env.launch()

    assert env._comm is not None
    assert env._notebook_display_handle == "handle"
    assert len(fake_display) == 1


def test_the_widget_carries_the_files_as_binary():
    pytest.importorskip("anywidget")
    from ipywidgets.widgets.widget import _remove_buffers

    viewer = nb._viewer_class()(files={"index.html": b"<html>"}, width=900, height=250)
    state, buffer_paths, buffers = _remove_buffers(viewer.get_state())

    assert ["files", "index.html"] in buffer_paths
    assert bytes(buffers[buffer_paths.index(["files", "index.html"])]) == b"<html>"
    assert (state["width"], state["height"]) == (900, 250)
    assert "export default" in state["_esm"]


def test_each_widget_has_its_own_id_for_the_two_parts_of_the_javascript():
    pytest.importorskip("anywidget")

    cls = nb._viewer_class()
    first, second = cls(), cls()

    assert first.viewer_id and second.viewer_id
    assert first.viewer_id != second.viewer_id
    assert first.get_state()["viewer_id"] == first.viewer_id


def fake_colab(monkeypatch, answers):
    """A google.colab.output whose eval_js gives these answers in turn."""
    calls = []

    def eval_js(code):
        calls.append(code)
        return answers[min(len(calls), len(answers)) - 1]

    output = types.SimpleNamespace(
        eval_js=eval_js, enable_custom_widget_manager=lambda: None
    )
    colab = types.ModuleType("google.colab")
    colab.output = output
    google = types.ModuleType("google")
    google.colab = colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.setattr(nb.time, "sleep", lambda _s: None)
    return calls


def test_colab_waits_until_the_page_is_listening(monkeypatch):
    calls = fake_colab(monkeypatch, [False, False, True])

    nb._wait_for_colab_viewer()

    assert len(calls) == 3
    assert "__swiftViewers" in calls[0]


def test_colab_raises_when_the_page_never_starts(monkeypatch):
    fake_colab(monkeypatch, [False])
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(clock))

    with pytest.raises(RuntimeError, match="did not start within 10 s"):
        nb._wait_for_colab_viewer(timeout=10)


def test_on_colab_messages_are_not_sent_until_the_page_is_up(monkeypatch, fake_display):
    fake_colab(monkeypatch, [False, True])
    env = Swift()

    nb.show_viewer(env)

    # attached (so the first messages exist) only after the wait ended
    (viewer,) = fake_display
    assert viewer.sent
    assert isinstance(env._comm, CommBridge)


def test_on_colab_a_page_that_never_starts_stops_launch(monkeypatch, fake_display):
    fake_colab(monkeypatch, [False])
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(nb.time, "monotonic", lambda: next(clock))
    env = Swift()

    with pytest.raises(RuntimeError, match="did not start"):
        nb.show_viewer(env)

    assert env._comm is None


def test_launch_passes_the_size_to_the_viewer(monkeypatch, fake_display):
    monkeypatch.setattr(sys.modules["swift.Swift"], "in_comm_environment", lambda: True)

    Swift().launch(width=900, height=700)

    assert (fake_display[0].width, fake_display[0].height) == (900, 700)
