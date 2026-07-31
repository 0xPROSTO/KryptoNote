import concurrent.futures
import sqlite3
import time
from datetime import datetime

from .models import NodeItemDTO, ConnectionDTO, TagDTO
from ..crypto import CryptoManager
from ..constants import MEDIA_CHUNK_SIZE
from ..exceptions import OperationCancelledError


# Shared chunked-media writer

def write_chunked_media(
    cursor, conn, crypto, item_type, x, y, w, h, title, thumb,
    file_path, chunk_size, progress_callback=None,
    media_width=0, media_height=0, media_duration=0.0,
    cancel_check=None, original_filename="",
):
    with open(file_path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()

    total_chunks = (file_size + chunk_size - 1) // chunk_size if file_size > 0 else 1
    now = datetime.now().isoformat(timespec="seconds")
    item_id = None

    cursor.execute("SAVEPOINT chunked_media_import")
    try:
        cursor.execute("""
            INSERT INTO items (type, title, x, y, width, height, thumbnail, is_chunked, total_size,
                               created_at, updated_at, media_width, media_height, media_duration,
                               original_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_type, b"", x, y, w, h, None, file_size,
            now, now, media_width, media_height, media_duration, None,
        ))
        item_id = cursor.lastrowid
        enc_title = crypto.encrypt(
            title.encode(), aad=crypto.item_aad(item_id, "title")
        )
        enc_thumb = (
            crypto.encrypt(
                thumb, aad=crypto.item_aad(item_id, "thumbnail")
            )
            if thumb else None
        )
        enc_original_filename = (
            crypto.encrypt(
                (original_filename or "").encode(),
                aad=crypto.item_aad(item_id, "original_filename"),
            )
            if original_filename else None
        )
        cursor.execute(
            "UPDATE items SET title=?, thumbnail=?, original_filename=? "
            "WHERE id=?",
            (enc_title, enc_thumb, enc_original_filename, item_id),
        )

        with open(file_path, "rb") as f:
            index = 0
            while True:
                if cancel_check and cancel_check():
                    raise OperationCancelledError("Media import cancelled")
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                enc_chunk = crypto.encrypt(
                    chunk, aad=crypto.chunk_aad(item_id, index)
                )
                cursor.execute(
                    "INSERT INTO media_chunks (item_id, chunk_index, data) VALUES (?, ?, ?)",
                    (item_id, index, enc_chunk),
                )

                index += 1
                if progress_callback:
                    status = "Writing to disk" if index % 25 == 0 else "Encrypting"
                    progress_callback(index, total_chunks, status)

        if progress_callback:
            progress_callback(total_chunks, total_chunks, "Finalizing")

        cursor.execute("RELEASE SAVEPOINT chunked_media_import")
        conn.commit()
        return item_id
    except Exception:
        try:
            cursor.execute("ROLLBACK TO SAVEPOINT chunked_media_import")
            cursor.execute("RELEASE SAVEPOINT chunked_media_import")
        except sqlite3.Error:
            conn.rollback()
        raise

# Repository

class NodeRepository:
    def __init__(self, db_conn, crypto: CryptoManager = None):
        self.conn_manager = db_conn
        self.conn = db_conn.conn
        self.cursor = db_conn.cursor
        self.crypto = crypto
        self._background_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._closed = False

    def close(self, wait=True):
        """Stop accepting work and optionally wait for active DB jobs."""
        if self._closed:
            return
        self._closed = True
        self._background_executor.shutdown(wait=wait, cancel_futures=False)

    # Background execution

    def _execute_on_separate_connection(
        self,
        operation,
        on_start=None,
        on_finish=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
        label="operation",
    ):
        db_path = getattr(self.conn_manager, "db_path", ":memory:")

        def _notify_error(exc):
            if on_error:
                on_error(exc)

        if db_path == ":memory:":
            try:
                if on_start:
                    on_start()
                operation(self.cursor, self.conn)
                self.conn.commit()
                if on_success:
                    on_success()
            except Exception as exc:
                self.conn.rollback()
                _notify_error(exc)
                raise
            finally:
                if on_finish:
                    on_finish()
            return None

        try:
            if on_start:
                on_start()
        except Exception as exc:
            _notify_error(exc)
            if on_finish:
                on_finish()
            raise

        def _run():
            try:
                last_error = None
                for attempt in range(1, 9):
                    v_conn = None
                    try:
                        v_conn = sqlite3.connect(db_path, timeout=1.0)
                        v_conn.execute("PRAGMA foreign_keys=ON;")
                        v_conn.execute("PRAGMA busy_timeout=1000;")
                        v_conn.execute("PRAGMA journal_mode=WAL;")
                        v_cursor = v_conn.cursor()
                        operation(v_cursor, v_conn)
                        v_conn.commit()
                        if on_success:
                            on_success()
                        return
                    except sqlite3.OperationalError as exc:
                        if v_conn is not None:
                            v_conn.rollback()
                        last_error = exc
                        if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                            raise
                        if on_waiting_lock:
                            on_waiting_lock(attempt)
                        time.sleep(min(0.25 * attempt, 1.5))
                    except Exception:
                        if v_conn is not None:
                            v_conn.rollback()
                        raise
                    finally:
                        if v_conn is not None:
                            v_conn.close()
                if last_error is not None:
                    raise last_error
            except Exception as exc:
                print(f"Background {label} Error: {exc}")
                _notify_error(exc)
                raise
            finally:
                if on_finish:
                    on_finish()

        try:
            return self._background_executor.submit(_run)
        except Exception as exc:
            print(f"CRASH IN {label}: {exc}")
            _notify_error(exc)
            if on_finish:
                on_finish()
            raise

    # CRUD
    def add_item(
            self, item_type, x, y, w, h, title="", text=None, thumb=None,
            data=None, title_size=14, text_size=10, media_width=0,
            media_height=0, media_duration=0.0, original_filename="",
            frame_locked=False, frame_color="", frame_opacity=0.21,
    ):
        is_chunked = 0
        total_size = len(data) if data else 0
        now = datetime.now().isoformat(timespec="seconds")

        self.cursor.execute("SAVEPOINT add_item")
        try:
            self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, text_content, thumbnail, full_data,
                                               is_chunked, total_size, title_size, text_size, created_at, updated_at,
                                               media_width, media_height, media_duration, original_filename,
                                               frame_locked, frame_color, frame_opacity)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item_type, b"", x, y, w, h, None, None,
                                None, is_chunked, total_size, title_size, text_size,
                                now, now, media_width, media_height, media_duration,
                                None, int(bool(frame_locked)),
                                frame_color or "", float(frame_opacity),
                            ))
            item_id = self.cursor.lastrowid
            aad = self.crypto.item_aad
            enc_title = self.crypto.encrypt(
                (title or "").encode(), aad=aad(item_id, "title")
            )
            enc_text = (
                self.crypto.encrypt(
                    text.encode(), aad=aad(item_id, "text_content")
                )
                if text else None
            )
            enc_thumb = (
                self.crypto.encrypt(
                    thumb, aad=aad(item_id, "thumbnail")
                )
                if thumb else None
            )
            enc_data = (
                self.crypto.encrypt(
                    data, aad=aad(item_id, "full_data")
                )
                if data else None
            )
            enc_original_filename = (
                self.crypto.encrypt(
                    (original_filename or "").encode(),
                    aad=aad(item_id, "original_filename"),
                )
                if original_filename else None
            )
            self.cursor.execute(
                "UPDATE items SET title=?, text_content=?, thumbnail=?, "
                "full_data=?, original_filename=? WHERE id=?",
                (
                    enc_title,
                    enc_text,
                    enc_thumb,
                    enc_data,
                    enc_original_filename,
                    item_id,
                ),
            )
            self.cursor.execute("RELEASE SAVEPOINT add_item")
            self.conn.commit()
            return item_id
        except Exception:
            self.cursor.execute("ROLLBACK TO SAVEPOINT add_item")
            self.cursor.execute("RELEASE SAVEPOINT add_item")
            raise

    def add_streamed_media(
            self, item_type, x, y, w, h, title, thumb, file_path,
            progress_callback=None, media_width=0, media_height=0,
            media_duration=0.0, original_filename=""
    ):
        """Thin wrapper around module-level write_chunked_media."""
        return write_chunked_media(
            self.cursor, self.conn, self.crypto,
            item_type, x, y, w, h, title, thumb,
            file_path, MEDIA_CHUNK_SIZE, progress_callback,
            media_width, media_height, media_duration,
            original_filename=original_filename,
        )

    def get_chunk(self, item_id, chunk_index):
        self.cursor.execute(
            "SELECT data FROM media_chunks WHERE item_id=? AND chunk_index=?",
            (item_id, chunk_index),
        )
        row = self.cursor.fetchone()
        if row:
            return self.crypto.decrypt(
                row[0], aad=self.crypto.chunk_aad(item_id, chunk_index)
            )
        return None

    _ITEM_SELECT = (
        "SELECT id, type, title, x, y, width, height, text_content, thumbnail, "
        "is_chunked, total_size, title_size, text_size, created_at, updated_at, "
        "media_width, media_height, media_duration, original_filename, "
        "frame_locked, frame_color, frame_opacity "
        "FROM items ORDER BY id"
    )

    def get_all_items(self, include_thumbnails=True):
        items = []
        for batch in self.iter_item_batches(
            batch_size=200, include_thumbnails=include_thumbnails
        ):
            items.extend(batch)
        return items

    def iter_item_batches(self, batch_size=200, include_thumbnails=True):
        """Yield decrypted DTO batches while letting the event loop breathe."""
        batch_size = max(1, int(batch_size))
        cursor = self.conn.cursor()
        try:
            cursor.execute(self._ITEM_SELECT)
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [
                    self._decode_item_row(row, include_thumbnails) for row in rows
                ]
        finally:
            cursor.close()

    def get_item_count(self):
        return int(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])

    def _decode_item_row(self, row, include_thumbnail):
        (
            item_id, item_type, encrypted_title, x, y, width, height,
            encrypted_text, encrypted_thumbnail, is_chunked, total_size,
            title_size, text_size, created_at, updated_at, media_width,
            media_height, media_duration, encrypted_original_filename,
            frame_locked, frame_color, frame_opacity,
        ) = row
        if self.crypto:
            title = (
                self.crypto.decrypt(
                    encrypted_title,
                    aad=self.crypto.item_aad(item_id, "title"),
                ).decode()
                if encrypted_title else ""
            )
            text = (
                self.crypto.decrypt(
                    encrypted_text,
                    aad=self.crypto.item_aad(item_id, "text_content"),
                ).decode()
                if encrypted_text else ""
            )
            thumbnail = (
                self.crypto.decrypt(
                    encrypted_thumbnail,
                    aad=self.crypto.item_aad(item_id, "thumbnail"),
                )
                if include_thumbnail and encrypted_thumbnail else None
            )
            original_filename = (
                self.crypto.decrypt(
                    encrypted_original_filename,
                    aad=self.crypto.item_aad(item_id, "original_filename"),
                ).decode()
                if encrypted_original_filename else ""
            )
        else:
            title = ""
            text = ""
            thumbnail = None
            original_filename = ""
        return NodeItemDTO(
            id=item_id, type=item_type, title=title, x=x, y=y,
            width=width, height=height, text_content=text, thumbnail=thumbnail,
            is_chunked=bool(is_chunked), total_size=total_size,
            title_size=title_size, text_size=text_size,
            created_at=created_at or "", updated_at=updated_at or "",
            media_width=media_width or 0, media_height=media_height or 0,
            media_duration=media_duration or 0.0,
            original_filename=original_filename,
            frame_locked=bool(frame_locked),
            frame_color=frame_color or "",
            frame_opacity=float(
                0.21 if frame_opacity is None else frame_opacity
            ),
        )


    # Tags

    def get_all_tags(self):
        self.cursor.execute("SELECT id, name, color FROM tags ORDER BY id")
        tags = []
        for tag_id, encrypted_name, color in self.cursor.fetchall():
            try:
                name = (
                    self.crypto.decrypt(
                        encrypted_name, aad=self.crypto.tag_aad(tag_id)
                    ).decode()
                    if encrypted_name else ""
                )
            except Exception:
                continue
            if name:
                tags.append(TagDTO(tag_id, name, color))
        return sorted(tags, key=lambda tag: tag.name.casefold())

    def ensure_tag(self, name, color):
        normalized = (name or "").strip().lstrip("@").casefold()
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        if len(normalized) > 32:
            raise ValueError("Tag name is too long")
        if not all(char.isalnum() or char in " _-" for char in normalized):
            raise ValueError("Use letters, numbers, spaces, underscore or hyphen")
        for tag in self.get_all_tags():
            if tag.name.casefold() == normalized:
                return tag.id
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute("SAVEPOINT add_tag")
        try:
            self.cursor.execute(
                "INSERT INTO tags (name, color, created_at) VALUES (?, ?, ?)",
                (b"", color, now),
            )
            tag_id = self.cursor.lastrowid
            encrypted_name = self.crypto.encrypt(
                normalized.encode(), aad=self.crypto.tag_aad(tag_id)
            )
            self.cursor.execute(
                "UPDATE tags SET name=? WHERE id=?",
                (encrypted_name, tag_id),
            )
            self.cursor.execute("RELEASE SAVEPOINT add_tag")
            self.conn.commit()
            return tag_id
        except Exception:
            self.cursor.execute("ROLLBACK TO SAVEPOINT add_tag")
            self.cursor.execute("RELEASE SAVEPOINT add_tag")
            raise

    def update_tag(self, tag_id, name, color):
        normalized = (name or "").strip().lstrip("@").casefold()
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        if len(normalized) > 32:
            raise ValueError("Tag name is too long")
        if not all(char.isalnum() or char in " _-" for char in normalized):
            raise ValueError("Use letters, numbers, spaces, underscore or hyphen")
        for tag in self.get_all_tags():
            if tag.id != tag_id and tag.name.casefold() == normalized:
                raise ValueError("A tag with this name already exists")
        self.cursor.execute(
            "UPDATE tags SET name=?, color=? WHERE id=?",
            (
                self.crypto.encrypt(
                    normalized.encode(), aad=self.crypto.tag_aad(tag_id)
                ),
                color,
                tag_id,
            ),
        )
        if self.cursor.rowcount == 0:
            raise ValueError("Tag not found")
        self.conn.commit()

    def get_item_tags_map(self):
        tags = {tag.id: tag for tag in self.get_all_tags()}
        result = {}
        self.cursor.execute(
            "SELECT item_id, tag_id FROM item_tags ORDER BY item_id, priority, tag_id"
        )
        for item_id, tag_id in self.cursor.fetchall():
            tag = tags.get(tag_id)
            if tag:
                result.setdefault(item_id, []).append(tag)
        return result

    def get_item_tags(self, item_id):
        self.cursor.execute(
            """
            SELECT tags.id, tags.name, tags.color
            FROM item_tags
            JOIN tags ON tags.id = item_tags.tag_id
            WHERE item_tags.item_id=?
            ORDER BY item_tags.priority, tags.id
            """,
            (item_id,),
        )
        tags = []
        for tag_id, encrypted_name, color in self.cursor.fetchall():
            try:
                name = (
                    self.crypto.decrypt(
                        encrypted_name,
                        aad=self.crypto.tag_aad(tag_id),
                    ).decode()
                    if encrypted_name
                    else ""
                )
            except Exception:
                continue
            if name:
                tags.append(TagDTO(tag_id, name, color))
        return tags

    def set_item_tag(self, item_id, tag_id, enabled):
        if enabled:
            self.cursor.execute(
                "SELECT COALESCE(MAX(priority), -1) + 1 FROM item_tags WHERE item_id=?",
                (item_id,),
            )
            priority = self.cursor.fetchone()[0]
            self.cursor.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag_id, priority) VALUES (?, ?, ?)",
                (item_id, tag_id, priority),
            )
        else:
            self.cursor.execute(
                "DELETE FROM item_tags WHERE item_id=? AND tag_id=?",
                (item_id, tag_id),
            )
        self.conn.commit()

    def set_item_tag_order(self, item_id, tag_ids):
        for priority, tag_id in enumerate(tag_ids):
            self.cursor.execute(
                "UPDATE item_tags SET priority=? WHERE item_id=? AND tag_id=?",
                (priority, item_id, tag_id),
            )
        self.conn.commit()

    def get_full_data(self, item_id):
        self.cursor.execute("SELECT full_data FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row and row[0]:
            return self.crypto.decrypt(
                row[0], aad=self.crypto.item_aad(item_id, "full_data")
            )
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
        enc_title = self.crypto.encrypt(
            (title or "").encode(),
            aad=self.crypto.item_aad(item_id, "title"),
        )
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET title=?, updated_at=? WHERE id=?",
            (enc_title, now, item_id),
        )
        self.conn.commit()

    def update_frame_locked(self, item_id, locked):
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET frame_locked=?, updated_at=? "
            "WHERE id=? AND type='frame'",
            (int(bool(locked)), now, item_id),
        )
        if self.cursor.rowcount == 0:
            raise ValueError("Frame not found")
        self.conn.commit()

    def update_frame_properties(
            self, item_id, title, frame_color, frame_opacity
    ):
        enc_title = self.crypto.encrypt(
            (title or "").encode(),
            aad=self.crypto.item_aad(item_id, "title"),
        )
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET title=?, frame_color=?, frame_opacity=?, "
            "updated_at=? WHERE id=? AND type='frame'",
            (
                enc_title,
                frame_color or "",
                float(frame_opacity),
                now,
                item_id,
            ),
        )
        if self.cursor.rowcount == 0:
            raise ValueError("Frame not found")
        self.conn.commit()

    def delete_item(self, item_id):
        self.delete_node_cascade(item_id)

    def update_text_content(self, item_id, title, new_text, title_size=14, text_size=10):
        enc_title = self.crypto.encrypt(
            (title or "").encode(),
            aad=self.crypto.item_aad(item_id, "title"),
        )
        enc_text = self.crypto.encrypt(
            new_text.encode(),
            aad=self.crypto.item_aad(item_id, "text_content"),
        )
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET title=?, text_content=?, title_size=?, text_size=?, updated_at=? WHERE id=?",
            (enc_title, enc_text, title_size, text_size, now, item_id),
        )
        self.conn.commit()

    def add_connection(self, start_id, end_id, commit=True):
        low_id, high_id = sorted((int(start_id), int(end_id)))
        self.cursor.execute(
            """
            SELECT id
            FROM connections
            WHERE min(start_id, end_id)=? AND max(start_id, end_id)=?
            ORDER BY id
            LIMIT 1
            """,
            (low_id, high_id),
        )
        existing = self.cursor.fetchone()
        if existing:
            if commit:
                self.conn.commit()
            return existing[0]

        self.cursor.execute(
            "INSERT OR IGNORE INTO connections (start_id, end_id) VALUES (?, ?)",
            (start_id, end_id),
        )
        connection_id = self.cursor.lastrowid if self.cursor.rowcount else None
        if connection_id is None:
            self.cursor.execute(
                """
                SELECT id
                FROM connections
                WHERE min(start_id, end_id)=? AND max(start_id, end_id)=?
                """,
                (low_id, high_id),
            )
            row = self.cursor.fetchone()
            if row is None:
                raise sqlite3.IntegrityError("Failed to create connection")
            connection_id = row[0]
        if commit:
            self.conn.commit()
        return connection_id

    def commit_changes(self):
        self.conn.commit()

    def vacuum_database(
        self,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
    ):
        self.conn.commit()

        def do_vacuum(cursor, conn):
            conn.execute("VACUUM")

        return self._execute_on_separate_connection(
            do_vacuum,
            on_start=on_start_vacuum,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
            label="VACUUM",
        )

    def get_all_connections(self):
        connections = []
        for batch in self.iter_connection_batches(200):
            connections.extend(batch)
        return connections

    def iter_connection_batches(self, batch_size=200):
        batch_size = max(1, int(batch_size))
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, start_id, end_id FROM connections ORDER BY id"
            )
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [
                    ConnectionDTO(id=row[0], start_id=row[1], end_id=row[2])
                    for row in rows
                ]
        finally:
            cursor.close()

    def get_connection_count(self):
        return int(
            self.conn.execute("SELECT COUNT(*) FROM connections").fetchone()[0]
        )

    def delete_connection(self, conn_id):
        self.cursor.execute("DELETE FROM connections WHERE id=?", (conn_id,))
        self.conn.commit()

    def delete_node_cascade(
        self,
        item_id,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
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
            cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            conn.commit()
            if should_vacuum:
                try:
                    conn.execute("VACUUM")
                except sqlite3.Error as exc:
                    print(f"VACUUM after delete failed: {exc}")

        return self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum if should_vacuum else None,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
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
        on_success=None,
        on_error=None,
    ):
        item_ids = list(
            dict.fromkeys(int(item_id) for item_id in item_ids)
        )
        if not item_ids:
            if on_finish_vacuum:
                on_finish_vacuum()
            return

        rows = []
        for start in range(0, len(item_ids), 900):
            batch = item_ids[start:start + 900]
            in_sql, in_params = self._in_clause(batch)
            self.cursor.execute(
                f"SELECT id, type, total_size FROM items WHERE id IN {in_sql}",
                in_params,
            )
            rows.extend(self.cursor.fetchall())

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
            for start in range(0, len(item_ids), 900):
                batch = item_ids[start:start + 900]
                in_sql, in_params = self._in_clause(batch)
                cursor.execute(
                    f"DELETE FROM items WHERE id IN {in_sql}",
                    in_params,
                )
            conn.commit()
            if should_vacuum:
                try:
                    conn.execute("VACUUM")
                except sqlite3.Error as exc:
                    print(f"VACUUM after delete failed: {exc}")

        return self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum if should_vacuum else None,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
            label="DELETE_NODES_CASCADE",
        )
