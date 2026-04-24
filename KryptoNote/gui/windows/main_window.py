import datetime
import os
import sqlite3
import sys

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import (
    QAction,
    QColor,
    QBrush,
    QShortcut,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QMainWindow,
    QGraphicsScene,
    QLabel,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QMessageBox,
)

from .native_window import NativeWindowMixin
from ..controllers.canvas_controller import CanvasController
from ..views.canvas_view import InfiniteCanvasView
from ..widgets.dialogs.search_dialog import SearchDialog
from ..widgets.dialogs.about_dialog import AboutDialog
from ..widgets.overlays.dim_overlay import DimOverlay
from ..widgets.overlays.arraylist_overlay import ArrayListOverlay
from ..widgets.progress_bar import ProgressBarWidget
from ..widgets.title_bar import CustomTitleBar
from ...config import Config
from ...core.crypto import CryptoManager
from ...core.database import NodeRepository, DatabaseConnection
from ...gui.theme import Theme
from ...services.node_service import NodeService
from ...utils.gui_utils import get_centered_input, adjust_window_to_screen


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
            adjust_window_to_screen(self)
        else:
            self.setWindowTitle(f"{Config.APP_NAME} [{os.path.basename(db_path)}]")
            self.title_bar = None
            adjust_window_to_screen(self)

        self.setStyleSheet(Theme.Styles.get_main_window_qss())
        self.default_status = (
            "Ready | Hold [SHIFT] to Link | Hold [CTRL] to Multi-Select"
        )

        self._init_core(db_path)
        self._setup_canvas()
        self._setup_menubar()

        try:
            self.canvas_controller.load_from_db()
        except Exception as e:
            print(f"Load Error: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to decrypt/load DB. Incorrect password?\nError: {e}",
            )
            self.db_conn.conn.close()
            raise RuntimeError("Failed to load DB")

        self.search_dialog = None
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.open_search)

        self.snap_shortcut = QShortcut(QKeySequence("G"), self)
        self.snap_shortcut.activated.connect(self.toggle_snap_to_grid)
        self.read_settings()

    def _init_core(self, db_path):
        self.db_conn = DatabaseConnection(db_path)
        self.crypto = CryptoManager()
        salt = self.db_conn.get_salt()

        if not salt:
            while True:
                pwd1, ok1 = get_centered_input(
                    self,
                    "Create Password",
                    f"Set password for new project:\n{os.path.basename(db_path)}",
                    QLineEdit.EchoMode.Password,
                )
                if not ok1 or not pwd1:
                    raise RuntimeError("Password entry cancelled")
                pwd2, ok2 = get_centered_input(
                    self,
                    "Confirm Password",
                    "Repeat password:",
                    QLineEdit.EchoMode.Password,
                )
                if not ok2:
                    raise RuntimeError("Password entry cancelled")
                if pwd1 == pwd2:
                    salt = os.urandom(16)
                    self.db_conn.set_salt(salt)
                    self.crypto.derive_key(pwd1, salt)
                    self.db_conn.set_auth_check(
                        self.crypto.encrypt(b"KryptoNote_Auth_OK")
                    )
                    break
                else:
                    QMessageBox.warning(
                        self, "Mismatch", "Passwords do not match! Try again."
                    )
        else:
            pwd, ok = get_centered_input(
                self,
                "Enter password",
                f"Password for {os.path.basename(db_path)}:",
                QLineEdit.EchoMode.Password,
            )
            if not ok or not pwd:
                raise RuntimeError("Password entry cancelled")

            self.crypto.derive_key(pwd, salt)

            auth_check = self.db_conn.get_auth_check()
            if auth_check:
                try:
                    if self.crypto.decrypt(auth_check) != b"KryptoNote_Auth_OK":
                        raise Exception("Verification failed")
                except Exception:
                    QMessageBox.critical(self, "Error", "Incorrect password!")
                    self.db_conn.conn.close()
                    raise RuntimeError("Incorrect password")

        self.repo = NodeRepository(self.db_conn, self.crypto)
        self.service = NodeService(self.repo)

    def _setup_canvas(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-25000, -25000, 50000, 50000)
        self.scene.setBackgroundBrush(QBrush(QColor(Config.BACKGROUND_COLOR)))

        self.view = InfiniteCanvasView(self.scene)
        self.canvas_controller = CanvasController(self.scene, self.view, self.service)

        self.view.mouse_moved.connect(self.update_coords)
        self.view.node_clicked_signal.connect(self.canvas_controller.handle_link_click)
        self.view.connection_right_clicked_signal.connect(
            self.canvas_controller.quick_delete_connection
        )
        self.canvas_controller.status_message.connect(self._handle_status_update)
        self.canvas_controller.progress_updated.connect(self._on_progress_updated)
        self.canvas_controller.progress_finished.connect(self._on_progress_finished)

        self.overlay = ArrayListOverlay(self)
        self.view.zoom_changed.connect(self.overlay.set_zoom_status)
        self.overlay.set_snap_status(Config.SNAP_TO_GRID)
        self.overlay.set_zoom_status(self.view.transform().m11())
        self.overlay.raise_()
        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        if getattr(self, "title_bar", None):
            vbox.addWidget(self.title_bar)

        vbox.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_menubar(self):
        menubar = (
            self.title_bar.menu_bar
            if getattr(self, "title_bar", None)
            else self.menuBar()
        )
        file_menu = menubar.addMenu("File")

        act_close = QAction("Close", self)
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        act_backup = QAction("Backup", self)
        act_backup.triggered.connect(self.create_backup)
        file_menu.addAction(act_backup)

        file_menu.addSeparator()

        act_export_md = QAction("Export Text Nodes to Markdown", self)
        act_export_md.triggered.connect(self._on_export_markdown)
        file_menu.addAction(act_export_md)

        file_menu.addSeparator()

        add_menu = menubar.addMenu("Add")

        act_note = QAction("Note\t[Ctrl+N]", self)
        act_note.setShortcut(QKeySequence("Ctrl+N"))
        act_note.triggered.connect(self.canvas_controller.add_text_node)
        add_menu.addAction(act_note)

        act_img = QAction("Image\t[Ctrl+M]", self)
        act_img.setShortcut(QKeySequence("Ctrl+M"))
        act_img.triggered.connect(
            lambda: self.canvas_controller.add_media_node("image")
        )
        add_menu.addAction(act_img)

        act_vid = QAction("Video\t[Ctrl+Shift+M]", self)
        act_vid.setShortcut(QKeySequence("Ctrl+Shift+M"))
        act_vid.triggered.connect(
            lambda: self.canvas_controller.add_media_node("video")
        )
        add_menu.addAction(act_vid)

        tools_menu = menubar.addMenu("Tools")

        act_search = QAction("Search\t[Ctrl+F]", self)
        act_search.triggered.connect(self.open_search)
        tools_menu.addAction(act_search)
        snap_state = "ON" if getattr(Config, "SNAP_TO_GRID", False) else "OFF"
        self.act_snap = QAction(f"Snap to Grid: {snap_state}\t[G]", self)
        self.act_snap.triggered.connect(self.toggle_snap_to_grid)
        tools_menu.addAction(self.act_snap)

        help_menu = menubar.addMenu("Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self.open_about)
        help_menu.addAction(act_about)

        self.status_label = QLabel(self.default_status)
        self.status_label.setStyleSheet(Theme.Styles.get_status_bar_qss())

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(Theme.Styles.get_status_bar_qss("accent"))
        self.progress_label.setVisible(False)

        self.progress_bar = ProgressBarWidget(self)

        self.coords_label = QLabel("X: 0 Y: 0")
        self.coords_label.setStyleSheet(Theme.Styles.get_status_bar_qss("coords"))
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addWidget(self.progress_label)
        self.statusBar().addPermanentWidget(self.coords_label)

    def _handle_status_update(self, message, type="normal"):
        if message == "Ready":
            message = self.default_status

        self.status_label.setText(message)
        self.status_label.setStyleSheet(Theme.Styles.get_status_bar_qss(type))

    def _on_progress_updated(self, value: float, message: str):
        self.progress_bar.set_progress(value, message)
        self.progress_label.setText(message)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)

    def _on_progress_finished(self, message: str):
        self.progress_bar.finish(message)
        self.progress_label.setVisible(False)
        self.status_label.setVisible(True)
        self._handle_status_update(message)

    def toggle_snap_to_grid(self):
        Config.SNAP_TO_GRID = not getattr(Config, "SNAP_TO_GRID", False)
        state_text = "ON" if Config.SNAP_TO_GRID else "OFF"
        self.act_snap.setText(f"Snap to Grid: {state_text}\t[G]")
        self.overlay.set_snap_status(Config.SNAP_TO_GRID)
        self.status_label.setText(f"Snap to grid {state_text.lower()}.")

    def _on_export_markdown(self):
        db_path = getattr(self.db_conn, "db_path", "Untitled")
        name, _ = os.path.splitext(os.path.basename(db_path))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        default_filename = f"{name}-KryptoNoteExported-{timestamp}.md"
        self.canvas_controller.export_to_markdown(default_filename)

    def create_backup(self):
        db_path = self.db_conn.db_path
        name, ext = os.path.splitext(os.path.basename(db_path))
        backup_dir = os.path.join(os.path.dirname(db_path), "backup")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{name}_{timestamp}{ext}")
        self.service.commit_changes()

        try:
            backup_conn = sqlite3.connect(backup_path)
            self.db_conn.conn.backup(backup_conn)
            backup_conn.close()
            QMessageBox.information(
                self, "Backup", f"Backup created successfully:\n{backup_path}"
            )
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

    def open_about(self):
        overlay = DimOverlay(self)
        overlay.show()
        dialog = AboutDialog(self)
        dialog.exec()
        overlay.close()

    def update_coords(self, pos):
        self.coords_label.setText(f"X: {int(pos.x())} Y: {int(pos.y())}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay") and hasattr(self, "statusBar"):
            sb_y = self.statusBar().y()
            ov_x = self.width() - self.overlay.width()
            ov_y = sb_y - self.overlay.height() + 3
            self.overlay.move(ov_x, ov_y)
            self.overlay.raise_()
        if hasattr(self, "progress_bar"):
            sb_y = self.statusBar().y()
            self.progress_bar.setFixedWidth(self.width())
            self.progress_bar.move(0, sb_y - self.progress_bar.height())
            self.progress_bar.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.canvas_controller.toggle_link_mode(True)
        elif event.key() == Qt.Key.Key_Control:
            self._handle_status_update(
                "SELECTION ACTIVE: Drag mouse to select multiple objects.", "accent"
            )
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.canvas_controller.toggle_link_mode(False)
        elif event.key() == Qt.Key.Key_Control:
            self._handle_status_update("Ready")
        super().keyReleaseEvent(event)

    def read_settings(self):
        settings = QSettings("ZeroXware", "KryptoNote")
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
            if self.width() <= 800:
                return False
            state = settings.value("windowState")
            if state:
                self.restoreState(state)
            return True
        return False

    def write_settings(self):
        settings = QSettings("ZeroXware", "KryptoNote")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def closeEvent(self, event):
        self.write_settings()
        if hasattr(self, "service"):
            try:
                self.service.commit_changes()
            except Exception as e:
                print(f"Error saving changes on close: {e}")
        super().closeEvent(event)
