import re
import types
import logging
from collections import OrderedDict as odict

# User-specified style, either write to this directly,
# or copy it and pass it to QArgumentParser(style=yourStyle)
DefaultStyle = {

    # Should comboboxes cover the full horizontal width?
    "comboboxFillWidth": False,

    # Should the QArgument(help=) be used as a tooltip?
    "useTooltip": True,
}


__version__ = "0.5.10"
_log = logging.getLogger(__name__)
_type = type  # used as argument
_dpi = None

try:
    # Python 2
    _basestring = basestring
except NameError:
    _basestring = str


# Support for both PyQt5 and PySide2
QtCompat = types.ModuleType("QtCompat")

try:
    from PySide2 import (
        QtWidgets,
        QtCore,
        QtGui,
    )

    from shiboken2 import wrapInstance, getCppPointer, isValid
    QtCompat.isValid = isValid
    QtCompat.wrapInstance = wrapInstance
    QtCompat.getCppPointer = getCppPointer
    QtCompat.setSectionResizeMode = QtWidgets.QHeaderView.setSectionResizeMode

    try:
        from PySide2 import QtUiTools
        QtCompat.loadUi = QtUiTools.QUiLoader

    except ImportError:
        _log.debug("QtUiTools not provided.")


except ImportError:
    try:
        from PyQt5 import (
            QtWidgets,
            QtCore,
            QtGui,
        )

        QtCore.Signal = QtCore.pyqtSignal
        QtCore.Slot = QtCore.pyqtSlot
        QtCore.Property = QtCore.pyqtProperty

        from sip import wrapinstance, unwrapinstance, isdeleted
        QtCompat.isValid = lambda w: not isdeleted(w)
        QtCompat.wrapInstance = wrapinstance
        QtCompat.getCppPointer = unwrapinstance
        QtCompat.setSectionResizeMode = (
            QtWidgets.QHeaderView.setSectionResizeMode)

        try:
            from PyQt5 import uic
            QtCompat.loadUi = uic.loadUi
        except ImportError:
            _log.debug("uic not provided.")

    except ImportError:
        _log.error(
            "Could not find either the required PySide2 or PyQt5"
        )


_stylesheet = """\
QWidget {
    font-size: 8pt;
}

*[type="Button"] {
    text-align:left;
}

*[type="Info"] {
    background: transparent;
    border: none;
}

*[type="Image"], *[type="ImageButton"] {
    border: 1px solid #555;
    background: #222;
}

*[type="ImageButton"]:hover {
    background: #2A2A2A;
}

*[type="ImageButton"]:pressed {
    background: #333;
}

QLabel[type="Separator"] {
    min-height: 20px;
    text-decoration: underline;
}

QWidget #resetButton {
    padding-top: 0px;
    padding-bottom: 0px;
    padding-left: 0px;
    padding-right: 0px;
    background: transparent;
}

#description, #icon {
    padding-bottom: 10px;
}

"""


def px(value):
    """Return a scaled value, for HDPI resolutions"""

    global _dpi

    if not _dpi:
        # We can get system DPI from a window handle,
        # but I haven't figured out how to get a window handle
        # without first making a widget. So here we make one
        # as invisibly as we can, as an invisible tooltip.
        # This doesn't create a taskbar icon nor changes focus
        # and in fact *should* happen without any noticeable effect
        # to the user. Welcome to provide a less naughty alternative
        any_widget = QtWidgets.QWidget()
        any_widget.setWindowFlags(QtCore.Qt.ToolTip)
        any_widget.show()
        window = any_widget.windowHandle()
        any_widget.deleteLater()

        # E.g. 1.5 or 2.0
        scale = window.screen().logicalDotsPerInch() / 96.0

        # Store for later
        _dpi = scale

    return value * _dpi


def _scaled_stylesheet():
    """Replace any mention of <num>px with scaled version

    This way, you can still use px without worrying about what
    it will look like at HDPI resolution.

    """

    output = []
    for line in _stylesheet.splitlines():
        line = line.rstrip()
        if line.endswith("px;"):
            key, value = line.rsplit(" ", 1)
            value = px(int(value[:-3]))
            line = "%s %dpx;" % (key, value)
        output += [line]
    return "\n".join(output)


DoNothing = None


