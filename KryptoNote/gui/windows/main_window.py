import concurrent.futures
import datetime
import importlib
import os
import sys
import threading

from PySide6.QtCore import (
    QEasingCurve,
    QFile,
    QMetaObject,
    QPropertyAnimation,
    QEvent,
    QPoint,
    QSize,
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
from PySide6.QtQuick import QQuickView

from .native_window import NativeWindowMixin
from ..controllers.canvas_controller_qml import QmlCanvasController
from ..controllers.viewer_controller import ViewerController
from ..services.frame_clock import HighRefreshFrameClock
from ..services.qml_network_policy import RestrictedQmlNetworkAccessManagerFactory
from ..services.window_state_service import WindowStateService
from ..services.operation_coordinator import OperationCoordinator
from ..models.node_list_model import NodeListModel, NodeRoles
from ..models.connection_list_model import ConnectionListModel
from ..models.media_preview_provider import MediaPreviewProvider
from ..models.thumbnail_provider import ThumbnailProvider
from ..models.viewport_proxy_model import (
    ConnectionViewportProxyModel,
    NodeViewportProxyModel,
)
from ..widgets.dialogs.about_dialog import AboutDialog
from ..widgets.dialogs.dashboard_dialog import DashboardDialog
from ..widgets.dialogs.keybinds_dialog import KeybindsDialog
from ..widgets.dialogs.theme_dialog import ThemeDialog
from ..widgets.overlays.dim_overlay import WindowOverlayManager
from ..widgets.overlays.arraylist_overlay import ArrayListOverlay
from ..widgets.progress_bar import ProgressBarWidget
from ..widgets.title_bar import CustomTitleBar
from ...config import Config
from ...gui.theme import Theme
from ...gui.theme.icons import SvgIcons
from ...gui.theme.theme_bridge import ThemeBridge
from ...gui.theme.theme_manager import get_theme_manager
from ...services.backup_service import BackupService
from ...services.stats_service import KnowledgeStatsService
from ...utils.gui_utils import adjust_window_to_screen, center_on_parent_window


def resolve_canvas_qml_source():
    """Return a packaged QRC URL when available, otherwise the source file."""
    resource_module = "KryptoNote.gui.resources_rc"
    try:
        importlib.import_module(resource_module)
    except ModuleNotFoundError as exc:
        if exc.name != resource_module:
            raise

    if QFile.exists(":/qml/Canvas.qml"):
        return QUrl("qrc:/qml/Canvas.qml")

    qml_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "qml", "Canvas.qml"
    )
    if not os.path.isfile(qml_path):
        raise FileNotFoundError(f"Canvas QML is missing: {qml_path}")
    return QUrl.fromLocalFile(qml_path)


def resolve_media_viewer_qml_source():
    """Return the reusable detached media-view source."""
    if QFile.exists(":/qml/MediaViewerWindow.qml"):
        return QUrl("qrc:/qml/MediaViewerWindow.qml")
    qml_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "qml",
        "MediaViewerWindow.qml",
    )
    if not os.path.isfile(qml_path):
        raise FileNotFoundError(f"Media viewer QML is missing: {qml_path}")
    return QUrl.fromLocalFile(qml_path)


