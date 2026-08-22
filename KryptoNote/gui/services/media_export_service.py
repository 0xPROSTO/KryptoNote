import os
import threading

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...core.constants import MEDIA_CHUNK_SIZE
from ...core.database import DatabaseConnection, NodeRepository
from ...core.exceptions import OperationCancelledError
from ...services.atomic_output import (
    atomic_output_path,
    database_related_paths,
)
from ...services.node_service import NodeService


class MediaExportService:
    """Write encrypted media node payloads back to disk."""

    def __init__(self, node_service, database_path=None):
        self._node_service = node_service
        self._database_path = database_path

    def export_node(
        self,
        node_id,
        path,
        *,
        cancel_check=None,
        progress_callback=None,
    ):
        item_info = self._get_item_info(node_id)
        if item_info is None:
            raise ValueError("Media node was not found.")
        is_chunked = bool(item_info and item_info.is_chunked)
        total_size = int(item_info.total_size) if item_info else 0

        self._raise_if_cancelled(cancel_check)
        database_path = self._database_path
        if database_path is None:
            get_db_path = getattr(self._node_service, "get_db_path", None)
            if callable(get_db_path):
                database_path = get_db_path()
        with atomic_output_path(
            path,
            forbidden_paths=database_related_paths(database_path),
        ) as temp_path:
            if is_chunked:
                written = self._export_chunked(
                    node_id,
                    temp_path,
                    total_size,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                )
            else:
                written = self._export_legacy(
                    node_id,
                    temp_path,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                )
            self._raise_if_cancelled(cancel_check)
        return written

    def _export_legacy(
        self,
        node_id,
        path,
        *,
        cancel_check=None,
        progress_callback=None,
    ):
        self._raise_if_cancelled(cancel_check)
        total_size = self._node_service.get_legacy_full_data_size(node_id)
        if total_size is None:
            raise ValueError("No data found for this node.")
        written = 0
        with open(path, "wb") as f:
            for data in self._node_service.iter_legacy_full_data(
                node_id,
                cancel_check=cancel_check,
            ):
                self._raise_if_cancelled(cancel_check)
                block_written = f.write(data)
                if block_written != len(data):
                    raise IOError(
                        "Incomplete export while writing legacy media block"
                    )
                written += block_written
                if progress_callback:
                    progress_callback(
                        min(0.995, written / max(total_size, 1)),
                        "Exporting media...",
                    )
            f.flush()
            os.fsync(f.fileno())
        if written != total_size:
            raise IOError(
                f"Incomplete export: expected {total_size} bytes, wrote {written}"
            )
        if progress_callback:
            progress_callback(1.0, "Exporting media...")
        return written

    def _export_chunked(
        self,
        node_id,
        path,
        total_size,
        *,
        cancel_check=None,
        progress_callback=None,
    ):
        written = 0
        chunk_count = (
            (total_size + MEDIA_CHUNK_SIZE - 1) // MEDIA_CHUNK_SIZE
            if total_size > 0
            else 0
        )
        with open(path, "wb") as f:
            for index in range(chunk_count):
                self._raise_if_cancelled(cancel_check)
                data = self._node_service.get_chunk(node_id, index)
                if data is None:
                    raise ValueError(
                        f"Missing media chunk {index} for node {node_id}"
                    )
                written += f.write(data)
                if progress_callback:
                    progress_callback(
                        min(0.995, (index + 1) / max(chunk_count, 1)),
                        "Exporting media...",
                    )
            f.flush()
            os.fsync(f.fileno())
        if written != total_size:
            raise IOError(
                f"Incomplete export: expected {total_size} bytes, wrote {written}"
            )
        return written

    @staticmethod
    def _raise_if_cancelled(cancel_check):
        if cancel_check and cancel_check():
            raise OperationCancelledError("Media export cancelled")

    def _get_item_info(self, node_id):
        if hasattr(self._node_service, "get_item_info"):
            return self._node_service.get_item_info(node_id)
        for item in self._node_service.get_all_items():
            if item.id == node_id:
                return item
        return None


class MediaExportWorker(QObject):
    progress = Signal(float, str)
    finished = Signal(str)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, db_path, crypto, node_id, output_path):
        super().__init__()
        self._db_path = str(db_path)
        self._crypto = crypto
        self._node_id = int(node_id)
        self._output_path = str(output_path)
        self._cancel_event = threading.Event()

    @Slot()
    def cancel(self):
        self._cancel_event.set()

    def _is_cancelled(self):
        return (
            self._cancel_event.is_set()
            or QThread.currentThread().isInterruptionRequested()
        )

    @Slot()
    def run(self):
        database = None
        repository = None
        terminal = None
        try:
            database = DatabaseConnection(
                self._db_path,
                initialize=False,
                must_exist=True,
                writable=False,
            )
            repository = NodeRepository(database, self._crypto)
            service = NodeService(repository)
            MediaExportService(
                service, database_path=self._db_path
            ).export_node(
                self._node_id,
                self._output_path,
                cancel_check=self._is_cancelled,
                progress_callback=self.progress.emit,
            )
            terminal = ("finished", self._output_path)
        except OperationCancelledError:
            terminal = ("cancelled",)
        except Exception as exc:
            terminal = ("failed", str(exc) or exc.__class__.__name__)
        finally:
            if repository is not None:
                try:
                    repository.close(wait=True)
                except Exception:
                    pass
            if database is not None:
                try:
                    database.close()
                except Exception:
                    pass
        if terminal[0] == "finished":
            self.finished.emit(terminal[1])
        elif terminal[0] == "cancelled":
            self.cancelled.emit()
        else:
            self.failed.emit(terminal[1])
