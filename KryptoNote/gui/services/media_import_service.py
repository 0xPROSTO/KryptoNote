import os
import sqlite3
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot

from ...config import Config
from ...core.crypto import CryptoManager
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

    def import_paths(self, media_type, paths, center_x, center_y, progress_callback=None):
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
            imported.append(
                ImportedMediaNode(
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
            )
        return imported


class MediaImportWorker(QObject):
    progress = Signal(float, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, db_path, crypto_manager, media_type, paths, center_x, center_y):
        super().__init__()
        self._db_path = db_path
        self._crypto = crypto_manager
        self._media_type = media_type
        self._paths = paths
        self._center_x = center_x
        self._center_y = center_y

    @Slot()
    def run(self):
        from ...core.database.repository import write_chunked_media

        conn = None
        try:
            crypto = self._crypto
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            cursor = conn.cursor()

            imported = []
            file_count = max(len(self._paths), 1)

            for file_index, path in enumerate(self._paths):
                self.progress.emit(
                    file_index / file_count,
                    f"Processing {self._media_type} {file_index + 1}/{len(self._paths)}",
                )

                thumbnail = create_thumbnail(path)
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
                    self.progress.emit(val, f"{status} {self._media_type} {_fi + 1}/{_fc}")

                node_id = write_chunked_media(
                    cursor, conn, crypto,
                    self._media_type, x, y, width, height, title, thumbnail,
                    path, Config.CHUNK_SIZE, _progress_adapter,
                    metadata.width, metadata.height, metadata.duration,
                )
                imported.append(
                    ImportedMediaNode(
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
                )

            self.finished.emit(imported)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            if conn is not None:
                conn.close()
