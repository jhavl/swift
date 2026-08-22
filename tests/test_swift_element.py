"""
Wire-format tests for SwiftElement subclasses (Slider/Button/Label/Select/
Checkbox/Radio). These dicts are the contract the browser's ui.js classes
are built against (see swift/public/js/ui.js) -- a change here without a
matching browser-side change silently breaks the UI panel.
"""

import pytest

from swift.SwiftElement import Button, Checkbox, Label, Radio, Select, Slider


def test_slider_to_dict():
    s = Slider(lambda v: None, min=0, max=10, step=0.5, value=2.5, label="d", unit="u")
    s._id = 3
    assert s.to_dict() == {
        "element": "slider",
        "id": 3,
        "builtin": False,
        "min": 0.0,
        "max": 10.0,
        "step": 0.5,
        "value": 2.5,
        "label": "d",
        "unit": "u",
        "precision": 3,
    }


def test_slider_update_from_browser():
    s = Slider(lambda v: None, value=0)
    s.update(7.5)
    assert s.value == 7.5


def test_slider_precision_defaults_to_3_and_is_settable():
    s = Slider(lambda v: None)
    assert s.precision == 3

    s2 = Slider(lambda v: None, precision=1)
    assert s2.precision == 1
    assert s2.to_dict()["precision"] == 1


def test_slider_cb_is_optional():
    s = Slider(min=0, max=10, value=3, desc="d")
    assert s.to_dict()["value"] == 3.0
    s.cb(3)  # default no-op cb must be callable, not None


def test_button_to_dict():
    b = Button(lambda v: None, label="Click Me")
    b._id = 0
    assert b.to_dict() == {"element": "button", "id": 0, "builtin": False, "label": "Click Me"}


def test_label_to_dict():
    lab = Label(label="hello")
    lab._id = 1
    assert lab.to_dict() == {"element": "label", "id": 1, "builtin": False, "label": "hello"}


def test_select_to_dict_and_update():
    sel = Select(lambda v: None, label="pick one", options=["a", "b", "c"], value=1)
    sel._id = 2
    assert sel.to_dict() == {
        "element": "select",
        "id": 2,
        "builtin": False,
        "label": "pick one",
        "options": ["a", "b", "c"],
        "value": 1,
    }
    sel.update(2)
    assert sel.value == 2


def test_checkbox_to_dict_and_update():
    cb = Checkbox(lambda v: None, label="opts", options=["x", "y"], checked=[True, False])
    cb._id = 4
    assert cb.to_dict() == {
        "element": "checkbox",
        "id": 4,
        "builtin": False,
        "label": "opts",
        "options": ["x", "y"],
        "checked": [True, False],
    }
    cb.update([False, True])
    assert cb.checked == [False, True]


def test_checkbox_checked_from_int_index():
    cb = Checkbox(lambda v: None, options=["x", "y", "z"], checked=1)
    assert cb.checked == [False, True, False]


def test_radio_to_dict_and_update():
    r = Radio(lambda v: None, label="pick", options=["x", "y"], checked=0)
    r._id = 5
    assert r.to_dict() == {
        "element": "radio",
        "id": 5,
        "builtin": False,
        "label": "pick",
        "options": ["x", "y"],
        "checked": [True, False],
    }
    r.update(1)
    assert r.checked == 1


def test_builtin_flag_defaults_false_and_is_settable():
    b = Button(lambda v: None, label="||")
    assert b.builtin is False
    b.builtin = True
    assert b.to_dict()["builtin"] is True


def test_changed_flag_only_set_once_added_to_swift():
    s = Slider(lambda v: None)
    s.value = 1
    assert s._changed is False

    s._added_to_swift = True
    s.value = 2
    assert s._changed is True


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (Slider, {"cb": lambda v: None}),
        (Label, {}),
        (Button, {"cb": lambda v: None}),
        (Select, {"cb": lambda v: None}),
        (Checkbox, {"cb": lambda v: None}),
        (Radio, {"cb": lambda v: None}),
    ],
)
def test_desc_constructor_kwarg_is_deprecated_but_still_works(cls, kwargs):
    with pytest.deprecated_call():
        el = cls(desc="legacy text", **kwargs)
    assert el.label == "legacy text"


@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (Slider, {"cb": lambda v: None}),
        (Label, {}),
        (Button, {"cb": lambda v: None}),
        (Select, {"cb": lambda v: None}),
        (Checkbox, {"cb": lambda v: None}),
        (Radio, {"cb": lambda v: None}),
    ],
)
def test_desc_property_is_deprecated_but_still_works(cls, kwargs):
    el = cls(**kwargs)

    with pytest.deprecated_call():
        el.desc = "legacy text"
    assert el.label == "legacy text"

    with pytest.deprecated_call():
        assert el.desc == "legacy text"
