from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.theme.style_factory import StyleFactory
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin
from KryptoNote.core.password_policy import (
    PROJECT_PASSWORD_MAX,
    WEAK_PASSWORD_LENGTH,
    is_weak_project_password,
)


class PasswordChangeDialog(FramelessWindowDragMixin, QDialog):
    passwordChangeRequested = Signal(str, str, bool)
    cancelRequested = Signal()

    MIN_PWD = 1
    MAX_PWD = PROJECT_PASSWORD_MAX

    def __init__(self, parent=None):
        super().__init__(parent)
        self.configure_dialog_chrome("Change Password")
        self.setModal(True)
        self.setFixedSize(420, 430)
        self.setStyleSheet(self._qss())

        self._changing = False
        self._cancel_requested = False

        self._init_ui()
        self._setup_window_drag(drag_height=56, drag_handles=[self._drag_handle])

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setObjectName("about_container")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 0, 24, 22)
        layout.setSpacing(10)

        header_widget = QWidget(self.container)
        self._drag_handle = header_widget
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(0, 5, 0, 0)
        header.addStretch()
        self.btn_close = DialogCloseButton()
        self.btn_close.setIconSize(QSize(18, 18))
        self.btn_close.setToolTip("Close")
        self.btn_close.setAccessibleName("Close")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(40, 40)
        self.btn_close.clicked.connect(self.reject)
        header.addWidget(self.btn_close)
        layout.addWidget(header_widget)

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
        self.backup_check.setIcon(SvgIcons.get_icon("backup"))
        self.backup_check.setIconSize(QSize(16, 16))
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
        self.cancel_btn.setIcon(SvgIcons.get_icon("close"))
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.setObjectName("btn_cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.change_btn = QPushButton("Change")
        self.change_btn.setIcon(SvgIcons.get_icon("lock"))
        self.change_btn.setIconSize(QSize(16, 16))
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
        if is_weak_project_password(new):
            answer = QMessageBox.question(
                self,
                "Weak Password",
                f"This password is shorter than {WEAK_PASSWORD_LENGTH} "
                "characters and may be easy to guess.\n\nUse it anyway?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.new_pwd.setFocus()
                return

        self.set_changing(True, "Changing password...")
        self.passwordChangeRequested.emit(current, new, self.backup_check.isChecked())

    def show_error(self, message):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {Palette.DANGER_HOVER}; font-size: 12px; font-weight: bold;")
        self.status_label.setVisible(True)

    def set_changing(self, changing, message=""):
        self._changing = changing
        self._cancel_requested = False
        for widget in (
            self.current_pwd,
            self.new_pwd,
            self.confirm_pwd,
            self.backup_check,
            self.change_btn,
        ):
            widget.setEnabled(not changing)
        self.cancel_btn.setEnabled(True)
        self.btn_close.setEnabled(True)
        if not changing:
            self.cancel_btn.setText("Cancel")
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
            if not self._cancel_requested:
                self._cancel_requested = True
                self.cancel_btn.setEnabled(False)
                self.btn_close.setEnabled(False)
                self.status_label.setText("Cancelling safely...")
                self.status_label.setVisible(True)
                self.cancelRequested.emit()
            return
        super().reject()

    def closeEvent(self, event):
        if self._changing:
            self.reject()
            event.ignore()
            return
        super().closeEvent(event)

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