class QArgumentParser(QtWidgets.QWidget):
    """User interface arguments

    Arguments:
        arguments (list, optional): Instances of QArgument
        description (str, optional): Long-form text of what this parser is for
        storage (QSettings, optional): Persistence to disk, providing
            value() and setValue() methods
        style (dict, optional): User-specified overrides to style choices
        parent (QWidget, optional): Parent of this widget

    """

    changed = QtCore.Signal(QtCore.QObject)  # A QArgument
    entered = QtCore.Signal(QtCore.QObject)
    exited = QtCore.Signal(QtCore.QObject)

    help_wanted = QtCore.Signal()
    help_entered = QtCore.Signal()
    help_exited = QtCore.Signal()

    def __init__(self,
                 arguments=None,
                 description=None,
                 storage=None,
                 style=None,
                 parent=None):
        super(QArgumentParser, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)

        # Create internal settings
        if storage is True:
            storage = QtCore.QSettings(
                QtCore.QSettings.IniFormat,
                QtCore.QSettings.UserScope,
                __name__, "QArgparse",
            )

        if storage is not None:
            _log.info("Storing settings @ %s" % storage.fileName())

        arguments = arguments or []

        assert hasattr(arguments, "__iter__"), "arguments must be iterable"
        assert isinstance(storage, (type(None), QtCore.QSettings)), (
            "storage must be of type QSettings"
        )

        layout = QtWidgets.QGridLayout(self)
        layout.setRowStretch(9999, 1)  # Push all options up
        layout.setColumnStretch(1, 1)

        Label = _with_entered_exited2(QtWidgets.QLabel)
        icon = Label()
        description = Label(description or "")
        description.setWordWrap(True)
        layout.addWidget(icon, 0, 0, 1, 1, QtCore.Qt.AlignRight)
        layout.addWidget(description, 0, 1, 1, 1, QtCore.Qt.AlignVCenter)

        # Shown when set
        icon.setVisible(False)
        description.setVisible(bool(description.text()))

        # For CSS
        icon.setObjectName("icon")
        icon.entered.connect(self.help_entered.emit)
        icon.exited.connect(self.help_exited.emit)
        icon.setCursor(QtCore.Qt.PointingHandCursor)

        description.setObjectName("description")
        description.entered.connect(self.help_entered.emit)
        description.exited.connect(self.help_exited.emit)
        description.setCursor(QtCore.Qt.PointingHandCursor)

        self._row = 1
        self._storage = storage
        self._arguments = odict()
        self._resets = dict()
        self._description = description
        self._icon = icon
        self._style = style or DefaultStyle

        for arg in arguments or []:
            self._addArgument(arg)

        # Prevent getting squashed on the vertical
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.MinimumExpanding)

        self.setStyleSheet(_scaled_stylesheet())

    def mouseReleaseEvent(self, event):
        widget = self.childAt(event.pos())

        if widget and widget.objectName() in ("icon", "description"):
            self.help_wanted.emit()

        super(QArgumentParser, self).mouseReleaseEvent(event)

    def __iter__(self):
        """Make parser iterable

        Arguments yield in the order they were added.

        Example
            >>> args = [Float("age"), Boolean("alive")]
            >>> parser = QArgumentParser(args)
            >>> for arg in parser:
            ...     print(arg["name"])
            ...
            age
            alive

        """

        for _, arg in self._arguments.items():
            yield arg

    def setDescription(self, text):
        self._description.setText(text or "")
        self._description.setVisible(bool(text))

    def setIcon(self, fname):
        self._icon.setPixmap(QtGui.QPixmap(fname))
        self._icon.setVisible(bool(fname))

    def addArgument(self, name, type=None, default=None, **kwargs):
        # Infer type from default
        if type is None and default is not None:
            type = _type(default)

        # Default to string
        type = type or str

        Argument = {
            None: String,
            int: Integer,
            float: Float,
            bool: Boolean,
            str: String,
            list: Enum,
            tuple: Enum,
        }.get(type, type)

        arg = Argument(name, default=default, **kwargs)
        self._addArgument(arg)
        return arg

    def _addArgument(self, arg):
        if arg["name"] in self._arguments:
            raise ValueError("Duplicate argument '%s'" % arg["name"])

        if self._storage is not None:
            default = self._storage.value(arg["name"])

            # Qt's native storage doesn't handle booleans
            # in either of the Python bindings, so we need
            # some jujitsu here to translate values it gives
            # us into something useful to Python
            if default:
                if isinstance(arg, Boolean):
                    default = bool({
                        None: QtCore.Qt.Unchecked,

                        0: QtCore.Qt.Unchecked,
                        1: QtCore.Qt.Checked,
                        2: QtCore.Qt.Checked,

                        "0": QtCore.Qt.Unchecked,
                        "1": QtCore.Qt.Checked,
                        "2": QtCore.Qt.Checked,

                        # May be stored as string, if used with IniFormat
                        "false": QtCore.Qt.Unchecked,
                        "true": QtCore.Qt.Checked,
                    }.get(default))

                if isinstance(arg, Number):
                    if isinstance(arg, Float):
                        default = float(default)
                    else:
                        default = int(default)

                arg["default"] = default

        # Argument label and editor widget
        label = _with_entered_exited2(QtWidgets.QLabel)(arg["label"])

        # Take condition into account
        if arg["condition"]:
            arg["enabled"] = arg["condition"]()

        if isinstance(arg, Enum):
            widget = arg.create(fillWidth=self._style["comboboxFillWidth"])
        else:
            widget = arg.create()

        if self._style.get("useTooltip"):
            label.setToolTip(arg["help"])
            widget.setToolTip(arg["help"])

        widget.setObjectName(arg["name"])  # useful in CSS
        widget.setAttribute(QtCore.Qt.WA_StyledBackground)
        widget.setEnabled(arg["enabled"])
        widget.setProperty("type", type(arg).__name__)

        def base64_to_pixmap(base64):
            data = QtCore.QByteArray.fromBase64(base64)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(data)
            return pixmap

        # Reset btn widget
        reset_icon = QtGui.QIcon(base64_to_pixmap(_reset_icon))
        reset_container = QtWidgets.QWidget()
        reset_container.setFixedSize(px(12), px(12))
        reset = QtWidgets.QPushButton("")  # default
        reset.setObjectName("resetButton")
        reset.setIcon(reset_icon)
        reset.setIconSize(QtCore.QSize(px(12), px(12)))
        reset.setToolTip(arg.compose_reset_tip())
        reset.hide()  # shown on edit

        # Internal
        arg["_widget"] = widget
        arg["_reset"] = reset

        # Align label on top of row if widget is over two times higher
        height = (lambda w: w.sizeHint().height())
        label_on_top = height(label) * 2 < height(widget)

        if label_on_top:
            alignment = (QtCore.Qt.AlignRight | QtCore.Qt.AlignTop,)
        else:
            alignment = (QtCore.Qt.AlignRight,)

        # Layout
        layout = QtWidgets.QVBoxLayout(reset_container)
        layout.addWidget(reset)
        layout.setContentsMargins(0, 0, 0, 0)

        layout = self.layout()

        #  ___________________________________________
        # |         |                         |       |
        # |  label  | editor                  | reset |
        # |_________|_________________________|_______|
        #

        # Checkboxes have their own label to the right
        if not isinstance(arg, Boolean):
            layout.addWidget(label, self._row, 0, *alignment)

        layout.addWidget(widget, self._row, 1)
        layout.addWidget(reset_container, self._row, 2, *alignment)

        # Packed tightly on the vertical
        layout.setHorizontalSpacing(px(10))
        layout.setVerticalSpacing(px(2))

        # Signals
        reset.pressed.connect(lambda: arg.write(arg["default"]))

        # Prevent button from getting stuck in down-state, since
        # it is hidden right after having been pressed
        reset.pressed.connect(lambda: reset.setDown(False))

        arg.changed.connect(lambda: self.on_changed(arg))
        arg.entered.connect(lambda: self.on_entered(arg))
        arg.exited.connect(lambda: self.on_exited(arg))
        label.entered.connect(lambda: self.on_entered(arg))
        label.exited.connect(lambda: self.on_exited(arg))

        # Take ownership for clean deletion alongside parser
        arg.setParent(self)

        def setVisible(value):
            label.setVisible(value)
            widget.setVisible(value)
            reset_container.setVisible(value)

        arg.setVisible = setVisible

        if not arg["visible"]:
            arg.setVisible(False)

        self._row += 1
        self._arguments[arg["name"]] = arg
        self._resets[arg["name"]] = reset

        # Establish initial state, taking "initial" value into account
        self.on_changed(arg)

    def clear(self):
        assert self._storage, "Cannot clear without persistent storage"
        self._storage.clear()
        _log.info("Clearing settings @ %s" % self._storage.fileName())

    def find(self, name):
        return self._arguments[name]

    def on_changed(self, arg):
        reset = self._resets[arg["name"]]
        reset.setVisible(arg.isEdited() and arg["enabled"] and arg["editable"])

        arg["edited"] = arg.isEdited()

        if arg["edited"]:
            arg["_widget"].setStyleSheet("""\
                QLabel,
                QCheckBox,
                QComboBox,
                QDoubleSpinBox,
                QSpinBox {
                    font-weight: bold
                }
            """)
        else:
            arg["_widget"].setStyleSheet(None)

        # Conditions may have changed
        for other in self._arguments.values():
            if other["condition"]:
                other["enabled"] = other["condition"]()
                other["_widget"].setEnabled(other["enabled"])
                other["_reset"].setEnabled(other["enabled"])

        self.changed.emit(arg)

    def on_entered(self, arg):
        """Emitted when an argument is entered"""
        self.entered.emit(arg)

    def on_exited(self, arg):
        """Emitted when an argument is exited"""
        self.exited.emit(arg)

    # Optional PEP08 syntax
    add_argument = addArgument