class ZeroXXWindow(NativeWindowMixin, QMainWindow):
    _password_change_progress = Signal(int, int, str)
    _password_change_finished = Signal(bool, str)
    _manual_vacuum_finished = Signal(bool, str)
    _backup_progress = Signal(int, int, str)
    _backup_finished = Signal(bool, str)

    def __init__(self, db_path, db_conn=None, crypto=None, repo=None, service=None):
        QMainWindow.__init__(self)
        self.is_windows = sys.platform == "win32"
        self._window_state_service = WindowStateService()
        self._theme_manager = get_theme_manager()

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
        self.operation_coordinator = OperationCoordinator(self)
        self._operation_blocked_actions = []
        self._ctrl_held = False
        self._shift_held = False
        self._manual_vacuum_finished.connect(self._on_manual_vacuum_finished)
        self._backup_progress.connect(self._on_backup_progress)
        self._backup_finished.connect(self._on_backup_finished)
        self._password_change_progress.connect(self._on_password_change_progress)
        self._password_change_finished.connect(self._on_password_change_finished)

        self._init_core(db_path, db_conn, crypto, repo, service)
        self._activate_saved_appearance()
        self._setup_canvas()
        self._setup_menubar()
        self._theme_manager.appearanceChanged.connect(
            self._apply_runtime_appearance
        )
        self._apply_runtime_appearance()

        self.operation_coordinator.state_changed.connect(
            self._on_operation_state_changed)
        try:
            self.canvas_controller.load_from_db()
        except Exception as e:
            print(f"Load Error: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to decrypt/load DB. Incorrect password?\nError: {e}",
            )
            self._theme_manager.preview(
                self._theme_manager.committed_settings
            )
            self._close_core_resources(wait=False)
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
                dlg.setInputMode(QInputDialog.InputMode.TextInput)
                dlg.setTextValue("")
                line_edit = dlg.findChild(QLineEdit)
                if line_edit is not None:
                    line_edit.setMaxLength(512)
                dlg.setMinimumWidth(400)
                dlg.resize(420, 160)
                center_on_parent_window(dlg, self)
                ok = dlg.exec() == QInputDialog.DialogCode.Accepted
                pwd = dlg.textValue()
                return pwd, ok

            self.db_conn, self.crypto, self.repo, self.service = (
                AuthService.authenticate(db_path, _password_provider, mode="open")
            )

    def _setup_canvas(self):
        self.node_model = NodeListModel(self)
        self.connection_model = ConnectionListModel(self.node_model, self)
        self.connection_model.set_connection_appearance(
            self._theme_manager.settings.connection_style,
            self._theme_manager.settings.connection_curve_formula,
            self._theme_manager.settings.connection_corner_style,
            self._theme_manager.settings.connection_anchor_mode,
        )
        self._theme_manager.canvasAppearanceChanged.connect(self._sync_connection_style)
        self.node_viewport_model = NodeViewportProxyModel(self.node_model, self)
        self.connection_viewport_model = ConnectionViewportProxyModel(
            self.connection_model, self
        )

        self.canvas_controller = QmlCanvasController(
            self.node_model, self.connection_model, self.service, self,
            operation_coordinator=self.operation_coordinator,
        )
        self.canvas_controller.status_message.connect(self._handle_status_update)
        self.canvas_controller.progress_updated.connect(self._on_progress_updated)
        self.canvas_controller.progress_finished.connect(self._on_progress_finished)
        self.canvas_controller.initial_load_failed.connect(
            self._on_initial_load_failed
        )

        self.media_preview_provider = MediaPreviewProvider()
        self.viewer_controller = ViewerController(
            self.node_model,
            self.canvas_controller,
            self.service,
            self.media_preview_provider,
            self,
        )
        self.canvas_controller.open_media_viewer_requested.connect(
            self._request_open_media
        )
        self.viewer_controller.detachRequested.connect(self._detach_media_viewer)
        self.viewer_controller.attachRequested.connect(self._attach_media_viewer)
        self.viewer_controller.sessionClosed.connect(
            self._schedule_detached_view_disposal
        )
        self.viewer_controller.titleChanged.connect(self._sync_detached_view_title)
        self._detached_view = None
        self._closing_detached_view = False
        self._detached_dispose_scheduled = False
        self._application_close_pending = False

        from PySide6.QtGui import QSurfaceFormat
        format = QSurfaceFormat()
        format.setSamples(8)
        self.view = QQuickWidget()
        gui_root = os.path.dirname(os.path.dirname(__file__))
        self._qml_network_factory = RestrictedQmlNetworkAccessManagerFactory(
            (
                os.path.join(gui_root, "qml"),
                os.path.join(gui_root, "assets"),
            )
        )
        self.view.engine().setNetworkAccessManagerFactory(
            self._qml_network_factory
        )
        self.view.setFormat(format)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.setClearColor(QColor(Theme.Palette.BG_CANVAS))

        quick_window = self.view.quickWindow()
        if quick_window:
            quick_window.setPersistentGraphics(True)
            quick_window.setPersistentSceneGraph(True)

        self.frame_clock = HighRefreshFrameClock(self.view.update, self)
        self.frame_clock.set_screen(self.screen())

        self.thumb_provider = ThumbnailProvider(
            self.node_model, self.service, max_cache_bytes=64 * 1024 * 1024
        )
        self.view.engine().addImageProvider("thumbnails", self.thumb_provider)
        self.view.engine().addImageProvider(
            "media-preview", self.media_preview_provider
        )

        self._theme_bridge = ThemeBridge(self, manager=self._theme_manager)

        self.view.setInitialProperties({
            "appTheme": self._theme_bridge,
            "nodeModel": self.node_model,
            "connectionModel": self.connection_model,
            "nodeViewportModel": self.node_viewport_model,
            "connectionViewportModel": self.connection_viewport_model,
            "canvasController": self.canvas_controller,
            "viewerController": self.viewer_controller,
            "frameClock": self.frame_clock,
        })

        self._qml_canvas_source = resolve_canvas_qml_source()
        if self._qml_canvas_source.scheme() == "qrc":
            self.view.engine().addImportPath("qrc:/qml")
            self.view.engine().addImportPath("qrc:/")

        self.view.setSource(self._qml_canvas_source)

        if self.view.status() == QQuickWidget.Status.Error:
            errors = self.view.errors()
            error_text = "\n".join(err.toString() for err in errors)
            if not error_text:
                error_text = f"Unable to load {self._qml_canvas_source.toString()}"
            print(f"QML Error: {error_text}")
            QMessageBox.critical(self, "QML Error", error_text)
            raise RuntimeError(f"QML load failed: {error_text}")

        root = self.view.rootObject()
        if root is None:
            error_text = f"QML root object is missing: {self._qml_canvas_source.toString()}"
            QMessageBox.critical(self, "QML Error", error_text)
            raise RuntimeError(error_text)
        root.arrayListSuppressionChanged.connect(
            self._on_arraylist_suppression_changed
        )
        root.applicationCloseRequested.connect(
            self._on_application_close_requested
        )

        self.overlay = ArrayListOverlay(self)
        self.overlay.set_snap_status(Config.SNAP_TO_GRID)
        self.overlay.set_zoom_status(1.0)
        self.overlay.stats_clicked.connect(self.open_dashboard)
        self.overlay.raise_()
        self._arraylist_hidden = False
        self._overlay_stats_timer = QTimer(self)
        self._overlay_stats_timer.setSingleShot(True)
        self._overlay_stats_timer.setInterval(150)
        self._overlay_stats_timer.timeout.connect(self._update_overlay_stats)
        self._arraylist_anim = QPropertyAnimation(self.overlay, b"pos", self)
        self._arraylist_anim.setDuration(220)
        self._arraylist_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # A surface handoff can briefly report "not suppressed" while QML
        # closes one panel and opens the next. Delay only the reveal, never
        # the hide, so the overlay cannot flash above an editor.
        self._arraylist_reveal_timer = QTimer(self)
        self._arraylist_reveal_timer.setSingleShot(True)
        self._arraylist_reveal_timer.setInterval(260)
        self._arraylist_reveal_timer.timeout.connect(
            self._reveal_arraylist_if_idle
        )
        self._sync_arraylist_visibility(animate=False)
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

        self._window_overlay_manager = WindowOverlayManager(self.view, self)

    def _connect_overlay_stats_updates(self):
        for signal in (
            self.node_model.rowsInserted,
            self.node_model.rowsRemoved,
            self.node_model.modelReset,
            self.connection_model.rowsInserted,
            self.connection_model.rowsRemoved,
            self.connection_model.modelReset,
        ):
            signal.connect(self._schedule_overlay_stats_update)
        self.node_model.dataChanged.connect(self._on_node_stats_data_changed)
        self._schedule_overlay_stats_update()

    def _on_node_stats_data_changed(self, _top_left, _bottom_right, roles):
        content_roles = {int(NodeRoles.TitleRole), int(NodeRoles.ContentRole)}
        if not roles or content_roles.intersection(int(role) for role in roles):
            self._schedule_overlay_stats_update()

    def _schedule_overlay_stats_update(self, *args):
        timer = getattr(self, "_overlay_stats_timer", None)
        if timer is not None:
            timer.start()

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
        if not hasattr(self, "overlay"):
            return
        if self.operation_coordinator.active_kind == "vacuum":
            return
        stats = self._overlay_stats()
        self.overlay.set_stats(
            stats["node_count"],
            stats["link_count"],
            stats["content_size_label"],
        )

    @Slot(str)
    def _on_initial_load_failed(self, error):
        QMessageBox.critical(
            self, "Database Error", f"Failed to load project data.\n{error}"
        )
        QTimer.singleShot(0, self.close)

    @Slot(bool)
    def _on_arraylist_suppression_changed(self, suppressed):
        if suppressed:
            self._arraylist_reveal_timer.stop()
            self._set_arraylist_hidden(True, animate=False)
            return
        self._arraylist_reveal_timer.start()

    @Slot()
    def _reveal_arraylist_if_idle(self):
        root = self.view.rootObject() if hasattr(self, "view") else None
        if root and bool(root.property("arrayListSuppressed")):
            self._set_arraylist_hidden(True, animate=False)
            return
        self._set_arraylist_hidden(False, animate=True)

    def _sync_arraylist_visibility(self, animate=False):
        root = self.view.rootObject() if hasattr(self, "view") else None
        hidden = bool(root and root.property("arrayListSuppressed"))
        if hidden:
            self._arraylist_reveal_timer.stop()
            self._set_arraylist_hidden(True, animate=False)
        elif animate:
            self._arraylist_reveal_timer.start()
        else:
            self._arraylist_reveal_timer.stop()
            self._set_arraylist_hidden(False, animate=False)

    def _commit_pending_media_edits(self):
        if not self.viewer_controller.active:
            return True
        root = None
        if self.viewer_controller.detached and self._detached_view is not None:
            root = self._detached_view.rootObject()
        if root is None and hasattr(self, "view"):
            root = self.view.rootObject()
        commit = getattr(root, "commitPendingMediaEdits", None) if root else None
        if not callable(commit):
            return True
        try:
            result = commit()
            return result is None or bool(result)
        except Exception as exc:
            self._handle_status_update(
                f"Unable to save the media title: {exc}", "error"
            )
            return False

    @Slot()
    def _on_application_close_requested(self):
        """Finish a close request after the media description guard resolved."""
        if self._application_close_pending:
            return
        self._application_close_pending = True
        # The viewer closes synchronously before this signal is emitted, but
        # defer the actual QMainWindow close until QML signal handlers unwind.
        QTimer.singleShot(0, self._finish_application_close)

    @Slot()
    def _finish_application_close(self):
        self._application_close_pending = False
        self.close()

    @Slot(int)
    def _request_open_media(self, node_id):
        if not self._commit_pending_media_edits():
            root = None
            if self.viewer_controller.detached and self._detached_view is not None:
                root = self._detached_view.rootObject()
            if root is None and hasattr(self, "view"):
                root = self.view.rootObject()
            prompt = getattr(root, "promptDescriptionGuard", None) if root else None
            if callable(prompt) and self.viewer_controller.descriptionDirty:
                prompt(f"switch:{int(node_id)}")
            return
        root = self.view.rootObject() if hasattr(self, "view") else None
        if root is not None and not self.viewer_controller.detached:
            if bool(root.property("hasUnsavedEditorChanges")):
                self._handle_status_update(
                    "Save or cancel the current editor before opening media.",
                    "warning",
                )
                return
            close_editors = getattr(root, "closeEditorsForMedia", None)
            if callable(close_editors):
                close_editors()
        self.viewer_controller.open_media_viewer(int(node_id))

    @Slot()
    def _detach_media_viewer(self):
        if not self.viewer_controller.active:
            return
        if not self._commit_pending_media_edits():
            return
        if self._detached_view is not None:
            self._detached_view.show()
            self._detached_view.raise_()
            self._detached_view.requestActivate()
            return

        self.viewer_controller.set_detached(True)
        detached = None
        try:
            detached = QQuickView(self.view.engine(), None)
            detached.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
            detached.setColor(QColor(Theme.Palette.BG_CANVAS))
            detached.setFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinMaxButtonsHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            detached.setIcon(self.windowIcon())
            detached.setTitle(self._detached_media_title())
            detached.setInitialProperties(
                {
                    "appTheme": self._theme_bridge,
                    "canvasController": self.canvas_controller,
                    "viewerController": self.viewer_controller,
                }
            )
            detached.setSource(resolve_media_viewer_qml_source())
            if detached.status() == QQuickView.Status.Error:
                errors = "\n".join(error.toString() for error in detached.errors())
                raise RuntimeError(errors or "Unable to load media viewer window")
            detached_root = detached.rootObject()
            if detached_root is not None:
                detached_root.applicationCloseRequested.connect(
                    self._on_application_close_requested
                )

            screen = self.screen()
            available = screen.availableGeometry()
            width = max(420, min(960, int(available.width() * 0.80)))
            height = max(340, min(720, int(available.height() * 0.80)))
            detached.setMinimumSize(QSize(min(520, width), min(360, height)))
            detached.resize(QSize(width, height))
            detached.setPosition(
                QPoint(
                    available.x() + (available.width() - width) // 2,
                    available.y() + (available.height() - height) // 2,
                )
            )
            self._detached_view = detached
            detached.show()
            detached.requestActivate()
        except Exception as exc:
            if detached is not None:
                detached.hide()
                detached.setSource(QUrl())
                detached.deleteLater()
            self.viewer_controller.set_detached(False)
            self._handle_status_update(
                f"Unable to detach media viewer: {exc}", "error"
            )

    @Slot()
    def _attach_media_viewer(self):
        if not self.viewer_controller.active:
            self._dispose_detached_view()
            return
        if not self._commit_pending_media_edits():
            if self._detached_view is not None and self.viewer_controller.descriptionDirty:
                root = self._detached_view.rootObject()
                prompt = getattr(root, "promptDescriptionGuard", None) if root else None
                if callable(prompt):
                    prompt("attach")
            return
        root = self.view.rootObject() if hasattr(self, "view") else None
        if root is not None:
            if bool(root.property("hasUnsavedEditorChanges")):
                self._handle_status_update(
                    "Save or cancel the current editor before attaching media.",
                    "warning",
                )
                return
            close_editors = getattr(root, "closeEditorsForMedia", None)
            if callable(close_editors):
                close_editors()
        self.viewer_controller.set_detached(False)
        # The request originates in the detached QML tree. Destroying that
        # tree before its button handler returns can crash inside Qt Quick.
        QTimer.singleShot(0, self._finish_media_viewer_attach)

    @Slot()
    def _finish_media_viewer_attach(self):
        self._dispose_detached_view()
        self.view.setFocus()

    def _on_detached_view_closing(self, close_event=None):
        if self._closing_detached_view:
            return False
        if not self._commit_pending_media_edits():
            if self._detached_view is not None and self.viewer_controller.descriptionDirty:
                root = self._detached_view.rootObject()
                prompt = getattr(root, "promptDescriptionGuard", None) if root else None
                if callable(prompt):
                    prompt("close")
            if close_event is not None:
                close_event.ignore()
            return True

        self._closing_detached_view = True
        try:
            if self.viewer_controller.active and self.viewer_controller.detached:
                self.viewer_controller.close_viewer()
            else:
                self._schedule_detached_view_disposal()
        finally:
            self._closing_detached_view = False
        return False

    @Slot()
    def _schedule_detached_view_disposal(self):
        if self._detached_dispose_scheduled:
            return
        self._detached_dispose_scheduled = True
        # Let any QML signal handler using the detached root unwind first.
        QTimer.singleShot(0, self._dispose_detached_view)

    @Slot()
    def _dispose_detached_view(self):
        self._detached_dispose_scheduled = False
        detached, self._detached_view = self._detached_view, None
        if detached is None:
            return
        already_closing = self._closing_detached_view
        self._closing_detached_view = True
        try:
            detached.hide()
            detached.setSource(QUrl())
            if not already_closing:
                detached.close()
            detached.deleteLater()
        finally:
            self._closing_detached_view = already_closing

    def _detached_media_title(self):
        title = self.viewer_controller.title.strip() or "Media viewer"
        return f"{title} — {Config.APP_NAME}"

    @Slot()
    def _sync_detached_view_title(self):
        if self._detached_view is not None:
            self._detached_view.setTitle(self._detached_media_title())

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
            self._raise_progress_bar()
            return
        if self.overlay.pos() == target:
            self._raise_progress_bar()
            return
        self._arraylist_anim.stop()
        self._arraylist_anim.setStartValue(self.overlay.pos())
        self._arraylist_anim.setEndValue(target)
        self._arraylist_anim.start()
        self._raise_progress_bar()

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
        self._main_menubar = menubar
        file_menu = menubar.addMenu("File")

        act_save = QAction("Save\t[Ctrl+S]", self)
        act_save.setIcon(SvgIcons.get_icon("save"))
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._on_manual_save)
        file_menu.addAction(act_save)

        act_select_all = QAction("Select All\t[Ctrl+A]", self)
        act_select_all.setIcon(SvgIcons.get_icon("select-all"))
        act_select_all.triggered.connect(self._on_select_all)
        file_menu.addAction(act_select_all)

        file_menu.addSeparator()

        act_vacuum = QAction("Vacuum", self)
        act_vacuum.setIcon(SvgIcons.get_icon("database"))
        act_vacuum.triggered.connect(self._on_manual_vacuum)
        file_menu.addAction(act_vacuum)

        act_backup = QAction("Backup", self)
        act_backup.setIcon(SvgIcons.get_icon("backup"))
        act_backup.triggered.connect(self._on_create_backup)
        file_menu.addAction(act_backup)

        self._cancel_operation_action = QAction("Cancel Current Operation", self)
        self._cancel_operation_action.setIcon(SvgIcons.get_icon("close"))
        self._cancel_operation_action.setEnabled(False)
        self._cancel_operation_action.triggered.connect(
            self._cancel_active_operation
        )
        file_menu.addAction(self._cancel_operation_action)

        act_export = QAction("Export…", self)
        act_export.setIcon(SvgIcons.get_icon("export"))
        act_export.triggered.connect(self._on_export)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_change_pwd = QAction("Change Password", self)
        act_change_pwd.setIcon(SvgIcons.get_icon("lock"))
        act_change_pwd.triggered.connect(self._on_change_password)
        file_menu.addAction(act_change_pwd)

        self._theme_action = QAction("Theme…", self)
        self._theme_action.setIcon(SvgIcons.get_icon("palette"))
        self._theme_action.triggered.connect(self.open_theme)
        file_menu.addAction(self._theme_action)


        file_menu.addSeparator()

        act_close = QAction("Exit", self)
        act_close.setIcon(SvgIcons.get_icon("exit"))
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        add_menu = menubar.addMenu("Add")

        act_note = QAction("Note\t[Ctrl+N]", self)
        act_note.setIcon(SvgIcons.get_icon("note"))
        act_note.setShortcut(QKeySequence("Ctrl+N"))
        act_note.triggered.connect(self._on_add_text_node)
        add_menu.addAction(act_note)

        act_img = QAction("Image\t[Ctrl+M]", self)
        act_img.setIcon(SvgIcons.get_icon("image"))
        act_img.setShortcut(QKeySequence("Ctrl+M"))
        act_img.triggered.connect(self._on_add_image_node)
        add_menu.addAction(act_img)

        act_vid = QAction("Video\t[Ctrl+Shift+M]", self)
        act_vid.setIcon(SvgIcons.get_icon("video"))
        act_vid.setShortcut(QKeySequence("Ctrl+Shift+M"))
        act_vid.triggered.connect(self._on_add_video_node)
        add_menu.addAction(act_vid)

        act_audio = QAction("Audio…", self)
        # Reuse the existing playback glyph until a dedicated asset is
        # available; this keeps menu iconography within the current SVG set.
        act_audio.setIcon(SvgIcons.get_icon("play"))
        act_audio.triggered.connect(self._on_add_audio_node)
        add_menu.addAction(act_audio)

        act_frame = QAction("Frame", self)
        act_frame.setIcon(SvgIcons.get_icon("frame"))
        act_frame.triggered.connect(self._on_add_frame)
        add_menu.addAction(act_frame)

        tools_menu = menubar.addMenu("Tools")

        act_search = QAction("Search\t[Ctrl+F]", self)
        act_search.setIcon(SvgIcons.get_icon("search"))
        act_search.triggered.connect(self.open_search)
        tools_menu.addAction(act_search)
        snap_state = "ON" if getattr(Config, "SNAP_TO_GRID", False) else "OFF"
        self.act_snap = QAction(f"Snap to Grid: {snap_state}\t[G]", self)
        self.act_snap.setIcon(SvgIcons.get_icon("grid"))
        self.act_snap.triggered.connect(self.toggle_snap_to_grid)
        tools_menu.addAction(self.act_snap)

        help_menu = menubar.addMenu("Help")
        act_keybinds = QAction("Show All Keybinds", self)
        act_keybinds.setIcon(SvgIcons.get_icon("keyboard"))
        act_keybinds.triggered.connect(self.open_keybinds)
        help_menu.addAction(act_keybinds)

        act_about = QAction("About", self)
        act_about.setIcon(SvgIcons.get_icon("info"))
        act_about.triggered.connect(self.open_about)
        help_menu.addAction(act_about)

        self._theme_icon_actions = (
            (act_save, "save"), (act_select_all, "select-all"),
            (act_vacuum, "database"), (act_backup, "backup"),
            (self._cancel_operation_action, "close"),
            (act_export, "export"),
            (act_change_pwd, "lock"), (self._theme_action, "palette"),
            (act_close, "exit"), (act_note, "note"), (act_img, "image"),
            (act_vid, "video"), (act_audio, "play"), (act_frame, "frame"),
            (act_search, "search"),
            (self.act_snap, "grid"), (act_keybinds, "keyboard"),
            (act_about, "info"),
        )

        self._operation_blocked_actions = [
            act_save,
            act_select_all,
            act_vacuum,
            act_backup,
            act_export,
            act_change_pwd,
            self._theme_action,
            act_note,
            act_img,
            act_vid,
            act_audio,
            act_frame,
            act_search,
            self.act_snap,
        ]

        self._register_menu_canvas_guard(file_menu, add_menu, tools_menu, help_menu)

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
        is_finalizing = str(message or "").lower().startswith(
            ("finalizing", "завершение обработки")
        )
        if is_finalizing:
            if (
                not self.progress_bar.is_active
                or not self.progress_bar.is_indeterminate
            ):
                self.progress_bar.start(message, indeterminate=True)
            else:
                self.progress_bar.set_message(message)
        else:
            self.progress_bar.set_progress(
                value,
                message,
                animate=(
                    self.operation_coordinator.active_kind == "graph_clone"
                ),
            )
        self.progress_label.setText(message)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)
        self._layout_progress_bar()

    def _on_progress_finished(self, message: str):
        self.progress_bar.finish(message)
        self.progress_label.setVisible(False)
        self.status_label.setVisible(True)
        if message:
            self._handle_status_update(message)

    # ── Coordinated Operations ──────────────────────────────────────

    @Slot(bool, str, str, bool)
    def _on_operation_state_changed(self, active, kind, message, blocking):
        enabled = not active
        if hasattr(self, "_cancel_operation_action"):
            self._cancel_operation_action.setEnabled(
                active
                and kind
                in {
                    "backup",
                    "initial_load",
                    "graph_export",
                    "graph_clone",
                    "media_import",
                }
            )
        for action in self._operation_blocked_actions:
            action.setEnabled(enabled)
        if hasattr(self, "_main_menubar"):
            self._main_menubar.setEnabled(not (active and kind == "vacuum"))
        if hasattr(self, "search_shortcut"):
            self.search_shortcut.setEnabled(enabled)
        if hasattr(self, "overlay"):
            self.overlay.setEnabled(enabled)
        if hasattr(self, "view"):
            self.view.setEnabled(not (active and blocking))
        if active and blocking:
            self._window_overlay_manager.acquire("operation")
        else:
            self._window_overlay_manager.release("operation")
        if active:
            if kind == "connection_delete":
                self.progress_label.setVisible(False)
                self.status_label.setVisible(True)
                return
            display_message = message or "Database operation in progress..."
            if kind == "vacuum":
                self.progress_bar.start(
                    "Optimizing database...", indeterminate=True
                )
                display_message = message or "Optimizing database..."
            elif not self.progress_bar.is_active:
                self.progress_bar.start(display_message, indeterminate=True)
            else:
                self.progress_bar.set_message(display_message)
            self.progress_label.setText(display_message)
            self.progress_label.setVisible(True)
            self.status_label.setVisible(False)
            self._layout_progress_bar()
            return
        self.progress_bar.finish()
        self.progress_label.setVisible(False)
        self.status_label.setVisible(True)
        self._schedule_overlay_stats_update()


    # ── Blocking Progress Overlay ───────────────────────────────────

    @Slot(str)
    def show_blocking_progress(self, msg: str):
        self._window_overlay_manager.acquire("legacy-progress")
        self.view.setEnabled(False)
        self.progress_bar.start(msg, indeterminate=True)
        self.progress_label.setText(msg)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)


    @Slot(str)
    def update_blocking_progress(self, msg: str):
        self.progress_bar.start(msg, indeterminate=True)
        self.progress_label.setText(msg)
        self.progress_label.setVisible(True)
        self.status_label.setVisible(False)

    @Slot()
    def hide_blocking_progress(self):
        self._window_overlay_manager.release("legacy-progress")
        self.view.setEnabled(not self.operation_coordinator.is_blocking)
        self.progress_bar.finish()
        self.progress_label.setVisible(False)
        self.status_label.setVisible(True)

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

    def _full_export_filename(self, label, extension):
        db_path = getattr(self.db_conn, "db_path", "Untitled")
        name, _ = os.path.splitext(os.path.basename(db_path))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
        return f"{name}-KryptoNote-{label}-{timestamp}.{extension}"

    def _on_select_all(self):
        self.canvas_controller.select_all_nodes()
        self._defer_modifier_sync()

    def _on_export(self):
        self.canvas_controller.open_export_dialog()

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

    def _on_export_complete_archive(self):
        self.canvas_controller.export_complete_archive(
            self._full_export_filename("Complete", "zip"), protected=False
        )

    def _on_export_protected_archive(self):
        self.canvas_controller.export_complete_archive(
            self._full_export_filename("Protected", "zip"), protected=True
        )

    def _on_export_standalone_html(self):
        self.canvas_controller.export_standalone_html(
            self._full_export_filename("Preview", "html")
        )

    def _on_export_pdf_report(self):
        self.canvas_controller.export_pdf_report(
            self._full_export_filename("Report", "pdf")
        )

    def _on_manual_save(self):
        if self.operation_coordinator.is_busy:
            self._handle_status_update("Cannot save during a database operation", "warning")
            return
        self.service.commit_changes()
        self._update_overlay_stats()
        self._handle_status_update("Saved", "secure")
        self._defer_modifier_sync()

    def _on_manual_vacuum(self):
        token = self.operation_coordinator.begin(
            "vacuum", "Vacuuming database...", blocking=True)
        if token is None:
            self._handle_status_update("Another database operation is active", "warning")
            return
        self._manual_vacuum_token = token
        self._manual_vacuum_running = True

        def on_start():
            self.operation_coordinator.update(token, "Vacuuming database...")

        def on_waiting_lock(attempt):
            message = f"Waiting for database lock... retry {attempt}/8"
            self.operation_coordinator.update(token, message)

        def on_success(result):
            self._manual_vacuum_finished.emit(
                True,
                getattr(result, "message", "Database optimized."),
            )

        def on_error(exc):
            self._manual_vacuum_finished.emit(False, str(exc))

        try:
            self.service.vacuum_database(
                on_start_vacuum=on_start,
                on_waiting_lock=on_waiting_lock,
                on_success=on_success,
                on_error=on_error,
            )
        except Exception as exc:
            if self.operation_coordinator.owns(token):
                self._manual_vacuum_finished.emit(False, str(exc))

    @Slot(bool, str)
    def _on_manual_vacuum_finished(self, success, message):
        self._manual_vacuum_running = False
        token = getattr(self, "_manual_vacuum_token", None)
        self._manual_vacuum_token = None
        if token is not None:
            self.operation_coordinator.finish(token)
        if success:
            self._update_overlay_stats()
            self._handle_status_update(message, "secure")
        else:
            self._handle_status_update(f"VACUUM failed: {message}", "error")

    def _on_create_backup(self):
        if getattr(self, "_backup_executor", None) is not None:
            return
        token = self.operation_coordinator.begin(
            "backup", "Creating backup...", blocking=True)
        if token is None:
            self._handle_status_update("Another database operation is active", "warning")
            return
        db_path = getattr(self.db_conn, "db_path", None)
        if not db_path or db_path == ":memory:":
            self.operation_coordinator.finish(token)
            self._handle_status_update("Backup requires a file database", "error")
            return
        try:
            self.service.commit_changes()
            self._backup_operation_token = token
            self._backup_cancel_event = threading.Event()
            progress_signal = self._backup_progress
            finished_signal = self._backup_finished

            def run_backup():
                success, message = BackupService.create_from_path(
                    db_path,
                    cancel_check=self._backup_cancel_event.is_set,
                    progress_callback=progress_signal.emit,
                )
                finished_signal.emit(success, message)

            self._backup_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            self._backup_executor.submit(run_backup)
        except Exception as exc:
            self._backup_executor = None
            self._backup_cancel_event = None
            self._backup_operation_token = None
            self.operation_coordinator.finish(token)
            self._handle_status_update(f"Backup failed: {exc}", "error")
            QMessageBox.critical(self, "Backup Error", str(exc))

    @Slot(int, int, str)
    def _on_backup_progress(self, current, total, message):
        token = getattr(self, "_backup_operation_token", None)
        if token is not None:
            self.operation_coordinator.update(token, message)
        if total > 0:
            self._on_progress_updated(current / total, message)

    @Slot(bool, str)
    def _on_backup_finished(self, success, message):
        executor = getattr(self, "_backup_executor", None)
        self._backup_executor = None
        self._backup_cancel_event = None
        if executor is not None:
            executor.shutdown(wait=False)
        token = getattr(self, "_backup_operation_token", None)
        self._backup_operation_token = None
        if token is not None:
            self.operation_coordinator.finish(token)
        self._on_progress_finished("Backup created" if success else "Backup stopped")
        if success:
            self._update_overlay_stats()
            self._handle_status_update("Backup created", "secure")
            QMessageBox.information(self, "Backup", message)
        else:
            self._handle_status_update(f"Backup failed: {message}", "error")
            QMessageBox.critical(self, "Backup Error", message)

    def _cancel_backup(self):
        cancel_event = getattr(self, "_backup_cancel_event", None)
        if cancel_event is None:
            return False
        cancel_event.set()
        token = getattr(self, "_backup_operation_token", None)
        if token is not None:
            self.operation_coordinator.update(token, "Cancelling backup safely...")
        return True

    def _cancel_active_operation(self):
        kind = self.operation_coordinator.active_kind
        if kind == "backup":
            self._cancel_backup()
        elif kind == "initial_load":
            self.canvas_controller.cancel_initial_load()
        elif kind == "graph_export":
            self.canvas_controller.cancel_graph_export()
        elif kind == "graph_clone":
            self.canvas_controller.cancel_graph_clone()
        elif kind == "media_import":
            self.canvas_controller.cancel_media_import()

    def _on_add_text_node(self):
        self.canvas_controller.add_text_node()
        self._defer_modifier_sync()

    def _on_add_image_node(self):
        self.canvas_controller.add_media_node("image")
        self._defer_modifier_sync()

    def _on_add_video_node(self):
        self.canvas_controller.add_media_node("video")
        self._defer_modifier_sync()

    def _on_add_audio_node(self):
        self.canvas_controller.add_media_node("audio")
        self._defer_modifier_sync()

    def _on_add_frame(self):
        self.canvas_controller.add_frame()
        self._defer_modifier_sync()

    # ── Dialogs ─────────────────────────────────────────────────────

    def open_search(self):
        if hasattr(self, "view"):
            self.view.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._invoke_qml_root("openSearchPanel")
        self._defer_modifier_sync()

    def open_about(self):
        dialog = AboutDialog(self)
        self._exec_dimmed_dialog("about", dialog)

    def open_keybinds(self):
        dialog = KeybindsDialog(self)
        self._exec_dimmed_dialog("keybinds", dialog)

    def open_dashboard(self):
        self._update_overlay_stats()
        dialog = DashboardDialog(self._dashboard_stats(), self)
        self._exec_dimmed_dialog("dashboard", dialog)

    def open_theme(self):
        dialog = ThemeDialog(
            self,
            self._theme_manager,
            project_store=self.service,
        )
        center_on_parent_window(dialog, self)
        return dialog.exec()

    def _activate_saved_appearance(self):
        profile = self.service.load_project_appearance()
        if profile and profile.get("scope") == "project":
            settings = self._theme_manager.validate(
                profile.get("settings", {})
            )
        else:
            settings = self._theme_manager.committed_settings
        self._theme_manager.preview(settings)

    def _exec_dimmed_dialog(self, owner, dialog):
        self._window_overlay_manager.acquire(owner)
        try:
            center_on_parent_window(dialog, self)
            return dialog.exec()
        finally:
            self._window_overlay_manager.release(owner)

    def _sync_connection_style(self):
        self.connection_model.set_connection_appearance(
            self._theme_manager.settings.connection_style,
            self._theme_manager.settings.connection_curve_formula,
            self._theme_manager.settings.connection_corner_style,
            self._theme_manager.settings.connection_anchor_mode,
        )

    def _apply_runtime_appearance(self, _settings=None):
        self.setStyleSheet(Theme.Styles.get_main_window_qss())
        if getattr(self, "title_bar", None):
            self.title_bar.refresh_theme()
        if hasattr(self, "view"):
            self.view.setClearColor(QColor(Theme.Palette.BG_CANVAS))
        SvgIcons.clear_cache()
        for action, icon_name in getattr(self, "_theme_icon_actions", ()):
            action.setIcon(SvgIcons.get_icon(icon_name))
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(Theme.Styles.get_status_bar_qss())
            self.progress_label.setStyleSheet(
                Theme.Styles.get_status_bar_qss("accent")
            )
            self.coords_label.setStyleSheet(
                Theme.Styles.get_status_bar_qss("coords")
            )
        if hasattr(self, "overlay"):
            self.overlay.update()
        self.update()

    # ── Password Change ─────────────────────────────────────────────

    def _on_change_password(self):
        from ..widgets.dialogs.password_change_dialog import PasswordChangeDialog
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            return
        token = self.operation_coordinator.begin(
            "password_change", "Changing password...", blocking=True)
        if token is None:
            self._handle_status_update("Another database operation is active", "warning")
            return
        self._password_operation_token = token
        self._window_overlay_manager.acquire("password")
        try:
            self._pwd_change_dialog = PasswordChangeDialog(self)
            self._pwd_change_dialog.passwordChangeRequested.connect(
                self._execute_password_change
            )
            self._pwd_change_dialog.cancelRequested.connect(
                self._cancel_password_change
            )
            self._pwd_change_dialog.finished.connect(self._cleanup_pwd_change_dialog)
            center_on_parent_window(self._pwd_change_dialog, self)
            self._pwd_change_dialog.show()
        except Exception:
            self._window_overlay_manager.release("password")
            self.operation_coordinator.finish(token)
            raise

    def _execute_password_change(self, old_pwd, new_pwd, create_backup):
        from ...services.password_change_service import PasswordChangeService

        if getattr(self, "_password_change_executor", None) is not None:
            return

        db_path = getattr(self.db_conn, 'db_path', None)
        if not db_path:
            if self._pwd_change_dialog:
                self._pwd_change_dialog.show_finished(False, "Database is not ready.")
            return

        progress_signal = self._password_change_progress
        finished_signal = self._password_change_finished
        self._password_change_cancel_event = threading.Event()

        def on_progress(current, total, msg):
            progress_signal.emit(current, total, msg)

        def on_finished(success, msg):
            finished_signal.emit(success, msg)

        try:
            self.service.commit_changes()

            def run_password_change():
                if create_backup:
                    on_progress(0, 1, "Creating backup...")
                    success, message = BackupService.create_from_path(
                        db_path,
                        cancel_check=self._password_change_cancel_event.is_set,
                        progress_callback=on_progress,
                    )
                    if not success:
                        on_finished(False, f"Backup failed: {message}")
                        return
                on_progress(0, 1, "Changing password...")
                PasswordChangeService.change_password(
                    db_path,
                    old_pwd,
                    new_pwd,
                    on_progress,
                    on_finished,
                    cancel_check=self._password_change_cancel_event.is_set,
                )

            self._password_change_executor = (
                concurrent.futures.ThreadPoolExecutor(max_workers=1)
            )
            self._password_change_executor.submit(run_password_change)
        except Exception as exc:
            executor = getattr(self, "_password_change_executor", None)
            if executor:
                executor.shutdown(wait=False)
            self._password_change_executor = None
            self._on_password_change_finished(False, str(exc))

    def _cancel_password_change(self):
        cancel_event = getattr(self, "_password_change_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
        token = getattr(self, "_password_operation_token", None)
        if token is not None:
            self.operation_coordinator.update(token, "Cancelling safely...")

    @Slot(int, int, str)
    def _on_password_change_progress(self, current, total, msg):
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            self._pwd_change_dialog.set_changing(True, msg)
        token = getattr(self, "_password_operation_token", None)
        if token is not None:
            self.operation_coordinator.update(token, msg)

    @Slot(bool, str)
    def _on_password_change_finished(self, success, msg):
        if hasattr(self, '_pwd_change_dialog') and self._pwd_change_dialog:
            self._pwd_change_dialog.show_finished(success, msg)
        status_type = "secure" if success else "error"
        prefix = "Password changed" if success else "Password change failed"
        self._handle_status_update(f"{prefix}: {msg}", status_type)
        executor = getattr(self, "_password_change_executor", None)
        if executor:
            executor.shutdown(wait=False)
            self._password_change_executor = None
        self._password_change_cancel_event = None

    def _cleanup_pwd_change_dialog(self, *args):
        self._pwd_change_dialog = None
        self._window_overlay_manager.release("password")
        token = getattr(self, "_password_operation_token", None)
        self._password_operation_token = None
        if token is not None:
            self.operation_coordinator.finish(token)

    # ── Coords ──────────────────────────────────────────────────────

    def update_coords(self, pos):
        self.coords_label.setText(f"X: {int(pos.x())} Y: {int(pos.y())}")

    # ── Key Events ──────────────────────────────────────────────────

    def eventFilter(self, watched, event):
        if (
            watched is getattr(self, "_detached_view", None)
            and event.type() == QEvent.Type.Close
        ):
            return self._on_detached_view_closing(event)
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
        key = event.key()
        if self._is_qml_node_properties_open():
            return True
        if key == Qt.Key.Key_Escape and self._is_qml_tag_picker_open():
            return True
        if self._is_qml_media_viewer_open():
            modifiers = event.modifiers()
            is_s_key = (
                key == Qt.Key.Key_S
                or event.nativeVirtualKey() == 0x53
            )
            return (
                key == Qt.Key.Key_Escape
                or bool(
                    is_s_key
                    and modifiers & Qt.KeyboardModifier.ControlModifier
                )
            )
        editor_open = (
            self._is_qml_text_editor_open()
            or self._is_qml_frame_editor_open()
        )
        if not editor_open:
            return bool(
                self._canvas_has_keyboard_focus()
                and self._canvas_graph_shortcut(event)
            )
        modifiers = event.modifiers()
        is_s_key = key == Qt.Key.Key_S or event.nativeVirtualKey() == 0x53
        if is_s_key and modifiers & Qt.KeyboardModifier.ControlModifier:
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and modifiers & Qt.KeyboardModifier.ControlModifier:
            return True
        if key == Qt.Key.Key_Escape:
            return True
        if (
            self._is_qml_text_editor_open()
            and self._is_search_shortcut(event)
        ):
            return True
        if self._is_app_shortcut_while_editor_open(event):
            return True
        return False

    def _handle_global_key_press(self, event):
        if not self.isActiveWindow() or QApplication.activeModalWidget() is not None:
            return False
        if self.operation_coordinator.is_busy and self._canvas_has_keyboard_focus():
            return True

        key = event.key()
        modifiers = event.modifiers()

        if self._is_qml_node_properties_open():
            if key == Qt.Key.Key_Escape:
                self._invoke_qml_root("closeNodeProperties")
                return True
            return False

        if key == Qt.Key.Key_Escape and self._is_qml_tag_picker_open():
            self._invoke_qml_root("closeTagPicker")
            return True

        if self._is_qml_media_viewer_open():
            if key == Qt.Key.Key_Escape:
                if self._is_qml_media_rename_editing():
                    self._invoke_qml_root("cancelMediaRename")
                else:
                    self._invoke_qml_root("collapseOrCloseMediaViewer")
                return True
            is_s_key = (
                key == Qt.Key.Key_S
                or event.nativeVirtualKey() == 0x53
            )
            if is_s_key and modifiers & Qt.KeyboardModifier.ControlModifier:
                if self.viewer_controller.save_description():
                    self._handle_status_update("Description saved", "secure")
                    self._protect_status(2000)
                self._defer_modifier_sync()
                return True
            return False

        if self._is_qml_frame_editor_open():
            if key == Qt.Key.Key_Escape:
                self._invoke_qml_root("cancelFrameEditor")
                return True
            is_s_key = (
                key == Qt.Key.Key_S
                or event.nativeVirtualKey() == 0x53
            )
            if is_s_key and modifiers & Qt.KeyboardModifier.ControlModifier:
                self._invoke_qml_root("saveFrameEditor")
                self._protect_status(2000)
                return True
            if (
                key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and modifiers & Qt.KeyboardModifier.ControlModifier
            ):
                self._invoke_qml_root("saveFrameEditor")
                self._protect_status(2000)
                return True
            if self._is_app_shortcut_while_editor_open(event):
                return True
            return False

        editor_open = self._is_qml_text_editor_open()
        if editor_open:
            if self._is_qml_search_panel_open() and key == Qt.Key.Key_Escape:
                self._invoke_qml_root("closeSearchPanel")
                return True

            if key == Qt.Key.Key_Escape:
                self._invoke_qml_root("cancelEditor")
                return True

            if self._is_search_shortcut(event):
                self.open_search()
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

        graph_shortcut = self._canvas_graph_shortcut(event)
        if graph_shortcut:
            if not self._is_auto_repeat_event(event):
                {
                    "copy": lambda: self.canvas_controller.copy_nodes(0),
                    "paste": self.canvas_controller.paste_nodes,
                    "system_copy": (
                        lambda: self.canvas_controller.copy_to_system_clipboard(0)
                    ),
                    "system_paste": (
                        self.canvas_controller.paste_from_system_clipboard
                    ),
                    "undo": self.canvas_controller.undo_graph,
                    "redo": self.canvas_controller.redo_graph,
                }[graph_shortcut]()
            return True

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

    @staticmethod
    def _canvas_graph_shortcut(event):
        modifiers = event.modifiers()
        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            return None
        if modifiers & (
            Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return None
        try:
            native = event.nativeVirtualKey()
        except AttributeError:
            native = 0
        key = event.key()
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_C or native == 0x43:
            return "system_copy" if shift else "copy"
        if key == Qt.Key.Key_V or native == 0x56:
            return "system_paste" if shift else "paste"
        if key == Qt.Key.Key_Z or native == 0x5A:
            return "redo" if shift else "undo"
        if (key == Qt.Key.Key_Y or native == 0x59) and not shift:
            return "redo"
        return None

    def _handle_global_key_release(self, event):
        if self._is_qml_media_viewer_open():
            return False
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

        return is_n_key or is_m_key

    @staticmethod
    def _is_search_shortcut(event):
        modifiers = event.modifiers()
        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            return False
        if modifiers & (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return False
        try:
            native = event.nativeVirtualKey()
        except AttributeError:
            native = 0
        return event.key() == Qt.Key.Key_F or native == 0x46

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

    def _is_qml_tag_picker_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isTagPickerOpen"))

    def _is_qml_frame_editor_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isFrameEditorOpen"))

    def _is_qml_node_properties_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isNodePropertiesOpen"))

    def _is_qml_search_panel_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isSearchPanelOpen"))

    def _is_qml_media_viewer_open(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isMediaViewerOpen"))

    def _is_qml_media_rename_editing(self):
        if not hasattr(self, "view"):
            return False
        root = self.view.rootObject()
        return bool(root and root.property("isMediaRenameEditing"))

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
        if self.operation_coordinator.is_busy:
            return
        if (
            self._is_qml_text_editor_open()
            or self._is_qml_frame_editor_open()
            or self._is_qml_node_properties_open()
            or self._is_qml_media_viewer_open()
        ):
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
        if (
            self._is_qml_text_editor_open()
            or self._is_qml_frame_editor_open()
            or self._is_qml_node_properties_open()
            or self._is_qml_media_viewer_open()
        ):
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
            self._sync_arraylist_visibility(animate=False)
            self.overlay.raise_()
        self._layout_progress_bar()

    def _raise_progress_bar(self):
        if hasattr(self, "progress_bar") and self.progress_bar.isVisible():
            self.progress_bar.raise_()

    def _layout_progress_bar(self):
        if not hasattr(self, "progress_bar"):
            return
        sb_y = self.statusBar().y()
        self.progress_bar.setGeometry(
            0,
            sb_y - self.progress_bar.height(),
            self.width(),
            self.progress_bar.height(),
        )
        self._raise_progress_bar()

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
        self._connect_frame_clock_screen()
        self._schedule_qml_render_recovery()

    def _connect_frame_clock_screen(self):
        handle = self.windowHandle()
        previous = getattr(self, "_frame_clock_window_handle", None)
        if handle is not None and handle is not previous:
            if previous is not None:
                try:
                    previous.screenChanged.disconnect(self._sync_frame_clock_screen)
                except (RuntimeError, TypeError):
                    pass
            handle.screenChanged.connect(self._sync_frame_clock_screen)
            self._frame_clock_window_handle = handle
        self._sync_frame_clock_screen(handle.screen() if handle is not None else None)

    def _sync_frame_clock_screen(self, screen=None):
        frame_clock = getattr(self, "frame_clock", None)
        if frame_clock is None:
            return
        if screen is None:
            screen = self.screen()
        frame_clock.set_screen(screen)

    def _sync_window_margins(self):
        self.setContentsMargins(0, 0, 0, 0)

    def _schedule_qml_render_recovery(self):
        if self.windowState() & Qt.WindowState.WindowMinimized:
            return
        QTimer.singleShot(0, self._recover_qml_render)
        QTimer.singleShot(40, self._recover_qml_render)
        QTimer.singleShot(140, self._recover_qml_render)

    def _recover_qml_render(self):
        if not hasattr(self, "view"):
            return
        if self.windowState() & Qt.WindowState.WindowMinimized:
            return
        quick_window = self.view.quickWindow()
        if quick_window:
            quick_window.setPersistentGraphics(True)
            quick_window.setPersistentSceneGraph(True)
        root = self.view.rootObject()
        if root is not None:
            root.update()
        self.view.update()

    # ── Settings Persistence ────────────────────────────────────────

    def read_settings(self):
        return self._window_state_service.restore(self)

    def write_settings(self):
        self._window_state_service.save(self)

    def _close_core_resources(self, wait=True):
        repo = getattr(self, "repo", None)
        if repo is not None:
            try:
                repo.close(wait=wait)
            except Exception:
                pass
        db_conn = getattr(self, "db_conn", None)
        if db_conn is not None:
            try:
                close = getattr(db_conn, "close", None)
                if close is not None:
                    close()
                else:
                    db_conn.conn.close()
            except Exception:
                pass

    def closeEvent(self, event):
        operation_kind = self.operation_coordinator.active_kind
        if operation_kind == "initial_load":
            self.canvas_controller.cancel_initial_load()
            operation_kind = self.operation_coordinator.active_kind
        if (
            self.operation_coordinator.is_busy
            and operation_kind not in {"media_import", "video_import"}
        ):
            event.ignore()
            if operation_kind == "vacuum":
                self._handle_status_update(
                    "Database optimization is still running", "warning"
                )
                return
            message = self.operation_coordinator.active_message or operation_kind
            self._handle_status_update(f"Cannot close: {message}", "warning")
            return

        canvas_controller = getattr(self, "canvas_controller", None)
        if (
            canvas_controller is not None
            and canvas_controller.has_active_synchronous_import()
        ):
            event.ignore()
            self._handle_status_update("Cannot close: image import in progress", "warning")
            return

        if (
            canvas_controller is not None
            and canvas_controller.has_active_background_jobs()
        ):
            self._handle_status_update("Stopping media import...", "warning")
            QApplication.processEvents()
            if not canvas_controller.shutdown_background_jobs():
                event.ignore()
                QMessageBox.warning(
                    self,
                    "Import Still Running",
                    "The current media chunk is still being processed. "
                    "Wait a moment and close the application again.",
                )
                return

        viewer_controller = getattr(self, "viewer_controller", None)
        if viewer_controller is not None and not self._commit_pending_media_edits():
            event.ignore()
            root = None
            if viewer_controller.detached and self._detached_view is not None:
                root = self._detached_view.rootObject()
            if root is None and hasattr(self, "view"):
                root = self.view.rootObject()
            prompt = getattr(root, "promptDescriptionGuard", None) if root else None
            if viewer_controller.descriptionDirty and callable(prompt):
                prompt("application-close")
            elif viewer_controller.descriptionDirty:
                self._handle_status_update(
                    "Save or discard the media description before closing.",
                    "warning",
                )
            else:
                self._handle_status_update(
                    "Save or cancel the current media edit before closing.",
                    "warning",
                )
            return
        self._dispose_detached_view()
        if viewer_controller is not None:
            viewer_controller.shutdown()

        self.write_settings()
        if hasattr(self, "service"):
            try:
                self.service.commit_changes()
            except Exception as e:
                print(f"Error saving changes on close: {e}")
        self._theme_manager.preview(
            self._theme_manager.committed_settings
        )
        self._close_core_resources(wait=True)
        super().closeEvent(event)
