from PySide6.QtCore import Qt, Signal, QPoint, QSequentialAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.widgets.overlays.dim_overlay import DimOverlay


class LauncherOverlay(DimOverlay):
    """Modal overlay displayed on top of the launcher.

    Supports four modes: 'create', 'confirm', 'enter', 'delete'.
    Emits inputSubmitted(text, ok) when user submits or cancels.
    """

    inputSubmitted = Signal(str, bool)

    MIN_INPUT_LEN = 1
    MAX_INPUT_LEN = 512

    _CARD_QSS = f"""
        QFrame#overlay_card {{
            background-color: {Palette.BG_PANEL};
            border: 1px solid {Palette.BORDER_DEFAULT};
            border-radius: 8px;
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel#overlay_title {{
            color: {Palette.TEXT_MAIN};
            font-size: 15px;
            font-weight: bold;
            font-family: 'Segoe UI Semibold';
            margin-top: 5px;
        }}
        QLabel#overlay_subtitle {{
            color: {Palette.TEXT_DIM};
            font-size: 12px;
            margin-bottom: 8px;
        }}
        QLabel#overlay_error {{
            color: {Palette.DANGER_HOVER};
            font-size: 12px;
            font-weight: bold;
            margin-top: 4px;
        }}
        QLabel#overlay_error_delete {{
            color: {Palette.DANGER_HOVER};
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        QLineEdit {{
            background-color: {Palette.BG_INPUT};
            color: {Palette.TEXT_MAIN};
            border: 1px solid {Palette.BORDER_DEFAULT};
            border-radius: 4px;
            padding: 8px 10px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {Palette.ACCENT_MAIN};
            outline: none;
        }}
        QPushButton {{
            padding: 8px 15px;
            font-size: 12px;
            font-weight: bold;
            border-radius: 4px;
            border: 1px solid {Palette.BORDER_DEFAULT};
        }}
        QPushButton#btn_submit {{
            background-color: {Palette.BTN_APPLY};
            border-color: {Palette.BTN_APPLY_BORDER};
            color: {Palette.BTN_APPLY_TEXT};
        }}
        QPushButton#btn_submit:hover {{
            background-color: {Palette.BTN_APPLY_HOVER};
            border-color: {Palette.SUCCESS_HOVER};
        }}
        QPushButton#btn_submit:disabled {{
            background-color: {Palette.BG_NODE};
            color: {Palette.TEXT_MUTED};
            border-color: {Palette.BORDER_DEFAULT};
        }}
        QPushButton#btn_danger {{
            background-color: {Palette.BTN_CANCEL};
            border-color: {Palette.BTN_CANCEL_BORDER};
            color: {Palette.DANGER_HOVER};
        }}
        QPushButton#btn_danger:hover {{
            background-color: {Palette.BTN_CANCEL_HOVER};
            border-color: {Palette.DANGER_HOVER};
        }}
        QPushButton#btn_cancel {{
            background-color: {Palette.BTN_CANCEL};
            border-color: {Palette.BTN_CANCEL_BORDER};
            color: {Palette.BTN_CANCEL_TEXT};
        }}
        QPushButton#btn_cancel:hover {{
            background-color: {Palette.BTN_CANCEL_HOVER};
            border-color: {Palette.DANGER_HOVER};
        }}
    """

    def __init__(self, parent=None, auto_show=False):
        super().__init__(parent, block_input=True, auto_show=auto_show)
        self._mode = "enter"
        self._db_name = ""
        self._shake_anim = None

        self.setObjectName("launcher_overlay_root")
        self.setStyleSheet("""
            LauncherOverlay#launcher_overlay_root {
                background-color: rgba(0, 0, 0, 200);
            }
        """)

        # ── Card ──
        card = QFrame(self)
        card.setObjectName("overlay_card")
        card.setFixedWidth(360)
        card.setStyleSheet(self._CARD_QSS)
        self._card = card

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self._title_label = QLabel()
        self._title_label.setObjectName("overlay_title")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel()
        self._subtitle_label.setObjectName("overlay_subtitle")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle_label)

        self._delete_warn_label = QLabel()
        self._delete_warn_label.setObjectName("overlay_error_delete")
        self._delete_warn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._delete_warn_label.setVisible(False)
        layout.addWidget(self._delete_warn_label)

        # Input
        self._input_edit = QLineEdit()
        self._input_edit.setMaxLength(self.MAX_INPUT_LEN)
        self._input_edit.returnPressed.connect(self._on_submit)
        self._input_edit.textChanged.connect(self._validate)
        layout.addWidget(self._input_edit)

        # Error label (hidden by default)
        self._error_label = QLabel("")
        self._error_label.setObjectName("overlay_error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Spacing before buttons
        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setObjectName("btn_cancel")
        self._btn_cancel.setMinimumHeight(36)
        self._btn_cancel.clicked.connect(self._on_cancel)

        self._btn_submit = QPushButton("Confirm")
        self._btn_submit.setObjectName("btn_submit")
        self._btn_submit.setMinimumHeight(36)
        self._btn_submit.clicked.connect(self._on_submit)

        btn_layout.addWidget(self._btn_cancel, 1)
        btn_layout.addWidget(self._btn_submit, 2)
        layout.addLayout(btn_layout)

    def show_message(self, title, message):
        self._mode = "message"
        self._title_label.setText(title)
        self._subtitle_label.setText(message)
        self._subtitle_label.setWordWrap(True)
        self._delete_warn_label.setVisible(False)
        self._input_edit.setVisible(False)
        self._error_label.setVisible(False)
        self._btn_cancel.setVisible(False)
        self._btn_submit.setVisible(False)
        self._card.adjustSize()

        self.show()
        self.raise_()
        self._center_card()
        self.fade_in()

    def show_overlay(self, mode, db_name):
        self._mode = mode
        self._db_name = db_name
        self._delete_warn_label.setVisible(False)
        self._input_edit.setVisible(True)
        self._btn_cancel.setVisible(True)
        self._btn_submit.setVisible(True)
        self._subtitle_label.setWordWrap(False)

        if mode == "create":
            self._title_label.setText("Create Password")
            self._subtitle_label.setText(f"Set a password for '{db_name}'")
            self._input_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._input_edit.setPlaceholderText("Password...")
            self._btn_submit.setObjectName("btn_submit")
            self._btn_submit.setText("Confirm")
        elif mode == "confirm":
            self._title_label.setText("Confirm Password")
            self._subtitle_label.setText(f"Re-enter password for '{db_name}'")
            self._input_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._input_edit.setPlaceholderText("Password...")
            self._btn_submit.setObjectName("btn_submit")
            self._btn_submit.setText("Confirm")
        elif mode == "delete":
            self._title_label.setText("Delete Project")
            self._subtitle_label.setText(f"Type '{db_name}' to confirm deletion.")
            self._delete_warn_label.setText("This action cannot be undone!")
            self._delete_warn_label.setVisible(True)
            self._input_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._input_edit.setPlaceholderText("Project name...")
            self._btn_submit.setObjectName("btn_danger")
            self._btn_submit.setText("Delete")
        else:
            self._title_label.setText("Enter Password")
            self._subtitle_label.setText(f"Unlock '{db_name}'")
            self._input_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._input_edit.setPlaceholderText("Password...")
            self._btn_submit.setObjectName("btn_submit")
            self._btn_submit.setText("Confirm")

        self._card.setStyleSheet(self._CARD_QSS)  # Re-apply for btn_danger vs btn_submit changes
        self._input_edit.clear()
        self._error_label.setVisible(False)
        self._validate()

        self.show()
        self.raise_()
        self._center_card()
        self.fade_in()
        self._input_edit.setFocus()

    def _validate(self):
        text = self._input_edit.text()
        valid = self.MIN_INPUT_LEN <= len(text) <= self.MAX_INPUT_LEN

        if self._mode == "delete":
            # For delete mode, require exact match to enable the button
            valid = (text == self._db_name)

        self._btn_submit.setEnabled(valid)

    def show_error(self, message):
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._card.adjustSize()
        self._center_card()
        self._shake_card()
        self._input_edit.setStyleSheet(
            f"border: 1px solid {Palette.DANGER_HOVER}; "
            f"background-color: {Palette.BG_INPUT}; "
            f"color: {Palette.TEXT_MAIN}; "
            f"border-radius: 4px; padding: 8px 10px; font-size: 13px;"
        )
        self._input_edit.selectAll()
        self._input_edit.setFocus()

    def _shake_card(self):
        if self._shake_anim is not None:
            self._shake_anim.stop()
        anim = QSequentialAnimationGroup(self)
        base_pos = self._card.pos()
        offsets = [10, -10, 6, -6, 3, -3, 0]
        for offset in offsets:
            step = QPropertyAnimation(self._card, b"pos")
            step.setDuration(40)
            step.setEndValue(QPoint(base_pos.x() + offset, base_pos.y()))
            anim.addAnimation(step)
        self._shake_anim = anim
        anim.start()

    def _on_submit(self):
        if not self._btn_submit.isEnabled():
            return
        text = self._input_edit.text()
        if len(text) < self.MIN_INPUT_LEN or len(text) > self.MAX_INPUT_LEN:
            return
        self._error_label.setVisible(False)
        self._input_edit.setStyleSheet("")
        self.inputSubmitted.emit(text, True)

    def _on_cancel(self):
        self.inputSubmitted.emit("", False)

    def _center_card(self):
        if not hasattr(self, '_card'):
            return
        px = (self.width() - self._card.width()) // 2
        py = (self.height() - self._card.height()) // 2
        self._card.move(px, py)

    def fade_out(self, delete_on_finish=False):
        super().fade_out(delete_on_finish=delete_on_finish)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_card()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
        else:
            super().keyPressEvent(event)