class QArgument(QtCore.QObject):
    """Base class of argument user interface"""

    changed = QtCore.Signal()
    entered = QtCore.Signal()
    exited = QtCore.Signal()

    # Provide a left-hand side label for this argument
    label = True

    # For defining default value for each argument type
    default = None

    def __init__(self, name, default=None, **kwargs):
        super(QArgument, self).__init__(kwargs.pop("parent", None))

        args = {}
        args["name"] = name
        args["label"] = kwargs.pop("label", camel_to_title(name))
        args["default"] = self.default if default is None else default
        args["initial"] = kwargs.pop("initial", None)
        args["help"] = kwargs.pop("help", "")
        args["read"] = kwargs.pop("read", None)
        args["write"] = kwargs.pop("write", None)
        args["items"] = kwargs.pop("items", [])
        args["min"] = kwargs.pop("min", 0)
        args["max"] = kwargs.pop("max", 99)
        args["enabled"] = bool(kwargs.pop("enabled", True))
        args["editable"] = bool(kwargs.pop("editable", True))
        args["edited"] = False
        args["condition"] = None
        args["placeholder"] = kwargs.pop("placeholder", None)
        args["visible"] = kwargs.pop("visible", True)

        # Anything left is an error
        for arg in kwargs:
            raise TypeError(
                "%s() got an unexpected keyword argument '%s' #"
                % (type(self).__name__, arg)
            )

        self._data = args

    def __str__(self):
        return self["name"]

    def __repr__(self):
        return "%s(\"%s\")" % (type(self).__name__, self["name"])

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __eq__(self, other):
        if isinstance(other, _basestring):
            return self["name"] == other
        return super(QArgument, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def isEdited(self):
        return self.read() != self["default"]

    def create(self):
        return QtWidgets.QWidget()

    def read(self):
        return self._read()

    def write(self, value, notify=True):
        self._write(value)

        if notify:
            self.changed.emit()

    def reset(self):
        self.write(self["default"])

    def setEnabled(self, value, notify=True):
        self["enabled"] = value

        if notify:
            self.changed.emit()

    def enable(self, notify=True):
        self.setEnabled(True, notify)

    def disable(self, notify=True):
        self.setEnabled(False, notify)

    def widget(self):
        widget = self._data["_widget"]

        # Let the bells chime
        assert QtCompat.isValid(widget), (
            "%s was no longer alive" % self["name"]
        )

        return widget

    def compose_reset_tip(self):
        return "Reset%s" % (
            "" if self["default"] is None else " to %s" % str(self["default"])
        )


def _with_entered_exited(cls, obj):
    """Factory function to append `enterEvent` and `leaveEvent`"""
    class WidgetHoverFactory(cls):
        entered = QtCore.Signal()
        exited = QtCore.Signal()

        def enterEvent(self, event):
            self.entered.emit()
            obj.entered.emit()
            return super(WidgetHoverFactory, self).enterEvent(event)

        def leaveEvent(self, event):
            self.exited.emit()
            obj.exited.emit()
            return super(WidgetHoverFactory, self).leaveEvent(event)

    return WidgetHoverFactory


def _with_entered_exited2(cls):
    """Factory function to append `enterEvent` and `leaveEvent`"""
    class WidgetHoverFactory(cls):
        entered = QtCore.Signal()
        exited = QtCore.Signal()

        def enterEvent(self, event):
            self.entered.emit()
            return super(WidgetHoverFactory, self).enterEvent(event)

        def leaveEvent(self, event):
            self.exited.emit()
            return super(WidgetHoverFactory, self).leaveEvent(event)

    return WidgetHoverFactory


class Boolean(QArgument):
    """Boolean type user interface

    Presented by `QtWidgets.QCheckBox`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (bool, optional): Argument's default value, default None
        enabled (bool, optional): Whether to enable this widget, default True

    """

    def create(self):
        Widget = _with_entered_exited(QtWidgets.QCheckBox, self)
        widget = Widget(self._data["label"])

        if isinstance(self, Tristate):
            self._read = lambda: widget.checkState()
            state = {
                0: QtCore.Qt.Unchecked,
                1: QtCore.Qt.PartiallyChecked,
                2: QtCore.Qt.Checked,
                "1": QtCore.Qt.PartiallyChecked,
                "0": QtCore.Qt.Unchecked,
                "2": QtCore.Qt.Checked,
            }
        else:
            self._read = lambda: bool(widget.checkState())
            state = {
                None: QtCore.Qt.Unchecked,

                0: QtCore.Qt.Unchecked,
                1: QtCore.Qt.Checked,
                2: QtCore.Qt.Checked,

                "0": QtCore.Qt.Unchecked,
                "1": QtCore.Qt.Checked,
                "2": QtCore.Qt.Checked,

                # May be stored as string, if used with QSettings(..IniFormat)
                "false": QtCore.Qt.Unchecked,
                "true": QtCore.Qt.Checked,
            }

        self._write = lambda value: widget.setCheckState(state[value])
        widget.clicked.connect(self.changed.emit)

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None:
            self._write(initial)

        return widget

    def read(self):
        return self._read()


class Tristate(QArgument):
    """Not implemented"""


class FractionSlider(QtWidgets.QSlider):
    """Slider capable of sliding between whole numbers

    Qt, surprisingly, doesn't provide this out of the box

    """

    _floatValueChanged = QtCore.Signal(float)
    entered = QtCore.Signal()
    exited = QtCore.Signal()

    def __init__(self, steps=100, parent=None):
        super(FractionSlider, self).__init__(parent=parent)

        self.steps = steps

        self.valueChanged.connect(self._onValueChanged)

        # Masquerade as native signal, now that we're connected
        # to and will translate that into a float value
        self.valueChanged = self._floatValueChanged

    def _onValueChanged(self, value):
        self._floatValueChanged.emit(value / float(self.steps))

    def setMinimum(self, value):
        super(FractionSlider, self).setMinimum(value * self.steps)

    def setMaximum(self, value):
        super(FractionSlider, self).setMaximum(value * self.steps)

    def setValue(self, value):
        super(FractionSlider, self).setValue(value * self.steps)

    def value(self):
        return super(FractionSlider, self).value() / float(self.steps)


class Number(QArgument):
    """Base class of numeric type user interface"""
    default = 0

    def create(self):
        if isinstance(self, Float):
            slider = _with_entered_exited(FractionSlider, self)()
            widget = _with_entered_exited(QtWidgets.QDoubleSpinBox, self)()
            default = self._data.get("default", 0.0)
            widget.setMinimum(min(default, self._data.get("min", 0.0)))
            widget.setMaximum(max(default, self._data.get("max", 99.99)))

            # Account for small values
            delta = widget.maximum() - widget.minimum()

            stepsize = 0.1 if delta < 10 else 1.0
            widget.setSingleStep(stepsize)

            minimum = self._data.get("min", 0.0)
            decimals = len(str(minimum - int(minimum)).rsplit(".")[-1])
            widget.setDecimals(max(1, decimals))

        else:
            slider = _with_entered_exited(QtWidgets.QSlider, self)()
            widget = _with_entered_exited(QtWidgets.QSpinBox, self)()
            default = self._data.get("default", 0)
            widget.setMinimum(min(default, self._data.get("min", 0)))
            widget.setMaximum(max(default, self._data.get("max", 99)))

        widget.setMinimumWidth(px(50))

        container = QtWidgets.QWidget()
        slider.setMaximum(widget.maximum())
        slider.setMinimum(widget.minimum())
        slider.setOrientation(QtCore.Qt.Horizontal)

        layout = QtWidgets.QHBoxLayout(container)
        layout.addWidget(widget)
        layout.addWidget(slider)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = slider
        self._widget = widget

        # Synchonise spinbox with slider
        widget.editingFinished.connect(self.changed.emit)
        widget.valueChanged.connect(self.on_spinbox_changed)
        slider.valueChanged.connect(self.on_slider_changed)

        self._read = lambda: widget.value()
        self._write = lambda value: widget.setValue(value)

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial != self.default:
            self._write(initial)

        return container

    def on_spinbox_changed(self, value):
        self._slider.setValue(value)
        # Spinbox emits a signal all on its own

    def on_slider_changed(self, value):
        self._widget.setValue(value)

        # Help spinbox emit this change
        self.changed.emit()


class Integer(Number):
    """Integer type user interface

    A subclass of `qargparse.Number`, presented by `QtWidgets.QSpinBox`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (int, optional): Argument's default value, default 0
        min (int, optional): Argument's minimum value, default 0
        max (int, optional): Argument's maximum value, default 99
        enabled (bool, optional): Whether to enable this widget, default True

    """


class Float(Number):
    """Float type user interface

    A subclass of `qargparse.Number`, presented by `QtWidgets.QDoubleSpinBox`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (float, optional): Argument's default value, default 0.0
        min (float, optional): Argument's minimum value, default 0.0
        max (float, optional): Argument's maximum value, default 99.99
        enabled (bool, optional): Whether to enable this widget, default True

    """


class Range(Number):
    """Range type user interface

    A subclass of `qargparse.Number`, not production ready.

    """


class Double3(QArgument):
    """Double3 type user interface

    Presented by three `QtWidgets.QLineEdit` widget
    with `QDoubleValidator` installed.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (tuple or list, optional): Default (0, 0, 0).
        enabled (bool, optional): Whether to enable this widget, default True

    """

    default = (0, 0, 0)

    def create(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        x, y, z = (self.child_arg(layout, i) for i in range(3))

        self._read = lambda: (
            float(x.text()), float(y.text()), float(z.text()))
        self._write = lambda value: [
            w.setText(str(float(v))) for w, v in zip([x, y, z], value)]

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial != self.default:
            self._write(initial)

        return widget

    def child_arg(self, layout, index):
        widget = _with_entered_exited(QtWidgets.QLineEdit, self)()
        widget.setValidator(QtGui.QDoubleValidator())

        default = str(float(self["default"][index]))
        widget.setText(default)

        def focusOutEvent(event):
            if not widget.text():
                widget.setText(default)  # Ensure value exists for `_read`
            QtWidgets.QLineEdit.focusOutEvent(widget, event)
        widget.focusOutEvent = focusOutEvent

        widget.editingFinished.connect(self.changed.emit)
        widget.returnPressed.connect(widget.editingFinished.emit)

        layout.addWidget(widget)

        return widget


class String(QArgument):
    """String type user interface

    Presented by `QtWidgets.QLineEdit`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (str, optional): Argument's default value, default None
        placeholder (str, optional): Placeholder message for the widget
        enabled (bool, optional): Whether to enable this widget, default True

    """

    def __init__(self, *args, **kwargs):
        super(String, self).__init__(*args, **kwargs)
        self._previous = None

    def isEdited(self):
        # There's no reasonable default value for a string
        return False

    def create(self):
        widget = _with_entered_exited(QtWidgets.QLineEdit, self)()
        widget.editingFinished.connect(self.onEditingFinished)
        self._read = lambda: widget.text()
        self._write = lambda value: widget.setText(value)

        if isinstance(self, Info):
            widget.setReadOnly(True)
        widget.setPlaceholderText(self._data.get("placeholder") or "")

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None:
            self._write(initial)
            self._previous = initial

        return widget

    def onEditingFinished(self):
        current = self._read()

        if current != self._previous:
            self._previous = current
            self.changed.emit()


class String2(String):
    """A pair of 2 strings"""

    def isEdited(self):
        return any(self.read())

    def create(self):
        a = _with_entered_exited(QtWidgets.QLineEdit, self)()
        b = _with_entered_exited(QtWidgets.QLineEdit, self)()

        if not self["editable"]:
            a.setReadOnly(True)
            b.setReadOnly(True)

        container = QtWidgets.QWidget()

        layout = QtWidgets.QHBoxLayout(container)
        layout.addWidget(a)
        layout.addWidget(b)
        layout.setSpacing(px(2))
        layout.setContentsMargins(0, 0, 0, 0)

        a.editingFinished.connect(self.onEditingFinished)
        b.editingFinished.connect(self.onEditingFinished)

        self._read = lambda: (a.text(), b.text())
        self._write = lambda value: (a.setText(value[0]), b.setText(value[1]))

        if isinstance(self, Info):
            a.setReadOnly(True)

        placeholder = self._data.get("placeholder") or ("", "")
        a.setPlaceholderText(placeholder[0])
        b.setPlaceholderText(placeholder[1])

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None:
            self._write(initial)
            self._previous = initial

        return container


class Path(String):
    """Path type user interface

    Represented by `QtWidgets.QLineEdit` and `QPushButton`

    Arguments:

    """

    browsed = QtCore.Signal()

    def create(self):
        # Keep the `onEditingFinished` signal
        widget = super(Path, self).create()
        widget.setPlaceholderText(r"Click 'Browse' or type in a full path.")

        browse = _with_entered_exited(QtWidgets.QPushButton, self)("Browse")
        browse.setMaximumHeight(px(22))
        widget.setMinimumWidth(px(50))

        container = QtWidgets.QWidget()

        layout = QtWidgets.QHBoxLayout(container)
        layout.addWidget(widget)
        layout.addWidget(browse)
        layout.setSpacing(px(2))
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = browse
        self._widget = widget

        # Synchonise spinbox with browse
        browse.clicked.connect(self.browsed.emit)

        self._read = lambda: widget.text()
        self._write = lambda value: widget.setText(value)

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial != self.default:
            self._write(initial)

        return container


class Info(String):
    """String type user interface but read-only

    A subclass of `qargparse.String`, presented by `QtWidgets.QLineEdit`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (str, optional): Argument's default value, default None
        enabled (bool, optional): Whether to enable this widget, default True

    """


class Color(String):
    """Color type user interface

    A subclass of `qargparse.String`, not production ready.

    """


class Button(QArgument):
    """Button type user interface

    Presented by `QtWidgets.QPushButton`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (bool, optional): Argument's default value, default None
        enabled (bool, optional): Whether to enable this widget, default True

    """
    label = False

    def create(self):
        Widget = _with_entered_exited(QtWidgets.QPushButton, self)
        widget = Widget(self["label"])
        widget.clicked.connect(self.changed.emit)

        state = [
            QtCore.Qt.Unchecked,
            QtCore.Qt.Checked,
        ]

        if isinstance(self, Toggle):
            widget.setCheckable(True)
            self._read = lambda: widget.checkState()
            self._write = (
                lambda value: widget.setCheckState(state[int(value)])
            )
        else:
            self._read = lambda: "clicked"
            self._write = lambda value: None

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None:
            self._write(initial)

        return widget


class Toggle(Button):
    """Checkable `Button` type user interface

    Presented by `QtWidgets.QPushButton`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        default (bool, optional): Argument's default value, default None
        enabled (bool, optional): Whether to enable this widget, default True

    """


class InfoList(QArgument):
    """String list type user interface

    Presented by `QtWidgets.QListView`, not production ready.

    """

    def __init__(self, name, **kwargs):
        kwargs["default"] = kwargs.pop("default", ["Empty"])
        super(InfoList, self).__init__(name, **kwargs)

    def create(self):
        class Model(QtCore.QStringListModel):
            def data(self, index, role):
                return super(Model, self).data(index, role)

        model = QtCore.QStringListModel(self["default"])
        widget = _with_entered_exited(QtWidgets.QListView, self)()
        widget.setModel(model)
        widget.setEditTriggers(widget.NoEditTriggers)

        self._read = lambda: model.stringList()
        self._write = lambda value: model.setStringList(value)

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None:
            self._write(initial)

        return widget


class Choice(QArgument):
    """Argument user interface for selecting one from list

    Presented by `QtWidgets.QListView`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        items (list, optional): List of strings for select, default `["Empty"]`
        default (str, optional): Default item in `items`, use first of `items`
            if not given.
        enabled (bool, optional): Whether to enable this widget, default True

    """

    def __init__(self, name, **kwargs):
        kwargs["items"] = kwargs.get("items", ["Empty"])
        kwargs["default"] = kwargs.pop("default", kwargs["items"][0])
        super(Choice, self).__init__(name, **kwargs)

    def index(self, value):
        """Return numerical equivalent to self.read()"""
        return self["items"].index(value)

    def create(self):
        def on_changed(selected, deselected):
            try:
                selected = selected.indexes()[0]
            except IndexError:
                # At least one item must be selected at all times
                selected = deselected.indexes()[0]

            value = selected.data(QtCore.Qt.DisplayRole)
            set_current(value)
            self.changed.emit()

        def set_current(current):
            options = model.stringList()

            if current == "Empty":
                index = 0
            else:
                for index, member in enumerate(options):
                    if member == current:
                        break
                else:
                    raise ValueError(
                        "%s not a member of %s" % (current, options)
                    )

            qindex = model.index(index, 0, QtCore.QModelIndex())
            smodel.setCurrentIndex(qindex, smodel.ClearAndSelect)
            self["current"] = options[index]

        def reset(items, default=None):
            items = items or ["Empty"]
            model.setStringList(items)
            set_current(default or items[0])

        model = QtCore.QStringListModel()
        widget = _with_entered_exited(QtWidgets.QListView, self)()
        widget.setModel(model)
        widget.setEditTriggers(widget.NoEditTriggers)
        widget.setSelectionMode(widget.SingleSelection)
        smodel = widget.selectionModel()
        smodel.selectionChanged.connect(on_changed)

        self._read = lambda: self["current"]
        self._write = lambda value: set_current(value)
        self.reset = reset

        reset(self["items"], self["default"])

        return widget


class ListItem(dict):
    pass


class List(QArgument):
    def isEdited(self):
        return False

    def create(self):
        assert all(isinstance(item, ListItem) for item in self["items"]), (
            "Items of a List must be of type ListItem"
        )

        widget = _with_entered_exited(QtWidgets.QListWidget, self)()

        # Containerise to allow for internal changes by the user
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.addWidget(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        def reset(items, current=0):
            for item in items:
                qitem = QtWidgets.QListWidgetItem()

                for role, value in item.items():
                    qitem.setData(role, value)

                widget.addItem(qitem)

            if items:
                widget.setCurrentRow(current)

        reset(self["items"])

        def read():
            item = widget.currentItem()
            if item is not None:
                return item.text()
            return ""

        def write(value):
            item = widget.currentItem()
            if item is not None:
                item.setText(value)

        self._read = read
        self._write = write
        self._reset = reset

        return container

    def reset(self, items=None, current=0):
        self["items"][:] = items or []
        self._reset(items, current)


class Table(QArgument):
    doubleClicked = QtCore.Signal()

    def isEdited(self):
        return False

    def create(self):
        model = GenericTreeModel()
        view = _with_entered_exited(GenericTreeView, self)()
        view.setIndentation(0)
        view.setHeaderHidden(True)
        view.setModel(model)

        def reset(items, header=None, current=None):
            root_item = GenericTreeModelItem({
                QtCore.Qt.DisplayRole: header or ("",),
            })

            current_row = None
            for row, item in enumerate(items):
                child_item = GenericTreeModelItem(item)
                root_item.addChild(child_item)

                if current is not None:
                    other = item.get(QtCore.Qt.DisplayRole, "")

                    if isinstance(other, (tuple, list)):
                        other = other[0]

                    if current == other:
                        current_row = row

            # Establish a sensible default
            model.reset(root_item)

            if current_row is not None:
                index = model.index(current_row, 0)

                if index.isValid():
                    sel_model = view.selectionModel()
                    sel_model.select(
                        index,
                        selection.ClearAndSelect | selection.Rows
                    )
                    view.scrollTo(index)

            self.changed.emit()

        reset(self["items"], ("key", "value"))

        def read(role=QtCore.Qt.DisplayRole):
            index = view.selectionModel().selectedIndexes()

            if not len(index):
                return ""

            index = index[0]
            if not index.isValid():
                return ""

            # Find column 0, in case another column was selected
            index = model.index(index.row(), 0, index.parent())

            if not index.isValid():
                return ""

            return index.data(role)

        def write(column, value):
            return
            # item = widget.currentItem()
            # if item is not None:
            #     item.setText(column, value)

        selection = view.selectionModel()
        selection.currentChanged.connect(self.onItemChanged)
        view.doubleClicked.connect(self.onItemDoubleClicked)

        # Containerise to allow for internal changes by the user
        container = QtWidgets.QWidget()
        container.setObjectName("Container")
        layout = QtWidgets.QHBoxLayout(container)
        layout.addWidget(view, 1)
        layout.setContentsMargins(0, 0, 0, 0)

        self._read = read
        self._write = write
        self._reset = reset
        self._model = model

        return container

    def read(self, role=QtCore.Qt.DisplayRole):
        return self._read(role)

    def reset(self, items=None, header=None, current=None):
        self["items"][:] = items or []
        self._reset(items, header, current)

    def setHeader(self, *columns):
        header = self._widget.headerItem()
        for index, label in enumerate(columns):
            header.setText(index, label)

        if columns:
            self._widget.setHeaderHidden(True)
        else:
            self._widget.setHeaderHidden(False)

    def onItemChanged(self, current, previous):
        # Give selection model a chance to update its selection
        QtCore.QTimer.singleShot(10, self.changed.emit)

    def onItemDoubleClicked(self):
        def emit():
            self.doubleClicked.emit()

        # Give widget a chance to render
        QtCore.QTimer.singleShot(10, emit)


class Separator(QArgument):
    """Visual separator

    Example:

        item1
        item2
        ------------
        item3
        item4

    """

    def create(self):
        widget = _with_entered_exited(QtWidgets.QWidget, self)()

        self._read = lambda: None
        self._write = lambda value: None

        return widget

    def reset(self):
        # This ain't got no default value
        pass


class Image(QArgument):
    """An image of sorts

               ________________
    Thumbnail |                |
              |                |
              |                |
              |                |
              |________________|

    """

    clicked = QtCore.Signal()

    def __init__(self, name, **kwargs):
        super(Image, self).__init__(name, **kwargs)
        self._data["editable"] = False

    def create(self):
        label = _with_entered_exited(QtWidgets.QLabel, self)()
        label.setMinimumHeight(px(200))
        label.setMinimumWidth(px(128))

        self._widget = label

        def _write(pixmap):
            if not isinstance(pixmap, QtGui.QPixmap):
                pixmap = QtGui.QPixmap(pixmap)
            label.setPixmap(pixmap)

        self._read = lambda: None
        self._write = _write

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial != self.default:
            self._write(initial)

        return label

    def reset(self):
        # This ain't got no default value
        pass


# For whatever reason, sizeHint of a QPushButton doesn't
# respect the minimum of fixed sizes. :/
class _ImageButton(QtWidgets.QPushButton):
    def sizeHint(self):
        return QtCore.QSize(px(200), px(128))


class ImageButton(QArgument):
    """An image of sorts

               ________________
    Thumbnail |                |
              |                |
              |                |
              |                |
              |________________|

    """

    clicked = QtCore.Signal()

    def __init__(self, name, **kwargs):
        super(ImageButton, self).__init__(name, **kwargs)
        self._data["editable"] = False  # No reset button

    def create(self):
        button = _with_entered_exited(_ImageButton, self)()

        size = QtCore.QSize(px(200), px(128))
        button.setIconSize(size)
        button.setFixedSize(size)

        button.clicked.connect(self.clicked.emit)

        def _write(pixmap):
            if isinstance(pixmap, QtGui.QIcon):
                pass

            elif isinstance(pixmap, QtGui.QPixmap):
                pixmap.scaled(
                    px(200), px(128),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                icon = QtGui.QIcon(pixmap)

            else:
                # Try making whatever this is into a pixmap
                pixmap = QtGui.QPixmap(pixmap)
                pixmap.scaled(
                    px(200), px(128),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                icon = QtGui.QIcon(pixmap)

            button.setIcon(icon)

        self._widget = button
        self._read = lambda: None
        self._write = _write
        self._size = size

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial != self.default:
            self._write(initial)

        return button

    def pixmap(self):
        icon = self._widget.icon()
        return icon.pixmap(self._size)

    def reset(self):
        # This ain't got no default value
        pass


class Enum(QArgument):
    """Argument user interface for selecting one from dropdown list

    Presented by `QtWidgets.QComboBox`.

    Arguments:
        name (str): The name of argument
        label (str, optional): Display name, convert from `name` if not given
        help (str, optional): Tool tip message of this argument
        items (list, optional): List of strings for select, default `[]`
        default (int, str, optional): Index or text of default item, use first
            of `items` if not given.
        enabled (bool, optional): Whether to enable this widget, default True

    """

    def __init__(self, name, **kwargs):
        kwargs["items"] = kwargs.get("items", ["Default"])
        kwargs["default"] = kwargs.pop("default", 0)

        _enum_types = (tuple, list, types.GeneratorType)
        assert isinstance(kwargs["items"], _enum_types), (
            "items must be list, tuple or generator"
        )

        super(Enum, self).__init__(name, **kwargs)

    def create(self, fillWidth=True):
        items = self["items"] = list(self["items"])  # eval generator

        widget = _with_entered_exited(QtWidgets.QComboBox, self)()
        widget.addItems(items)
        widget.currentIndexChanged.connect(
            lambda index: self.changed.emit())

        # Comboboxes aren't allowed to stretch without
        # the choices also being stretched
        container = QtWidgets.QWidget()

        if not fillWidth:
            layout = QtWidgets.QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)

            # Shrink to smallest horizontal size
            widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                 QtWidgets.QSizePolicy.Fixed)
            layout.addWidget(widget, 1, QtCore.Qt.AlignLeft)

        self._read = widget.currentIndex
        self.text = widget.itemText

        def _write(value):
            index = None

            # Support passing an index directly
            if isinstance(value, int):
                index = value

            else:
                for idx, val in enumerate(items):
                    if value == val:
                        index = idx
                        break

            # Be forgiving, as it isn't easy handling an
            # error happening at this level
            if index is None:
                _log.debug(
                    "%r isn't an option for '%s', whose options are '%s'" % (

                        # Help the caller understand why this is happening
                        value, self["name"], "', '".join(self["items"])
                    )
                )

                index = 0

            widget.setCurrentIndex(index)

        self._write = _write

        initial = self["initial"]

        if initial is None:
            initial = self["default"]

        if initial is not None and initial < len(items):
            if isinstance(initial, int):
                index = initial
                index = 0 if index > len(items) else index
                initial = items[index]
            else:
                # Must be str type. If the default str is not in list, will
                # fallback to the first item silently.
                pass

            self._write(initial)

        return widget if fillWidth else container

    def isEdited(self):
        default = self["default"]

        # Account for string defaults
        if isinstance(default, _basestring):
            default = self["items"].index(self["default"])

        return self.read() != default

    def compose_reset_tip(self):
        default = self["default"]
        if isinstance(default, int):
            default = self["items"][default]
        return "Reset to %s" % default


def camelToTitle(text):
    """Convert camelCase `text` to Title Case

    Example:
        >>> camelToTitle("mixedCase")
        "Mixed Case"
        >>> camelToTitle("myName")
        "My Name"
        >>> camelToTitle("you")
        "You"
        >>> camelToTitle("You")
        "You"
        >>> camelToTitle("This is That")
        "This Is That"

    """

    return re.sub(
        r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))",
        r" \1", text
    ).title()


camel_to_title = camelToTitle


# Utility classes to avoid having to deal with QTreeWidget
# which is buggy as heck.


class GenericTreeView(QtWidgets.QTreeView):
    doubleClicked = QtCore.Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        return super(GenericTreeView, self).mouseDoubleClickEvent(event)


class GenericTreeModel(QtCore.QAbstractItemModel):
    """A tree model able to display any number of roles and columns

    Items are of GenericItemModel type.

    """

    def __init__(self, parent=None):
        super(GenericTreeModel, self).__init__(parent)

        self._rootItem = GenericTreeModelItem()

    def reset(self, root, current=None):
        """Set a new root item

        Arguments:
            targets (list): List of { Role : [Col1, Col2] } pairs

        """

        assert isinstance(root, GenericTreeModelItem)

        self.beginResetModel()
        self._rootItem = root
        self.endResetModel()

        return True

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()

        try:
            column = item.data(role)

            # Passed as either single-value or tuple of columns
            # (column1, column2, column3, ...)
            if isinstance(column, (tuple, list)):
                return column[index.column()]
            elif index.column() == 0:
                return column

        except (KeyError, IndexError):
            pass

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.DisplayRole:
            return None

        if orientation == QtCore.Qt.Horizontal:
            return self._rootItem.data(QtCore.Qt.DisplayRole)[section]

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self._rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._rootItem.data(QtCore.Qt.DisplayRole))


