from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLineEdit, QMessageBox

from ...config import Config
from ..theme.palette import Palette
from ..services.auto_fit_service import AutoFitService
from ..services.graph_command_service import GraphCommandService
from ..services.operation_coordinator import OperationCoordinator
from .delete_controller import DeleteController
from .import_export_controller import ImportExportController


class QmlCanvasController(QObject):
    status_message = Signal(str, str)
    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    snap_to_grid_changed = Signal(bool)
    openTextEditorRequested = Signal(int)
    openFrameEditorRequested = Signal(int)
    open_media_viewer_requested = Signal(int)  # node_id
    initial_load_failed = Signal(str)
    initial_load_finished = Signal()

    def __init__(self, node_model, connection_model, service, parent=None,
                 operation_coordinator=None):
        super().__init__(parent)
        self._node_model = node_model
        self._conn_model = connection_model
        self._service = service
        self._auto_fit_service = AutoFitService()
        self._graph_commands = GraphCommandService(node_model, connection_model, service)
        self._operations = operation_coordinator or OperationCoordinator(self)
        self._connection_delete_token = None
        self._pending_connection_deletes = set()
        self._initial_load_timer = QTimer(self)
        self._initial_load_timer.setInterval(0)
        self._initial_load_timer.timeout.connect(self._load_next_batch)
        self._initial_load_token = None
        self._initial_load_phase = "idle"
        self._initial_load_iterator = None
        self._initial_tags_by_item = {}
        self._initial_loaded = 0
        self._initial_total = 0

        # --- Delegate controllers ---
        self._delete_ctrl = DeleteController(
            node_model,
            connection_model,
            self._graph_commands,
            self,
            operation_coordinator=self._operations,
        )
        self._import_export_ctrl = ImportExportController(
            node_model, service, self._auto_fit_media_node, self,
            operation_coordinator=self._operations,
        )


        # Wire delegate signals
        self._delete_ctrl.progress_updated.connect(self.progress_updated)
        self._delete_ctrl.progress_finished.connect(self.progress_finished)
        self._delete_ctrl.status_message.connect(self.status_message)

        self._import_export_ctrl.status_message.connect(self.status_message)
        self._import_export_ctrl.progress_updated.connect(self.progress_updated)
        self._import_export_ctrl.progress_finished.connect(self.progress_finished)

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
        """Load DTOs in event-loop-sized batches so the window can appear first."""
        if self._initial_load_timer.isActive():
            return
        token = self._operations.begin(
            "initial_load", "Decrypting database...", blocking=False
        )
        if token is None:
            return
        self._initial_load_token = token
        try:
            self._service.ensure_tag("starred", Palette.TAG_STARRED)
            self._initial_tags_by_item = self._service.get_item_tags_map()
            item_total = self._service.get_item_count()
            connection_total = self._service.get_connection_count()
            self._initial_total = max(1, item_total + connection_total)
            self._initial_loaded = 0
            self._node_model.begin_incremental_load()
            self._conn_model.begin_incremental_load()
            self._initial_load_iterator = self._service.iter_item_batches(
                200, include_thumbnails=False
            )
            self._initial_load_phase = "nodes"
            self.progress_updated.emit(0.0, "Decrypting database...")
            self._initial_load_timer.start()
        except Exception as exc:
            self._fail_initial_load(exc)

    def _load_next_batch(self):
        try:
            if self._initial_load_phase == "nodes":
                try:
                    batch = next(self._initial_load_iterator)
                except StopIteration:
                    self._initial_load_iterator = (
                        self._service.iter_connection_batches(200)
                    )
                    self._initial_load_phase = "connections"
                    self.progress_updated.emit(
                        self._initial_loaded / self._initial_total,
                        "Loading connections...",
                    )
                    return
                self._node_model.append_item_batch(
                    batch, self._initial_tags_by_item
                )
                self._initial_loaded += len(batch)
                self.progress_updated.emit(
                    self._initial_loaded / self._initial_total,
                    "Decrypting database...",
                )
                return

            if self._initial_load_phase == "connections":
                try:
                    batch = next(self._initial_load_iterator)
                except StopIteration:
                    self._finish_initial_load()
                    return
                self._conn_model.append_connection_batch(batch)
                self._initial_loaded += len(batch)
                self.progress_updated.emit(
                    self._initial_loaded / self._initial_total,
                    "Loading connections...",
                )
        except Exception as exc:
            self._fail_initial_load(exc)

    def _finish_initial_load(self):
        self._initial_load_timer.stop()
        self._close_initial_load_iterator()
        self._initial_load_phase = "idle"
        token = self._initial_load_token
        self._initial_load_token = None
        if token is not None:
            self._operations.finish(token)
        self.progress_finished.emit("Ready")
        self.initial_load_finished.emit()

    def _fail_initial_load(self, error):
        self._initial_load_timer.stop()
        self._close_initial_load_iterator()
        self._initial_load_phase = "idle"
        token = self._initial_load_token
        self._initial_load_token = None
        if token is not None:
            self._operations.finish(token)
        self.progress_finished.emit("Load failed")
        self.initial_load_failed.emit(str(error))

    def cancel_initial_load(self):
        if self._initial_load_phase == "idle":
            return False
        self._initial_load_timer.stop()
        self._close_initial_load_iterator()
        self._initial_load_phase = "idle"
        token = self._initial_load_token
        self._initial_load_token = None
        if token is not None:
            self._operations.finish(token)
        self.progress_finished.emit("Loading cancelled")
        return True

    def _close_initial_load_iterator(self):
        iterator = self._initial_load_iterator
        self._initial_load_iterator = None
        close = getattr(iterator, "close", None)
        if close is not None:
            close()

    # ── Tags ───────────────────────────────────────────────────────

    @Slot(result=list)
    def get_all_tags(self):
        return [
            {"id": tag.id, "name": tag.name, "color": tag.color}
            for tag in self._service.get_all_tags()
        ]

    @Slot(int, result=list)
    def get_node_tags(self, node_id):
        node = self._node_model.get_node_data(node_id)
        return list(node.get("tags", [])) if node else []

    @Slot(str, str, result=int)
    def create_tag(self, name, color):
        parsed_color = QColor(color)
        if not parsed_color.isValid():
            self.status_message.emit("Invalid tag color.", "error")
            return 0
        try:
            tag_id = self._service.ensure_tag(name, parsed_color.name())
        except ValueError as exc:
            self.status_message.emit(str(exc), "error")
            return 0
        self.status_message.emit(f"Tag ready: @{name.strip().lstrip('@').casefold()}", "accent")
        return tag_id

    @Slot(int, str, str, result=bool)
    def update_tag(self, tag_id, name, color):
        parsed_color = QColor(color)
        if not parsed_color.isValid():
            self.status_message.emit("Invalid tag color.", "error")
            return False
        normalized = name.strip().lstrip("@").casefold()
        try:
            self._service.update_tag(tag_id, normalized, parsed_color.name())
        except ValueError as exc:
            self.status_message.emit(str(exc), "error")
            return False
        self._node_model.update_tag_definition(tag_id, normalized, parsed_color.name())
        self.status_message.emit(f"Updated tag: @{normalized}", "accent")
        return True

    @Slot(int, int, bool)
    def set_node_tag(self, node_id, tag_id, enabled):
        try:
            self._service.set_item_tag(node_id, tag_id, enabled)
        except Exception as exc:
            self.status_message.emit(f"Tag update failed: {exc}", "error")
            return
        tags_map = self._service.get_item_tags_map()
        tags = [
            {"id": tag.id, "name": tag.name, "color": tag.color}
            for tag in tags_map.get(node_id, [])
        ]
        self._node_model.set_node_tags(node_id, tags)

    @Slot(int, list)
    def set_node_tag_order(self, node_id, tag_ids):
        self._service.set_item_tag_order(node_id, [int(tag_id) for tag_id in tag_ids])
        tags_map = self._service.get_item_tags_map()
        tags = [
            {"id": tag.id, "name": tag.name, "color": tag.color}
            for tag in tags_map.get(node_id, [])
        ]
        self._node_model.set_node_tags(node_id, tags)

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

    @Slot()
    def add_frame(self):
        center = self.get_viewport_center()
        width = Config.FRAME_DEFAULT_WIDTH
        height = Config.FRAME_DEFAULT_HEIGHT
        x = center[0] - width / 2
        y = center[1] - height / 2
        frame_id = self._service.add_item(
            "frame", x, y, width, height, title="New Frame",
            frame_locked=False,
            frame_color="",
            frame_opacity=Config.FRAME_DEFAULT_OPACITY,
        )
        self._node_model.add_node(
            frame_id, "frame", x, y, width, height, title="New Frame",
            frame_locked=False,
            frame_color="",
            frame_opacity=Config.FRAME_DEFAULT_OPACITY,
        )
        self._node_model.clear_selection()
        self._node_model.set_selected(frame_id, True)
        self.status_message.emit(
            "Frame added unlocked. Lock it to move contained nodes.", "accent"
        )

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

    def has_active_synchronous_import(self):
        return self._import_export_ctrl.has_active_synchronous_import()

    def has_active_background_jobs(self):
        return self._import_export_ctrl.has_active_background_jobs()

    def shutdown_background_jobs(self, timeout_ms=15000):
        return self._import_export_ctrl.shutdown_background_jobs(timeout_ms)

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
            is_frame = bool(node and node.get("type") == "frame")
            new_title, ok = QInputDialog.getText(
                None,
                "Rename Frame" if is_frame else "Rename Node",
                "Enter frame title:" if is_frame else "Enter new title:",
                QLineEdit.EchoMode.Normal, old_title
            )
            if not ok:
                return
            title = new_title

        self._service.update_item_title(node_id, title)
        self._node_model.update_title(node_id, title)

    @Slot(int)
    def select_frame_contents(self, frame_id):
        count = self._node_model.select_frame_contents(frame_id)
        suffix = "node" if count == 1 else "nodes"
        self.status_message.emit(
            f"Selected frame and {count} contained {suffix}.", "accent"
        )

    @Slot(int, result=bool)
    def is_frame_locked(self, frame_id):
        frame = self._node_model.get_node_data(frame_id)
        return bool(
            frame
            and frame.get("type") == "frame"
            and frame.get("frame_locked", False)
        )

    @Slot(int, result=bool)
    def toggle_frame_locked(self, frame_id):
        frame = self._node_model.get_node_data(frame_id)
        if not frame or frame.get("type") != "frame":
            return False
        locked = not bool(frame.get("frame_locked", False))
        try:
            self._service.update_frame_locked(frame_id, locked)
        except (ValueError, RuntimeError) as exc:
            self.status_message.emit(f"Frame lock failed: {exc}", "error")
            return bool(frame.get("frame_locked", False))
        self._node_model.set_frame_locked(frame_id, locked)
        self.status_message.emit(
            "Frame locked. Contained nodes will move with it."
            if locked else
            "Frame unlocked. It now moves independently.",
            "accent",
        )
        return locked

    @Slot(int, result=list)
    def get_frame_editor_data(self, frame_id):
        frame = self._node_model.get_node_data(frame_id)
        if not frame or frame.get("type") != "frame":
            return []
        return [
            frame.get("title", ""),
            frame.get("frame_color", ""),
            float(
                frame.get(
                    "frame_opacity", Config.FRAME_DEFAULT_OPACITY
                )
            ),
            float(Config.FRAME_DEFAULT_OPACITY),
        ]

    @staticmethod
    def _normalized_frame_appearance(frame_color, frame_opacity):
        normalized_color = ""
        if frame_color:
            parsed_color = QColor(frame_color)
            if not parsed_color.isValid():
                raise ValueError("Invalid frame color.")
            normalized_color = parsed_color.name()
        opacity = max(0.0, min(1.0, float(frame_opacity)))
        return normalized_color, opacity

    @Slot(int, str, str, float)
    def preview_frame_properties(
            self, frame_id, title, frame_color, frame_opacity
    ):
        frame = self._node_model.get_node_data(frame_id)
        if not frame or frame.get("type") != "frame":
            return
        try:
            color, opacity = self._normalized_frame_appearance(
                frame_color, frame_opacity
            )
        except (TypeError, ValueError):
            return
        self._node_model.update_frame_properties(
            frame_id,
            title,
            color,
            opacity,
            update_timestamp=False,
        )

    @Slot(int, str, str, float, result=bool)
    def save_frame_properties(
            self, frame_id, title, frame_color, frame_opacity
    ):
        try:
            color, opacity = self._normalized_frame_appearance(
                frame_color, frame_opacity
            )
            self._service.update_frame_properties(
                frame_id, title, color, opacity
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            self.status_message.emit(
                f"Frame update failed: {exc}", "error"
            )
            return False
        self._node_model.update_frame_properties(
            frame_id, title, color, opacity
        )
        self.status_message.emit("Frame updated.", "accent")
        return True

    # ── Links ───────────────────────────────────────────────────────

    @Slot(int)
    def handle_link_click(self, node_id):
        status = self._graph_commands.handle_link_click(node_id)
        if status:
            self.status_message.emit(status[0], status[1])

    @Slot(int, result=bool)
    def delete_connection(self, conn_id):
        conn_id = int(conn_id)
        if conn_id in self._pending_connection_deletes:
            return True

        if self._connection_delete_token is None:
            token = self._operations.begin(
                "connection_delete", "Deleting link...", blocking=False
            )
            if token is None:
                self.status_message.emit(
                    "Another database operation is active.", "warning"
                )
                return False
            self._connection_delete_token = token

        try:
            if not self._graph_commands.delete_connection(conn_id):
                self._finish_connection_delete(conn_id)
                self.status_message.emit("Link no longer exists.", "warning")
                return False
            self._pending_connection_deletes.add(conn_id)
            return True
        except Exception as exc:
            self._finish_connection_delete(conn_id)
            self.status_message.emit(f"Delete failed: {exc}", "error")
            return False

    @Slot(int)
    def perform_delete_connection(self, conn_id):
        try:
            self._graph_commands.delete_connection_after_animation(conn_id)
            self.status_message.emit("Link deleted.", "normal")
        except Exception as exc:
            self._conn_model.set_deleting(conn_id, False, finalize=True)
            self.status_message.emit(f"Delete failed: {exc}", "error")
        finally:
            self._finish_connection_delete(conn_id)

    def _finish_connection_delete(self, conn_id=None):
        if conn_id is not None:
            self._pending_connection_deletes.discard(int(conn_id))
        if self._pending_connection_deletes:
            return
        token = self._connection_delete_token
        self._connection_delete_token = None
        if token is not None:
            self._operations.finish(token)


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
        elif data and data["type"] == "frame":
            self.openFrameEditorRequested.emit(node_id)

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

    def export_complete_archive(self, default_filename, protected=False):
        self._import_export_ctrl.export_complete_archive(
            default_filename, protected=protected
        )

    def export_standalone_html(self, default_filename):
        self._import_export_ctrl.export_standalone_html(default_filename)

    def export_pdf_report(self, default_filename):
        self._import_export_ctrl.export_pdf_report(default_filename)

    def open_export_dialog(self):
        self._import_export_ctrl.open_export_dialog()

    def cancel_graph_export(self):
        return self._import_export_ctrl.cancel_graph_export()

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
