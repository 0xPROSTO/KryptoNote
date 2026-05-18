from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.theme.style_factory import StyleFactory


class PasswordChangeDialog(QDialog):
    passwordChangeRequested = Signal(str, str, bool)

    MIN_PWD = 1
    MAX_PWD = 512

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(420, 430)
        self.setStyleSheet(self._qss())

        self._dragging = False
        self._drag_start_pos = QPoint()
        self._changing = False

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setObjectName("about_container")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 0, 24, 22)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 5, 0, 0)
        header.addStretch()
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(40, 40)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        title = QLabel("Change Password")
        title.setObjectName("app_name")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        note = QLabel(
            "Password key will be updated. Notes and media stay unchanged. "
            "Backup is optional."
        )
        note.setObjectName("desc_label")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setMinimumHeight(42)
        layout.addWidget(note)

        self.current_pwd = self._password_field("Current password")
        self.new_pwd = self._password_field("New password")
        self.confirm_pwd = self._password_field("Confirm new password")
        layout.addWidget(self.current_pwd)
        layout.addWidget(self.new_pwd)
        layout.addWidget(self.confirm_pwd)

        self.backup_check = QCheckBox("Create backup before changing password")
        self.backup_check.setChecked(True)
        layout.addWidget(self.backup_check)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        self.status_label.setMinimumHeight(34)
        layout.addWidget(self.status_label)

        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("btn_cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.change_btn = QPushButton("Change")
        self.change_btn.setObjectName("btn_submit")
        self.change_btn.clicked.connect(self._submit)
        buttons.addWidget(self.cancel_btn, 1)
        buttons.addWidget(self.change_btn, 2)
        layout.addLayout(buttons)

        main_layout.addWidget(self.container)
        self.confirm_pwd.returnPressed.connect(self._submit)

    def _submit(self):
        if self._changing:
            return
        current = self.current_pwd.text()
        new = self.new_pwd.text()
        confirm = self.confirm_pwd.text()
        if not current:
            self.show_error("Enter current password")
            self.current_pwd.setFocus()
            return
        if len(new) < self.MIN_PWD or len(new) > self.MAX_PWD:
            self.show_error(f"Password must be {self.MIN_PWD}-{self.MAX_PWD} characters")
            self.new_pwd.setFocus()
            return
        if new != confirm:
            self.show_error("Passwords do not match")
            self.confirm_pwd.selectAll()
            self.confirm_pwd.setFocus()
            return

        self.set_changing(True, "Changing password...")
        self.passwordChangeRequested.emit(current, new, self.backup_check.isChecked())

    def show_error(self, message):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {Palette.DANGER_HOVER}; font-size: 12px; font-weight: bold;")
        self.status_label.setVisible(True)

    def set_changing(self, changing, message=""):
        self._changing = changing
        for widget in (
            self.current_pwd,
            self.new_pwd,
            self.confirm_pwd,
            self.backup_check,
            self.cancel_btn,
            self.change_btn,
            self.btn_close,
        ):
            widget.setEnabled(not changing)
        if message:
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {Palette.TEXT_DIM}; font-size: 12px;")
            self.status_label.setVisible(True)

    def show_finished(self, success, message):
        self.set_changing(False)
        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {Palette.GREEN_SECURE}; font-size: 12px; font-weight: bold;")
            self.status_label.setVisible(True)
            self.cancel_btn.setText("Close")
            self.change_btn.setVisible(False)
        else:
            self.show_error(message)
            self.current_pwd.selectAll()
            self.current_pwd.setFocus()

    def is_changing(self):
        return self._changing

    def reject(self):
        if self._changing:
            return
        super().reject()

    def closeEvent(self, event):
        if self._changing:
            event.ignore()
            return
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False

    @staticmethod
    def _password_field(placeholder):
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setMaxLength(PasswordChangeDialog.MAX_PWD)
        field.setPlaceholderText(placeholder)
        return field

    @staticmethod
    def _qss():
        return (
            Theme.Styles.get_about_dialog_qss()
            + f"""
            QLineEdit {{
                background-color: {Palette.BG_INPUT};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 9px 11px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Palette.ACCENT_MAIN};
            }}
            QCheckBox {{
                color: {Palette.TEXT_MAIN};
                font-size: 12px;
                spacing: 8px;
            }}
            QLabel#status_label {{
                background: transparent;
                border: none;
            }}
            {StyleFactory._generate_button_qss(Palette.BTN_APPLY, Palette.BTN_APPLY_BORDER, Palette.BTN_APPLY_TEXT, Palette.BTN_APPLY_HOVER, Palette.SUCCESS_HOVER, "QPushButton#btn_submit")}
            {StyleFactory._generate_button_qss(Palette.BTN_CANCEL, Palette.BTN_CANCEL_BORDER, Palette.BTN_CANCEL_TEXT, Palette.BTN_CANCEL_HOVER, Palette.DANGER_HOVER, "QPushButton#btn_cancel")}
            """
        )
