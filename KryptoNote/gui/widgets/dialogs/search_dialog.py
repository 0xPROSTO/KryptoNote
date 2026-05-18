from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)

from ...theme import Theme


class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find Node")
        self.setFixedWidth(400)
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setStyleSheet(Theme.Styles.get_search_dialog_qss())

        self.main_window = parent
        self.results = []
        self.current_index = -1
        self.last_query = ""

        layout = QVBoxLayout(self)

        input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search query...")
        self.search_input.returnPressed.connect(self.perform_search)
        input_layout.addWidget(self.search_input)

        btn_search = QPushButton("Find")
        btn_search.clicked.connect(self.perform_search)
        input_layout.addWidget(btn_search)
        layout.addLayout(input_layout)

        nav_layout = QHBoxLayout()
        self.lbl_count = QLabel("0 results")
        nav_layout.addWidget(self.lbl_count)

        nav_layout.addStretch()

        self.btn_prev = QPushButton("< Prev")
        self.btn_prev.clicked.connect(self.prev_result)
        self.btn_prev.setEnabled(False)
        nav_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self.next_result)
        self.btn_next.setEnabled(False)
        nav_layout.addWidget(self.btn_next)

        layout.addLayout(nav_layout)

    def perform_search(self):
        query = self.search_input.text()
        if not query:
            return

        if query == self.last_query and self.results:
            self.next_result()
            return

        self.last_query = query
        if self.main_window and hasattr(self.main_window, "node_model"):
            model = self.main_window.node_model
            matching_ids = model.search_nodes(query)
            self.results = []
            for nid in matching_ids:
                data = model.get_node_data(nid)
                if data:
                    self.results.append(type("R", (), data)())
            self.current_index = 0
            self.update_ui_state()
            self.jump_to_current()

    def next_result(self):
        if not self.results:
            return
        self.current_index = (self.current_index + 1) % len(self.results)
        self.update_ui_state()
        self.jump_to_current()

    def prev_result(self):
        if not self.results:
            return
        self.current_index = (self.current_index - 1) % len(self.results)
        self.update_ui_state()
        self.jump_to_current()

    def update_ui_state(self):
        count = len(self.results)
        self.lbl_count.setText(f"{count} results" if count != 1 else "1 result")
        if count > 0:
            self.lbl_count.setText(f"{self.current_index + 1} / {count}")
            self.btn_next.setEnabled(True)
            self.btn_prev.setEnabled(True)

        else:
            self.btn_next.setEnabled(False)
            self.btn_prev.setEnabled(False)

    def jump_to_current(self):
        if not self.results:
            return
        target = self.results[self.current_index]
        if self.main_window:
            # Use live model data instead of stale DB coordinates
            node_data = self.main_window.node_model.get_node_data(target.id)
            if node_data:
                center_x = node_data["x"] + node_data["width"] / 2
                center_y = node_data["y"] + node_data["height"] / 2
            else:
                center_x = target.x + target.width / 2
                center_y = target.y + target.height / 2

            root_obj = self.main_window.view.rootObject()
            if root_obj:
                root_obj.smoothCenterOn(center_x, center_y)

            self.main_window.node_model.clear_selection()
            self.main_window.node_model.set_selected(target.id, True)
