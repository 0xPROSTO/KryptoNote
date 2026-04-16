import os

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QInputDialog,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme


class ProjectLauncher(QDialog):
    def __init__(self, base_dir=None):
        super().__init__()
        self.setWindowTitle(Config.APP_NAME)
        self.resize(400, 500)
        self.base_dir = base_dir if base_dir else Config.DB_PATH
        self.selected_file = None
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        Theme.apply_to(self, Theme.Styles.get_launcher_qss)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel("SELECT PROJECT:")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("New project name...")

        btn_create = QPushButton("+ CREATE")
        btn_create.setObjectName("btn_create")
        btn_create.setAutoDefault(False)
        btn_create.clicked.connect(self.create_project)

        self.new_name_input.returnPressed.connect(self.create_project)
        tools_layout.addWidget(self.new_name_input, 1)
        tools_layout.addWidget(btn_create)
        layout.addLayout(tools_layout)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        btn_del = QPushButton("DELETE")
        btn_del.setObjectName("btn_danger")
        btn_del.setAutoDefault(False)
        btn_del.clicked.connect(self.delete_project)

        btn_open = QPushButton("OPEN CASE")
        btn_open.setObjectName("btn_success")
        btn_open.setDefault(True)
        btn_open.setAutoDefault(True)
        btn_open.clicked.connect(self.accept_selection)

        actions_layout.addWidget(btn_del, 1)
        actions_layout.addWidget(btn_open, 2)
        layout.addLayout(actions_layout)

    def refresh_list(self):
        self.list_widget.clear()
        if os.path.exists(self.base_dir):
            files = [f for f in os.listdir(self.base_dir) if f.endswith(".zrx")]
            for f in files:
                self.list_widget.addItem(f)

            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)

    def delete_project(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        filename = item.text()
        text, ok = QInputDialog.getText(
            self,
            "Delete Confirmation",
            f"Type the full filename '{filename}' to confirm deletion:",
        )

        if ok and text == filename:
            full_path = os.path.join(self.base_dir, filename)
            try:
                os.remove(full_path)
                QMessageBox.information(self, "Success", "Project deleted.")
                self.refresh_list()

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

        elif ok:
            QMessageBox.warning(
                self, "Error", "Filename did not match. Deletion cancelled."
            )

    def create_project(self):
        name = self.new_name_input.text().strip()
        if not name:
            return
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
