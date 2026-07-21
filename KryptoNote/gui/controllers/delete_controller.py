from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ..services.operation_coordinator import OperationCoordinator


class DeleteController(QObject):
    """Handles node and connection deletion with animations.

    Extracted from QmlCanvasController to reduce god-object complexity.
    """

    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    status_message = Signal(str, str)
    _node_delete_finished = Signal(object, object)

    def __init__(self, node_model, connection_model, graph_commands, parent=None,
                 operation_coordinator=None):
        super().__init__(parent)
        self._node_model = node_model
        self._conn_model = connection_model
        self._graph_commands = graph_commands
        self._operations = operation_coordinator or OperationCoordinator(self)
        self._delete_token = None
        self._pending_delete_batch = None
        self._node_delete_finished.connect(self._handle_node_delete_finished)

    @Slot(int)
    def request_animated_delete(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node or node.get("is_deleting"):
            return
        token = self._operations.begin("delete", "Deleting item...", blocking=True)
        if token is None:
            self.status_message.emit("Another database operation is active.", "warning")
            return
        self._delete_token = token
        try:
            self._conn_model.mark_connections_for_node_deleting(node_id)
            self._node_model.set_deleting(node_id, True)
        except Exception as exc:
            self._conn_model.mark_connections_for_node_deleting(
                node_id, deleting=False, finalize=False
            )
            self._finish_delete()
            self.status_message.emit(f"Delete failed: {exc}", "error")

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
            self._finish_delete()
            return
        if self._delete_token is None:
            token = self._operations.begin("delete", "Deleting item...", blocking=True)
            if token is None:
                self.status_message.emit("Another database operation is active.", "warning")
                return
            self._delete_token = token

        def on_start():
            self._operations.update(self._delete_token, "Deleting item...")
            self.progress_updated.emit(0.5, "Deleting item...")

        def on_waiting_lock(attempt):
            message = f"Waiting for database lock... retry {attempt}/8"
            self._operations.update(self._delete_token, message)
            self.progress_updated.emit(0.0, message)

        completion_sent = False

        def complete(error=None):
            nonlocal completion_sent
            if completion_sent:
                return
            completion_sent = True
            self._node_delete_finished.emit(
                [node_id], None if error is None else str(error)
            )

        try:
            self._graph_commands.delete_node_after_animation(
                node_id,
                on_start_vacuum=on_start,
                on_waiting_lock=on_waiting_lock,
                on_success=complete,
                on_error=complete,
            )
        except Exception as exc:
            complete(exc)

    def _perform_delete_batch(self, node_ids, _has_video):
        def on_start():
            self._operations.update(self._delete_token, "Deleting items...")
            self.progress_updated.emit(0.5, "Deleting items...")

        def on_waiting_lock(attempt):
            message = f"Waiting for database lock... retry {attempt}/8"
            self._operations.update(self._delete_token, message)
            self.progress_updated.emit(0.0, message)

        ids = list(node_ids)
        completion_sent = False

        def complete(error=None):
            nonlocal completion_sent
            if completion_sent:
                return
            completion_sent = True
            self._node_delete_finished.emit(
                ids, None if error is None else str(error)
            )

        try:
            self._graph_commands.delete_nodes_after_animation(
                ids,
                on_start_vacuum=on_start,
                on_waiting_lock=on_waiting_lock,
                on_success=complete,
                on_error=complete,
            )
        except Exception as exc:
            complete(exc)

    def _handle_node_delete_finished(self, node_ids, error):
        ids = [int(node_id) for node_id in node_ids]
        if error:
            for node_id in ids:
                self._node_model.set_deleting(node_id, False)
                self._conn_model.mark_connections_for_node_deleting(
                    node_id, deleting=False, finalize=False
                )
            self.status_message.emit(f"Delete failed: {error}", "error")
            self._finish_delete()
            return

        for node_id in ids:
            self._conn_model.remove_connections_for_node(node_id)
        for node_id in ids:
            self._node_model.remove_node(node_id)

        if len(ids) == 1:
            self.status_message.emit("Item deleted.", "normal")
        else:
            self.status_message.emit(f"Deleted {len(ids)} items.", "normal")
        self._finish_delete()

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
        token = self._operations.begin("delete", "Deleting items...", blocking=True)
        if token is None:
            self.status_message.emit("Another database operation is active.", "warning")
            return
        self._delete_token = token
        self._pending_delete_batch = {
            "ids": valid_ids,
            "pending": set(valid_ids),
            "completed": set(),
            "has_video": has_video,
        }
        try:
            for node_id in valid_ids:
                self._conn_model.mark_connections_for_node_deleting(node_id)
                self._node_model.set_deleting(node_id, True)
        except Exception as exc:
            for node_id in valid_ids:
                self._node_model.set_deleting(node_id, False)
                self._conn_model.mark_connections_for_node_deleting(
                    node_id, deleting=False, finalize=False
                )
            self._pending_delete_batch = None
            self._finish_delete()
            self.status_message.emit(f"Delete failed: {exc}", "error")

    def _finish_delete(self):
        token = self._delete_token
        self._delete_token = None
        if token is not None:
            self._operations.finish(token)
        self.progress_finished.emit("")
