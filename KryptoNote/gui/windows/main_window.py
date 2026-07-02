import datetime
import os
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QMetaObject,
    QPropertyAnimation,
    QSettings,
    QEvent,
    QPoint,
    QTimer,
    QUrl,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QShortcut,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QApplication,
)
from PySide6.QtQuickWidgets import QQuickWidget

from .native_window import NativeWindowMixin
from ..controllers.canvas_controller_qml import QmlCanvasController
from ..controllers.viewer_controller import ViewerController
from ..models.node_list_model import NodeListModel
from ..models.connection_list_model import ConnectionListModel
from ..models.thumbnail_provider import ThumbnailProvider
from ..widgets.dialogs.about_dialog import AboutDialog
from ..widgets.dialogs.dashboard_dialog import DashboardDialog
from ..widgets.dialogs.keybinds_dialog import KeybindsDialog
from ..widgets.overlays.dim_overlay import DimOverlay
from ..widgets.overlays.arraylist_overlay import ArrayListOverlay
from ..widgets.overlays.node_properties_overlay import NodePropertiesOverlay
from ..widgets.progress_bar import ProgressBarWidget
from ..widgets.title_bar import CustomTitleBar
from ...config import Config
from ...gui.theme import Theme
from ...gui.theme.theme_bridge import ThemeBridge
from ...services.backup_service import BackupService
from ...services.stats_service import KnowledgeStatsService
from ...utils.gui_utils import adjust_window_to_screen, center_on_parent_window


