import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QBrush, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QGraphicsScene, QLabel,
                             QToolBar, QFileDialog, QInputDialog, QLineEdit, QMessageBox, QApplication)

from .canvas_view import InfiniteCanvasView
from .nodes import ConnectionLine, NodeFactory
from .widgets.dialogs.SearchDialog import SearchDialog
from ..config import Config
from ..core.crypto import CryptoManager
from ..core.database import NodeRepository, DatabaseConnection
from ..utils.media_proc import create_thumbnail


class ZeroXXWindow(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.setWindowTitle(f"{Config.APP_NAME} [{os.path.basename(db_path)}]")
        self.resize(1200, 800)

        self.setStyleSheet(Config.STYLE_MAIN_WINDOW)

        self.link_start_node = None
        self.nodes_map = {}
        self.pending_commits = False

        self._init_core(db_path)
        self._setup_canvas()
        self._setup_toolbar()

        try:
            self.load_from_db()
        except Exception as e:
            print(e)
            QMessageBox.critical(self, "Error", f"Failed to decrypt/load DB.\nError: {e}")

        self.search_dialog = None
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.open_search)

    def _init_core(self, db_path):
        self.db_conn = DatabaseConnection(db_path)
        self.crypto = CryptoManager()
        salt = self.db_conn.get_salt()

        if not salt:
            while True:
                pwd1, ok1 = QInputDialog.getText(self, "Create Password",
                                                 f"Set password for new project:\n{os.path.basename(db_path)}",
                                                 QLineEdit.EchoMode.Password)
                if not ok1 or not pwd1: sys.exit()

                pwd2, ok2 = QInputDialog.getText(self, "Confirm Password",
                                                 "Repeat password:",
                                                 QLineEdit.EchoMode.Password)
                if not ok2: sys.exit()

                if pwd1 == pwd2:
                    salt = os.urandom(16)
                    self.db_conn.set_salt(salt)
                    self.crypto.derive_key(pwd1, salt)
                    break
                else:
                    QMessageBox.warning(self, "Mismatch", "Passwords do not match! Try again.")
        else:
            pwd, ok = QInputDialog.getText(self, "Enter password", f"Password for {os.path.basename(db_path)}:",
                                           QLineEdit.EchoMode.Password)
            if not ok or not pwd:
                sys.exit()
            self.crypto.derive_key(pwd, salt)

        self.repo = NodeRepository(self.db_conn, self.crypto)

    def _setup_canvas(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-25000, -25000, 50000, 50000)
        self.scene.setBackgroundBrush(QBrush(QColor(Config.BACKGROUND_COLOR)))

        self.view = InfiniteCanvasView(self.scene)
        self.view.mouse_moved.connect(self.update_coords)
        self.view.node_clicked_signal.connect(self.handle_link_click)
        self.view.connection_right_clicked_signal.connect(self.quick_delete_connection)

        self.setCentralWidget(self.view)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_toolbar(self):
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        actions = [
            ("Add Note", self.add_text_node),
            ("Add Image", lambda: self.add_media_node("image")),
            ("Add Video", lambda: self.add_media_node("video")),
            ("Search", self.open_search),
        ]

        for name, slot in actions:
            act = QAction(name, self)
            act.triggered.connect(slot)
            toolbar.addAction(act)

        toolbar.addSeparator()

        self.status_label = QLabel("Hold [SHIFT] to Link Nodes")
        self.status_label.setStyleSheet("padding-left: 10px;")
        self.coords_label = QLabel("X: 0 Y: 0")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.coords_label)

    def open_search(self):
        query, ok = QInputDialog.getText(self, "Search", "Find node:")
        if ok and query:
            results = self.repo.search_items(query)
            if results:
                target = results[0]
                self.view.centerOn(target['x'], target['y'])
                if target['id'] in self.nodes_map:
                    self.nodes_map[target['id']].setSelected(True)
            else:
                QMessageBox.information(self, "Info", "Nothing found.")

    def update_coords(self, pos):
        self.coords_label.setText(f"X: {int(pos.x())} Y: {int(pos.y())}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.status_label.setText("LINK MODE ACTIVE: Select start node...")
            self.status_label.setStyleSheet(
                f"color: {Config.COLOR_SECURE_LABEL}; font-weight: bold; padding-left: 10px;")
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            if self.link_start_node:
                self.link_start_node.setSelected(False)
                self.link_start_node = None

            if self.pending_commits:
                self.status_label.setText("Saving changes to database...")
                self.status_label.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; padding-left: 10px;")

                QApplication.processEvents()

                self.repo.commit_changes()
                self.pending_commits = False
                print("Bulk connection insert committed.")

            self.status_label.setText("Hold [SHIFT] to Link Nodes")
            self.status_label.setStyleSheet("color: #777; padding-left: 10px;")

        super().keyReleaseEvent(event)

    def handle_link_click(self, node):
        if self.link_start_node is None:
            self.link_start_node = node
            node.setSelected(True)
            self.status_label.setText(f"LINKING: Chain started. Click next...")
        else:
            if self.link_start_node != node:
                created = self.create_connection(self.link_start_node, node)
                if created:
                    self.status_label.setText(f"LINKED! Chain moves to new node.")
                    self.link_start_node.setSelected(False)
                    self.link_start_node = node
                    self.link_start_node.setSelected(True)

    def quick_delete_connection(self, connection_item):
        connection_item.delete_connection()
        self.status_label.setText("Link deleted.")

    def create_connection(self, node_a, node_b):
        existing_conns = [c for c in node_a.connections if c.end_node == node_b or c.start_node == node_b]
        if existing_conns: return False

        conn_id = self.repo.add_connection(node_a.item_id, node_b.item_id, commit=False)
        self.pending_commits = True

        line = ConnectionLine(conn_id, node_a, node_b, self.repo)
        self.scene.addItem(line)
        node_a.add_connection(line)
        node_b.add_connection(line)
        return True

    def load_from_db(self):
        items = self.repo.get_all_items()
        for item_data in items:
            try:
                node = NodeFactory.create_node_from_db(item_data, self.repo)
                self.scene.addItem(node)
                self.nodes_map[item_data['id']] = node
            except Exception as e:
                print(f"Skipping broken node {item_data.get('id')}: {e}")

        conns = self.repo.get_all_connections()
        for c in conns:
            n1 = self.nodes_map.get(c['start_id'])
            n2 = self.nodes_map.get(c['end_id'])
            if n1 and n2:
                line = ConnectionLine(c['id'], n1, n2, self.repo)
                self.scene.addItem(line)
                n1.add_connection(line)
                n2.add_connection(line)

    def get_center_pos(self):
        return self.view.mapToScene(self.view.viewport().rect().center())

    def add_text_node(self):
        title, ok = QInputDialog.getText(self, "New Note", "Title:")
        if ok:
            title = title.strip() or "Untitled"

            pos = self.get_center_pos()
            node = NodeFactory.create_new_text(self.repo, pos.x(), pos.y(), title)

            self.scene.addItem(node)
            self.nodes_map[node.item_id] = node
            node.mouseDoubleClickEvent(None)

    def add_media_node(self, mtype):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media")
        if path:
            pos = self.get_center_pos()
            thumb_bytes = create_thumbnail(path)
            title = os.path.basename(path)

            full_data = None
            if mtype != "video":
                with open(path, "rb") as f:
                    full_data = f.read()

            if mtype == "video":
                self.status_label.setText("Encrypting video...")
                QApplication.processEvents()

            node = NodeFactory.create_new_media(
                self.repo, pos.x(), pos.y(), mtype, title, thumb_bytes,
                full_data=full_data, file_path=path
            )

            self.status_label.setText("")
            self.scene.addItem(node)
            self.nodes_map[node.item_id] = node

    def open_search(self):
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self)

        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
        self.search_dialog.search_input.setFocus()
        self.search_dialog.search_input.selectAll()
