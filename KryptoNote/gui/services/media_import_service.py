import os
import sqlite3
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...config import Config
from ...core.constants import MEDIA_CHUNK_SIZE
from ...core.exceptions import OperationCancelledError
from ...utils.media_proc import create_thumbnail, read_media_metadata


@dataclass
class ImportedMediaNode:
    node_id: int
    node_type: str
    x: float
    y: float
    width: float
    height: float
    title: str
    thumbnail_bytes: bytes | None
    total_size: int = 0
    media_width: int = 0
    media_height: int = 0
    media_duration: float = 0.0


class MediaImportService:
    """Validate and import selected media paths into the encrypted store."""

    LARGE_FILE_WARNING_BYTES = 256 * 1024 * 1024

    VALID_EXTENSIONS = {
        "image": {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"},
        "video": {".mp4", ".avi", ".mkv", ".mov", ".webm"},
    }

    def __init__(self, node_service):
        self._node_service = node_service

    def file_filter_for(self, media_type):
        if media_type == "image":
            return "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        if media_type == "video":
            return "Videos (*.mp4 *.avi *.mkv *.mov *.webm)"
        return "All Files (*)"

    def validate_path(self, media_type, path):
        valid = self.VALID_EXTENSIONS.get(media_type)
        if not valid:
            return True
        return os.path.splitext(path)[1].lower() in valid

    def get_large_files(self, paths):
        """Return existing files large enough to deserve a UI warning."""
        result = []
        for path in paths:
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size >= self.LARGE_FILE_WARNING_BYTES:
                result.append((path, size))
        return result

    def import_paths(
        self,
        media_type,
        paths,
        center_x,
        center_y,
        progress_callback=None,
        imported_callback=None,
    ):
        imported = []
        for index, path in enumerate(paths):
            if not self.validate_path(media_type, path):
                raise ValueError(f"'{os.path.basename(path)}' is not a valid {media_type}.")

            if progress_callback:
                progress_callback(index, len(paths), 0, 1, f"Processing {media_type}")

            thumbnail = create_thumbnail(path)
            metadata = read_media_metadata(path)
            file_size = os.path.getsize(path)
            title = os.path.basename(path)
            width = Config.NODE_MEDIA_SIZE
            height = Config.NODE_MEDIA_SIZE
            offset = index * 25
            x = center_x - width / 2 + offset
            y = center_y - height / 2 + offset

            def chunk_progress(current, total, status="Encrypting"):
                if progress_callback:
                    progress_callback(index, len(paths), current, total, status)

            node_id = self._node_service.add_streamed_media(
                media_type, x, y, width, height, title, thumbnail, path,
                chunk_progress, metadata.width, metadata.height, metadata.duration
            )
            item = ImportedMediaNode(
                node_id=node_id,
                node_type=media_type,
                x=x,
                y=y,
                width=width,
                height=height,
                title=title,
                thumbnail_bytes=thumbnail,
                total_size=file_size,
                media_width=metadata.width,
                media_height=metadata.height,
                media_duration=metadata.duration,
            )
            imported.append(item)
            if imported_callback:
                imported_callback(item)
        return imported


class MediaImportWorker(QObject):
    progress = Signal(float, str)
    item_imported = Signal(object)
    finished = Signal(int)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, db_path, crypto_manager, media_type, paths, center_x, center_y):
        super().__init__()
        self._db_path = db_path
        self._crypto = crypto_manager
        self._media_type = media_type
        self._paths = paths
        self._center_x = center_x
        self._center_y = center_y

    @staticmethod
    def _is_cancelled():
        return QThread.currentThread().isInterruptionRequested()

    @Slot()
    def run(self):
        from ...core.database.repository import write_chunked_media

        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            cursor = conn.cursor()

            imported_count = 0
            file_count = max(len(self._paths), 1)

            for file_index, path in enumerate(self._paths):
                if self._is_cancelled():
                    raise OperationCancelledError("Media import cancelled")
                self.progress.emit(
                    file_index / file_count,
                    self._format_progress_message(
                        "Processing",
                        file_index,
                        file_count,
                        0,
                        0,
                    ),
                )

                thumbnail = create_thumbnail(path)
                if self._is_cancelled():
                    raise OperationCancelledError("Media import cancelled")
                metadata = read_media_metadata(path)
                file_size = os.path.getsize(path)
                title = os.path.basename(path)
                width = Config.NODE_MEDIA_SIZE
                height = Config.NODE_MEDIA_SIZE
                offset = file_index * 25
                x = self._center_x - width / 2 + offset
                y = self._center_y - height / 2 + offset

                def _progress_adapter(chunk_idx, total_chunks, status,
                                      _fi=file_index, _fc=file_count):
                    val = (_fi + chunk_idx / max(total_chunks, 1)) / _fc
                    self.progress.emit(
                        val,
                        self._format_progress_message(
                            status,
                            _fi,
                            _fc,
                            chunk_idx,
                            total_chunks,
                        ),
                    )

                node_id = write_chunked_media(
                    cursor, conn, self._crypto,
                    self._media_type, x, y, width, height, title, thumbnail,
                    path, MEDIA_CHUNK_SIZE, _progress_adapter,
                    metadata.width, metadata.height, metadata.duration,
                    cancel_check=self._is_cancelled,
                )
                item = ImportedMediaNode(
                    node_id=node_id,
                    node_type=self._media_type,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    title=title,
                    thumbnail_bytes=thumbnail,
                    total_size=file_size,
                    media_width=metadata.width,
                    media_height=metadata.height,
                    media_duration=metadata.duration,
                )
                imported_count += 1
                self.item_imported.emit(item)

            self.finished.emit(imported_count)
        except OperationCancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if conn is not None:
                conn.close()

    def _format_progress_message(
        self,
        status,
        file_index,
        file_count,
        chunk_index,
        chunk_count,
    ):
        safe_file_count = max(int(file_count), 1)
        safe_file_index = min(max(int(file_index), 0), safe_file_count - 1)
        file_progress = safe_file_index / safe_file_count
        details = ""
        if chunk_count:
            safe_chunk_count = max(int(chunk_count), 1)
            safe_chunk_index = min(max(int(chunk_index), 0), safe_chunk_count)
            file_progress = (
                safe_file_index + safe_chunk_index / safe_chunk_count
            ) / safe_file_count
            details = f" · Chunk {safe_chunk_index}/{safe_chunk_count}"
        percent = round(file_progress * 100)
        media_label = self._media_type.capitalize()
        return (
            f"{status} {media_label} {safe_file_index + 1}/{safe_file_count}"
            f"{details} · {percent}%"
        )
