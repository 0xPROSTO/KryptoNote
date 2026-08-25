"""Application-styled confirmation dialog for destructive actions."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class ConfirmationDialog(FramelessWindowDragMixin, QDialog):
    """Small modal confirmation surface with a safe default action."""

    def __init__(
        self,
        heading,
        message,
        *,
        confirm_text="Confirm",
        cancel_text="Cancel",
        destructive=False,
        icon_name="info",
        parent=None,
    ):
        super().__init__(parent)
        self.configure_dialog_chrome(str(heading))
        self.setObjectName("confirmation_dialog")
        self.setModal(True)
        self.setFixedWidth(400)
        self.setStyleSheet(Theme.Styles.get_confirmation_dialog_qss())

        self._build_ui(
            str(heading),
            str(message),
            str(confirm_text),
            str(cancel_text),
            bool(destructive),
            str(icon_name),
        )
        self._setup_window_drag(
            drag_height=56,
            drag_handles=[self._drag_handle],
        )

    def _build_ui(
        self,
        heading,
        message,
        confirm_text,
        cancel_text,
        destructive,
        icon_name,
    ):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        container = QWidget(self)
        container.setObjectName("confirmation_container")
        container.setFixedWidth(400)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 17, 22, 20)
        layout.setSpacing(0)

        self._drag_handle = QWidget(container)
        self._drag_handle.setObjectName("confirmation_header")
        header_layout = QHBoxLayout(self._drag_handle)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        icon_label = QLabel(self._drag_handle)
        icon_label.setObjectName("confirmation_icon")
        icon_label.setProperty("destructive", destructive)
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = SvgIcons.get_icon(
            icon_name,
            color=Palette.BTN_CANCEL_TEXT if destructive else Palette.TEXT_DIM,
            active_color=(
                Palette.BTN_CANCEL_TEXT if destructive else Palette.ACCENT_MAIN
            ),
        )
        icon_label.setPixmap(icon.pixmap(QSize(20, 20)))
        header_layout.addWidget(icon_label)

        title_label = QLabel(heading, self._drag_handle)
        title_label.setObjectName("confirmation_title")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label, 1)

        close_button = DialogCloseButton(self._drag_handle)
        close_button.setObjectName("confirmation_close")
        close_button.setFixedSize(34, 34)
        close_button.setIconSize(QSize(17, 17))
        close_button.setToolTip("Cancel")
        close_button.setAccessibleName("Cancel")
        close_button.setAutoDefault(False)
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)
        layout.addWidget(self._drag_handle)

        layout.addSpacing(14)
        message_label = QLabel(message, container)
        message_label.setObjectName("confirmation_message")
        message_label.setWordWrap(True)
        message_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        layout.addWidget(message_label)

        layout.addSpacing(18)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addStretch(1)

        self.cancel_button = QPushButton(cancel_text, container)
        self.cancel_button.setObjectName("confirmation_cancel")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.setAccessibleName(cancel_text)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.confirm_button = QPushButton(confirm_text, container)
        self.confirm_button.setObjectName(
            "confirmation_confirm_danger"
            if destructive
            else "confirmation_confirm"
        )
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.setDefault(False)
        self.confirm_button.setAutoDefault(False)
        self.confirm_button.setAccessibleName(confirm_text)
        self.confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(self.confirm_button)
        layout.addLayout(button_layout)

        self.setTabOrder(self.cancel_button, self.confirm_button)
        self.cancel_button.setFocus(Qt.FocusReason.OtherFocusReason)
        root_layout.addWidget(container)
        root_layout.activate()
        self.adjustSize()

    def keyPressEvent(self, event):
        key = event.key()
        focused = self.focusWidget()

        if key in {Qt.Key.Key_Left, Qt.Key.Key_Up}:
            target = (
                self.confirm_button
                if focused is self.cancel_button
                else self.cancel_button
            )
            target.setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return

        if key in {Qt.Key.Key_Right, Qt.Key.Key_Down}:
            target = (
                self.cancel_button
                if focused is self.confirm_button
                else self.confirm_button
            )
            target.setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return

        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if focused is self.confirm_button:
                self.confirm_button.click()
            else:
                self.cancel_button.click()
            event.accept()
            return

        super().keyPressEvent(event)