class GenericTreeModelItem(object):
    """An item for the GenericTreeModel

    Items take `data` in the form:

    {
        role: column0
    }

    For multiple columns, pass value as tuple.

    {
        role: (column0, column1, ...)
    }

    """

    def __init__(self, data=None, parent=None):
        self._data = data or {
            # Role                 # Columns
            QtCore.Qt.DisplayRole: ("key", "value")
        }

        self._children = list()
        self._parent = parent

    def __hash__(self):
        return "%x" % id(self)

    def data(self, role):
        return self._data.get(role)

    def hasData(self, role):
        return role in self._data

    def addChild(self, child):
        child._parent = self
        self._children.append(child)

    def childCount(self):
        return len(self._children)

    def child(self, row):
        return self._children[row]

    def parent(self):
        return self._parent

    def row(self):
        if self._parent:
            return self._parent._children.index(self)
        else:
            return 0


def _demo():
    import sys
    app = QtWidgets.QApplication(sys.argv)

    parser = QArgumentParser()
    parser.setWindowTitle("Demo")
    parser.setMinimumWidth(300)

    parser.add_argument("name", default="Marcus", help="Your name")
    parser.add_argument("age", default=33, help="Your age")
    parser.add_argument("height", default=1.87, help="Your height")
    parser.add_argument("alive", default=True, help="Your state")
    parser.add_argument("class", type=Enum, items=[
        "Ranger",
        "Warrior",
        "Sorcerer",
        "Monk",
    ], default=2, help="Your class")

    parser.add_argument("options", type=Separator)
    parser.add_argument("paths", type=InfoList, items=[  # (TODO) Doesn't work
        "Value A",
        "Value B",
        "Some other value",
        "And finally, value C",
    ])
    parser.add_argument("location", type=Double3)

    parser.show()
    app.exec_()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--demo", action="store_true")

    opts = parser.parse_args()

    if opts.demo:
        _demo()

    if opts.version:
        print(__version__)


