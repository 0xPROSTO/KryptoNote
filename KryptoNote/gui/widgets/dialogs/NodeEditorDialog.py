from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLineEdit, QLabel


class NoteEditorDialog(QDialog):
    def __init__(self, current_title, current_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Note")
        self.resize(500, 450)

        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLineEdit { background-color: #1e1e1e; color: #ffaa00; border: 1px solid #555; padding: 5px; font-weight: bold; }
            QTextEdit { background-color: #1e1e1e; color: #ffffff; border: 1px solid #555; font-size: 14px; }
            QLabel { color: #aaa; margin-top: 5px; }
        """)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("TITLE:"))
        self.title_edit = QLineEdit(current_title)
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("CONTENT:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(current_text)
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.text_edit.setFocus()

    def get_data(self):
        return self.title_edit.text(), self.text_edit.toPlainText()