
import os

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

from ...config import Config
from ..services.auto_fit_service import AutoFitService
from ..services.graph_command_service import GraphCommandService
from .delete_controller import DeleteController
from .import_export_controller import ImportExportController


class QmlCanvasController(QObject):
    status_message = Signal(str, str)
    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    snap_to_grid_changed = Signal(bool)
    openTextEditorRequested = Signal(int)
    open_media_viewer_requested = Signal(int)  # node_id
    _video_transition_show_requested = Signal(str)
    _video_transition_update_requested = Signal(str)
    _video_transition_hide_requested = Signal()

    def __init__(self, node_model, connection_model, service, parent=None):
        super().__init__(parent)
        self._node_model = node_model
        self._conn_model = connection_model
        self._service = service
        self._auto_fit_service = AutoFitService()
        self._graph_commands = GraphCommandService(node_model, connection_model, service)

        # --- Delegate controllers ---
        self._delete_ctrl = DeleteController(node_model, connection_model, self._graph_commands, self)
        self._import_export_ctrl = ImportExportController(
            node_model, service, self._auto_fit_media_node, self
        )

        # Wire video overlay signals through to parent window
        self._video_transition_show_requested.connect(self._show_video_transition_overlay)
        self._video_transition_update_requested.connect(self._update_video_transition_overlay)
        self._video_transition_hide_requested.connect(self._hide_video_transition_overlay)

        # Wire delegate signals
        self._delete_ctrl.progress_updated.connect(self.progress_updated)
        self._delete_ctrl.progress_finished.connect(self.progress_finished)
        self._delete_ctrl._video_transition_show_requested.connect(self._video_transition_show_requested)
        self._delete_ctrl._video_transition_update_requested.connect(self._video_transition_update_requested)
        self._delete_ctrl._video_transition_hide_requested.connect(self._video_transition_hide_requested)

        self._import_export_ctrl.status_message.connect(self.status_message)
        self._import_export_ctrl.progress_updated.connect(self.progress_updated)
        self._import_export_ctrl.progress_finished.connect(self.progress_finished)
        self._import_export_ctrl._video_transition_show_requested.connect(self._video_transition_show_requested)
        self._import_export_ctrl._video_transition_update_requested.connect(self._video_transition_update_requested)
        self._import_export_ctrl._video_transition_hide_requested.connect(self._video_transition_hide_requested)

        # Persist position/size changes to DB
        self._node_model.node_position_changed.connect(self._on_position_changed)
        self._node_model.node_size_changed.connect(self._on_size_changed)

    # ── DB Persistence Slots ────────────────────────────────────────

    def _on_position_changed(self, node_id, x, y):
        self._service.update_pos(node_id, x, y)

    def _on_size_changed(self, node_id, w, h):
        self._service.update_size(node_id, w, h)

    @Slot(str, str)
    def set_status_message(self, message, status_type="normal"):
        self.status_message.emit(message, status_type)

    @Slot(int)
    def show_node_properties(self, node_id):
        lines = self._node_model.get_node_metadata_lines(node_id)
        if not lines:
            return
        parent = self.parent()
        if parent and hasattr(parent, "show_node_properties_overlay"):
            parent.show_node_properties_overlay(lines)
        else:
            QMessageBox.information(None, "Node Properties", "\n".join(lines))

    # ── Loading ─────────────────────────────────────────────────────

    def load_from_db(self):
        self.progress_updated.emit(0.0, "Decrypting database...")
        QApplication.processEvents()

        self._node_model.load_from_service(self._service)
        self.progress_updated.emit(0.85, "Loading connections...")
        QApplication.processEvents()

        self._conn_model.load_from_service(self._service)
        self.progress_finished.emit("Ready")

    # ── Node Creation ───────────────────────────────────────────────

    open_new_text_editor_requested = Signal()

    @Slot()
    def add_text_node(self):
        center = self.get_viewport_center()
        x = center[0] - Config.NODE_DEFAULT_WIDTH / 2
        y = center[1] - Config.NODE_DEFAULT_HEIGHT / 2
        node_id = self.create_text_node_at(
            x, y, "", "", 14, 10,
            auto_fit_pending=True,
            draft=True,
            auto_fit_now=False,
        )
        self._node_model.clear_selection()
        self._node_model.set_selected(node_id, True)
        self.openTextEditorRequested.emit(node_id)

    def create_text_node_at(
            self, x, y, title, content, title_size=14, text_size=10,
            auto_fit_pending=False, draft=False, auto_fit_now=True
    ):
        """Actually create the node after editor confirms."""
        w, h = Config.NODE_DEFAULT_WIDTH, Config.NODE_DEFAULT_HEIGHT
        rid = self._service.add_item(
            "text", x, y, w, h, title=title, text=content,
            title_size=title_size, text_size=text_size
        )
        self._node_model.add_node(
            rid, "text", x, y, w, h,
            title=title, content=content,
            title_size=title_size, text_size=text_size,
            auto_fit_pending=auto_fit_pending,
            draft=draft,
        )
        if auto_fit_now:
            self._auto_fit_text_node(rid)
        return rid

    # ── Media (delegated) ───────────────────────────────────────────

    @Slot(str)
    def add_media_node(self, mtype):
        center = self.get_viewport_center()
        self._import_export_ctrl.add_media_node(mtype, viewport_center=center)

    @Slot(list, float, float)
    def handle_dropped_files(self, file_urls, drop_x, drop_y):
        """Handle files dropped onto the canvas DropArea."""
        from PySide6.QtCore import QUrl
        paths = []
        for url in file_urls:
            if isinstance(url, QUrl):
                local = url.toLocalFile()
            else:
                local = QUrl(str(url)).toLocalFile()
            if local:
                paths.append(local)
        if paths:
            self._import_export_ctrl.import_files_by_paths(paths, drop_x, drop_y)

    # ── Delete (delegated) ──────────────────────────────────────────

    @Slot(int)
    def request_animated_delete(self, node_id):
        self._delete_ctrl.request_animated_delete(node_id)

    @Slot(int)
    def perform_delete(self, node_id):
        self._delete_ctrl.perform_delete(node_id)

    @Slot(int)
    def delete_node(self, node_id):
        """Legacy direct delete (no animation)."""
        self._delete_ctrl.perform_delete(node_id)

    @Slot()
    def delete_selected_nodes(self):
        self._delete_ctrl.delete_selected_nodes()

    @Slot()
    def delete_selected_nodes_without_confirmation(self):
        self._delete_ctrl.delete_selected_nodes_without_confirmation()

    @Slot()
    def select_all_nodes(self):
        self._node_model.select_all()
        self.status_message.emit("Selected all nodes.", "accent")

    @Slot()
    def clear_selection(self):
        self._node_model.clear_selection()
        self.status_message.emit("Selection cleared.", "normal")

    # ── Text Editing ────────────────────────────────────────────────

    @Slot(int, str, str)
    @Slot(int, str, str, int, int)
    def save_text_content(self, node_id, title, content, title_size=14, text_size=10):
        self._service.update_text_content(node_id, title, content, title_size, text_size)
        self._node_model.update_text_content(node_id, title, content, title_size, text_size)
        node = self._node_model.get_node_data(node_id)
        should_auto_fit = bool(node and node.get("auto_fit_pending"))
        self._node_model.set_draft(node_id, False)
        self._node_model.set_auto_fit_pending(node_id, False)
        if should_auto_fit:
            self._auto_fit_text_node(node_id)
        display = title.strip() if title and title.strip() else "Untitled"
        if len(display) > 32:
            display = display[:29] + "..."
        self.status_message.emit(f"Saved: {display}", "accent")

    @Slot(int, str, str, int, int)
    def preview_text_content(self, node_id, title, content, title_size=14, text_size=10):
        self._node_model.update_text_content(
            node_id, title, content, title_size, text_size, update_timestamp=False
        )

    @Slot(int, result=list)
    def get_text_editor_data(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node or node.get("type") != "text":
            return []
        return [
            node.get("title", ""),
            node.get("content", ""),
            int(node.get("title_size") or 14),
            int(node.get("text_size") or 10),
            bool(node.get("draft")),
            node.get("created_at_display", "-"),
            node.get("updated_at_display", "-"),
        ]

    @Slot(int, str)
    def rename_node(self, node_id, title):
        if not title:
            from PySide6.QtWidgets import QInputDialog
            node = self._node_model.get_node_data(node_id)
            old_title = node["title"] if node else ""
            new_title, ok = QInputDialog.getText(
                None, "Rename Node", "Enter new title:",
                QLineEdit.EchoMode.Normal, old_title
            )
            if not ok:
                return
            title = new_title

        self._service.update_item_title(node_id, title)
        self._node_model.update_title(node_id, title)

    # ── Links ───────────────────────────────────────────────────────

    @Slot(int)
    def handle_link_click(self, node_id):
        status = self._graph_commands.handle_link_click(node_id)
        if status:
            self.status_message.emit(status[0], status[1])

    @Slot(int)
    def delete_connection(self, conn_id):
        self._graph_commands.delete_connection(conn_id)

    @Slot(int)
    def perform_delete_connection(self, conn_id):
        self._graph_commands.delete_connection_after_animation(conn_id)
        self.status_message.emit("Link deleted.", "normal")

    @Slot()
    def toggle_link_mode_off(self):
        self._graph_commands.toggle_link_mode_off()

    @Slot()
    def commit_changes(self):
        self._graph_commands.commit_pending()

    # ── Open Editor/Viewer ──────────────────────────────────────────

    @Slot(int)
    def request_open_editor(self, node_id):
        data = self._node_model.get_node_data(node_id)
        if data and data["type"] == "text":
            self.openTextEditorRequested.emit(node_id)
        elif data and data["type"] in ("image", "video"):
            self.open_media_viewer_requested.emit(node_id)

    # ── Export (delegated) ──────────────────────────────────────────

    @Slot(int)
    def export_node_to_disk(self, node_id):
        self._import_export_ctrl.export_node_to_disk(node_id)

    def export_to_markdown(self, default_filename="kryptonote_export.md", selected_only=False):
        selected_ids = self._node_model.get_selected_ids() if selected_only else None
        self._import_export_ctrl.export_to_markdown(
            default_filename,
            selected_only=selected_only,
            selected_ids=selected_ids,
        )

    # ── Viewport & Snap ─────────────────────────────────────────────

    @Slot(float, float)
    def report_mouse_position(self, x: float, y: float):
        if hasattr(self.parent(), "update_coords"):
            from PySide6.QtCore import QPointF
            self.parent().update_coords(QPointF(x, y))

    @Slot(float)
    def report_zoom(self, scale: float):
        """Called from QML when zoom changes — updates overlay."""
        if hasattr(self.parent(), "overlay"):
            self.parent().overlay.set_zoom_status(scale)

    @Slot(result=list)
    def get_viewport_center(self):
        """Return [x, y] of viewport center in content coordinates."""
        try:
            root = self.parent().view.rootObject()
            if root:
                cx = root.property("width") / 2
                cy = root.property("height") / 2
                scale = root.property("contentScale") or 1.0
                clx = root.property("_contentLayerX")
                cly = root.property("_contentLayerY")
                content_layer_x = clx if clx is not None else 0
                content_layer_y = cly if cly is not None else 0
                x = (cx - content_layer_x) / scale
                y = (cy - content_layer_y) / scale
                return [x, y]
        except Exception:
            pass
        return [0.0, 0.0]

    @Property(bool, notify=snap_to_grid_changed)
    def snap_to_grid(self):
        return Config.SNAP_TO_GRID

    @Slot()
    def toggle_snap_to_grid(self):
        parent = self.parent()
        if parent and hasattr(parent, "toggle_snap_to_grid"):
            parent.toggle_snap_to_grid()

    # ── Auto-Fit ────────────────────────────────────────────────────

    @Slot(int)
    def auto_fit_node(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return
        if node["type"] == "text":
            self._auto_fit_text_node(node_id)
        elif node["type"] in ("image", "video"):
            self._auto_fit_media_node_from_qimage(node_id, node.get("thumbnail"))

    def _auto_fit_text_node(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return
        new_w, new_h = self._auto_fit_service.fit_text(node)
        self._node_model.update_size(node_id, float(new_w), float(new_h))
        self._service.update_size(node_id, int(new_w), int(new_h))

    def _auto_fit_media_node(self, node_id, thumb_bytes):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return
        thumbnail = thumb_bytes or node.get("thumbnail")
        self._auto_fit_media_node_from_qimage(node_id, thumbnail)

    def _auto_fit_media_node_from_qimage(self, node_id, thumb_image):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return
        new_w, new_h = self._auto_fit_service.fit_media(node, thumb_image)
        self._node_model.update_size(node_id, float(new_w), float(new_h))
        self._service.update_size(node_id, int(new_w), int(new_h))

    # ── Video Overlay Helpers ───────────────────────────────────────

    def _show_video_transition_overlay(self, message="Processing video..."):
        parent = self.parent()
        if parent and hasattr(parent, "show_video_transition_overlay"):
            parent.show_video_transition_overlay(message)

    def _update_video_transition_overlay(self, message="Processing video..."):
        parent = self.parent()
        if parent and hasattr(parent, "update_video_transition_overlay"):
            parent.update_video_transition_overlay(message)

    def _hide_video_transition_overlay(self):
        parent = self.parent()
        if parent and hasattr(parent, "hide_video_transition_overlay"):
            parent.hide_video_transition_overlay()
