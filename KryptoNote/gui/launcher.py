import os
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QPushButton,
                             QLineEdit, QLabel, QHBoxLayout, QMessageBox, QWidget)
from PyQt6.QtCore import Qt


class ProjectLauncher(QDialog):
    def __init__(self, base_dir="cases"):
        super().__init__()
        self.setWindowTitle("ZeroXX Case Manager")
        self.resize(400, 500)
        self.base_dir = base_dir
        self.selected_file = None

        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: white; }
            QListWidget { background-color: #252525; color: #ddd; border: 1px solid #333; font-size: 14px; }
            QListWidget::item { padding: 5px; }
            QListWidget::item:selected { background-color: #3d3d3d; }
            QLineEdit { background-color: #252525; color: white; border: 1px solid #333; padding: 5px; }
            QPushButton { background-color: #333; color: white; border: none; padding: 8px; }
            QPushButton:hover { background-color: #444; }
            QLabel { color: #aaa; }
        """)

        layout = QVBoxLayout(self)

        lbl = QLabel("SELECT PROJECT:")
        lbl.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 5px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)

        input_layout = QHBoxLayout()
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("New case name...")
        btn_create = QPushButton("+ Create")
        btn_create.clicked.connect(self.create_project)

        input_layout.addWidget(self.new_name_input)
        input_layout.addWidget(btn_create)
        layout.addLayout(input_layout)

        btn_open = QPushButton("Open Selected Case")
        btn_open.setStyleSheet("background-color: #005500; font-weight: bold; margin-top: 10px;")
        btn_open.clicked.connect(self.accept_selection)
        layout.addWidget(btn_open)

    def refresh_list(self):
        self.list_widget.clear()
        files = [f for f in os.listdir(self.base_dir) if f.endswith('.zrx')]
        for f in files:
            self.list_widget.addItem(f)

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