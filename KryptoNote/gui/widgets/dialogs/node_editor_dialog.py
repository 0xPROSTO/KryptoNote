from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
)

from KryptoNote.gui.theme import Theme


class NoteEditorDialog(QDialog):
    def __init__(self, title, content, parent=None):
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
        layout.addWidget(self.title_edit)
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
        self.save_btn = QPushButton("SAVE CHANGES")
        self.save_btn.setObjectName("btn_apply")
        self.save_btn.setDefault(True)
        self.save_btn.setAutoDefault(True)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.cancel_btn, 1)
        btn_layout.addWidget(self.save_btn, 2)
        layout.addLayout(btn_layout)

    def get_data(self):
        return self.title_edit.text(), self.content_edit.toPlainText()
