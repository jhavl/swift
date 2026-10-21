"""Where ``launch`` shows the page: a browser window, or a frame of the notebook cell."""

import importlib
import warnings

import pytest

# the package exports a class with the name of the module, so ask for the module
swift_module = importlib.import_module("swift.Swift")
_display_options = swift_module._display_options


def test_default_is_the_default_browser_window():
    assert _display_options(None, False) == (None, False)


@pytest.mark.parametrize("name", ["chrome", "firefox", "safari", "/path/to/brave %s"])
def test_a_named_browser_is_used_as_given(name):
    assert _display_options(name, False) == (name, False)


def test_notebook_is_a_frame_of_the_cell():
    assert _display_options(None, True) == (None, True)


def test_the_old_browser_notebook_is_deprecated_but_still_works():
    with pytest.warns(FutureWarning, match="notebook=True"):
        assert _display_options("notebook", False) == (None, True)


def test_the_new_way_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _display_options(None, True)
        _display_options("firefox", False)


def test_a_browser_and_a_notebook_frame_cannot_both_be_asked_for():
    with pytest.raises(ValueError, match="notebook=True"):
        _display_options("firefox", True)


def test_start_servers_accepts_the_old_name_too():
    # callers of start_servers directly, which is not part of launch()
    import inspect
    from swift import start_servers

    parameters = inspect.signature(start_servers).parameters
    assert parameters["notebook"].default is False
