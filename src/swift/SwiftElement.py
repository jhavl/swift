
import warnings
from abc import ABC, abstractmethod
from functools import wraps


class SwiftElement(ABC):
    """
    A basic super class for HTML elements which can be added to Swift

    """

    def __init__(self):

        self._id = None
        self._added_to_swift = False
        self._changed = False
        # Optional debug/display name, also the key under which this
        # element's value is pushed into Swift.values -- see
        # Swift.add_ui()/_notify_value_changed() below.
        self.name = None
        # Set by Swift.add_ui() for named elements with a .value; called
        # by that subclass's value.setter on every change so Swift.values
        # stays current without Swift having to scan every element.
        self._on_change = None
        # Set True only for the pause/realtime-speed controls Swift adds
        # itself (see Swift._add_controls()) -- lets the frontend route
        # them into its own control panel instead of the user sidebar.
        self.builtin = False

        super().__init__()

    def _notify_value_changed(self):
        if self._on_change is not None:
            self._on_change(self.value)

    def _update(func):   # pragma nocover
        @wraps(func)
        def wrapper_update(*args, **kwargs):

            if args[0]._added_to_swift:
                args[0]._changed = True

            return func(*args, **kwargs)
        return wrapper_update

    @abstractmethod
    def to_dict(self):
        '''
        Outputs the element in dictionary form

        '''

        pass

    @abstractmethod
    def update(self):
        '''
        Update state of element to reflect what's going on in the front-end

        '''

        pass


class Slider(SwiftElement):
    """
    Create a range-slider html element

    :param cb: A callback function which is executed when the value of the
        slider changes. The callback should accept one argument which
        represents the new value of the slider. Optional -- if not given,
        the slider has no per-element callback, which is the common case
        for a named slider read via ``env.values`` in a shape/assembly
        callback instead.
    :type cb: function
    :param min: the minimum value of the slider, optional
    :type min: float
    :param max: the maximum value of the slider, optional
    :type max: float
    :param step: the step size of the slider, optional
    :type step: float
    :param label: caption shown next to the slider, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    :param unit: add a unit to the slider value, optional
    :type unit: str
    :param precision: number of *decimal places* shown for the current
        value and the min/max range labels next to the slider -- e.g.
        ``precision=3`` shows ``2.478``, not ``2.48`` (that would be 3
        *significant figures* instead, a different, narrower value this
        parameter does not control). Optional, defaults to 3. Purely a
        display rounding -- the underlying value (what a callback or
        ``env.values`` actually receives) always keeps full float
        precision, e.g. whatever a step()-side computation produced.
    :type precision: int

    """

    def __init__(self, cb=None, min=0, max=100, step=1, value=0, label='', unit='', precision=3, desc=None):
        super(Slider, self).__init__()

        if desc is not None:
            warnings.warn(
                "Slider(desc=...) is deprecated, use Slider(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'slider'
        self.cb = cb if cb is not None else lambda x: None
        self.min = min
        self.max = max
        self.step = step
        self.value = value
        self.label = label
        self.unit = unit
        self.precision = precision

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def min(self):
        return self._min

    @min.setter
    @SwiftElement._update
    def min(self, value):
        self._min = float(value)

    @property
    def max(self):
        return self._max

    @max.setter
    @SwiftElement._update
    def max(self, value):
        self._max = float(value)

    @property
    def step(self):
        return self._step

    @step.setter
    @SwiftElement._update
    def step(self, value):
        self._step = float(value)

    @property
    def value(self):
        return self._value

    @value.setter
    @SwiftElement._update
    def value(self, value):
        self._value = float(value)
        self._notify_value_changed()

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Slider.desc is deprecated, use Slider.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Slider.desc is deprecated, use Slider.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    @property
    def unit(self):
        return self._unit

    @unit.setter
    @SwiftElement._update
    def unit(self, value):
        self._unit = value

    @property
    def precision(self):
        return self._precision

    @precision.setter
    @SwiftElement._update
    def precision(self, value):
        self._precision = int(value)

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'min': self.min,
            'max': self.max,
            'step': self.step,
            'value': self.value,
            'label': self.label,
            'unit': self.unit,
            'precision': self.precision,
        }

    def update(self, e):
        self._value = e
        self._notify_value_changed()


class Label(SwiftElement):
    """
    Create a Label html element

    :param label: the text of the label, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    """

    def __init__(self, label='', desc=None):
        super(Label, self).__init__()

        if desc is not None:
            warnings.warn(
                "Label(desc=...) is deprecated, use Label(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'label'
        self.label = label

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Label.desc is deprecated, use Label.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Label.desc is deprecated, use Label.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'label': self.label
        }

    def update(self, _):
        pass


