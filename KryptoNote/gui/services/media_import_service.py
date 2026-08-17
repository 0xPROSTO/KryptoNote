import os
import sqlite3
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...config import Config
from ...core.constants import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_CHUNK_SIZE,
    VIDEO_EXTENSIONS,
)
from ...core.database.connection import (
    acquire_database_operation_lock,
    cleanup_staged_items,
    open_sqlite_connection,
)
from ...core.database.operations import DatabaseOperationProgress
from ...core.exceptions import (
    InsufficientDiskSpaceError,
    OperationCancelledError,
)
from ...utils.media_proc import (
    AudioAnalysisCancelled,
    create_thumbnail,
    read_media_metadata,
    supported_audio_extensions,
)


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
        "image": set(IMAGE_EXTENSIONS),
        "video": set(VIDEO_EXTENSIONS),
        "audio": set(AUDIO_EXTENSIONS),
    }

    def __init__(self, node_service):
        self._node_service = node_service

    def file_filter_for(self, media_type):
        if media_type == "image":
            return "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        if media_type == "video":
            return "Videos (*.mp4 *.avi *.mkv *.mov *.webm)"
        if media_type == "audio":
            suffixes = " ".join(
                f"*{suffix}" for suffix in sorted(supported_audio_extensions())
            )
            return f"Audio ({suffixes})"
        return "All Files (*)"

    @classmethod
    def validate_path(cls, media_type, path):
        valid = (
            supported_audio_extensions()
            if media_type == "audio"
            else cls.VALID_EXTENSIONS.get(media_type)
        )
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
        cancel_check=None,
    ):
        imported = []
        for index, path in enumerate(paths):
            if cancel_check and cancel_check():
                raise OperationCancelledError("Media import cancelled")
            if not self.validate_path(media_type, path):
                raise ValueError(f"'{os.path.basename(path)}' is not a valid {media_type}.")

            if progress_callback:
                progress_callback(index, len(paths), 0, 1, f"Processing {media_type}")

            if media_type == "audio":
                if progress_callback:
                    progress_callback(
                        index, len(paths), 0, 1, "Analyzing audio"
                    )

                def audio_progress(current, total):
                    if not progress_callback:
                        return
                    progress_callback(
                        index,
                        len(paths),
                        max(0, int(current)),
                        max(1, int(total)),
                        "Analyzing audio",
                    )

                try:
                    metadata = read_media_metadata(
                        path,
                        media_type="audio",
                        cancel_check=cancel_check,
                        progress_callback=audio_progress,
                    )
                except AudioAnalysisCancelled as exc:
                    raise OperationCancelledError(
                        "Media import cancelled"
                    ) from exc
                thumbnail = metadata.waveform
            else:
                thumbnail = create_thumbnail(path)
                metadata = read_media_metadata(path, media_type=media_type)
            if cancel_check and cancel_check():
                raise OperationCancelledError("Media import cancelled")
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
                chunk_progress, metadata.width, metadata.height, metadata.duration,
                os.path.basename(path),
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
    progress = Signal(object)
    item_imported = Signal(object)
    finished = Signal(int)
    cancelled = Signal()
    failed = Signal(str)

    BATCH_CHUNKS = 8
    MIN_FREE_RESERVE = 256 * 1024 * 1024

    def __init__(
        self, db_path, crypto_manager, jobs, center_x, center_y
    ):
        super().__init__()
        self._db_path = db_path
        self._crypto = crypto_manager
        self._jobs = [
            (str(media_type), os.fspath(path))
            for media_type, path in jobs
        ]
        self._center_x = center_x
        self._center_y = center_y

    @staticmethod
    def _is_cancelled():
        return QThread.currentThread().isInterruptionRequested()

    def _emit_progress(
        self,
        phase,
        current_bytes,
        total_bytes,
        message,
        *,
        cancellable=True,
    ):
        self.progress.emit(
            DatabaseOperationProgress(
                kind="media_import",
                phase=phase,
                determinate=True,
                current_bytes=max(0, int(current_bytes)),
                total_bytes=max(1, int(total_bytes)),
                message=str(message),
                cancellable=cancellable,
            )
        )

    @staticmethod
    def _source_fingerprint(stat_result):
        return (
            int(stat_result.st_dev),
            int(stat_result.st_ino),
            int(stat_result.st_size),
            int(stat_result.st_mtime_ns),
        )

    @classmethod
    def _assert_source_unchanged(cls, path, expected_stat, title):
        try:
            current_stat = os.stat(path)
        except OSError as exc:
            raise sqlite3.DatabaseError(
                f"Source media changed during import: {title}"
            ) from exc
        if cls._source_fingerprint(current_stat) != cls._source_fingerprint(
            expected_stat
        ):
            raise sqlite3.DatabaseError(
                f"Source media changed during import: {title}"
            )

    def _write_staged_media(
        self,
        conn,
        cursor,
        media_type,
        path,
        title,
        thumbnail,
        metadata,
        x,
        y,
        width,
        height,
        file_size,
        completed_bytes,
        total_bytes,
        source_stat=None,
    ):
        now = datetime.now().isoformat(timespec="seconds")
        item_id = None
        try:
            source_stat = source_stat or os.stat(path)
            self._assert_source_unchanged(path, source_stat, title)
            cursor.execute(
                """
                INSERT INTO items (
                    type, title, x, y, width, height, thumbnail,
                    is_chunked, total_size, created_at, updated_at,
                    media_width, media_height, media_duration,
                    original_filename, storage_state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 'importing')
                """,
                (
                    media_type,
                    b"",
                    x,
                    y,
                    width,
                    height,
                    None,
                    file_size,
                    now,
                    now,
                    metadata.width,
                    metadata.height,
                    metadata.duration,
                    None,
                ),
            )
            item_id = int(cursor.lastrowid)
            enc_title = self._crypto.encrypt(
                title.encode(), aad=self._crypto.item_aad(item_id, "title")
            )
            enc_thumbnail = (
                self._crypto.encrypt(
                    thumbnail,
                    aad=self._crypto.item_aad(item_id, "thumbnail"),
                )
                if thumbnail
                else None
            )
            enc_filename = self._crypto.encrypt(
                os.path.basename(path).encode(),
                aad=self._crypto.item_aad(item_id, "original_filename"),
            )
            cursor.execute(
                "UPDATE items SET title=?, thumbnail=?, original_filename=? "
                "WHERE id=? AND storage_state='importing'",
                (enc_title, enc_thumbnail, enc_filename, item_id),
            )
            conn.commit()

            chunk_index = 0
            written_bytes = 0
            with open(path, "rb") as source:
                if self._source_fingerprint(
                    os.fstat(source.fileno())
                ) != self._source_fingerprint(source_stat):
                    raise sqlite3.DatabaseError(
                        f"Source media changed during import: {title}"
                    )
                while True:
                    if self._is_cancelled():
                        raise OperationCancelledError("Media import cancelled")
                    chunk = source.read(MEDIA_CHUNK_SIZE)
                    if not chunk:
                        break
                    encrypted = self._crypto.encrypt(
                        chunk,
                        aad=self._crypto.chunk_aad(item_id, chunk_index),
                    )
                    cursor.execute(
                        "INSERT INTO media_chunks "
                        "(item_id, chunk_index, data) VALUES (?, ?, ?)",
                        (item_id, chunk_index, encrypted),
                    )
                    chunk_index += 1
                    written_bytes += len(chunk)
                    self._emit_progress(
                        "writing",
                        completed_bytes + written_bytes,
                        total_bytes,
                        f"Encrypting and writing {title}",
                    )

                    if chunk_index % self.BATCH_CHUNKS == 0:
                        self._emit_progress(
                            "flushing",
                            completed_bytes + written_bytes,
                            total_bytes,
                            f"Flushing database for {title}",
                        )
                        conn.commit()
                        conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()

                if self._source_fingerprint(
                    os.fstat(source.fileno())
                ) != self._source_fingerprint(source_stat):
                    raise sqlite3.DatabaseError(
                        f"Source media changed during import: {title}"
                    )

            conn.commit()
            self._emit_progress(
                "flushing",
                completed_bytes + file_size,
                total_bytes,
                f"Flushing database for {title}",
            )
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            if self._is_cancelled():
                raise OperationCancelledError("Media import cancelled")
            self._assert_source_unchanged(path, source_stat, title)
            if written_bytes != file_size:
                raise sqlite3.DatabaseError(
                    f"Source media changed during import: {title}"
                )

            expected_chunks = (
                (file_size + MEDIA_CHUNK_SIZE - 1) // MEDIA_CHUNK_SIZE
                if file_size
                else 0
            )
            count, minimum, maximum = cursor.execute(
                "SELECT COUNT(*), MIN(chunk_index), MAX(chunk_index) "
                "FROM media_chunks WHERE item_id=?",
                (item_id,),
            ).fetchone()
            valid_range = (
                expected_chunks == 0
                or (minimum == 0 and maximum == expected_chunks - 1)
            )
            if int(count or 0) != expected_chunks or not valid_range:
                raise sqlite3.DatabaseError(
                    f"Incomplete media blocks for {title}"
                )

            self._emit_progress(
                "publishing",
                completed_bytes + max(file_size, 1),
                total_bytes,
                f"Publishing {title}",
                cancellable=False,
            )
            cursor.execute(
                "UPDATE items SET storage_state='ready' "
                "WHERE id=? AND storage_state='importing'",
                (item_id,),
            )
            if cursor.rowcount != 1:
                raise sqlite3.DatabaseError(
                    f"Failed to publish imported media {title}"
                )
            conn.commit()
            return item_id
        except Exception:
            if item_id is not None:
                try:
                    cleanup_staged_items(conn, [item_id])
                except sqlite3.Error:
                    # Leave the hidden importing row for startup recovery.
                    pass
            raise

    @Slot()
    def run(self):
        conn = None
        operation_lock = None
        try:
            for media_type, path in self._jobs:
                if not MediaImportService.validate_path(media_type, path):
                    raise ValueError(
                        f"'{os.path.basename(path)}' is not a valid "
                        f"{media_type}."
                    )

            job_stats = [os.stat(path) for _kind, path in self._jobs]
            job_sizes = [int(stat.st_size) for stat in job_stats]
            # Audio performs two substantial passes: decode/analyse, then
            # encrypted chunk writing.  Count both so progress never reaches
            # the end during analysis and then jumps backwards for import.
            job_work_sizes = [
                max(size, 1) * (2 if media_type == "audio" else 1)
                for (media_type, _path), size in zip(self._jobs, job_sizes)
            ]
            total_bytes = sum(job_work_sizes)
            reserve = max(
                self.MIN_FREE_RESERVE,
                sum(job_sizes) // 10,
            )
            free_bytes = shutil.disk_usage(
                Path(self._db_path).resolve().parent
            ).free
            required_bytes = sum(job_sizes) + reserve
            if free_bytes < required_bytes:
                raise InsufficientDiskSpaceError(
                    "Not enough free disk space for media import: "
                    f"required {required_bytes} bytes, available {free_bytes} bytes"
                )

            operation_lock = acquire_database_operation_lock(self._db_path)
            conn = open_sqlite_connection(
                self._db_path, timeout=30.0, must_exist=True
            )
            cursor = conn.cursor()

            imported_count = 0
            file_count = max(len(self._jobs), 1)
            completed_bytes = 0

            for file_index, (media_type, path) in enumerate(self._jobs):
                if self._is_cancelled():
                    raise OperationCancelledError("Media import cancelled")
                file_size = job_sizes[file_index]
                import_progress_base = completed_bytes
                self._emit_progress(
                    "preparing",
                    completed_bytes,
                    total_bytes,
                    f"Preparing media {file_index + 1}/{file_count}",
                )

                title = os.path.basename(path)
                if media_type == "audio":
                    self._emit_progress(
                        "Analyzing audio",
                        completed_bytes,
                        total_bytes,
                        f"Analyzing audio {title}",
                    )

                    def audio_progress(current, total):
                        if self._is_cancelled():
                            raise AudioAnalysisCancelled(
                                "Media import cancelled"
                            )
                        try:
                            current_value = float(current or 0)
                            total_value = float(total or 0)
                        except (TypeError, ValueError):
                            current_value = total_value = 0.0
                        fraction = (
                            current_value / total_value
                            if total_value > 0
                            else 0.0
                        )
                        fraction = max(0.0, min(1.0, fraction))
                        self._emit_progress(
                            "Analyzing audio",
                            completed_bytes
                            + int(max(file_size, 1) * fraction),
                            total_bytes,
                            f"Analyzing audio {title}",
                        )

                    try:
                        metadata = read_media_metadata(
                            path,
                            media_type="audio",
                            cancel_check=self._is_cancelled,
                            progress_callback=audio_progress,
                        )
                    except AudioAnalysisCancelled as exc:
                        raise OperationCancelledError(
                            "Media import cancelled"
                        ) from exc
                    thumbnail = metadata.waveform
                    import_progress_base += max(file_size, 1)
                else:
                    thumbnail = create_thumbnail(path)
                    if self._is_cancelled():
                        raise OperationCancelledError("Media import cancelled")
                    metadata = read_media_metadata(path, media_type=media_type)
                title = os.path.basename(path)
                self._assert_source_unchanged(
                    path, job_stats[file_index], title
                )
                width = Config.NODE_MEDIA_SIZE
                height = Config.NODE_MEDIA_SIZE
                offset = file_index * 25
                x = self._center_x - width / 2 + offset
                y = self._center_y - height / 2 + offset

                node_id = self._write_staged_media(
                    conn,
                    cursor,
                    media_type,
                    path,
                    title,
                    thumbnail,
                    metadata,
                    x,
                    y,
                    width,
                    height,
                    file_size,
                    import_progress_base,
                    total_bytes,
                    source_stat=job_stats[file_index],
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
                imported_count += 1
                completed_bytes += job_work_sizes[file_index]
                self.item_imported.emit(item)

            self.finished.emit(imported_count)
        except OperationCancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                if conn is not None:
                    conn.close()
            finally:
                if operation_lock is not None:
                    operation_lock.release()
