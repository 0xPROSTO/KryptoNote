import sqlite3

from PySide6.QtCore import QIODevice


class BlockEncryptedStream(QIODevice):
    def __init__(self, db_path, crypto_manager, item_id, total_size, chunk_size):
        super().__init__()
        self.db_path = db_path
        self.crypto = crypto_manager
        self.item_id = item_id
        self._size = total_size
        self._pos = 0
        self.chunk_size = chunk_size
        self.conn = None
        self.cursor = None
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def open(self, mode):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            return super().open(mode)

        except Exception as e:
            print(f"IO Error: {e}")
            return False

    def close(self):
        if self.conn:
            self.conn.close()

        super().close()

    def isSequential(self):
        return False

    def size(self):
        return self._size

    def bytesAvailable(self):
        return self._size - self._pos

    def pos(self):
        return self._pos

    def seek(self, pos):
        if 0 <= pos <= self._size:
            self._pos = pos
            return True

        return False

    def readData(self, max_len):
        try:
            if self._pos >= self._size:
                return b""
            chunk_idx = self._pos // self.chunk_size
            offset_in_chunk = self._pos % self.chunk_size
            self.cursor.execute(
                "SELECT data FROM media_chunks WHERE item_id=? AND chunk_index=?",
                (self.item_id, chunk_idx),
            )

            row = self.cursor.fetchone()
            self.cursor.fetchall()  # Finalize statement to release read lock
            if not row or not row[0]:
                return b""
            decrypted_chunk = self.crypto.decrypt(row[0])
            to_read = min(max_len, len(decrypted_chunk) - offset_in_chunk)
            result = decrypted_chunk[offset_in_chunk: offset_in_chunk + to_read]
            self._pos += len(result)
            return result

        except Exception as e:
            print(f"Stream Error: {e}")
            return b""

    def writeData(self, data):
        return -1
