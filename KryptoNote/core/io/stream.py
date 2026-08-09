import sqlite3
import threading
import weakref
from pathlib import Path

from PySide6.QtCore import QIODevice

_active_streams = weakref.WeakSet()
_active_streams_lock = threading.RLock()


def close_streams_for_item(item_id):
    with _active_streams_lock:
        streams = [
            stream
            for stream in list(_active_streams)
            if getattr(stream, "item_id", None) == item_id
        ]
    for stream in streams:
        stream.close()


class BlockEncryptedStream(QIODevice):
    def __init__(self, db_path, crypto_manager, item_id, total_size, chunk_size):
        super().__init__()
        self.db_path = db_path
        self.crypto = crypto_manager
        self.item_id = item_id
        self._size = total_size
        self._read_pos = 0
        self._read_failed = False
        self.chunk_size = chunk_size
        self.conn = None
        self.cursor = None
        self._lock = threading.RLock()
        self._closed = False
        with _active_streams_lock:
            _active_streams.add(self)
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def open(self, mode):
        with self._lock:
            try:
                db_path = Path(self.db_path).resolve()
                uri = f"{db_path.as_uri()}?mode=ro"
                self.conn = sqlite3.connect(
                    uri, uri=True, check_same_thread=False, timeout=5.0
                )
                self.cursor = self.conn.cursor()
                self._closed = False
                return super().open(mode)

            except Exception as e:
                if self.cursor is not None:
                    self.cursor.close()
                if self.conn is not None:
                    self.conn.close()
                self.cursor = None
                self.conn = None
                self._closed = True
                with _active_streams_lock:
                    _active_streams.discard(self)
                self.setErrorString(str(e))
                print(f"IO Error: {e}")
                return False

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
            self.cursor = None
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
            self.conn = None
            with _active_streams_lock:
                _active_streams.discard(self)
            super().close()

    def isSequential(self):
        return False

    def size(self):
        return self._size

    def bytesAvailable(self):
        with self._lock:
            if self._closed or not self.isOpen():
                return 0
            logical_pos = max(0, int(super().pos()))
            if self._read_failed:
                return max(0, self._read_pos - logical_pos)
            return max(0, self._size - logical_pos)

    def seek(self, pos):
        with self._lock:
            if self._closed or not 0 <= pos <= self._size:
                return False
            if not super().seek(pos):
                return False
            self._read_pos = pos
            self._read_failed = False
            self.setErrorString("")
            return True

    def readData(self, max_len):
        with self._lock:
            try:
                if self._closed or not self.cursor:
                    self.setErrorString("Encrypted media stream is closed")
                    return -1
                if self._read_failed:
                    return -1
                if self._read_pos >= self._size or max_len <= 0:
                    return b""

                remaining = min(int(max_len), self._size - self._read_pos)
                output = bytearray()
                while remaining > 0:
                    chunk_idx = self._read_pos // self.chunk_size
                    offset_in_chunk = self._read_pos % self.chunk_size
                    self.cursor.execute(
                        "SELECT media_chunks.data FROM media_chunks "
                        "JOIN items ON items.id=media_chunks.item_id "
                        "WHERE media_chunks.item_id=? "
                        "AND media_chunks.chunk_index=? "
                        "AND items.storage_state='ready'",
                        (self.item_id, chunk_idx),
                    )

                    row = self.cursor.fetchone()
                    self.cursor.fetchall()
                    if not row or not row[0]:
                        raise OSError(
                            f"Missing media chunk {chunk_idx} for item {self.item_id}"
                        )

                    decrypted_chunk = self.crypto.decrypt(
                        row[0],
                        aad=self.crypto.chunk_aad(self.item_id, chunk_idx),
                    )
                    available = len(decrypted_chunk) - offset_in_chunk
                    if available <= 0:
                        raise OSError(
                            f"Invalid media chunk {chunk_idx} for item {self.item_id}"
                        )
                    to_read = min(remaining, available)
                    output.extend(
                        decrypted_chunk[
                            offset_in_chunk: offset_in_chunk + to_read
                        ]
                    )
                    self._read_pos += to_read
                    remaining -= to_read

                return bytes(output)

            except Exception as e:
                self._read_failed = True
                self.setErrorString(str(e))
                print(f"Stream Error: {e}")
                if "output" in locals() and output:
                    return bytes(output)
                return -1

    def writeData(self, data):
        return -1

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
