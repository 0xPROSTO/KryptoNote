import datetime
import os
import sqlite3
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QBrush, QShortcut, QKeySequence, QGuiApplication
from PySide6.QtWidgets import (QMainWindow, QGraphicsScene, QLabel, QWidget, QVBoxLayout,
                               QFileDialog, QInputDialog, QLineEdit, QMessageBox, QApplication)

from .canvas_view import InfiniteCanvasView
from .native_window import NativeWindowMixin
from .nodes import ConnectionLine, NodeFactory
from .widgets.dialogs.SearchDialog import SearchDialog
from .widgets.title_bar import CustomTitleBar
from ..config import Config
from ..core.crypto import CryptoManager
from ..core.database import NodeRepository, DatabaseConnection
from ..utils.media_proc import create_thumbnail


class ZeroXXWindow(NativeWindowMixin, QMainWindow):

    def __init__(self, db_path):
        QMainWindow.__init__(self)
        self.is_windows = sys.platform == "win32"

        self.resize(1280, 800)
        self.setMinimumSize(600, 450)

        if self.is_windows:
            self.title_bar = CustomTitleBar(self)
            self.title_bar.set_title(f"{Config.APP_NAME} [{os.path.basename(db_path)}]")
            self.init_native_window()
        else:
            self.setWindowTitle(f"{Config.APP_NAME} [{os.path.basename(db_path)}]")
            self.title_bar = None

        self._adjust_initial_window_size()

        self.setStyleSheet(Config.STYLE_MAIN_WINDOW)

        self.link_start_node = None
        self.nodes_map = {}
        self.pending_commits = False

        self.default_status = "Ready | Hold [SHIFT] to Link | Hold [CTRL] to Multi-Select"

        self._init_core(db_path)
        self._setup_canvas()
        self._setup_menubar()

        try:
            self.load_from_db()
        except Exception as e:
            print(e)
            QMessageBox.critical(self, "Error", f"Failed to decrypt/load DB. Incorrect password?\nError: {e}")
            self.db_conn.conn.close()
            raise RuntimeError("Failed to load DB")

        self.search_dialog = None
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.open_search)

        self.snap_shortcut = QShortcut(QKeySequence("G"), self)
        self.snap_shortcut.activated.connect(self.toggle_snap_to_grid)

    def _adjust_initial_window_size(self):
        screen = QGuiApplication.primaryScreen()
        if not screen: return

        available = screen.availableGeometry()
        target_w = 1440
        target_h = 900

        if target_w > available.width() * 0.9:
            target_w = available.width() * 0.9
        if target_h > available.height() * 0.9:
            target_h = available.height() * 0.9

        x = available.x() + (available.width() - target_w) // 2
        y = available.y() + (available.height() - target_h) // 2

        self.setGeometry(int(x), int(y), int(target_w), int(target_h))

    def _init_core(self, db_path):
        self.db_conn = DatabaseConnection(db_path)
        self.crypto = CryptoManager()
        salt = self.db_conn.get_salt()

        if not salt:
            while True:
                pwd1, ok1 = self._get_centered_input("Create Password",
                                                     f"Set password for new project:\n{os.path.basename(db_path)}",
                                                     QLineEdit.EchoMode.Password)
                if not ok1 or not pwd1: raise RuntimeError("Password entry cancelled")

                pwd2, ok2 = self._get_centered_input("Confirm Password",
                                                     "Repeat password:",
                                                     QLineEdit.EchoMode.Password)
                if not ok2: raise RuntimeError("Password entry cancelled")

                if pwd1 == pwd2:
                    salt = os.urandom(16)
                    self.db_conn.set_salt(salt)
                    self.crypto.derive_key(pwd1, salt)

                    check_bytes = self.crypto.encrypt(b"KryptoNote_Auth_OK")
                    self.db_conn.set_auth_check(check_bytes)
                    break
                else:
                    QMessageBox.warning(self, "Mismatch", "Passwords do not match! Try again.")
        else:
            pwd, ok = self._get_centered_input("Enter password", f"Password for {os.path.basename(db_path)}:",
                                               QLineEdit.EchoMode.Password)
            if not ok or not pwd:
                raise RuntimeError("Password entry cancelled")

            self.crypto.derive_key(pwd, salt)

            auth_check = self.db_conn.get_auth_check()
            if auth_check:
                try:
                    dec = self.crypto.decrypt(auth_check)
                    if dec != b"KryptoNote_Auth_OK":
                        raise Exception("Verification failed")
                except Exception:
                    QMessageBox.critical(self, "Error", "Incorrect password!")
                    self.db_conn.conn.close()
                    raise RuntimeError("Incorrect password")

        self.repo = NodeRepository(self.db_conn, self.crypto)

    def _setup_canvas(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-25000, -25000, 50000, 50000)
        self.scene.setBackgroundBrush(QBrush(QColor(Config.BACKGROUND_COLOR)))

        self.view = InfiniteCanvasView(self.scene)
        self.view.mouse_moved.connect(self.update_coords)
        self.view.node_clicked_signal.connect(self.handle_link_click)
        self.view.connection_right_clicked_signal.connect(self.quick_delete_connection)

        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        if getattr(self, 'title_bar', None):
            vbox.addWidget(self.title_bar)

        vbox.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_menubar(self):
        if getattr(self, 'title_bar', None):
            menubar = self.title_bar.menu_bar
        else:
            menubar = self.menuBar()
            menubar.setStyleSheet("""
                QMenuBar { background-color: #1e1e1e; color: #dddddd; border-bottom: 1px solid #333; }
                QMenuBar::item { background-color: transparent; padding: 4px 10px; margin: 2px; }
                QMenuBar::item:selected { background-color: #3a3a3a; border-radius: 4px; }
                QMenu { background-color: #2b2b2b; color: #dddddd; border: 1px solid #444; }
                QMenu::item { padding: 6px 30px 6px 20px; }
                QMenu::item:selected { background-color: #444444; }
            """)

        file_menu = menubar.addMenu("File")

        act_close = QAction("Close", self)
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        act_backup = QAction("Backup", self)
        act_backup.triggered.connect(self.create_backup)
        file_menu.addAction(act_backup)

        add_menu = menubar.addMenu("Add")

        act_note = QAction("Note\t[Ctrl+N]", self)
        act_note.setShortcut(QKeySequence("Ctrl+N"))
        act_note.triggered.connect(self.add_text_node)
        add_menu.addAction(act_note)

        act_img = QAction("Image\t[Ctrl+M]", self)
        act_img.setShortcut(QKeySequence("Ctrl+M"))
        act_img.triggered.connect(lambda: self.add_media_node("image"))
        add_menu.addAction(act_img)

        act_vid = QAction("Video\t[Ctrl+Shift+M]", self)
        act_vid.setShortcut(QKeySequence("Ctrl+Shift+M"))
        act_vid.triggered.connect(lambda: self.add_media_node("video"))
        add_menu.addAction(act_vid)

        tools_menu = menubar.addMenu("Tools")

        act_search = QAction("Search\t[Ctrl+F]", self)
        act_search.triggered.connect(self.open_search)
        tools_menu.addAction(act_search)

        snap_state = "ON" if getattr(Config, 'SNAP_TO_GRID', False) else "OFF"
        self.act_snap = QAction(f"Snap to Grid: {snap_state}\t[G]", self)
        self.act_snap.triggered.connect(self.toggle_snap_to_grid)
        tools_menu.addAction(self.act_snap)

        self.status_label = QLabel(self.default_status)
        self.status_label.setStyleSheet("padding-left: 10px; color: #999;")
        self.coords_label = QLabel("X: 0 Y: 0")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.coords_label)

    def toggle_snap_to_grid(self):
        Config.SNAP_TO_GRID = not getattr(Config, 'SNAP_TO_GRID', False)
        self.act_snap.setText("Snap to Grid: ON\t[G]" if Config.SNAP_TO_GRID else "Snap to Grid: OFF\t[G]")
        msg = "Snap to grid enabled." if Config.SNAP_TO_GRID else "Snap to grid disabled."
        self.status_label.setText(msg)
        self.view._update_overlay()

    def create_backup(self):
        db_path = self.db_conn.db_path
        base_name = os.path.basename(db_path)
        name, ext = os.path.splitext(base_name)

        backup_dir = os.path.join(os.path.dirname(db_path), "backup")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{name}_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_name)

        self.repo.commit_changes()

        try:
            backup_conn = sqlite3.connect(backup_path)
            self.db_conn.conn.backup(backup_conn)
            backup_conn.close()
            QMessageBox.information(self, "Backup", f"Backup created successfully:\n{backup_path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to create backup:\n{e}")

    def open_search(self):
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self)

        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
        self.search_dialog.search_input.setFocus()
        self.search_dialog.search_input.selectAll()

    def update_coords(self, pos):
        self.coords_label.setText(f"X: {int(pos.x())} Y: {int(pos.y())}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.status_label.setText("LINK MODE ACTIVE: Select start node to link...")
            self.status_label.setStyleSheet(
                f"color: {Config.COLOR_SECURE_LABEL}; font-weight: bold; padding-left: 10px;")
        elif event.key() == Qt.Key.Key_Control:
            self.status_label.setText("SELECTION ACTIVE: Drag mouse to select multiple objects.")
            self.status_label.setStyleSheet(f"color: {Config.COLOR_ACCENT}; font-weight: bold; padding-left: 10px;")

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

            self.status_label.setText(self.default_status)
            self.status_label.setStyleSheet("color: #999; padding-left: 10px;")

        elif event.key() == Qt.Key.Key_Control:
            self.status_label.setText(self.default_status)
            self.status_label.setStyleSheet("color: #999; padding-left: 10px;")

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
        title = "New Note"
        pos = self.get_center_pos()
        node = NodeFactory.create_new_text(self.repo, pos.x(), pos.y(), title)

        self.scene.addItem(node)
        self.nodes_map[node.item_id] = node
        node.mouseDoubleClickEvent(None)

    def add_media_node(self, mtype):
        if mtype == "image":
            file_filter = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        elif mtype == "video":
            file_filter = "Videos (*.mp4 *.avi *.mkv *.mov *.webm)"
        else:
            file_filter = "All Files (*)"

        paths, _ = QFileDialog.getOpenFileNames(self, f"Select {mtype.capitalize()}s", "", file_filter)
        if not paths: return

        valid_img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        valid_vid_exts = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

        for i, path in enumerate(paths):
            ext = os.path.splitext(path)[1].lower()

            if mtype == "image" and ext not in valid_img_exts:
                QMessageBox.critical(self, "Invalid File",
                                     f"The file '{os.path.basename(path)}' is not a valid image format.")
                continue
            elif mtype == "video" and ext not in valid_vid_exts:
                QMessageBox.critical(self, "Invalid File",
                                     f"The file '{os.path.basename(path)}' is not a valid video format.")
                continue
            pos = self.get_center_pos()
            offset = i * 25
            x, y = pos.x() + offset, pos.y() + offset

            if getattr(Config, 'SNAP_TO_GRID', False):
                x = round(x / Config.GRID_SIZE) * Config.GRID_SIZE
                y = round(y / Config.GRID_SIZE) * Config.GRID_SIZE

            thumb_bytes = create_thumbnail(path)
            title = os.path.basename(path)

            full_data = None

            def progress_cb(current, total, status="Encrypting"):
                self.status_label.setText(f"{status} video {i + 1}/{len(paths)} (Chunk {current}/{total})...")
                QApplication.processEvents()

            if mtype != "video":
                try:
                    with open(path, "rb") as f:
                        full_data = f.read()
                except Exception as e:
                    print(f"Error reading image file: {e}")

            if mtype == "video":
                self.status_label.setText(f"Preparing video {i + 1}/{len(paths)}...")
                QApplication.processEvents()

            node = NodeFactory.create_new_media(
                self.repo, x, y, mtype, title, thumb_bytes,
                full_data=full_data, file_path=path, progress_callback=progress_cb
            )

            self.status_label.setText(self.default_status)
            self.scene.addItem(node)
            self.nodes_map[node.item_id] = node

    def _get_centered_input(self, title, label, echo_mode=QLineEdit.EchoMode.Normal):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextEchoMode(echo_mode)
        dialog.resize(400, 150)

        screen = QGuiApplication.primaryScreen()
        screen_geom = screen.availableGeometry()

        x = screen_geom.x() + (screen_geom.width() - dialog.width()) // 2
        y = screen_geom.y() + (screen_geom.height() - dialog.height()) // 2
        dialog.move(x, y)

        if dialog.exec() == QInputDialog.DialogCode.Accepted:
            return dialog.textValue(), True
        return "", False
