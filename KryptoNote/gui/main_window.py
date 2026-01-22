import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QGraphicsView, QGraphicsScene, QLabel,
                             QToolBar, QFileDialog, QInputDialog, QLineEdit, QMessageBox)
from PyQt6.QtGui import QAction, QColor, QBrush
from PyQt6.QtCore import Qt

from ..core.crypto import CryptoManager
from ..core.storage import Storage
from ..utils.media_proc import create_thumbnail

from .nodes import TextNode, MediaNode
from .nodes.ConnectionLine import ConnectionLine
from .canvas_view import InfiniteCanvasView


class ZeroXXWindow(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.setWindowTitle(f"ZeroXX-KryptoNote [{os.path.basename(db_path)}]")
        self.resize(1200, 800)

        self.is_linking = False
        self.link_start_node = None
        self.nodes_map = {}

        self._init_core(db_path)
        self._setup_canvas()
        self._setup_toolbar()

        try:
            self.load_from_db()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to decrypt/load DB.\nError: {e}")
            sys.exit()

    def _init_core(self, db_path):
        self.storage = Storage(db_path, None)
        salt = self.storage.get_salt()

        pwd, ok = QInputDialog.getText(self, "Login", f"Password for {os.path.basename(db_path)}:",
                                       QLineEdit.EchoMode.Password)
        if not ok or not pwd:
            sys.exit()

        self.crypto = CryptoManager()

        if not salt:
            salt = os.urandom(16)
            self.storage.set_salt(salt)
            print("New DB initialized. Salt generated.")

        self.crypto.derive_key(pwd, salt)
        self.storage = Storage(db_path, self.crypto)

    def _setup_canvas(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.scene.setBackgroundBrush(QBrush(QColor("#121212")))

        self.scene.selectionChanged.connect(self.handle_selection_change)

        self.view = InfiniteCanvasView(self.scene)
        self.setCentralWidget(self.view)

    def _setup_toolbar(self):
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.setStyleSheet("""
            QToolBar { background: #1e1e1e; border-bottom: 1px solid #333; }
            QToolButton { color: #ddd; padding: 5px; }
            QToolButton:hover { background: #333; }
            QToolButton:checked { background: #440000; border: 1px solid red; }
        """)

        btn_text = QAction("Add Text", self)
        btn_text.triggered.connect(self.add_text_node)
        toolbar.addAction(btn_text)

        btn_img = QAction("Add Image", self)
        btn_img.triggered.connect(lambda *args: self.add_media_node("image"))
        toolbar.addAction(btn_img)

        btn_vid = QAction("Add Video", self)
        btn_vid.triggered.connect(lambda *args: self.add_media_node("video"))
        toolbar.addAction(btn_vid)

        toolbar.addSeparator()

        self.btn_link = QAction("🔗 Link Mode", self)
        self.btn_link.setCheckable(True)
        self.btn_link.triggered.connect(self.toggle_link_mode)
        toolbar.addAction(self.btn_link)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #777; padding-left: 10px;")
        self.statusBar().addWidget(self.status_label)

    def toggle_link_mode(self):
        self.is_linking = self.btn_link.isChecked()
        self.link_start_node = None

        if self.is_linking:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.status_label.setText("LINK MODE: Select FIRST node")
        else:
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.status_label.setText("Ready")

    def handle_selection_change(self):
        if not self.is_linking: return

        selected = self.scene.selectedItems()
        if not selected: return

        item = selected[0]
        if not hasattr(item, 'item_id'): return

        if self.link_start_node is None:
            self.link_start_node = item
            self.status_label.setText(f"LINK MODE: First selected. Now select SECOND node.")
            item.setSelected(False)
        else:
            node_a = self.link_start_node
            node_b = item

            if node_a == node_b: return

            self.create_connection(node_a, node_b)

            self.link_start_node = None
            self.status_label.setText("LINK MODE: Link created! Select next FIRST node or Disable Link Mode.")
            node_b.setSelected(False)

    def create_connection(self, node_a, node_b):
        conn_id = self.storage.add_connection(node_a.item_id, node_b.item_id)
        line = ConnectionLine(conn_id, node_a, node_b, self.storage)
        self.scene.addItem(line)
        node_a.add_connection(line)
        node_b.add_connection(line)

    def load_from_db(self):
        items = self.storage.get_all_items()
        for item in items:
            w, h = item['w'], item['h']

            if item['type'] == 'text':
                node = TextNode(item['id'], item['x'], item['y'], w, h, item['text'], self.storage)
            elif item['type'] in ['image', 'video']:
                node = MediaNode(item['id'], item['x'], item['y'], w, h, item['thumbnail'],
                                 self.storage, item['type'])

            self.scene.addItem(node)
            self.nodes_map[item['id']] = node

        conns = self.storage.get_all_connections()
        for c in conns:
            start_node = self.nodes_map.get(c['start_id'])
            end_node = self.nodes_map.get(c['end_id'])

            if start_node and end_node:
                line = ConnectionLine(c['id'], start_node, end_node, self.storage)
                self.scene.addItem(line)
                start_node.add_connection(line)
                end_node.add_connection(line)

    def get_center_pos(self):
        return self.view.mapToScene(self.view.viewport().rect().center())

    def add_text_node(self):
        pos = self.get_center_pos()
        text, ok = QInputDialog.getText(self, "New Note", "Текст заметки:")
        if ok and text:
            rid = self.storage.add_item("text", pos.x(), pos.y(), 200, 150, text=text)
            node = TextNode(rid, pos.x(), pos.y(), 200, 150, text, self.storage)
            self.scene.addItem(node)
            self.nodes_map[rid] = node

    def add_media_node(self, mtype):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media")
        if path:
            pos = self.get_center_pos()
            thumb_bytes = create_thumbnail(path)
            with open(path, "rb") as f: full_data = f.read()

            rid = self.storage.add_item(mtype, pos.x(), pos.y(), 220, 220,
                                        thumb=thumb_bytes, data=full_data)
            node = MediaNode(rid, pos.x(), pos.y(), 220, 220, thumb_bytes, self.storage, mtype)
            self.scene.addItem(node)
            self.nodes_map[rid] = node