_reset_icon = b"iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAYAAACM/rhtAAAACXBIWXMAABYlAAAWJQFJUiTwAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAhpJREFUWIXt2MFLFGEcxvHn1ZI9KBixBnb1oKAsHSJEELt06JIdOnjtYkRKUYEegq6Bp/6JEE8Fhrc9FJSKh7JUrIjw5MGDUkLi7rfD/oRpXdeZ9505FPPcdt/3feaz7+wOMyvlyZPn347zXQick3RT0jVJJUndktolbUv6Kqks6YVzbiNG16KkqnNu0NcTLTsPPAd+cjzVBu/NA/2ndAKQBm4U2LG+CrAAjAMDQJvNKQCXgGngm809AKaAlsyAdoCjHXoN9MVYcxa4D/yydXNAIXUg8NA6DoFJj/X9kd1cAYqpAYGrBqsAY14ltZ5u4JNZVoGuYKB9n77Y+qe+uEhf0XB/IUOAE7b2A3AmFGidXfXIEOCmrb2RBq4J0hu4BLzjhMtDisiwX3EA4j0J0qgj9Z2pSzXB3DeZKfLkySp2mYmbpSwMJ/6KASfpcoKu/XBOggCuboc+AxcyOE6rXS/LvsAq8DErJHDLutdDgMUskEAbsG69d7yB9jp1JPDM+tawRwZvYAPkGnAxAHfbzs4BMORTcAwYQS7b2Heg5NE7Re0OHeBuYlwzoI0VgFkb3wcexTlFQAko27oK8MALdxowMv4Y+G3zfgBPgCtAh81pp/YIei8CA9gGrnvj4gAj8/qAlzR+aK/PLjADdMZ1NP3rA3gr6dA5NxLjA/VIGpM0LKlXUodq94NbklYlLUh65Zzbi4vLkyfP/5A/DV639GAOvUoAAAAASUVORK5CYII="