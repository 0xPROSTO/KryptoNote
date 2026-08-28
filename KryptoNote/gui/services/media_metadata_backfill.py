import os
import shutil
import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ...core.constants import MEDIA_CHUNK_SIZE
from ...core.io.stream import BlockEncryptedStream
from ...utils.media_proc import read_media_metadata, read_mutagen_metadata
from ...utils.secure_temp import (
    create_guarded_metadata_temp_file,
    discard_guarded_metadata_temp_file,
    metadata_temp_directory,
)


class MediaMetadataBackfillWorker(QObject):
    """Extract metadata from an existing encrypted media payload off the UI thread."""

    finished = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int)

    def __init__(
        self,
        db_path,
        crypto,
        node_id,
        media_type,
        total_size,
        original_filename,
        is_chunked,
    ):
        super().__init__()
        self._db_path = db_path
        self._crypto = crypto
        self._node_id = int(node_id)
        self._media_type = str(media_type or "")
        self._total_size = max(0, int(total_size or 0))
        self._original_filename = str(original_filename or "")
        self._is_chunked = bool(is_chunked)

    def _raise_if_cancelled(self):
        if QThread.currentThread().isInterruptionRequested():
            raise InterruptedError("Metadata indexing cancelled")

    def _suffix(self):
        suffix = Path(self._original_filename).suffix.lower()
        if (
            suffix
            and len(suffix) <= 12
            and suffix[1:].replace("_", "").isalnum()
        ):
            return suffix
        return {
            "audio": ".ogg",
            "image": ".png",
            "video": ".mp4",
        }.get(self._media_type, ".bin")

    def _write_chunked_payload(self, output):
        stream = BlockEncryptedStream(
            self._db_path,
            self._crypto,
            self._node_id,
            self._total_size,
            MEDIA_CHUNK_SIZE,
        )
        if not stream.isOpen():
            error = stream.errorString() or "Unable to open encrypted media"
            stream.close()
            raise OSError(error)
        written = 0
        try:
            while written < self._total_size:
                self._raise_if_cancelled()
                requested = min(MEDIA_CHUNK_SIZE, self._total_size - written)
                block = bytes(stream.read(requested))
                if not block:
                    raise OSError(
                        f"Incomplete media payload: expected {self._total_size}, "
                        f"read {written} bytes"
                    )
                written += output.write(block)
        finally:
            stream.close()
        if written != self._total_size:
            raise OSError(
                f"Incomplete media payload: expected {self._total_size}, "
                f"wrote {written} bytes"
            )

    def _write_legacy_payload(self, output):
        path = Path(self._db_path).resolve()
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        try:
            row = connection.execute(
                "SELECT full_data FROM items "
                "WHERE id=? AND storage_state='ready'",
                (self._node_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None or row[0] is None:
            raise ValueError("Media payload is unavailable")
        payload = self._crypto.decrypt(
            row[0],
            aad=self._crypto.item_aad(self._node_id, "full_data"),
        )
        self._raise_if_cancelled()
        written = output.write(payload)
        if written != len(payload):
            raise OSError(
                f"Incomplete media payload: expected {len(payload)}, "
                f"wrote {written} bytes"
            )

    @Slot()
    def run(self):
        temp_path = ""
        try:
            self._raise_if_cancelled()
            temp_dir = metadata_temp_directory()
            if self._total_size > 0:
                free_bytes = shutil.disk_usage(temp_dir).free
                if free_bytes < self._total_size + 64 * 1024 * 1024:
                    raise OSError(
                        "Not enough temporary disk space to index media metadata"
                    )
            descriptor, temp_path = create_guarded_metadata_temp_file(
                self._suffix(),
            )
            with os.fdopen(descriptor, "wb") as output:
                if self._is_chunked:
                    self._write_chunked_payload(output)
                else:
                    self._write_legacy_payload(output)

            self._raise_if_cancelled()
            if self._media_type == "audio":
                metadata = read_mutagen_metadata(temp_path)
            else:
                metadata = read_media_metadata(
                    temp_path,
                    media_type=self._media_type,
                ).embedded_metadata
            self._raise_if_cancelled()
            self.finished.emit(self._node_id, list(metadata or ()))
        except InterruptedError:
            self.cancelled.emit(self._node_id)
        except Exception as exc:
            self.failed.emit(
                self._node_id,
                str(exc) or "Unable to read embedded metadata",
            )
        finally:
            if temp_path:
                discard_guarded_metadata_temp_file(temp_path)
