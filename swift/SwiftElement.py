
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

        super().__init__()

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
        represents the new value of the slider
    :type cb: function
    :param min: the minimum value of the slider, optional
    :type min: float
    :param max: the maximum value of the slider, optional
    :type max: float
    :param step: the step size of the slider, optional
    :type step: float
    :param desc: add a description of the slider, optional
    :type desc: str
    :param unit: add a unit to the slider value, optional
    :type unit: str

    """

    def __init__(self, cb, min=0, max=100, step=1, value=0, desc='', unit=''):
        super(Slider, self).__init__()

        self._element = 'slider'
        self.cb = cb
        self.min = min
        self.max = max
        self.step = step
        self.value = value
        self.desc = desc
        self.unit = unit

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

    @property
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

    @property
    def unit(self):
        return self._unit

    @unit.setter
    @SwiftElement._update
    def unit(self, value):
        self._unit = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'min': self.min,
            'max': self.max,
            'step': self.step,
            'value': self.value,
            'desc': self.desc,
            'unit': self.unit
        }

    def update(self, e):
        self._value = e


class Label(SwiftElement):
    """
    Create a Label html element

    :param desc: the value of the label, optional
    :type desc: str
    """

    def __init__(self, desc=''):
        super(Label, self).__init__()

        self._element = 'label'
        self.desc = desc

    @property
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'desc': self.desc
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
    :param desc: text written on the button, optional
    :type desc: str
    """

    def __init__(self, cb, desc=''):
        super(Button, self).__init__()

        self._element = 'button'
        self.cb = cb
        self.desc = desc

    @property
    def cb(self):
        return self._cb

    @cb.setter
    @SwiftElement._update
    def cb(self, value):
        self._cb = value

    @property
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'desc': self.desc
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
    :param desc: add a description of the select box, optional
    :type desc: str
    :param options: represent the options inside the select box, optional
    :type options: List of str
    :param value: the index of the initial selection of the select
        box, optional
    :type value: int
    """

    def __init__(self, cb, desc='', options=[], value=0):
        super(Select, self).__init__()

        self._element = 'select'
        self.cb = cb
        self.desc = desc
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
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

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

    def to_dict(self):
        return {
            'element': self._element,
            'id': self._id,
            'desc': self.desc,
            'options': self.options,
            'value': self.value
        }

    def update(self, e):
        self._value = e


class Checkbox(SwiftElement):
    """
    Create a checkbox element, used to create multi-selection list.

    :param cb: A callback function which is executed when a box is checked.
        The callback should accept one argument which represents a List of
        bool representing the checked state of each box
    :type cb: function
    :param desc: add a description of the checkboxes, optional
    :type desc: str
    :param options: represents the checkboxes, optional
    :type options: List of str
    :param checked: a List represented boxes initially checked
    :type checked: List of bool
    """

    def __init__(self, cb, desc='', options=[], checked=[]):
        super(Checkbox, self).__init__()

        self._element = 'checkbox'
        self.cb = cb
        self.desc = desc
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
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

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
            'desc': self.desc,
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
    :param desc: add a description of the radio buttons, optional
    :type desc: str
    :param options: represents the radio buttons, optional
    :type options: List of str
    :param checked: the initial radio button checked, optional
    :type checked: int
    """

    def __init__(self, cb, desc='', options=[], checked=[]):
        super(Radio, self).__init__()

        self._element = 'radio'
        self.cb = cb
        self.desc = desc
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
    def desc(self):
        return self._desc

    @desc.setter
    @SwiftElement._update
    def desc(self, value):
        self._desc = value

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
            'desc': self.desc,
            'options': self.options,
            'checked': self.checked
        }

    def update(self, e):
        self._checked = e
