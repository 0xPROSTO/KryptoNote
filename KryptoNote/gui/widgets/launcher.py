import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QPushButton,
                             QLineEdit, QLabel, QHBoxLayout, QMessageBox, QWidget, QInputDialog)
from KryptoNote.config import Config


class ProjectLauncher(QDialog):
    def __init__(self, base_dir=None):
        super().__init__()
        self.setWindowTitle(Config.APP_NAME)
        self.resize(450, 550)
        self.base_dir = base_dir if base_dir else Config.DB_PATH
        self.selected_file = None

        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        self.setStyleSheet(Config.STYLE_LAUNCHER)

        layout = QVBoxLayout(self)

        lbl = QLabel("SELECT PROJECT:")
        lbl.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 5px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)

        btn_del = QPushButton("Delete Selected Project")
        btn_del.setStyleSheet("background-color: #550000; color: #ffaaaa; margin: 5px 0;")
        btn_del.setAutoDefault(False)
        btn_del.clicked.connect(self.delete_project)
        layout.addWidget(btn_del)

        input_layout = QHBoxLayout()
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("New case name...")

        btn_create = QPushButton("+ Create")
        btn_create.setAutoDefault(False)
        btn_create.clicked.connect(self.create_project)

        self.new_name_input.returnPressed.connect(self.create_project)

        input_layout.addWidget(self.new_name_input)
        input_layout.addWidget(btn_create)
        layout.addLayout(input_layout)

        btn_open = QPushButton("Open Selected Case")
        btn_open.setStyleSheet("background-color: #005500; font-weight: bold; margin-top: 10px;")
        btn_open.setDefault(True)
        btn_open.setAutoDefault(True)
        btn_open.clicked.connect(self.accept_selection)
        layout.addWidget(btn_open)

    def refresh_list(self):
        self.list_widget.clear()
        if os.path.exists(self.base_dir):
            files = [f for f in os.listdir(self.base_dir) if f.endswith('.zrx')]
            for f in files:
                self.list_widget.addItem(f)

    def delete_project(self):
        item = self.list_widget.currentItem()
        if not item: return

        filename = item.text()
        text, ok = QInputDialog.getText(self, "Delete Confirmation",
                                        f"Type the full filename '{filename}' to confirm deletion:")

        if ok and text == filename:
            full_path = os.path.join(self.base_dir, filename)
            try:
                os.remove(full_path)
                QMessageBox.information(self, "Success", "Project deleted.")
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
        elif ok:
            QMessageBox.warning(self, "Error", "Filename did not match. Deletion cancelled.")

    def create_project(self):
        name = self.new_name_input.text().strip()
        if not name: return
        if not name.endswith(".zrx"):
            name += ".zrx"

        full_path = os.path.join(self.base_dir, name)
        if os.path.exists(full_path):
            QMessageBox.warning(self, "Error", "Project already exists!")
            return

        self.selected_file = full_path
        self.accept()

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_file = os.path.join(self.base_dir, current_item.text())
            self.accept()
        elif self.new_name_input.text():
            self.create_project()