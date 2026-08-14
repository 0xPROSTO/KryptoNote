import re

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QIODevice,
    QMimeData,
    QObject,
    Signal,
    Slot,
    Property,
    QTimer,
    QThread,
    Qt,
)
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QLineEdit

from ...config import Config
from ..theme.palette import Palette
from ..services.auto_fit_service import AutoFitService
from ..services.graph_command_service import GraphCommandService
from ..services.graph_clone_worker import GraphCloneWorker
from ..services.operation_coordinator import OperationCoordinator
from .delete_controller import DeleteController
from .import_export_controller import ImportExportController


class QmlCanvasController(QObject):
    _SYSTEM_MIXED_MIME = "application/x-kryptonote-mixed-selection"
    _SYSTEM_TITLE_RE = re.compile(r"^\s*##[ \t]+(.+?)\s*$")

    status_message = Signal(str, str)
    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    snap_to_grid_changed = Signal(bool)
    openTextEditorRequested = Signal(int)
    openFrameEditorRequested = Signal(int)
    openNodePropertiesRequested = Signal(int)
    open_media_viewer_requested = Signal(int)  # node_id
    initial_load_failed = Signal(str)
    initial_load_finished = Signal()
    _graph_delete_finished = Signal(object, object, str)

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
        self._last_graph_copy_summary = None
        self._graph_paste_count = 0
        self._graph_history = []
        self._graph_redo = []
        self._pending_graph_history = None
        self._graph_clone_thread = None
        self._graph_clone_worker = None
        self._graph_clone_token = None
        self._graph_delete_token = None
        self._pending_graph_clone = None
        self._graph_delete_finished.connect(self._on_graph_delete_finished)

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
        self._node_model.node_positions_changed.connect(self._on_positions_changed)
        self._node_model.node_size_changed.connect(self._on_size_changed)

    # ── DB Persistence Slots ────────────────────────────────────────

    def _on_position_changed(self, node_id, x, y):
        self._service.update_pos(node_id, x, y)

    def _on_positions_changed(self, positions):
        self._service.update_positions(positions)

    def _on_size_changed(self, node_id, w, h):
        self._service.update_size(node_id, w, h)

    @Slot(str, str)
    def set_status_message(self, message, status_type="normal"):
        self.status_message.emit(message, status_type)

    @Slot(int)
    def show_node_properties(self, node_id):
        if not self._node_model.get_node_data(node_id):
            return
        self.openNodePropertiesRequested.emit(node_id)

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
            tags = [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self._service.get_item_tags(node_id)
            ]
            self._node_model.set_node_tags(node_id, tags)
        except Exception as exc:
            self.status_message.emit(f"Tag update failed: {exc}", "error")

    @Slot(int, list)
    def set_node_tag_order(self, node_id, tag_ids):
        try:
            self._service.set_item_tag_order(
                node_id, [int(tag_id) for tag_id in tag_ids]
            )
            tags = [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in self._service.get_item_tags(node_id)
            ]
            self._node_model.set_node_tags(node_id, tags)
        except Exception as exc:
            self.status_message.emit(
                f"Tag reorder failed: {exc}", "error"
            )

    # ── Node Creation ───────────────────────────────────────────────

    open_new_text_editor_requested = Signal()

    @Slot()
    def add_text_node(self):
        center = self.get_viewport_center()
        self.add_text_node_at(center[0], center[1])

    @Slot(float, float)
    def add_text_node_at(self, center_x, center_y):
        x = float(center_x) - Config.NODE_DEFAULT_WIDTH / 2
        y = float(center_y) - Config.NODE_DEFAULT_HEIGHT / 2
        node_id = self.create_text_node_at(
            x, y, "", "", 14, 10,
            auto_fit_pending=True,
            draft=True,
            auto_fit_now=False,
        )
        self._node_model.set_selection([node_id])
        self.openTextEditorRequested.emit(node_id)

    def create_text_node_at(
            self, x, y, title, content, title_size=14, text_size=10,
            auto_fit_pending=False, draft=False, auto_fit_now=True,
            commit=True, created_ids=None,
    ):
        """Actually create the node after editor confirms."""
        w, h = Config.NODE_DEFAULT_WIDTH, Config.NODE_DEFAULT_HEIGHT
        rid = self._service.add_item(
            "text", x, y, w, h, title=title, text=content,
            title_size=title_size, text_size=text_size, commit=commit,
        )
        if created_ids is not None:
            created_ids.append(rid)
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
        self.add_frame_at(center[0], center[1])

    @Slot(float, float)
    def add_frame_at(self, center_x, center_y):
        width = Config.FRAME_DEFAULT_WIDTH
        height = Config.FRAME_DEFAULT_HEIGHT
        x = float(center_x) - width / 2
        y = float(center_y) - height / 2
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
        self._node_model.set_selection([frame_id])
        self.status_message.emit(
            "Frame added unlocked. Lock it to move contained nodes.", "accent"
        )

    # ── Media (delegated) ───────────────────────────────────────────

    @Slot(str)
    def add_media_node(self, mtype):
        center = self.get_viewport_center()
        self._import_export_ctrl.add_media_node(mtype, viewport_center=center)

    @Slot(str, float, float)
    def add_media_node_at(self, mtype, center_x, center_y):
        self._import_export_ctrl.add_media_node(
            mtype,
            viewport_center=[float(center_x), float(center_y)],
        )

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
        return (
            self._import_export_ctrl.has_active_background_jobs()
            or self.has_active_graph_clone()
        )

    def cancel_media_import(self):
        return self._import_export_ctrl.cancel_media_import()

    def shutdown_background_jobs(self, timeout_ms=15000):
        graph_stopped = True
        thread = self._graph_clone_thread
        if thread is not None:
            try:
                if thread.isRunning():
                    thread.requestInterruption()
                    thread.quit()
                    graph_stopped = bool(thread.wait(timeout_ms))
            except RuntimeError:
                graph_stopped = True
            if graph_stopped:
                self._clear_active_graph_clone(thread, report_unexpected=False)
        delegated_stopped = self._import_export_ctrl.shutdown_background_jobs(
            timeout_ms
        )
        return graph_stopped and delegated_stopped

    def has_active_graph_clone(self):
        thread = self._graph_clone_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._clear_active_graph_clone(thread)
            return False

    @Slot(result=bool)
    def cancel_graph_clone(self):
        thread = self._graph_clone_thread
        if thread is None:
            return False
        try:
            if not thread.isRunning():
                return False
            thread.requestInterruption()
            if self._graph_clone_token is not None:
                self._operations.update(
                    self._graph_clone_token,
                    "Cancelling graph copy safely...",
                )
            return True
        except RuntimeError:
            return False

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

    # ── Graph clipboard / duplication ─────────────────────────────

    def _graph_target_ids(self, node_id=0):
        selected = self._node_model.get_selected_ids()
        node_id = int(node_id or 0)
        if node_id and node_id in selected:
            return selected
        if node_id:
            return [node_id]
        return selected

    def _paste_offset_for_bounds(self, width, height, cascade=0):
        center_x, center_y = self.get_viewport_center()
        return self._paste_offset_for_bounds_at(
            center_x,
            center_y,
            width,
            height,
            cascade,
        )

    @staticmethod
    def _paste_offset_for_bounds_at(
        center_x, center_y, width, height, cascade=0
    ):
        shift = max(0, int(cascade)) * 32.0
        return (
            float(center_x) - float(width) / 2.0 + shift,
            float(center_y) - float(height) / 2.0 + shift,
        )

    @Slot(int, result=bool)
    def copy_nodes(self, node_id=0):
        node_ids = self._graph_target_ids(node_id)
        if not node_ids:
            self.status_message.emit("Select a node to copy.", "warning")
            return False
        try:
            summary = self._service.copy_graph(node_ids)
        except Exception as exc:
            self.status_message.emit(f"Copy failed: {exc}", "error")
            return False
        self._last_graph_copy_summary = summary
        self._graph_paste_count = 0
        count = int(summary.get("count", len(node_ids)))
        self.status_message.emit(
            f"Copied {count} node{'s' if count != 1 else ''}.", "accent"
        )
        return True

    @Slot(result=bool)
    def paste_nodes(self):
        return self._paste_nodes_at()

    @Slot(float, float, result=bool)
    def paste_nodes_at(self, center_x, center_y):
        return self._paste_nodes_at((float(center_x), float(center_y)))

    def _paste_nodes_at(self, center=None):
        if not self._service.has_clipboard():
            self.status_message.emit("Internal clipboard is empty.", "warning")
            return False
        if self._operations.is_busy:
            self.status_message.emit(
                "Another database operation is active.", "warning"
            )
            return False
        summary = self._last_graph_copy_summary or {}
        bounds = summary.get("bounds") or {}
        if center is None:
            offset = self._paste_offset_for_bounds(
                bounds.get("width", 0.0),
                bounds.get("height", 0.0),
                self._graph_paste_count,
            )
        else:
            offset = self._paste_offset_for_bounds_at(
                center[0],
                center[1],
                bounds.get("width", 0.0),
                bounds.get("height", 0.0),
                self._graph_paste_count,
            )
        try:
            preparation = self._service.prepare_paste_graph(offset=offset)
        except Exception as exc:
            self.status_message.emit(f"Paste failed: {exc}", "error")
            return False
        return self._start_graph_clone(
            preparation,
            "paste",
            list(preparation.get("source_ids") or []),
            history_action="paste",
        )

    @Slot(int, result=bool)
    def duplicate_node(self, node_id=0):
        node_ids = self._graph_target_ids(node_id)
        if not node_ids:
            self.status_message.emit("Select a node to duplicate.", "warning")
            return False
        if self._operations.is_busy:
            self.status_message.emit(
                "Another database operation is active.", "warning"
            )
            return False
        try:
            preparation = self._service.prepare_duplicate_graph(node_ids)
        except Exception as exc:
            self.status_message.emit(f"Duplicate failed: {exc}", "error")
            return False
        return self._start_graph_clone(
            preparation,
            "duplicate",
            node_ids,
            history_action="duplicate",
        )

    def _start_graph_clone(
        self,
        preparation,
        operation_kind,
        source_ids,
        *,
        history_action,
        redo_entry=None,
        clear_redo=True,
    ):
        if self.has_active_graph_clone():
            self.status_message.emit("Graph copy is already running.", "warning")
            return False

        db_path = self._service.get_db_path()
        try:
            crypto = self._service.create_crypto_clone()
        except Exception as exc:
            self.status_message.emit(f"Graph copy failed: {exc}", "error")
            return False
        if not db_path or not crypto:
            self.status_message.emit("Database is not ready.", "error")
            return False

        verb = "Pasting" if operation_kind == "paste" else "Duplicating"
        if history_action == "redo":
            verb = "Redoing"
        token = self._operations.begin(
            "graph_clone", f"{verb} nodes...", blocking=True
        )
        if token is None:
            self.status_message.emit(
                "Another database operation is active.", "warning"
            )
            return False

        target = (
            preparation.get("target_origin")
            or preparation.get("offset")
            or {}
        )
        offset = (
            float(preparation.get("offset_x", target.get("x", 0.0))),
            float(preparation.get("offset_y", target.get("y", 0.0))),
        )
        self._graph_clone_token = token
        self._pending_graph_clone = {
            "operation_kind": operation_kind,
            "history_action": history_action,
            "source_ids": [int(node_id) for node_id in source_ids],
            "offset": offset,
            "redo_entry": redo_entry,
            "clear_redo": bool(clear_redo),
        }

        thread = None
        try:
            self._service.commit_changes()
            thread = QThread(self)
            worker = GraphCloneWorker(db_path, crypto, preparation)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.progress.connect(self._on_graph_clone_progress)
            worker.finished.connect(self._on_graph_clone_finished)
            worker.cancelled.connect(self._on_graph_clone_cancelled)
            worker.failed.connect(self._on_graph_clone_failed)
            worker.finished.connect(thread.quit)
            worker.cancelled.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            worker.cancelled.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(
                lambda: self._clear_active_graph_clone(thread)
            )

            self._graph_clone_thread = thread
            self._graph_clone_worker = worker
            thread.start()
        except Exception as exc:
            self._pending_graph_clone = None
            self._graph_clone_thread = None
            self._graph_clone_worker = None
            self._finish_graph_clone()
            if thread is not None:
                thread.deleteLater()
            self.progress_finished.emit("")
            self.status_message.emit(f"Graph copy failed: {exc}", "error")
            return False
        return True

    @Slot(object, object, str)
    def _on_graph_clone_progress(self, current_bytes, total_bytes, message):
        total = max(1, int(total_bytes or 0))
        current = max(0, min(int(current_bytes or 0), total))
        self._operations.update(self._graph_clone_token, message)
        self.progress_updated.emit(current / total, message)

    @Slot(object)
    def _on_graph_clone_finished(self, result):
        pending = self._pending_graph_clone
        self._pending_graph_clone = None
        if pending is None:
            self._finish_graph_clone()
            self.progress_finished.emit("")
            return
        try:
            created_ids = self._materialize_graph_result(
                result,
                pending["operation_kind"],
                pending["source_ids"],
                pending["offset"],
                clear_redo=pending["clear_redo"],
            )
            if not created_ids:
                self._restore_graph_clone_redo(pending)
            elif pending["history_action"] == "paste":
                self._graph_paste_count += 1
        except Exception as exc:
            self._restore_graph_clone_redo(pending)
            self._finish_graph_clone()
            self.progress_finished.emit("")
            self.status_message.emit(f"Graph copy failed: {exc}", "error")
            return
        self._finish_graph_clone()
        self.progress_finished.emit("")

    @Slot()
    def _on_graph_clone_cancelled(self):
        pending = self._pending_graph_clone
        self._pending_graph_clone = None
        self._restore_graph_clone_redo(pending)
        self._finish_graph_clone()
        self.progress_finished.emit("")
        self.status_message.emit("Graph copy cancelled.", "warning")

    @Slot(str)
    def _on_graph_clone_failed(self, message):
        pending = self._pending_graph_clone
        self._pending_graph_clone = None
        self._restore_graph_clone_redo(pending)
        self._finish_graph_clone()
        self.progress_finished.emit("")
        self.status_message.emit(f"Graph copy failed: {message}", "error")

    def _restore_graph_clone_redo(self, pending):
        if not pending:
            return
        redo_entry = pending.get("redo_entry")
        if redo_entry is not None:
            self._graph_redo.append(redo_entry)

    def _finish_graph_clone(self):
        token = self._graph_clone_token
        self._graph_clone_token = None
        if token is not None:
            self._operations.finish(token)

    def _clear_active_graph_clone(self, thread, report_unexpected=True):
        if self._graph_clone_thread is not thread:
            return
        self._graph_clone_thread = None
        self._graph_clone_worker = None
        pending = self._pending_graph_clone
        self._pending_graph_clone = None
        if pending is not None:
            self._restore_graph_clone_redo(pending)
            self.progress_finished.emit("")
            if report_unexpected:
                self.status_message.emit(
                    "Graph copy stopped unexpectedly.", "error"
                )
        self._finish_graph_clone()

    def _materialize_graph_result(
        self,
        result,
        operation_kind,
        source_ids,
        offset,
        record_history=True,
        clear_redo=True,
    ):
        created_ids = [int(node_id) for node_id in result.get("created_ids", [])]
        if not created_ids:
            self.status_message.emit("Nothing was pasted.", "warning")
            return []
        created_set = set(created_ids)
        existing_ids = {
            int(node["id"])
            for node in getattr(self._node_model, "_nodes", ())
        }
        tags_by_item = self._service.get_item_tags_map()
        items = [
            item
            for item in self._service.get_items_by_ids(
                created_ids, include_thumbnails=True
            )
            if int(item.id) not in existing_ids
        ]
        for item in sorted(items, key=lambda value: int(value.id)):
            self._node_model.add_node(
                item.id,
                item.type,
                item.x,
                item.y,
                item.width,
                item.height,
                title=item.title,
                content=item.text_content,
                thumbnail_bytes=item.thumbnail,
                title_size=item.title_size,
                text_size=item.text_size,
                total_size=item.total_size,
                media_width=item.media_width,
                media_height=item.media_height,
                media_duration=item.media_duration,
                created_at=item.created_at,
                updated_at=item.updated_at,
                frame_locked=getattr(item, "frame_locked", False),
                frame_color=getattr(item, "frame_color", ""),
                frame_opacity=getattr(item, "frame_opacity", 0.21),
            )
            self._node_model.set_node_tags(
                item.id,
                [
                    {"id": tag.id, "name": tag.name, "color": tag.color}
                    for tag in tags_by_item.get(item.id, [])
                ],
            )

        connection_ids = [
            int(connection_id)
            for connection_id in result.get("connection_ids", [])
        ]
        connection_set = set(connection_ids)
        if connection_set:
            for connection in self._service.get_all_connections():
                if int(connection.id) in connection_set:
                    self._conn_model.add_connection(
                        connection.id,
                        connection.start_id,
                        connection.end_id,
                    )

        selected_ids = [
            int(node_id)
            for node_id in result.get("selection")
            or result.get("selected_ids")
            or created_ids
            if int(node_id) in created_set
        ]
        self._node_model.set_selection(selected_ids)

        if record_history:
            self._graph_history.append({
                "kind": operation_kind,
                "source_ids": [int(node_id) for node_id in source_ids],
                "offset": (float(offset[0]), float(offset[1])),
                "created_ids": created_ids,
                "connection_ids": connection_ids,
            })
            if clear_redo:
                self._graph_redo.clear()
        label = "Pasted" if operation_kind == "paste" else "Duplicated"
        self.status_message.emit(
            f"{label} {len(created_ids)} node{'s' if len(created_ids) != 1 else ''}.",
            "accent",
        )
        return created_ids

    @Slot(result=bool)
    def undo_graph(self):
        if (
            self._pending_graph_history is not None
            or self.has_active_graph_clone()
        ):
            return False
        if not self._graph_history:
            self.status_message.emit("Nothing to undo.", "normal")
            return False
        token = self._operations.begin(
            "graph_undo", "Undoing graph operation...", blocking=True
        )
        if token is None:
            self.status_message.emit(
                "Another database operation is active.", "warning"
            )
            return False
        entry = self._graph_history.pop()
        self._graph_delete_token = token
        self._pending_graph_history = {"action": "undo", "entry": entry}
        try:
            self._service.delete_nodes_cascade(
                entry["created_ids"],
                on_success=lambda: self._graph_delete_finished.emit(
                    entry, None, "undo"
                ),
                on_error=lambda error: self._graph_delete_finished.emit(
                    entry, error, "undo"
                ),
            )
        except Exception as exc:
            self._pending_graph_history = None
            self._graph_history.append(entry)
            self._finish_graph_delete()
            self.status_message.emit(f"Undo failed: {exc}", "error")
            return False
        return True

    @Slot(result=bool)
    def redo_graph(self):
        if (
            self._pending_graph_history is not None
            or self.has_active_graph_clone()
        ):
            return False
        if not self._graph_redo:
            self.status_message.emit("Nothing to redo.", "normal")
            return False
        entry = self._graph_redo.pop()
        try:
            preparation = self._service.prepare_duplicate_graph(
                entry["source_ids"], offset=entry["offset"]
            )
            started = self._start_graph_clone(
                preparation,
                entry["kind"],
                entry["source_ids"],
                history_action="redo",
                redo_entry=entry,
                clear_redo=False,
            )
        except Exception as exc:
            self._graph_redo.append(entry)
            self.status_message.emit(f"Redo failed: {exc}", "error")
            return False
        if not started:
            self._graph_redo.append(entry)
            return False
        return True

    @Slot(object, object, str)
    def _on_graph_delete_finished(self, entry, error, action):
        if self._pending_graph_history is None:
            self._finish_graph_delete()
            return
        self._pending_graph_history = None
        try:
            if error:
                if action == "undo":
                    self._graph_history.append(entry)
                else:
                    self._graph_redo.append(entry)
                self.status_message.emit(f"Undo failed: {error}", "error")
                return
            for node_id in entry.get("created_ids", []):
                self._conn_model.remove_connections_for_node(node_id)
            for node_id in entry.get("created_ids", []):
                self._node_model.remove_node(node_id)
            if action == "undo":
                self._graph_redo.append(entry)
                self.status_message.emit("Undo complete.", "normal")
            else:
                self._graph_history.append(entry)
        finally:
            self._finish_graph_delete()

    def _finish_graph_delete(self):
        token = self._graph_delete_token
        self._graph_delete_token = None
        if token is not None:
            self._operations.finish(token)

    def _system_clipboard_nodes(self, node_id=0):
        node_ids = self._graph_target_ids(node_id)
        primary_id = int(node_id or 0)
        if primary_id in node_ids:
            node_ids = [primary_id] + [
                candidate_id
                for candidate_id in node_ids
                if candidate_id != primary_id
            ]
        compatible = []
        for candidate_id in node_ids:
            node = self._node_model.get_node_data(candidate_id)
            if node and node.get("type") in ("text", "image"):
                compatible.append(node)
        return compatible, len(node_ids) - len(compatible)

    @staticmethod
    def _text_for_system_clipboard(node):
        parts = []
        title = " ".join(str(node.get("title") or "").splitlines()).strip()
        content = str(node.get("content") or "")
        if title:
            parts.append(f"## {title}")
        if content:
            parts.append(content)
        return "\n\n".join(parts)

    @classmethod
    def _parse_system_clipboard_text(cls, text):
        text = str(text or "")
        first_line, separator, remainder = text.partition("\n")
        match = cls._SYSTEM_TITLE_RE.fullmatch(first_line.rstrip("\r"))
        if not match:
            return "", text
        title = match.group(1).strip()
        body = remainder if separator else ""
        if body.startswith("\r\n"):
            body = body[2:]
        elif body.startswith("\n"):
            body = body[1:]
        return title, body

    def _image_for_system_clipboard(self, node):
        try:
            payload = self._service.get_item_data(int(node["id"]))
        except Exception:
            payload = None
        image = QImage.fromData(payload) if payload else QImage()
        if image.isNull():
            thumbnail = node.get("thumbnail")
            if isinstance(thumbnail, QImage) and not thumbnail.isNull():
                image = QImage(thumbnail)
        return image

    @Slot(int, result=bool)
    def copy_to_system_clipboard(self, node_id=0):
        nodes, ignored_count = self._system_clipboard_nodes(node_id)
        if not nodes:
            self.status_message.emit(
                "System clipboard supports text and photo nodes only.",
                "warning",
            )
            return False
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self.status_message.emit("System clipboard is unavailable.", "error")
            return False

        text_nodes = [node for node in nodes if node["type"] == "text"]
        image_nodes = [node for node in nodes if node["type"] == "image"]
        mime = QMimeData()
        if text_nodes:
            mime.setText(
                "\n\n".join(
                    self._text_for_system_clipboard(node)
                    for node in text_nodes
                )
            )

        copied_image = False
        if image_nodes:
            for image_node in image_nodes:
                image = self._image_for_system_clipboard(image_node)
                if image.isNull():
                    continue
                mime.setImageData(image)
                copied_image = True
                break
            if not copied_image and not text_nodes:
                self.status_message.emit("Photo data is unavailable.", "warning")
                return False

        if text_nodes and copied_image:
            mime.setData(self._SYSTEM_MIXED_MIME, QByteArray(b"1"))
        clipboard.setMimeData(mime)

        labels = []
        if text_nodes:
            labels.append(f"{len(text_nodes)} text")
        if copied_image:
            labels.append("1 image")
        skipped = ignored_count + max(0, len(image_nodes) - int(copied_image))
        suffix = f"; skipped {skipped}" if skipped else ""
        self.status_message.emit(
            f"Copied {' and '.join(labels)} to system clipboard{suffix}.",
            "accent",
        )
        return True

    @staticmethod
    def _clipboard_image_bytes(image):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            return None
        return bytes(buffer.data())

    @staticmethod
    def _clipboard_qimage(mime):
        if mime.hasImage():
            value = mime.imageData()
            try:
                if isinstance(value, QImage):
                    image = QImage(value)
                elif hasattr(value, "toImage"):
                    image = value.toImage()
                else:
                    image = QImage(value)
            except (TypeError, ValueError):
                image = QImage()
            if not image.isNull():
                return image
        for mime_type in mime.formats():
            if not str(mime_type).lower().startswith("image/"):
                continue
            image = QImage.fromData(bytes(mime.data(mime_type)))
            if not image.isNull():
                return image
        return QImage()

    def _create_clipboard_image_node(
        self, image, center_x, center_y, *, commit=True, created_ids=None
    ):
        payload = self._clipboard_image_bytes(image)
        if not payload:
            raise ValueError("Clipboard image could not be encoded")
        thumbnail_image = image.scaled(
            800,
            800,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        thumbnail = self._clipboard_image_bytes(thumbnail_image) or payload
        width, height = self._auto_fit_service.fit_media(
            {"title": "Pasted image"}, thumbnail_image
        )
        x = float(center_x) - width / 2.0
        y = float(center_y) - height / 2.0
        node_id = self._service.add_item(
            "image",
            x,
            y,
            width,
            height,
            title="Pasted image",
            thumb=thumbnail,
            data=payload,
            media_width=image.width(),
            media_height=image.height(),
            original_filename="pasted-image.png",
            commit=commit,
        )
        if created_ids is not None:
            created_ids.append(node_id)
        self._node_model.add_node(
            node_id,
            "image",
            x,
            y,
            width,
            height,
            title="Pasted image",
            thumbnail_bytes=thumbnail,
            total_size=len(payload),
            media_width=image.width(),
            media_height=image.height(),
        )
        return node_id

    def _create_clipboard_text_node(
        self, text, center_x, center_y, *, commit=True, created_ids=None
    ):
        title, content = self._parse_system_clipboard_text(text)
        return self.create_text_node_at(
            float(center_x) - Config.NODE_DEFAULT_WIDTH / 2.0,
            float(center_y) - Config.NODE_DEFAULT_HEIGHT / 2.0,
            title,
            content,
            14,
            10,
            auto_fit_now=False,
            commit=commit,
            created_ids=created_ids,
        )

    @Slot(result=bool)
    def paste_from_system_clipboard(self):
        center_x, center_y = self.get_viewport_center()
        return self._paste_from_system_clipboard_at(center_x, center_y)

    @Slot(float, float, result=bool)
    def paste_from_system_clipboard_at(self, center_x, center_y):
        return self._paste_from_system_clipboard_at(
            float(center_x), float(center_y)
        )

    def _paste_from_system_clipboard_at(self, center_x, center_y):
        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        if mime is None:
            self.status_message.emit("System clipboard is unavailable.", "warning")
            return False
        image = self._clipboard_qimage(mime)
        text = mime.text() if mime.hasText() else ""
        paste_mixed = bool(mime.data(self._SYSTEM_MIXED_MIME))
        created_ids = []
        text_ids = []
        try:
            if not image.isNull():
                image_x = center_x - 130.0 if paste_mixed and text else center_x
                self._create_clipboard_image_node(
                    image,
                    image_x,
                    center_y,
                    commit=False,
                    created_ids=created_ids,
                )
            if text and (image.isNull() or paste_mixed):
                text_x = center_x + 130.0 if created_ids else center_x
                text_id = self._create_clipboard_text_node(
                    text,
                    text_x,
                    center_y,
                    commit=False,
                    created_ids=created_ids,
                )
                text_ids.append(text_id)
            if created_ids:
                self._service.commit_changes()
        except Exception as exc:
            rollback_error = None
            try:
                self._service.rollback_changes()
            except Exception as cleanup_exc:
                rollback_error = cleanup_exc
            finally:
                for node_id in reversed(created_ids):
                    self._conn_model.remove_connections_for_node(node_id)
                    self._node_model.remove_node(node_id)
            message = f"System paste failed: {exc}"
            if rollback_error is not None:
                message += f"; rollback failed: {rollback_error}"
            self.status_message.emit(message, "error")
            return False

        if created_ids:
            auto_fit_error = None
            for node_id in text_ids:
                try:
                    self._auto_fit_text_node(node_id)
                except Exception as exc:
                    auto_fit_error = exc
            self._node_model.set_selection(created_ids)
            message = (
                f"Pasted {len(created_ids)} clipboard node"
                f"{'s' if len(created_ids) != 1 else ''}."
            )
            if auto_fit_error is not None:
                message += f" Text auto-fit failed: {auto_fit_error}"
            self.status_message.emit(
                message, "warning" if auto_fit_error is not None else "accent"
            )
            return True
        self.status_message.emit(
            "System clipboard contains no supported text or image.",
            "warning",
        )
        return False

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
