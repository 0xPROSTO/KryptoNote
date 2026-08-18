import logging
import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ...core.constants import AUTO_VACUUM_THRESHOLD_BYTES, PLAYABLE_NODE_TYPES
from ...core.database.operations import DatabaseOperationProgress, DeletionResult
from ...core.exceptions import InsufficientDiskSpaceError
from ..services.operation_coordinator import OperationCoordinator


logger = logging.getLogger(__name__)


class DeleteController(QObject):
    """Coordinate animated node deletion and optional database maintenance.

    The QML animation is deliberately cosmetic.  Database work starts as
    soon as the model enters the deleting state, so a lost animation callback
    can never leave the global operation lock alive.
    """

    progress_updated = Signal(float, str)
    progress_finished = Signal(str)
    status_message = Signal(str, str)

    # Repository callbacks may run on its single background executor thread.
    # These signals are explicitly connected with QueuedConnection below.
    _worker_progress = Signal(object, float, str, bool)
    _node_delete_finished = Signal(object, object, object)
    _vacuum_progress = Signal(object, str)
    _vacuum_finished = Signal(object, bool, object)

    def __init__(
        self,
        node_model,
        connection_model,
        graph_commands,
        parent=None,
        operation_coordinator=None,
    ):
        super().__init__(parent)
        self._node_model = node_model
        self._conn_model = connection_model
        self._graph_commands = graph_commands
        self._operations = operation_coordinator or OperationCoordinator(self)
        self._delete_token = None
        self._delete_started_token = None
        self._delete_ids = ()
        self._animation_finished_ids = set()

        self._worker_progress.connect(
            self._handle_worker_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        self._node_delete_finished.connect(
            self._handle_node_delete_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._vacuum_progress.connect(
            self._handle_vacuum_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        self._vacuum_finished.connect(
            self._handle_vacuum_finished,
            Qt.ConnectionType.QueuedConnection,
        )

    @Slot(int)
    def request_animated_delete(self, node_id):
        node_id = int(node_id)
        node = self._node_model.get_node_data(node_id)
        if not node or node.get("is_deleting"):
            return

        token = self._operations.begin(
            "delete",
            "Deleting item...",
            blocking=True,
        )
        if token is None:
            self.status_message.emit(
                "Another database operation is active.",
                "warning",
            )
            return

        self._delete_token = token
        self._delete_ids = (node_id,)
        self._animation_finished_ids.clear()
        try:
            self._conn_model.mark_connections_for_node_deleting(node_id)
            self._node_model.set_deleting(node_id, True)
            self._start_delete_backend(token, self._delete_ids)
        except Exception as exc:
            self._restore_delete_state(self._delete_ids)
            self._finish_delete(token)
            self.status_message.emit(f"Delete failed: {exc}", "error")

    @Slot(int)
    def perform_delete(self, node_id):
        """Receive the legacy QML animation callback without owning correctness."""

        node_id = int(node_id)
        if node_id in self._delete_ids:
            self._animation_finished_ids.add(node_id)
        # The backend is started by request_animated_delete or the batch
        # request.  This method is intentionally idempotent and never starts
        # or finishes an operation.

    def _start_delete_backend(self, token, node_ids):
        if token != self._delete_token or self._delete_started_token == token:
            return
        self._delete_started_token = token
        ids = tuple(int(node_id) for node_id in node_ids)
        completion_lock = threading.Lock()
        completion_sent = False

        def emit_terminal(result=None, error=None):
            nonlocal completion_sent
            with completion_lock:
                if completion_sent:
                    return
                completion_sent = True
            if error is None and not isinstance(result, DeletionResult):
                result = DeletionResult(
                    item_ids=ids,
                    item_types=(),
                    deleted_bytes=0,
                    requires_vacuum=False,
                )
            self._node_delete_finished.emit(token, result, error)

        def on_start():
            self._worker_progress.emit(token, 0.0, "Deleting data...", False)

        def on_progress(current, total, message):
            snapshot = DatabaseOperationProgress(
                kind="delete",
                phase=self._delete_phase(message),
                determinate=True,
                current_bytes=current,
                total_bytes=total,
                message=message,
            )
            self._worker_progress.emit(
                token,
                self._delete_progress_value(snapshot),
                message,
                False,
            )

        def on_waiting_lock(attempt):
            message = f"Waiting for database lock... retry {attempt}/8"
            self._worker_progress.emit(token, 0.0, message, False)

        def on_finished():
            emit_terminal(
                error=RuntimeError(
                    "Database delete finished without a terminal result"
                )
            )

        try:
            if len(ids) == 1:
                self._graph_commands.delete_node_after_animation(
                    ids[0],
                    on_start_vacuum=on_start,
                    on_finish_vacuum=on_finished,
                    on_waiting_lock=on_waiting_lock,
                    progress_callback=on_progress,
                    on_success=lambda result=None: emit_terminal(result=result),
                    on_error=lambda error: emit_terminal(error=error),
                )
            else:
                self._graph_commands.delete_nodes_after_animation(
                    ids,
                    on_start_vacuum=on_start,
                    on_finish_vacuum=on_finished,
                    on_waiting_lock=on_waiting_lock,
                    progress_callback=on_progress,
                    on_success=lambda result=None: emit_terminal(result=result),
                    on_error=lambda error: emit_terminal(error=error),
                )
        except Exception as exc:
            emit_terminal(error=exc)

    @Slot(object, float, str, bool)
    def _handle_worker_progress(self, token, value, message, vacuum):
        if token != self._delete_token or not self._operations.owns(token):
            return
        self._operations.update(token, message)
        if not vacuum:
            self.progress_updated.emit(float(value), str(message))

    @Slot(object, str)
    def _handle_vacuum_progress(self, token, message):
        if token != self._delete_token or not self._operations.owns(token):
            return
        self._operations.update(token, str(message))

    @Slot(object, object, object)
    def _handle_node_delete_finished(self, token, result, error):
        if token != self._delete_token or not self._operations.owns(token):
            return

        ids = tuple(
            int(node_id)
            for node_id in (
                result.item_ids
                if isinstance(result, DeletionResult) and result.item_ids
                else self._delete_ids
            )
        )
        vacuum_started = False
        try:
            if error is not None:
                self._restore_delete_state(ids)
                self.status_message.emit(f"Delete failed: {error}", "error")
                return

            for node_id in ids:
                self._conn_model.remove_connections_for_node(node_id)
            for node_id in ids:
                self._node_model.remove_node(node_id)

            requires_vacuum = bool(
                isinstance(result, DeletionResult)
                and result.requires_vacuum
            )
            if requires_vacuum:
                message = (
                    "Item deleted. Optimizing database..."
                    if len(ids) == 1
                    else f"Deleted {len(ids)} items. Optimizing database..."
                )
                self.status_message.emit(message, "normal")
                self._start_vacuum_after_delete(token)
                vacuum_started = True
                return

            message = (
                "Item deleted."
                if len(ids) == 1
                else f"Deleted {len(ids)} items."
            )
            self.status_message.emit(message, "normal")
        except Exception as exc:
            logger.exception("Failed to reconcile deleted nodes: %s", exc)
            self.status_message.emit(
                f"Delete completed, but the canvas needs to resync: {exc}",
                "error",
            )
            self._schedule_model_resync()
        finally:
            if not vacuum_started and self._delete_token == token:
                self._finish_delete(token)

    def _start_vacuum_after_delete(self, delete_token):
        token = self._operations.transition(
            delete_token,
            "vacuum",
            "Optimizing database...",
            blocking=True,
        )
        if token is None:
            self.status_message.emit(
                "Item deleted, but database optimization could not start.",
                "error",
            )
            self._finish_delete(delete_token)
            return

        self._delete_token = token
        completion_lock = threading.Lock()
        completion_sent = False

        def emit_terminal(success, payload):
            nonlocal completion_sent
            with completion_lock:
                if completion_sent:
                    return
                completion_sent = True
            self._vacuum_finished.emit(token, bool(success), payload)

        def on_start():
            self._vacuum_progress.emit(token, "Optimizing database...")

        def on_phase(_phase, message):
            self._vacuum_progress.emit(token, str(message))

        def on_waiting_lock(attempt):
            self._vacuum_progress.emit(
                token,
                f"Waiting to optimize database... retry {attempt}/8",
            )

        def on_finished():
            emit_terminal(
                False,
                RuntimeError(
                    "Database VACUUM finished without a terminal result"
                ),
            )

        try:
            self._graph_commands.vacuum_database(
                on_start=on_start,
                on_waiting_lock=on_waiting_lock,
                on_phase=on_phase,
                on_finish=on_finished,
                on_success=lambda result: emit_terminal(True, result),
                on_error=lambda error: emit_terminal(False, error),
            )
        except Exception as exc:
            emit_terminal(False, exc)

    @Slot(object, bool, object)
    def _handle_vacuum_finished(self, token, success, payload):
        if token != self._delete_token or not self._operations.owns(token):
            return
        try:
            if success:
                self.status_message.emit(
                    getattr(
                        payload,
                        "message",
                        "Database optimized successfully.",
                    ),
                    "secure",
                )
            elif isinstance(payload, InsufficientDiskSpaceError):
                self.status_message.emit(
                    "Item deleted. Database optimization failed: "
                    "insufficient free space.",
                    "error",
                )
            else:
                self.status_message.emit(
                    f"Item deleted, but database optimization failed: {payload}",
                    "error",
                )
        finally:
            self._finish_delete(token)

    @Slot()
    def delete_selected_nodes(self):
        selected = self._node_model.get_selected_ids()
        if not selected:
            return
        confirm = QMessageBox.question(
            None,
            "Delete",
            f"Delete {len(selected)} items?",
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
        if self._delete_token is not None:
            return

        valid_ids = []
        for node_id in node_ids:
            node = self._node_model.get_node_data(node_id)
            if node and not node.get("is_deleting"):
                valid_ids.append(int(node_id))

        if not valid_ids:
            return
        token = self._operations.begin(
            "delete",
            "Deleting items...",
            blocking=True,
        )
        if token is None:
            self.status_message.emit(
                "Another database operation is active.",
                "warning",
            )
            return

        self._delete_token = token
        self._delete_ids = tuple(valid_ids)
        self._animation_finished_ids.clear()
        try:
            for node_id in self._delete_ids:
                self._conn_model.mark_connections_for_node_deleting(node_id)
                self._node_model.set_deleting(node_id, True)
            self._start_delete_backend(token, self._delete_ids)
        except Exception as exc:
            self._restore_delete_state(self._delete_ids)
            self._finish_delete(token)
            self.status_message.emit(f"Delete failed: {exc}", "error")

    def _restore_delete_state(self, node_ids):
        for node_id in node_ids:
            try:
                self._node_model.set_deleting(node_id, False)
                self._conn_model.mark_connections_for_node_deleting(
                    node_id,
                    deleting=False,
                    finalize=False,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to restore delete state for %s: %s",
                    node_id,
                    exc,
                )

    def _finish_delete(self, token=None):
        if token is not None and token != self._delete_token:
            return False
        active_token = self._delete_token
        self._delete_token = None
        self._delete_started_token = None
        self._delete_ids = ()
        self._animation_finished_ids.clear()
        try:
            if active_token is not None:
                self._operations.finish(active_token)
        finally:
            self.progress_finished.emit("")
        return True

    def _schedule_model_resync(self):
        parent = self.parent()
        reload_from_db = getattr(parent, "load_from_db", None)
        if callable(reload_from_db):
            QTimer.singleShot(0, reload_from_db)

    @classmethod
    def _node_requires_vacuum(cls, node):
        """Compatibility predicate for callers that still use the helper."""

        if not node or str(node.get("type") or "").lower() == "text":
            return False
        return bool(
            node.get("type") in PLAYABLE_NODE_TYPES
            or int(node.get("total_size") or 0)
            >= AUTO_VACUUM_THRESHOLD_BYTES
        )

    @staticmethod
    def _delete_phase(message):
        text = str(message)
        if text.startswith("Deleting media blocks"):
            return "media"
        if text.startswith("Deleting related"):
            return "relations"
        return "commit"

    @staticmethod
    def _delete_progress_value(progress):
        if progress.phase == "media":
            return progress.fraction * 0.8
        if progress.phase == "relations":
            return 0.9
        return 0.98
