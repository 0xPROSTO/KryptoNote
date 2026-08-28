"""Compact exact canvas navigation dialogs."""

import re

from PySide6.QtCore import QSize, QTimer, Signal, Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.theme.style_factory import StyleFactory
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class _ClampedSpinBox(QSpinBox):
    _INTEGER_PATTERN = re.compile(r"[+-]?\d{1,10}")

    def _number_text(self, text):
        number_text = str(text).strip()
        prefix = self.prefix()
        suffix = self.suffix()
        if prefix and number_text.startswith(prefix):
            number_text = number_text[len(prefix) :]
        if suffix and number_text.endswith(suffix):
            number_text = number_text[: -len(suffix)]
        return number_text.strip()

    def validate(self, text, position):
        number_text = self._number_text(text)
        if number_text in {"", "+", "-"}:
            state = QValidator.State.Intermediate
        elif self._INTEGER_PATTERN.fullmatch(number_text):
            state = QValidator.State.Acceptable
        else:
            state = QValidator.State.Invalid
        return state, text, position

    def valueFromText(self, text):
        try:
            value = int(self._number_text(text))
        except (TypeError, ValueError):
            return self.value()
        return max(self.minimum(), min(self.maximum(), value))


class _DirectionalSpinBox(QSpinBox):
    navigateLeft = Signal()
    navigateRight = Signal()

    def __init__(self, *, navigate_left=False, navigate_right=False, parent=None):
        super().__init__(parent)
        self._navigate_left = bool(navigate_left)
        self._navigate_right = bool(navigate_right)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if event.key() == Qt.Key.Key_Left and self._navigate_left:
                self.navigateLeft.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Right and self._navigate_right:
                self.navigateRight.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class _CanvasNavigationDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, title, action_text, icon_name, parent=None):
        super().__init__(parent)
        self.configure_dialog_chrome(title)
        self.setObjectName("canvas_navigation_dialog")
        self.setModal(True)
        self.setFixedWidth(360)
        self.setStyleSheet(self._qss())
        self._initial_focus_widget = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.container = QWidget(self)
        self.container.setObjectName("about_container")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(8, 8, 8, 22)
        layout.setSpacing(0)

        self._drag_handle = QWidget(self.container)
        header_layout = QHBoxLayout(self._drag_handle)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addSpacing(40)

        self.title_label = QLabel(title, self._drag_handle)
        self.title_label.setObjectName("app_name")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title_label, 1)

        self.close_button = DialogCloseButton(self._drag_handle)
        self.close_button.setObjectName("btn_close")
        self.close_button.setFixedSize(40, 40)
        self.close_button.setIconSize(QSize(18, 18))
        self.close_button.setToolTip("Close")
        self.close_button.setAccessibleName("Close")
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject)
        header_layout.addWidget(self.close_button)
        layout.addWidget(self._drag_handle)

        layout.addSpacing(18)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(14, 0, 14, 0)
        self.content_layout.setSpacing(0)
        layout.addLayout(self.content_layout)

        self.action_button = QPushButton(action_text, self.container)
        self.action_button.setObjectName("btn_submit")
        self.action_button.setIcon(SvgIcons.get_icon(icon_name))
        self.action_button.setIconSize(QSize(16, 16))
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.setAccessibleName(action_text)
        self.action_button.setDefault(False)
        self.action_button.setAutoDefault(False)
        self.action_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.action_button.setFixedHeight(42)
        self.action_button.setMinimumWidth(126)
        self.action_button.clicked.connect(self.accept)

        root_layout.addWidget(self.container)
        self._setup_window_drag(
            drag_height=50,
            drag_handles=[self._drag_handle],
        )

    def _finish_setup(self, initial_focus_widget, tab_widgets):
        self._initial_focus_widget = initial_focus_widget
        for current, following in zip(tab_widgets, tab_widgets[1:]):
            self.setTabOrder(current, following)
        self.layout().activate()
        self.adjustSize()

    @staticmethod
    def _configure_spinbox(field, accessible_name):
        field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        field.setKeyboardTracking(False)
        field.setGroupSeparatorShown(False)
        field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        field.setFixedHeight(42)
        field.setAccessibleName(accessible_name)

    @staticmethod
    def _focus_and_select(field):
        if field is None or not field.isVisible():
            return
        field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        field.selectAll()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(
            0,
            lambda: self._focus_and_select(self._initial_focus_widget),
        )

    @staticmethod
    def _qss():
        return (
            Theme.Styles.get_about_dialog_qss()
            + f"""
            QDialog#canvas_navigation_dialog {{
                color: {Palette.TEXT_MAIN};
                font-family: 'Segoe UI', sans-serif;
            }}
            QSpinBox {{
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                selection-color: {Palette.TEXT_MAIN};
                selection-background-color: {Palette.ACCENT_LOW};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 8px 11px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 600;
            }}
            QSpinBox:hover {{
                border-color: {Palette.BORDER_HOVER};
            }}
            QSpinBox:focus {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QSpinBox:disabled {{
                color: {Palette.TEXT_DISABLED};
                border-color: {Palette.BORDER_SUBTLE};
            }}
            {StyleFactory._generate_button_qss(
                Palette.BTN_APPLY,
                Palette.BTN_APPLY_BORDER,
                Palette.BTN_APPLY_TEXT,
                Palette.BTN_APPLY_HOVER,
                Palette.SUCCESS_HOVER,
                "QPushButton#btn_submit",
            )}
            QPushButton#btn_submit:focus {{
                border-color: {Palette.ACCENT_MAIN};
            }}
            QPushButton#btn_submit:pressed {{
                background-color: {Palette.BG_CONTROL_PRESSED};
            }}
            QPushButton#btn_submit:disabled {{
                color: {Palette.TEXT_DISABLED};
                background-color: {Palette.BG_CONTROL};
                border-color: {Palette.BORDER_SUBTLE};
            }}
            """
        )


