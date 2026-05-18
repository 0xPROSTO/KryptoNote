from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox, QApplication


class DeleteController(QObject):
    """Handles node and connection deletion with animations.

    Extracted from QmlCanvasController to reduce god-object complexity.
    """

    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    _video_transition_show_requested = Signal(str)
    _video_transition_update_requested = Signal(str)
    _video_transition_hide_requested = Signal()

    def __init__(self, node_model, connection_model, graph_commands, parent=None):
        super().__init__(parent)
        self._node_model = node_model
        self._conn_model = connection_model
        self._graph_commands = graph_commands
        self._pending_delete_batch = None

    @Slot(int)
    def request_animated_delete(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node or node.get("is_deleting"):
            return
        if node and node["type"] == "video":
            self._video_transition_show_requested.emit("Deleting video...")
        self._conn_model.mark_connections_for_node_deleting(node_id)
        self._node_model.set_deleting(node_id, True)

    @Slot(int)
    def perform_delete(self, node_id):
        if self._pending_delete_batch and node_id in self._pending_delete_batch["pending"]:
            self._pending_delete_batch["completed"].add(node_id)
            if self._pending_delete_batch["completed"] == self._pending_delete_batch["pending"]:
                batch_ids = list(self._pending_delete_batch["ids"])
                is_video_batch = self._pending_delete_batch["has_video"]
                self._pending_delete_batch = None
                self._perform_delete_batch(batch_ids, is_video_batch)
            return

        node = self._node_model.get_node_data(node_id)
        if not node:
            return
        is_video = bool(node and node["type"] == "video")

        def on_start():
            if is_video:
                self._video_transition_update_requested.emit("Vacuuming database...")
            else:
                self.progress_updated.emit(0.5, "Vacuuming database...")
                QApplication.processEvents()

        def on_finish():
            if is_video:
                self._video_transition_hide_requested.emit()
            self.progress_finished.emit("Ready")

        def on_waiting_lock(attempt):
            if is_video:
                self._video_transition_update_requested.emit(
                    f"Waiting for database lock... retry {attempt}/8"
                )
            else:
                self.progress_updated.emit(0.0, f"Waiting for database lock... retry {attempt}/8")

        self._graph_commands.delete_node_after_animation(
            node_id,
            on_start_vacuum=on_start,
            on_finish_vacuum=on_finish,
            on_waiting_lock=on_waiting_lock,
        )

    def _perform_delete_batch(self, node_ids, has_video):
        def on_start():
            if has_video:
                self._video_transition_show_requested.emit("Vacuuming database...")
            else:
                self.progress_updated.emit(0.5, "Deleting items...")

        def on_finish():
            if has_video:
                self._video_transition_hide_requested.emit()
            self.progress_finished.emit("Ready")

        def on_waiting_lock(attempt):
            if has_video:
                self._video_transition_update_requested.emit(
                    f"Waiting for database lock... retry {attempt}/8"
                )
            else:
                self.progress_updated.emit(0.0, f"Waiting for database lock... retry {attempt}/8")

        self._graph_commands.delete_nodes_after_animation(
            node_ids,
            on_start_vacuum=on_start,
            on_finish_vacuum=on_finish,
            on_waiting_lock=on_waiting_lock,
        )

    @Slot()
    def delete_selected_nodes(self):
        selected = self._node_model.get_selected_ids()
        if not selected:
            return
        confirm = QMessageBox.question(
            None, "Delete", f"Delete {len(selected)} items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            if len(selected) > 1:
                self._request_animated_delete_batch(selected)
            else:
                self.request_animated_delete(selected[0])

    @Slot()
    def delete_selected_nodes_without_confirmation(self):
        selected = self._node_model.get_selected_ids()
        if not selected:
            return
        if len(selected) > 1:
            self._request_animated_delete_batch(selected)
        else:
            self.request_animated_delete(selected[0])

    def _request_animated_delete_batch(self, node_ids):
        if self._pending_delete_batch:
            return

        valid_ids = []
        has_video = False
        for node_id in node_ids:
            node = self._node_model.get_node_data(node_id)
            if not node or node.get("is_deleting"):
                continue
            valid_ids.append(node_id)
            if node["type"] == "video":
                has_video = True

        if not valid_ids:
            return

        self._pending_delete_batch = {
            "ids": valid_ids,
            "pending": set(valid_ids),
            "completed": set(),
            "has_video": has_video,
        }
        for node_id in valid_ids:
            self._conn_model.mark_connections_for_node_deleting(node_id)
            self._node_model.set_deleting(node_id, True)