class ZeroXXWindow(NativeWindowMixin, QMainWindow):
    _manual_vacuum_started = Signal(str)
    _manual_vacuum_updated = Signal(str)
    _password_change_progress = Signal(int, int, str)
    _password_change_finished = Signal(bool, str)
    _manual_vacuum_finished = Signal(str)

    def __init__(self, db_path, db_conn=None, crypto=None, repo=None, service=None):
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
        self._manual_vacuum_running = False
        self._ctrl_held = False
        self._shift_held = False
        self._manual_vacuum_started.connect(self.show_blocking_progress)
        self._manual_vacuum_updated.connect(self.update_blocking_progress)
        self._manual_vacuum_finished.connect(self._on_manual_vacuum_finished)
        self._password_change_progress.connect(self._on_password_change_progress)
        self._password_change_finished.connect(self._on_password_change_finished)

        self._init_core(db_path, db_conn, crypto, repo, service)
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

        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.open_search)

        self.read_settings()
        self._install_key_event_filter()

    def _init_core(self, db_path, db_conn=None, crypto=None, repo=None, service=None):
        if db_conn and crypto and repo and service:
            self.db_conn = db_conn
            self.crypto = crypto
            self.repo = repo
            self.service = service
        else:
            # Fallback for legacy callers (e.g. tests)
            from ...services.auth_service import AuthService
            from PySide6.QtWidgets import QInputDialog, QLineEdit

            def _password_provider(mode, db_name, error_msg=None):
                if mode == "create":
                    prompt = f"Create password for '{db_name}':"
                elif mode == "confirm":
                    prompt = f"Confirm password for '{db_name}':"
                else:
                    prompt = f"Enter password for '{db_name}':"
                if error_msg:
                    prompt = f"{error_msg}\n\n{prompt}"
                dlg = QInputDialog(self)
                dlg.setWindowTitle("KryptoNote")
                dlg.setLabelText(prompt)
                dlg.setTextEchoMode(QLineEdit.EchoMode.Password)
                dlg.setMinimumWidth(400)
                dlg.resize(420, 160)
                center_on_parent_window(dlg, self)
                ok = dlg.exec() == QInputDialog.DialogCode.Accepted
                pwd = dlg.textValue()
                return pwd, ok

            self.db_conn, self.crypto, self.repo, self.service = (
                AuthService.authenticate(db_path, _password_provider)
            )

    def _setup_canvas(self):
        self.node_model = NodeListModel(self)
        self.connection_model = ConnectionListModel(self.node_model, self)

        self.canvas_controller = QmlCanvasController(
            self.node_model, self.connection_model, self.service, self
        )
        self.canvas_controller.status_message.connect(self._handle_status_update)
        self.canvas_controller.progress_updated.connect(self._on_progress_updated)
        self.canvas_controller.progress_finished.connect(self._on_progress_finished)

        self.viewer_controller = ViewerController(
            self.node_model, self.canvas_controller, self.service, self
        )
        self.canvas_controller.open_media_viewer_requested.connect(
            self.viewer_controller.open_media_viewer
        )

        from PySide6.QtGui import QSurfaceFormat
        format = QSurfaceFormat()
        format.setSamples(8)
        self.view = QQuickWidget()
        self.view.setFormat(format)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.setClearColor(QColor("#050505"))

        quick_window = self.view.quickWindow()
        if quick_window:
            quick_window.setPersistentGraphics(True)
            quick_window.setPersistentSceneGraph(True)

        self.thumb_provider = ThumbnailProvider(self.node_model)
        self.view.engine().addImageProvider("thumbnails", self.thumb_provider)

        self._theme_bridge = ThemeBridge(self)

        ctx = self.view.rootContext()
        ctx.setContextProperty("AppTheme", self._theme_bridge)
        ctx.setContextProperty("nodeModel", self.node_model)
        ctx.setContextProperty("connectionModel", self.connection_model)
        ctx.setContextProperty("canvasController", self.canvas_controller)

        qml_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qml")
        qml_path = os.path.join(qml_dir, "Canvas.qml")
        self._qml_canvas_source = QUrl.fromLocalFile(qml_path)

        self.view.setSource(self._qml_canvas_source)

        if self.view.status() == QQuickWidget.Status.Error:
            errors = self.view.errors()
            for err in errors:
                print(f"QML Error: {err.toString()}")
        else:
            root = self.view.rootObject()
            if root is not None:
                root.textEditorOpenChanged.connect(self._on_text_editor_open_changed)

        self.overlay = ArrayListOverlay(self)
        self.overlay.set_snap_status(Config.SNAP_TO_GRID)
        self.overlay.set_zoom_status(1.0)
        self.overlay.stats_clicked.connect(self.open_dashboard)
        self.overlay.raise_()
        self._arraylist_hidden = False
        self._overlay_stats_update_scheduled = False
        self._arraylist_anim = QPropertyAnimation(self.overlay, b"pos", self)
        self._arraylist_anim.setDuration(220)
        self._arraylist_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._connect_overlay_stats_updates()
        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        if getattr(self, "title_bar", None):
            vbox.addWidget(self.title_bar)

        vbox.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _connect_overlay_stats_updates(self):
        for signal in (
            self.node_model.rowsInserted,
            self.node_model.rowsRemoved,
            self.node_model.modelReset,
            self.node_model.dataChanged,
            self.connection_model.rowsInserted,
            self.connection_model.rowsRemoved,
            self.connection_model.modelReset,
            self.connection_model.dataChanged,
        ):
            signal.connect(self._schedule_overlay_stats_update)
        QTimer.singleShot(0, self._update_overlay_stats)

    def _schedule_overlay_stats_update(self, *args):
        if getattr(self, "_overlay_stats_update_scheduled", False):
            return
        self._overlay_stats_update_scheduled = True
        QTimer.singleShot(0, self._update_overlay_stats)

    def _overlay_stats(self):
        db_path = getattr(self.db_conn, "db_path", None)
        return KnowledgeStatsService.build_overlay(
            getattr(self.node_model, "_nodes", ()),
            self.connection_model.rowCount(),
            db_path,
        )

    def _dashboard_stats(self):
        db_path = getattr(self.db_conn, "db_path", None)
        return KnowledgeStatsService.build(
            getattr(self.node_model, "_nodes", ()),
            self.connection_model.rowCount(),
            db_path,
            getattr(self.connection_model, "_connections", ()),
        )

    def _update_overlay_stats(self):
        self._overlay_stats_update_scheduled = False
        if not hasattr(self, "overlay"):
            return
        stats = self._overlay_stats()
        self.overlay.set_stats(
            stats["node_count"],
            stats["link_count"],
            stats["content_size_label"],
        )

    @Slot(bool)
    def _on_text_editor_open_changed(self, opened):
        self._set_arraylist_hidden(bool(opened), animate=True)

    def _arraylist_visible_pos(self):
        sb_y = self.statusBar().y()
        return QPoint(
            self.width() - self.overlay.width(),
            sb_y - self.overlay.height() + 3,
        )

    def _arraylist_hidden_pos(self):
        visible = self._arraylist_visible_pos()
        return QPoint(self.width() + 2, visible.y())

    def _set_arraylist_hidden(self, hidden, animate=True):
        if not hasattr(self, "overlay"):
            return
        self._arraylist_hidden = hidden
        target = self._arraylist_hidden_pos() if hidden else self._arraylist_visible_pos()
        self.overlay.raise_()
        if not animate:
            self._arraylist_anim.stop()
            self.overlay.move(target)
            return
        if self.overlay.pos() == target:
            return
        self._arraylist_anim.stop()
        self._arraylist_anim.setStartValue(self.overlay.pos())
        self._arraylist_anim.setEndValue(target)
        self._arraylist_anim.start()

    def _install_key_event_filter(self):
        if getattr(self, "_key_event_filter_installed", False):
            return
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
            self._key_event_filter_installed = True

    def _setup_menubar(self):
        menubar = (
            self.title_bar.menu_bar
            if getattr(self, "title_bar", None)
            else self.menuBar()
        )
        file_menu = menubar.addMenu("File")

        act_save = QAction("Save\t[Ctrl+S]", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._on_manual_save)
        file_menu.addAction(act_save)

        act_select_all = QAction("Select All\t[Ctrl+A]", self)
        act_select_all.triggered.connect(self._on_select_all)
        file_menu.addAction(act_select_all)

        file_menu.addSeparator()

        act_vacuum = QAction("Vacuum", self)
        act_vacuum.triggered.connect(self._on_manual_vacuum)
        file_menu.addAction(act_vacuum)

        act_backup = QAction("Backup", self)
        act_backup.triggered.connect(self._on_create_backup)
        file_menu.addAction(act_backup)

        export_menu = file_menu.addMenu("Export")

        act_export_all_md = QAction("Export all text nodes to md", self)
        act_export_all_md.triggered.connect(self._on_export_all_markdown)
        export_menu.addAction(act_export_all_md)

        act_export_selected_md = QAction("Export selected text nodes to md", self)
        act_export_selected_md.triggered.connect(self._on_export_selected_markdown)
        export_menu.addAction(act_export_selected_md)

        file_menu.addSeparator()

        act_change_pwd = QAction("Change Password", self)
        act_change_pwd.triggered.connect(self._on_change_password)
        file_menu.addAction(act_change_pwd)

        file_menu.addSeparator()

        act_close = QAction("Exit", self)
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        add_menu = menubar.addMenu("Add")

        act_note = QAction("Note\t[Ctrl+N]", self)
        act_note.setShortcut(QKeySequence("Ctrl+N"))
        act_note.triggered.connect(self._on_add_text_node)
        add_menu.addAction(act_note)

        act_img = QAction("Image\t[Ctrl+M]", self)
        act_img.setShortcut(QKeySequence("Ctrl+M"))
        act_img.triggered.connect(self._on_add_image_node)
        add_menu.addAction(act_img)

        act_vid = QAction("Video\t[Ctrl+Shift+M]", self)
        act_vid.setShortcut(QKeySequence("Ctrl+Shift+M"))
        act_vid.triggered.connect(self._on_add_video_node)
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
        act_keybinds = QAction("Show All Keybinds", self)
        act_keybinds.triggered.connect(self.open_keybinds)
        help_menu.addAction(act_keybinds)

        act_about = QAction("About", self)
        act_about.triggered.connect(self.open_about)
        help_menu.addAction(act_about)

        self._register_menu_canvas_guard(file_menu, export_menu, add_menu, tools_menu, help_menu)

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

    def _register_menu_canvas_guard(self, *menus):
        for menu in menus:
            menu.aboutToHide.connect(self._suppress_next_canvas_mouse_press)

    def _suppress_next_canvas_mouse_press(self):
        self._suppress_next_canvas_press = True
        self._suppress_canvas_mouse_sequence = False
        self._invoke_qml_root("suppressNextMousePress")
        QTimer.singleShot(450, self._clear_canvas_mouse_suppression)

    def _clear_canvas_mouse_suppression(self):
        self._suppress_next_canvas_press = False
        self._suppress_canvas_mouse_sequence = False
        self._invoke_qml_root("cancelPointerGesture")

    def _should_suppress_canvas_mouse_event(self, event):
        if not hasattr(self, "view"):
            return False
        event_type = event.type()
        mouse_events = (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseMove,
        )
        if event_type not in mouse_events:
            return False

        try:
            global_pos = event.globalPosition().toPoint()
        except AttributeError:
            try:
                global_pos = event.globalPos()
            except AttributeError:
                return False

        local_pos = self.view.mapFromGlobal(global_pos)
        if not self.view.rect().contains(local_pos):
            return False

        if getattr(self, "_suppress_canvas_mouse_sequence", False):
            if event_type == QEvent.Type.MouseButtonRelease:
                self._suppress_canvas_mouse_sequence = False
            return True

        if not getattr(self, "_suppress_next_canvas_press", False):
            return False

        if event_type == QEvent.Type.MouseButtonPress:
            self._suppress_next_canvas_press = False
            self._suppress_canvas_mouse_sequence = True
            self._invoke_qml_root("cancelPointerGesture")
            return True
        if event_type == QEvent.Type.MouseButtonRelease:
            self._suppress_next_canvas_press = False
            self._invoke_qml_root("cancelPointerGesture")
            return True
        return False

    # ── Status & Progress ───────────────────────────────────────────

    def _handle_status_update(self, message, type="normal"):
        if message == "Ready":
            if getattr(self, "_status_protected", False):
                return
            message = self.default_status
        self.status_label.setText(message)
        self.status_label.setStyleSheet(Theme.Styles.get_status_bar_qss(type))

    def _protect_status(self, duration_ms=1000):
        self._status_protected = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(duration_ms, self._unprotect_status)

    def _unprotect_status(self):
        self._status_protected = False

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

    # ── Blocking Progress Overlay ───────────────────────────────────

    @Slot(str)
    def show_blocking_progress(self, msg: str):
        was_inactive = getattr(self, "_blocking_progress_depth", 0) == 0
        self._blocking_progress_depth = getattr(self, "_blocking_progress_depth", 0) + 1
        if was_inactive and hasattr(self, "view"):
            self.view.setEnabled(False)
        if not hasattr(self, "global_dim_overlay") or not self.global_dim_overlay:
            self.global_dim_overlay = DimOverlay(self.view, block_input=True)
            self.global_dim_overlay.setParent(self.view)
            self.global_dim_overlay.resize(self.view.size())
            self.global_dim_overlay.destroyed.connect(self._on_blocking_overlay_destroyed)
        elif hasattr(self.global_dim_overlay, "fade_in"):
            self.global_dim_overlay.fade_in()

        self.global_dim_overlay.show()
        self.global_dim_overlay.raise_()
        self.progress_bar.start(msg, indeterminate=True)
        self.progress_label.setText(msg)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)

    @Slot(str)
    def update_blocking_progress(self, msg: str):
        if getattr(self, "_blocking_progress_depth", 0) <= 0:
            self.show_blocking_progress(msg)
            return
        self.progress_bar.start(msg, indeterminate=True)
        self.progress_label.setText(msg)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)
        if hasattr(self, "global_dim_overlay") and self.global_dim_overlay:
            self.global_dim_overlay.raise_()

    @Slot()
    def hide_blocking_progress(self):
        depth = max(0, getattr(self, "_blocking_progress_depth", 0) - 1)
        self._blocking_progress_depth = depth
        if depth > 0:
            return
        if hasattr(self, "global_dim_overlay") and self.global_dim_overlay:
            self.global_dim_overlay.fade_out()
        if hasattr(self, "view"):
            self.view.setEnabled(True)
        self.progress_bar.finish()
        self.progress_label.setVisible(False)
        self.status_label.setVisible(True)
        self.status_label.setText("Ready")

    def _on_blocking_overlay_destroyed(self, *args):
        self.global_dim_overlay = None

    def show_video_transition_overlay(self, message="Processing video..."):
        self.show_blocking_progress(message)

    def update_video_transition_overlay(self, message="Processing video..."):
        self.update_blocking_progress(message)

    def hide_video_transition_overlay(self):
        self.hide_blocking_progress()

    # ── Actions ─────────────────────────────────────────────────────

    def toggle_snap_to_grid(self):
        Config.SNAP_TO_GRID = not getattr(Config, "SNAP_TO_GRID", False)
        state_text = "ON" if Config.SNAP_TO_GRID else "OFF"
        self.act_snap.setText(f"Snap to Grid: {state_text}\t[G]")
        self.overlay.set_snap_status(Config.SNAP_TO_GRID)
        self.status_label.setText(f"Snap to grid {state_text.lower()}.")
        self.canvas_controller.snap_to_grid_changed.emit(Config.SNAP_TO_GRID)

    def _markdown_export_filename(self, selected=False):
        db_path = getattr(self.db_conn, "db_path", "Untitled")
        name, _ = os.path.splitext(os.path.basename(db_path))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        suffix = "Selected" if selected else "Exported"
        return f"{name}-KryptoNote{suffix}-{timestamp}.md"

    def _on_select_all(self):
        self.canvas_controller.select_all_nodes()
        self._defer_modifier_sync()

    def _on_export_all_markdown(self):
        self.canvas_controller.export_to_markdown(
            self._markdown_export_filename(selected=False),
            selected_only=False,
        )

    def _on_export_selected_markdown(self):
        self.canvas_controller.export_to_markdown(
            self._markdown_export_filename(selected=True),
            selected_only=True,
        )

    def _on_manual_save(self):
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog and self._pwd_change_dialog.is_changing():
            self._handle_status_update("Cannot save during password change", "warning")
            return
        self.service.commit_changes()
        self._update_overlay_stats()
        self._handle_status_update("Saved", "secure")
        self._defer_modifier_sync()

    def _on_manual_vacuum(self):
        if self._manual_vacuum_running:
            return
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog and self._pwd_change_dialog.is_changing():
            return
        self._manual_vacuum_running = True

        def on_start():
            self._manual_vacuum_started.emit("Vacuuming database...")

        def on_finish():
            self._manual_vacuum_finished.emit("Ready")

        def on_waiting_lock(attempt):
            self._manual_vacuum_updated.emit(
                f"Waiting for database lock... retry {attempt}/8"
            )

        self.service.vacuum_database(
            on_start_vacuum=on_start,
            on_finish_vacuum=on_finish,
            on_waiting_lock=on_waiting_lock,
        )

    @Slot(str)
    def _on_manual_vacuum_finished(self, message: str):
        self._manual_vacuum_running = False
        self.hide_blocking_progress()
        self._update_overlay_stats()
        self._handle_status_update(message)

    def _on_create_backup(self):
        success, message = BackupService.create(self.db_conn, self.service)
        if success:
            self._update_overlay_stats()
            QMessageBox.information(self, "Backup", message)
        else:
            QMessageBox.critical(self, "Backup Error", message)

    def _on_add_text_node(self):
        self.canvas_controller.add_text_node()
        self._defer_modifier_sync()

    def _on_add_image_node(self):
        self.canvas_controller.add_media_node("image")
        self._defer_modifier_sync()

    def _on_add_video_node(self):
        self.canvas_controller.add_media_node("video")
        self._defer_modifier_sync()

    # ── Dialogs ─────────────────────────────────────────────────────

    def open_search(self):
        if hasattr(self, "view"):
            self.view.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._invoke_qml_root("openSearchPanel")
        self._defer_modifier_sync()

    def open_about(self):
        overlay = DimOverlay(self)
        overlay.show()
        dialog = AboutDialog(self)
        center_on_parent_window(dialog, self)
        dialog.exec()
        overlay.fade_out(delete_on_finish=True)

    def open_keybinds(self):
        overlay = DimOverlay(self)
        overlay.show()
        dialog = KeybindsDialog(self)
        center_on_parent_window(dialog, self)
        dialog.exec()
        overlay.fade_out(delete_on_finish=True)

    def open_dashboard(self):
        self._update_overlay_stats()
        overlay = DimOverlay(self)
        overlay.show()
        dialog = DashboardDialog(self._dashboard_stats(), self)
        center_on_parent_window(dialog, self)
        dialog.exec()
        overlay.fade_out(delete_on_finish=True)

    def show_node_properties_overlay(self, metadata_lines):
        """Show themed node properties overlay over the canvas."""
        if hasattr(self, 'view'):
            if hasattr(self, '_node_props_overlay') and self._node_props_overlay:
                self._node_props_overlay.fade_out(delete_on_finish=True)
            self._node_props_overlay = NodePropertiesOverlay(metadata_lines, parent=self.view)
            self._node_props_overlay.destroyed.connect(lambda: setattr(self, '_node_props_overlay', None))
            self._node_props_overlay.raise_()

    # ── Password Change ─────────────────────────────────────────────

    def _on_change_password(self):
        from ..widgets.dialogs.password_change_dialog import PasswordChangeDialog
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            return

        self._pwd_change_dim = DimOverlay(self.view, block_input=True, auto_show=True)
        self._pwd_change_dim.setStyleSheet("DimOverlay { background-color: rgba(0, 0, 0, 150); }")
        self._pwd_change_dim.raise_()

        self._pwd_change_dialog = PasswordChangeDialog(self)
        self._pwd_change_dialog.passwordChangeRequested.connect(
            self._execute_password_change
        )
        self._pwd_change_dialog.finished.connect(self._cleanup_pwd_change_dialog)
        center_on_parent_window(self._pwd_change_dialog, self)
        self._pwd_change_dialog.show()

    def _execute_password_change(self, old_pwd, new_pwd, create_backup):
        import concurrent.futures
        from ...services.password_change_service import PasswordChangeService

        if create_backup:
            success, message = BackupService.create(self.db_conn, self.service)
            if not success:
                if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
                    self._pwd_change_dialog.show_finished(False, f"Backup failed: {message}")
                return

        db_path = getattr(self.db_conn, 'db_path', None)
        if not db_path:
            return

        progress_signal = self._password_change_progress
        finished_signal = self._password_change_finished

        def on_progress(current, total, msg):
            progress_signal.emit(current, total, msg)

        def on_finished(success, msg):
            finished_signal.emit(success, msg)

        self._password_change_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._password_change_executor.submit(
            PasswordChangeService.change_password,
            db_path, old_pwd, new_pwd,
            on_progress, on_finished,
        )

    @Slot(int, int, str)
    def _on_password_change_progress(self, current, total, msg):
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            self._pwd_change_dialog.set_changing(True, msg)

    @Slot(bool, str)
    def _on_password_change_finished(self, success, msg):
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            self._pwd_change_dialog.show_finished(success, msg)
        executor = getattr(self, "_password_change_executor", None)
        if executor:
            executor.shutdown(wait=False)
            self._password_change_executor = None

    def _cleanup_pwd_change_dialog(self, *args):
        self._pwd_change_dialog = None
        if hasattr(self, "_pwd_change_dim") and self._pwd_change_dim:
            self._pwd_change_dim.fade_out()
            self._pwd_change_dim = None

    # ── Coords ──────────────────────────────────────────────────────

    def update_coords(self, pos):
        self.coords_label.setText(f"X: {int(pos.x())} Y: {int(pos.y())}")

    # ── Key Events ──────────────────────────────────────────────────

    def eventFilter(self, watched, event):
        if self._should_suppress_canvas_mouse_event(event):
            return True
        if event.type() == QEvent.Type.ShortcutOverride:
            if self._should_claim_shortcut(event):
                event.accept()
        if event.type() == QEvent.Type.KeyPress:
            self._handle_global_modifier_press(event)
            if self._handle_global_key_press(event):
                return True
        if event.type() == QEvent.Type.KeyRelease:
            self._handle_global_modifier_release(event)
            if self._handle_global_key_release(event):
                return True
        return super().eventFilter(watched, event)

    def _should_claim_shortcut(self, event):
        """Return True for shortcuts we want to handle in Python, not QML."""
        if not self.isActiveWindow():
            return False
        editor_open = self._is_qml_text_editor_open()
        if not editor_open:
            return False
        key = event.key()
        modifiers = event.modifiers()
        is_s_key = key == Qt.Key.Key_S or event.nativeVirtualKey() == 0x53
        if is_s_key and modifiers & Qt.KeyboardModifier.ControlModifier:
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and modifiers & Qt.KeyboardModifier.ControlModifier:
            return True
        if key == Qt.Key.Key_Escape:
            return True
        if self._is_app_shortcut_while_editor_open(event):
            return True
        return False

    def _handle_global_key_press(self, event):
        if not self.isActiveWindow() or QApplication.activeModalWidget() is not None:
            return False

        key = event.key()
        modifiers = event.modifiers()

        editor_open = self._is_qml_text_editor_open()
        if editor_open:
            if key == Qt.Key.Key_Escape:
                self._invoke_qml_root("cancelEditor")
                return True

            is_s_key = key == Qt.Key.Key_S or event.nativeVirtualKey() == 0x53
            if is_s_key and modifiers & Qt.KeyboardModifier.ControlModifier:
                self._invoke_qml_root("saveEditor")
                self._protect_status(2000)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and modifiers & Qt.KeyboardModifier.ControlModifier:
                self._invoke_qml_root("saveEditor")
                self._protect_status(2000)
                return True
            if self._is_app_shortcut_while_editor_open(event):
                return True
            return False

        if not self._canvas_has_keyboard_focus():
            return False

        search_open = self._is_qml_search_panel_open()

        if search_open and key == Qt.Key.Key_Escape:
            self._invoke_qml_root("closeSearchPanel")
            return True
        if search_open:
            return False

        if self._is_select_all_shortcut(event):
            self.canvas_controller.select_all_nodes()
            return True

        if key == Qt.Key.Key_Escape and modifiers == Qt.KeyboardModifier.NoModifier:
            self.canvas_controller.clear_selection()
            return True

        if modifiers == Qt.KeyboardModifier.NoModifier and key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            self._set_keyboard_pan_key(key, True)
            return True

        if self._is_snap_key(event) and modifiers == Qt.KeyboardModifier.NoModifier:
            self.toggle_snap_to_grid()
            return True

        if key == Qt.Key.Key_Delete:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.canvas_controller.delete_selected_nodes_without_confirmation()
            else:
                self.canvas_controller.delete_selected_nodes()
            return True

        return False

    def _is_snap_key(self, event):
        if event.key() == Qt.Key.Key_G:
            return True
        try:
            return event.nativeVirtualKey() == 0x47
        except AttributeError:
            return False

    def _is_select_all_shortcut(self, event):
        modifiers = event.modifiers()
        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            return False
        if modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
            return False
        try:
            native = event.nativeVirtualKey()
        except AttributeError:
            native = 0
        return event.key() == Qt.Key.Key_A or native == 0x41

    def _handle_global_key_release(self, event):
        if self._keyboard_pan_key_name(event.key()) is None:
            return False
        if self._is_auto_repeat_event(event):
            return True
        self._set_keyboard_pan_key(event.key(), False)
        return self.isActiveWindow()

    def _set_keyboard_pan_key(self, key, pressed):
        key_name = self._keyboard_pan_key_name(key)
        if key_name is None:
            return
        self._invoke_qml_root("setKeyboardPanKey", key_name, bool(pressed))

    @staticmethod
    def _keyboard_pan_key_name(key):
        if key == Qt.Key.Key_Left:
            return "left"
        if key == Qt.Key.Key_Right:
            return "right"
        if key == Qt.Key.Key_Up:
            return "up"
        if key == Qt.Key.Key_Down:
            return "down"
        return None

    @staticmethod
    def _is_auto_repeat_event(event):
        try:
            return event.isAutoRepeat()
        except AttributeError:
            return False

    def _is_app_shortcut_while_editor_open(self, event):
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Escape):
            return True
        if not ctrl:
            return False

        native = event.nativeVirtualKey()
        is_n_key = key == Qt.Key.Key_N or native == 0x4E
        is_m_key = key == Qt.Key.Key_M or native == 0x4D
        is_f_key = key == Qt.Key.Key_F or native == 0x46

        return is_n_key or is_f_key or is_m_key

    def _canvas_has_keyboard_focus(self):
        if not hasattr(self, "view"):
            return False
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        return focus is self.view or self.view.isAncestorOf(focus)

    def _is_qml_text_editor_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isTextEditorOpen"))

    def _is_qml_search_panel_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isSearchPanelOpen"))

    def _invoke_qml_root(self, method_name, *args):
        if not hasattr(self, "view"):
            return
        root = self.view.rootObject()
        if root is not None:
            fn = getattr(root, method_name, None)
            if fn and callable(fn):
                fn(*args)
            else:
                QMetaObject.invokeMethod(root, method_name)



    def _reset_all_modifiers(self):
        """Reset both QML modifier flags and Python status bar.

        Called when the window regains focus after a dialog (e.g. QFileDialog)
        consumed the key-release event, leaving modifiers stuck.
        """
        self._ctrl_held = False
        self._shift_held = False
        self._invoke_qml_root("resetModifiers")
        self._invoke_qml_root("stopKeyboardPan")
        self.canvas_controller.toggle_link_mode_off()
        self._handle_status_update("Ready")

    def _handle_global_modifier_press(self, event):
        if not self.isActiveWindow() or QApplication.activeModalWidget() is not None:
            return
        if self._is_qml_text_editor_open():
            return
        key = event.key()
        if key not in (Qt.Key.Key_Control, Qt.Key.Key_Shift):
            return
        if key == Qt.Key.Key_Control:
            self._ctrl_held = True
        elif key == Qt.Key.Key_Shift:
            self._shift_held = True
        self._apply_modifier_state(self._ctrl_held, self._shift_held)

    def _handle_global_modifier_release(self, event):
        if self._is_qml_text_editor_open():
            return
        key = event.key()
        if key not in (Qt.Key.Key_Control, Qt.Key.Key_Shift):
            return
        if key == Qt.Key.Key_Control:
            self._ctrl_held = False
        elif key == Qt.Key.Key_Shift:
            self._shift_held = False
        self._apply_modifier_state(self._ctrl_held, self._shift_held)

    def _sync_modifier_state(self):
        """Clear stale modifier state without re-enabling it from Qt's cache."""
        mods = QApplication.keyboardModifiers()
        if not (mods & Qt.KeyboardModifier.ControlModifier):
            self._ctrl_held = False
        if not (mods & Qt.KeyboardModifier.ShiftModifier):
            self._shift_held = False
        self._apply_modifier_state(self._ctrl_held, self._shift_held)

    def _apply_modifier_state(self, ctrl_held, shift_held):
        self._ctrl_held = ctrl_held
        self._shift_held = shift_held
        root = self.view.rootObject() if hasattr(self, "view") else None
        if root is None:
            return
        if root.property("isCtrlHeld") != ctrl_held or root.property("isShiftHeld") != shift_held:
            root.setProperty("isCtrlHeld", ctrl_held)
            root.setProperty("isShiftHeld", shift_held)
            root.setProperty("isLinkMode", shift_held)
            if not shift_held:
                self.canvas_controller.toggle_link_mode_off()
        if shift_held:
            self._handle_status_update(
                "LINKING: Hold Shift and click nodes to create links.", "secure"
            )
        elif ctrl_held:
            self._handle_status_update(
                "SELECTION ACTIVE: Drag mouse to select multiple objects.", "accent"
            )
        else:
            self._handle_status_update("Ready")

    def _defer_modifier_sync(self):
        """Shortcuts can consume key-release events before QML sees them."""
        QTimer.singleShot(0, self._reset_all_modifiers)
        QTimer.singleShot(80, self._reset_all_modifiers)
        QTimer.singleShot(220, self._reset_all_modifiers)

    # ── Window Events ───────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_window_margins()

        if hasattr(self, "overlay") and hasattr(self, "statusBar"):
            self._set_arraylist_hidden(
                getattr(self, "_arraylist_hidden", False),
                animate=False,
            )
            self.overlay.raise_()
        if hasattr(self, "progress_bar"):
            sb_y = self.statusBar().y()
            self.progress_bar.setFixedWidth(self.width())
            self.progress_bar.move(0, sb_y - self.progress_bar.height())
            self.progress_bar.raise_()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_window_margins()
            self._schedule_qml_render_recovery()
        elif event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                # Window regained focus — modifiers may have been released
                # inside a native dialog (QFileDialog, etc.).
                QTimer.singleShot(0, self._sync_modifier_state)

    def showEvent(self, event):
        super().showEvent(event)
        if self.is_windows:
            self._apply_native_dwm_attributes()
        self._schedule_qml_render_recovery()

    def _sync_window_margins(self):
        self.setContentsMargins(0, 0, 0, 0)

    def _schedule_qml_render_recovery(self):
        if self.windowState() & Qt.WindowState.WindowMinimized:
            return
        QTimer.singleShot(0, self._recover_qml_render)
        QTimer.singleShot(40, self._recover_qml_render)
        QTimer.singleShot(140, lambda: self._recover_qml_render(release_resources=True))

    def _recover_qml_render(self, release_resources=False):
        if not hasattr(self, "view"):
            return
        if self.windowState() & Qt.WindowState.WindowMinimized:
            return
        quick_window = self.view.quickWindow()
        if quick_window:
            quick_window.setPersistentGraphics(True)
            quick_window.setPersistentSceneGraph(True)
            if release_resources:
                quick_window.releaseResources()
        root = self.view.rootObject()
        if root is not None:
            root.update()
        self.view.update()

    # ── Settings Persistence ────────────────────────────────────────

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
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            if self._pwd_change_dialog.is_changing():
                event.ignore()
                self._handle_status_update("Cannot close: password change in progress", "warning")
                return

        self.write_settings()
        if hasattr(self, "service"):
            try:
                self.service.commit_changes()
            except Exception as e:
                print(f"Error saving changes on close: {e}")
        if hasattr(self, "repo"):
            try:
                self.repo.close()
            except Exception:
                pass
        if hasattr(self, "db_conn"):
            try:
                self.db_conn.conn.close()
            except Exception:
                pass
        super().closeEvent(event)