class ZoomToDialog(_CanvasNavigationDialog):
    def __init__(
        self,
        minimum_percent,
        maximum_percent,
        parent=None,
    ):
        minimum_percent = int(minimum_percent)
        maximum_percent = int(maximum_percent)
        default_percent = max(
            minimum_percent,
            min(maximum_percent, 100),
        )
        super().__init__(
            "Zoom To",
            "Apply",
            "zoom-in",
            parent,
        )

        self.zoom_input = _ClampedSpinBox(self.container)
        self._configure_spinbox(self.zoom_input, "Zoom percentage")
        self.zoom_input.setRange(minimum_percent, maximum_percent)
        self.zoom_input.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.zoom_input.setSingleStep(1)
        self.zoom_input.setSuffix("%")
        self.zoom_input.setMinimumWidth(162)
        self.zoom_input.setValue(default_percent)
        self.zoom_input.returnPressed.connect(self.accept)
        self.content_layout.addWidget(self.zoom_input)
        self.content_layout.addSpacing(18)
        self.content_layout.addWidget(self.action_button)

        self._finish_setup(
            self.zoom_input,
            (self.zoom_input, self.action_button, self.close_button),
        )

    @property
    def zoom_percent(self):
        self.zoom_input.interpretText()
        return self.zoom_input.value()


class GoToDialog(_CanvasNavigationDialog):
    COORDINATE_MINIMUM = -(2**31)
    COORDINATE_MAXIMUM = 2**31 - 1

    def __init__(self, current_x, current_y, parent=None):
        super().__init__(
            "Go To",
            "Go",
            "fit",
            parent,
        )
        self.setFixedWidth(480)

        fields_layout = QHBoxLayout()
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(10)

        self.x_input = _DirectionalSpinBox(
            navigate_right=True,
            parent=self.container,
        )
        self._configure_coordinate_input(
            self.x_input,
            "X coordinate",
            "X ",
            current_x,
        )
        fields_layout.addWidget(self.x_input, 1)

        self.y_input = _DirectionalSpinBox(
            navigate_left=True,
            parent=self.container,
        )
        self._configure_coordinate_input(
            self.y_input,
            "Y coordinate",
            "Y ",
            current_y,
        )
        fields_layout.addWidget(self.y_input, 1)
        self.action_button.setMinimumWidth(
            max(
                self.x_input.minimumSizeHint().width(),
                self.y_input.minimumSizeHint().width(),
            )
        )
        fields_layout.addWidget(self.action_button, 1)
        self.content_layout.addLayout(fields_layout)

        self.x_input.returnPressed.connect(self._focus_y)
        self.y_input.returnPressed.connect(self.accept)
        self.x_input.navigateRight.connect(self._focus_y)
        self.y_input.navigateLeft.connect(self._focus_x)

        self._finish_setup(
            self.x_input,
            (
                self.x_input,
                self.y_input,
                self.action_button,
                self.close_button,
            ),
        )

    def _configure_coordinate_input(self, field, accessible_name, prefix, value):
        self._configure_spinbox(field, accessible_name)
        field.setRange(self.COORDINATE_MINIMUM, self.COORDINATE_MAXIMUM)
        field.setSingleStep(1)
        field.setPrefix(prefix)
        field.setValue(
            max(
                self.COORDINATE_MINIMUM,
                min(self.COORDINATE_MAXIMUM, int(round(float(value)))),
            )
        )

    def _focus_x(self):
        self._focus_and_select(self.x_input)

    def _focus_y(self):
        self._focus_and_select(self.y_input)

    @property
    def coordinates(self):
        return self.x_input.value(), self.y_input.value()
