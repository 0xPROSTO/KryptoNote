from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
    QComboBox,
    QLabel,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.animated_button import AnimatedButton


class NoteEditorDialog(QDialog):
    def __init__(self, title, content, title_size=14, text_size=10, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Note")
        self.resize(500, 480)
        Theme.apply_to(self, Theme.Styles.get_node_editor_qss)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        self.title_edit = QLineEdit(title)
        self.title_edit.setObjectName("title_edit")
        self.title_edit.setPlaceholderText("Title...")

        size_layout = QHBoxLayout()
        size_layout.setSpacing(10)

        self.title_size_combo = QComboBox()
        self.title_size_combo.setObjectName("font_combo")
        sizes = [str(s) for s in [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 64]]
        self.title_size_combo.addItems(sizes)
        self.title_size_combo.setCurrentText(str(title_size))

        self.text_size_combo = QComboBox()
        self.text_size_combo.setObjectName("font_combo")
        self.text_size_combo.addItems(sizes)
        self.text_size_combo.setCurrentText(str(text_size))

        size_layout.addWidget(QLabel("Title Size:"))
        size_layout.addWidget(self.title_size_combo)
        size_layout.addStretch()
        size_layout.addWidget(QLabel("Text Size:"))
        size_layout.addWidget(self.text_size_combo)

        layout.addWidget(self.title_edit)
        layout.addLayout(size_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setObjectName("separator")
        layout.addWidget(line)
        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(content)
        self.content_edit.setPlaceholderText("Start typing your note here...")
        layout.addWidget(self.content_edit)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self.cancel_btn = QPushButton("CANCEL")
        self.cancel_btn.setObjectName("btn_cancel")
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = AnimatedButton("SAVE CHANGES")
        self.save_btn.setObjectName("btn_apply")
        self.save_btn.setDefault(True)
        self.save_btn.setAutoDefault(True)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.cancel_btn, 1)
        btn_layout.addWidget(self.save_btn, 2)
        layout.addLayout(btn_layout)

        self.title_edit.textChanged.connect(self._validate_inputs)
        self.content_edit.textChanged.connect(self._validate_inputs)
        self._validate_inputs()

    def _validate_inputs(self):
        has_content = bool(self.title_edit.text().strip() or self.content_edit.toPlainText().strip())
        self.save_btn.setEnabled(has_content)

    def accept(self):
        super().accept()

    def get_data(self):
        return (
            self.title_edit.text(),
            self.content_edit.toPlainText(),
            int(self.title_size_combo.currentText()),
            int(self.text_size_combo.currentText())
        )
