import concurrent.futures
import sqlite3
import time
from datetime import datetime

from .models import NodeItemDTO, ConnectionDTO
from ..crypto import CryptoManager
from ...config import Config


# Shared chunked-media writer

def write_chunked_media(
    cursor, conn, crypto, item_type, x, y, w, h, title, thumb,
    file_path, chunk_size, progress_callback=None,
    media_width=0, media_height=0, media_duration=0.0,
):
    enc_title = crypto.encrypt(title.encode())
    enc_thumb = crypto.encrypt(thumb) if thumb else None

    with open(file_path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()

    total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
    now = datetime.now().isoformat(timespec="seconds")

    cursor.execute("""
        INSERT INTO items (type, title, x, y, width, height, thumbnail, is_chunked, total_size,
                           created_at, updated_at, media_width, media_height, media_duration)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
    """, (
        item_type, enc_title, x, y, w, h, enc_thumb, file_size,
        now, now, media_width, media_height, media_duration,
    ))
    item_id = cursor.lastrowid

    with open(file_path, "rb") as f:
        index = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            if progress_callback:
                progress_callback(index + 1, total_chunks, "Encrypting")

            enc_chunk = crypto.encrypt(chunk)
            cursor.execute(
                "INSERT INTO media_chunks (item_id, chunk_index, data) VALUES (?, ?, ?)",
                (item_id, index, enc_chunk),
            )

            index += 1
            if index % 25 == 0:
                if progress_callback:
                    progress_callback(index, total_chunks, "Writing to disk")
                conn.commit()

    if progress_callback:
        progress_callback(total_chunks, total_chunks, "Finalizing")

    conn.commit()
    return item_id


# Repository

class NodeRepository:
    def __init__(self, db_conn, crypto: CryptoManager = None):
        self.conn_manager = db_conn
        self.conn = db_conn.conn
        self.cursor = db_conn.cursor
        self.crypto = crypto
        self._background_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def close(self):
        """Shutdown background executor. Call from window closeEvent."""
        self._background_executor.shutdown(wait=False)

    # Background execution

    def _execute_on_separate_connection(self, operation, on_start=None, on_finish=None, on_waiting_lock=None, label="operation"):
        db_path = getattr(self.conn_manager, "db_path", ":memory:")

        if db_path == ":memory:":
            if on_start:
                on_start()
            operation(self.cursor, self.conn)
            self.conn.commit()
            if on_finish:
                on_finish()
            return

        try:
            if on_start:
                on_start()

            def _run():
                try:
                    last_error = None
                    for attempt in range(1, 9):
                        v_conn = None
                        try:
                            v_conn = sqlite3.connect(db_path, timeout=1.0)
                            v_conn.execute("PRAGMA busy_timeout=1000;")
                            v_conn.execute("PRAGMA journal_mode=WAL;")
                            v_cursor = v_conn.cursor()
                            operation(v_cursor, v_conn)
                            v_conn.commit()
                            return
                        except sqlite3.OperationalError as e:
                            last_error = e
                            if "locked" not in str(e).lower() and "busy" not in str(e).lower():
                                raise
                            if on_waiting_lock:
                                on_waiting_lock(attempt)
                            time.sleep(min(0.25 * attempt, 1.5))
                        finally:
                            if v_conn is not None:
                                v_conn.close()
                    if last_error is not None:
                        raise last_error
                except Exception as e:
                    print(f"Background {label} Error: {e}")
                finally:
                    if on_finish:
                        on_finish()

            self._background_executor.submit(_run)
        except Exception as e:
            print(f"CRASH IN {label}: {e}")
            if on_finish:
                on_finish()

    # CRUD

    def add_item(
            self, item_type, x, y, w, h, title="", text=None, thumb=None,
            data=None, title_size=14, text_size=10, media_width=0,
            media_height=0, media_duration=0.0
    ):
        enc_title = self.crypto.encrypt((title or "").encode())
        enc_text = self.crypto.encrypt(text.encode()) if text else None
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        enc_data = self.crypto.encrypt(data) if data else None
        is_chunked = 0
        total_size = len(data) if data else 0
        now = datetime.now().isoformat(timespec="seconds")

        self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, text_content, thumbnail, full_data,
                                               is_chunked, total_size, title_size, text_size, created_at, updated_at,
                                               media_width, media_height, media_duration)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item_type, enc_title, x, y, w, h, enc_text, enc_thumb,
                                enc_data, is_chunked, total_size, title_size, text_size,
                                now, now, media_width, media_height, media_duration,
                            ))
        item_id = self.cursor.lastrowid
        self.conn.commit()
        return item_id

    def add_streamed_media(
            self, item_type, x, y, w, h, title, thumb, file_path,
            progress_callback=None, media_width=0, media_height=0,
            media_duration=0.0
    ):
        """Thin wrapper around module-level write_chunked_media."""
        return write_chunked_media(
            self.cursor, self.conn, self.crypto,
            item_type, x, y, w, h, title, thumb,
            file_path, Config.CHUNK_SIZE, progress_callback,
            media_width, media_height, media_duration,
        )

    def get_chunk(self, item_id, chunk_index):
        self.cursor.execute(
            "SELECT data FROM media_chunks WHERE item_id=? AND chunk_index=?",
            (item_id, chunk_index),
        )
        row = self.cursor.fetchone()
        if row:
            return self.crypto.decrypt(row[0])
        return None

    def get_all_items(self):
        self.cursor.execute(
            "SELECT id, type, title, x, y, width, height, text_content, thumbnail, is_chunked, total_size, title_size, text_size, created_at, updated_at, media_width, media_height, media_duration FROM items"
        )

        rows = self.cursor.fetchall()
        decrypted_rows = []
        for r in rows:
            (
                rid, rtype, etitle, x, y, w, h, etext, ethumb, chunked,
                tsize, tsize_val, text_size_val, created_at, updated_at,
                media_width, media_height, media_duration,
            ) = r
            if self.crypto:
                dtitle = self.crypto.decrypt(etitle).decode() if etitle else ""
                dtext = self.crypto.decrypt(etext).decode() if etext else ""
                dthumb = self.crypto.decrypt(ethumb) if ethumb else None

            else:
                dtitle = ""
                dtext = ""
                dthumb = None

            decrypted_rows.append(NodeItemDTO(
                id=rid, type=rtype, title=dtitle, x=x, y=y, width=w, height=h,
                text_content=dtext, thumbnail=dthumb, is_chunked=bool(chunked), total_size=tsize,
                title_size=tsize_val, text_size=text_size_val,
                created_at=created_at or "", updated_at=updated_at or "",
                media_width=media_width or 0, media_height=media_height or 0,
                media_duration=media_duration or 0.0,
            ))
        return decrypted_rows

    def get_full_data(self, item_id):
        self.cursor.execute("SELECT full_data FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row and row[0]:
            return self.crypto.decrypt(row[0])
        return None

    def get_item_info(self, item_id):
        self.cursor.execute("SELECT id, type, is_chunked, total_size FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row:
            return NodeItemDTO(
                id=row[0], type=row[1], title="", x=0, y=0, width=0, height=0,
                is_chunked=bool(row[2]), total_size=row[3]
            )
        return None

    def update_pos(self, item_id, x, y):
        self.cursor.execute("UPDATE items SET x=?, y=? WHERE id=?", (x, y, item_id))
        self.conn.commit()

    def update_size(self, item_id, w, h):
        self.cursor.execute(
            "UPDATE items SET width=?, height=? WHERE id=?", (w, h, item_id)
        )
        self.conn.commit()

    def update_item_title(self, item_id, title):
        enc_title = self.crypto.encrypt((title or "").encode())
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET title=?, updated_at=? WHERE id=?",
            (enc_title, now, item_id),
        )
        self.conn.commit()

    def delete_item(self, item_id):
        self.delete_node_cascade(item_id)

    def update_text_content(self, item_id, title, new_text, title_size=14, text_size=10):
        enc_title = self.crypto.encrypt((title or "").encode())
        enc_text = self.crypto.encrypt(new_text.encode())
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET title=?, text_content=?, title_size=?, text_size=?, updated_at=? WHERE id=?",
            (enc_title, enc_text, title_size, text_size, now, item_id),
        )
        self.conn.commit()

    def add_connection(self, start_id, end_id, commit=True):
        self.cursor.execute(
            "INSERT INTO connections (start_id, end_id) VALUES (?, ?)",
            (start_id, end_id),
        )
        if commit:
            self.conn.commit()

        return self.cursor.lastrowid

    def commit_changes(self):
        self.conn.commit()

    def vacuum_database(
        self,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
    ):
        self.conn.commit()

        def do_vacuum(cursor, conn):
            conn.execute("VACUUM")

        self._execute_on_separate_connection(
            do_vacuum,
            on_start=on_start_vacuum,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            label="VACUUM",
        )

    def get_all_connections(self):
        self.cursor.execute("SELECT id, start_id, end_id FROM connections")
        rows = self.cursor.fetchall()
        return [ConnectionDTO(id=r[0], start_id=r[1], end_id=r[2]) for r in rows]

    def delete_connection(self, conn_id):
        self.cursor.execute("DELETE FROM connections WHERE id=?", (conn_id,))
        self.conn.commit()

    def delete_node_cascade(
        self,
        item_id,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
    ):
        self.cursor.execute("SELECT type, total_size FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()

        should_vacuum = False
        if row:
            item_type, total_size = row
            if item_type == "video" or (total_size and total_size > 10 * 1024 * 1024):
                should_vacuum = True
            if item_type == "video":
                try:
                    from ..io.stream import close_streams_for_item
                    close_streams_for_item(item_id)
                except Exception:
                    pass

        def do_delete(cursor, conn):
            cursor.execute("DELETE FROM connections WHERE start_id=? OR end_id=?", (item_id, item_id))
            cursor.execute("DELETE FROM media_chunks WHERE item_id=?", (item_id,))
            cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            conn.commit()
            if should_vacuum:
                conn.execute("VACUUM")

        self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum if should_vacuum else None,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            label="DELETE_NODE_CASCADE",
        )

    @staticmethod
    def _in_clause(items):
        """Build a safe parameterised IN clause: returns (sql_fragment, params)."""
        placeholders = ",".join("?" for _ in items)
        return f"({placeholders})", list(items)

    def delete_nodes_cascade(
        self,
        item_ids,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
    ):
        item_ids = [int(item_id) for item_id in item_ids]
        if not item_ids:
            if on_finish_vacuum:
                on_finish_vacuum()
            return

        in_sql, in_params = self._in_clause(item_ids)
        self.cursor.execute(
            f"SELECT id, type, total_size FROM items WHERE id IN {in_sql}",
            in_params,
        )
        rows = self.cursor.fetchall()

        should_vacuum = False
        try:
            from ..io.stream import close_streams_for_item
        except Exception:
            close_streams_for_item = None

        for item_id, item_type, total_size in rows:
            if item_type == "video" or (total_size and total_size > 10 * 1024 * 1024):
                should_vacuum = True
            if item_type == "video" and close_streams_for_item:
                close_streams_for_item(item_id)

        def do_delete(cursor, conn):
            cursor.execute(
                f"DELETE FROM connections WHERE start_id IN {in_sql} OR end_id IN {in_sql}",
                in_params + in_params,
            )
            cursor.execute(
                f"DELETE FROM media_chunks WHERE item_id IN {in_sql}",
                in_params,
            )
            cursor.execute(
                f"DELETE FROM items WHERE id IN {in_sql}",
                in_params,
            )
            conn.commit()
            if should_vacuum:
                conn.execute("VACUUM")

        self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum if should_vacuum else None,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            label="DELETE_NODES_CASCADE",
        )