class Button(SwiftElement):
    """
    Create a Button html element

    :param cb: A callback function which is executed when the button is
        clicked. The callback should accept one argument which
        can be disregarded
    :type cb: function
    :param label: text written on the button, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    """

    def __init__(self, cb, label='', desc=None):
        super(Button, self).__init__()

        if desc is not None:
            warnings.warn(
                "Button(desc=...) is deprecated, use Button(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'button'
        self.cb = cb
        self.label = label

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Button.desc is deprecated, use Button.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Button.desc is deprecated, use Button.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'label': self.label
        }

    def update(self, _):
        pass


class Select(SwiftElement):
    """
    Create a Select element, used to create a drop-down list.

    :param cb: A callback function which is executed when the value select
        box changes. The callback should accept one argument which
        represents the index of the new value
    :type cb: function
    :param label: caption shown next to the select box, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    :param options: represent the options inside the select box, optional
    :type options: List of str
    :param value: the index of the initial selection of the select
        box, optional
    :type value: int
    """

    def __init__(self, cb, label='', options=[], value=0, desc=None):
        super(Select, self).__init__()

        if desc is not None:
            warnings.warn(
                "Select(desc=...) is deprecated, use Select(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'select'
        self.cb = cb
        self.label = label
        self.options = options
        self.value = value

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Select.desc is deprecated, use Select.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Select.desc is deprecated, use Select.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    @property
    def options(self):
        return self._options

    @options.setter
    @SwiftElement._update
    def options(self, value):
        self._options = value

    @property
    def value(self):
        return self._value

    @value.setter
    @SwiftElement._update
    def value(self, nvalue):
        self._value = nvalue
        self._notify_value_changed()

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'label': self.label,
            'options': self.options,
            'value': self.value
        }

    def update(self, e):
        self._value = e
        self._notify_value_changed()


class Checkbox(SwiftElement):
    """
    Create a checkbox element, used to create multi-selection list.

    :param cb: A callback function which is executed when a box is checked.
        The callback should accept one argument which represents a List of
        bool representing the checked state of each box
    :type cb: function
    :param label: caption shown next to the checkboxes, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    :param options: represents the checkboxes, optional
    :type options: List of str
    :param checked: a List represented boxes initially checked
    :type checked: List of bool
    """

    def __init__(self, cb, label='', options=[], checked=[], desc=None):
        super(Checkbox, self).__init__()

        if desc is not None:
            warnings.warn(
                "Checkbox(desc=...) is deprecated, use Checkbox(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'checkbox'
        self.cb = cb
        self.label = label
        self.options = options
        self.checked = checked

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Checkbox.desc is deprecated, use Checkbox.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Checkbox.desc is deprecated, use Checkbox.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    @property
    def options(self):
        return self._options

    @options.setter
    @SwiftElement._update
    def options(self, value):
        self._options = value

    @property
    def checked(self):
        return self._checked

    @checked.setter
    @SwiftElement._update
    def checked(self, value):
        print(value)
        if isinstance(value, int):
            new = [False] * len(self.options)
            new[value] = True
            self._checked = new
        else:
            self._checked = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'label': self.label,
            'options': self.options,
            'checked': self.checked
        }

    def update(self, e):
        self._checked = e


class Radio(SwiftElement):
    """
    Create a radio element, used to create single-selection list.

    :param cb: A callback function which is executed when a radio is checked.
        The callback should accept one argument which represents a index
        corresponding to the checked radio button
    :type cb: function
    :param label: caption shown next to the radio buttons, optional
    :type label: str
    :param desc: deprecated alias for ``label``
    :type desc: str
    :param options: represents the radio buttons, optional
    :type options: List of str
    :param checked: the initial radio button checked, optional
    :type checked: int
    """

    def __init__(self, cb, label='', options=[], checked=[], desc=None):
        super(Radio, self).__init__()

        if desc is not None:
            warnings.warn(
                "Radio(desc=...) is deprecated, use Radio(label=...) instead",
                DeprecationWarning,
                stacklevel=2,
            )
            label = desc

        self._element = 'radio'
        self.cb = cb
        self.label = label
        self.options = options
        self.checked = checked

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def label(self):
        return self._label

    @label.setter
    @SwiftElement._update
    def label(self, value):
        self._label = value

    @property
    def desc(self):
        warnings.warn(
            "Radio.desc is deprecated, use Radio.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._label

    @desc.setter
    def desc(self, value):
        warnings.warn(
            "Radio.desc is deprecated, use Radio.label instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.label = value

    @property
    def options(self):
        return self._options

    @options.setter
    @SwiftElement._update
    def options(self, value):
        self._options = value

    @property
    def checked(self):
        return self._checked

    @checked.setter
    @SwiftElement._update
    def checked(self, value):
        if isinstance(value, int):
            new = [False] * len(self.options)
            new[value] = True
            self._checked = new
        else:
            self._checked = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'builtin': self.builtin,
            'label': self.label,
            'options': self.options,
            'checked': self.checked
        }

    def update(self, e):
        self._checked = e
