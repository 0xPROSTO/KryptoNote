import concurrent.futures
import json
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .models import NodeItemDTO, ConnectionDTO, TagDTO
from .connection import (
    READY_STORAGE_STATE,
    STAGED_STORAGE_STATE,
    acquire_database_operation_lock,
    cleanup_staged_items,
    open_sqlite_connection,
    validate_database_integrity,
)
from .operations import MaintenanceResult, read_database_space_stats
from ..crypto import CryptoManager
from ..constants import MEDIA_CHUNK_SIZE, MEDIA_NODE_TYPES, PLAYABLE_NODE_TYPES
from ..exceptions import InsufficientDiskSpaceError, OperationCancelledError


# Shared chunked-media writer


def _encode_media_metadata(metadata):
    if not metadata:
        return None
    return json.dumps(
        list(metadata),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_media_metadata(payload):
    if not payload:
        return []
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return []
    if not isinstance(decoded, list):
        return []
    return [entry for entry in decoded if isinstance(entry, dict)]

def write_chunked_media(
    cursor, conn, crypto, item_type, x, y, w, h, title, thumb,
    file_path, chunk_size, progress_callback=None,
    media_width=0, media_height=0, media_duration=0.0,
    cancel_check=None, original_filename="", media_metadata=None,
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
                               original_filename, media_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_type, b"", x, y, w, h, None, file_size,
            now, now, media_width, media_height, media_duration, None, None,
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
        metadata_payload = _encode_media_metadata(media_metadata)
        enc_media_metadata = (
            crypto.encrypt(
                metadata_payload,
                aad=crypto.item_aad(item_id, "media_metadata"),
            )
            if metadata_payload else None
        )
        cursor.execute(
            "UPDATE items SET title=?, thumbnail=?, original_filename=?, "
            "media_metadata=? "
            "WHERE id=?",
            (
                enc_title,
                enc_thumb,
                enc_original_filename,
                enc_media_metadata,
                item_id,
            ),
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
    _CLONE_CHUNK_COMMIT_BATCH = 8
    _CLONE_DISK_RESERVE_BYTES = 256 * 1024 * 1024

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

        # A pending main-connection write can lock this database's worker.
        if self.conn.in_transaction:
            self.conn.commit()

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
                    succeeded = False
                    try:
                        v_conn = open_sqlite_connection(
                            db_path, timeout=1.0, must_exist=True
                        )
                        v_cursor = v_conn.cursor()
                        operation(v_cursor, v_conn)
                        v_conn.commit()
                        succeeded = True
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
                    if succeeded:
                        if on_success:
                            on_success()
                        return
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
            commit=True,
            media_metadata=None,
    ):
        is_chunked = 0
        total_size = len(data) if data else 0
        now = datetime.now().isoformat(timespec="seconds")

        if not commit and not self.conn.in_transaction:
            self.conn.execute("BEGIN")
        self.cursor.execute("SAVEPOINT add_item")
        try:
            self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, text_content, thumbnail, full_data,
                                               is_chunked, total_size, title_size, text_size, created_at, updated_at,
                                               media_width, media_height, media_duration, original_filename,
                                               frame_locked, frame_color, frame_opacity, media_metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item_type, b"", x, y, w, h, None, None,
                                None, is_chunked, total_size, title_size, text_size,
                                now, now, media_width, media_height, media_duration,
                                None, int(bool(frame_locked)),
                                frame_color or "", float(frame_opacity), None,
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
            metadata_payload = _encode_media_metadata(media_metadata)
            enc_media_metadata = (
                self.crypto.encrypt(
                    metadata_payload,
                    aad=aad(item_id, "media_metadata"),
                )
                if metadata_payload else None
            )
            self.cursor.execute(
                "UPDATE items SET title=?, text_content=?, thumbnail=?, "
                "full_data=?, original_filename=?, media_metadata=? WHERE id=?",
                (
                    enc_title,
                    enc_text,
                    enc_thumb,
                    enc_data,
                    enc_original_filename,
                    enc_media_metadata,
                    item_id,
                ),
            )
            self.cursor.execute("RELEASE SAVEPOINT add_item")
            if commit:
                self.conn.commit()
            return item_id
        except Exception:
            self.cursor.execute("ROLLBACK TO SAVEPOINT add_item")
            self.cursor.execute("RELEASE SAVEPOINT add_item")
            raise

    def add_streamed_media(
            self, item_type, x, y, w, h, title, thumb, file_path,
            progress_callback=None, media_width=0, media_height=0,
            media_duration=0.0, original_filename="", media_metadata=None,
    ):
        """Thin wrapper around module-level write_chunked_media."""
        return write_chunked_media(
            self.cursor, self.conn, self.crypto,
            item_type, x, y, w, h, title, thumb,
            file_path, MEDIA_CHUNK_SIZE, progress_callback,
            media_width, media_height, media_duration,
            original_filename=original_filename,
            media_metadata=media_metadata,
        )

    def get_chunk(self, item_id, chunk_index):
        self.cursor.execute(
            "SELECT media_chunks.data FROM media_chunks "
            "JOIN items ON items.id=media_chunks.item_id "
            "WHERE media_chunks.item_id=? AND media_chunks.chunk_index=? "
            "AND items.storage_state=?",
            (item_id, chunk_index, READY_STORAGE_STATE),
        )
        row = self.cursor.fetchone()
        if row:
            return self.crypto.decrypt(
                row[0], aad=self.crypto.chunk_aad(item_id, chunk_index)
            )
        return None

    _ITEM_SELECT_BASE = (
        "SELECT id, type, title, x, y, width, height, text_content, thumbnail, "
        "is_chunked, total_size, title_size, text_size, created_at, updated_at, "
        "media_width, media_height, media_duration, original_filename, "
        "media_metadata, frame_locked, frame_color, frame_opacity "
        "FROM items"
    )
    _ITEM_SELECT = (
        _ITEM_SELECT_BASE + " WHERE storage_state='ready' ORDER BY id"
    )

    _GRAPH_COPY_ITEM_SELECT = (
        "SELECT id, type, x, y, width, height, "
        "is_chunked, "
        "CASE WHEN COALESCE(is_chunked, 0)=0 AND full_data IS NOT NULL "
        "AND COALESCE(total_size, 0)=0 "
        "THEN MAX(length(full_data)-28, 0) ELSE total_size END, "
        "title_size, text_size, created_at, updated_at, "
        "media_width, media_height, media_duration, "
        "frame_locked, frame_color, frame_opacity, "
        "thumbnail IS NOT NULL, full_data IS NOT NULL, "
        "text_content IS NOT NULL, original_filename IS NOT NULL, "
        "media_metadata IS NOT NULL "
        "FROM items"
    )

    def get_all_items(self, include_thumbnails=True):
        items = []
        for batch in self.iter_item_batches(
            batch_size=200, include_thumbnails=include_thumbnails
        ):
            items.extend(batch)
        return items

    def get_items_by_ids(self, item_ids, include_thumbnails=True):
        item_ids = list(dict.fromkeys(int(item_id) for item_id in item_ids))
        if not item_ids:
            return []
        rows = []
        for start in range(0, len(item_ids), 900):
            batch = item_ids[start:start + 900]
            in_sql, in_params = self._in_clause(batch)
            self.cursor.execute(
                f"{self._ITEM_SELECT_BASE} WHERE storage_state='ready' "
                f"AND id IN {in_sql} ORDER BY id",
                in_params,
            )
            rows.extend(self.cursor.fetchall())
        return [
            self._decode_item_row(row, include_thumbnails) for row in rows
        ]

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
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM items WHERE storage_state='ready'"
            ).fetchone()[0]
        )

    def _decode_item_row(self, row, include_thumbnail):
        (
            item_id, item_type, encrypted_title, x, y, width, height,
            encrypted_text, encrypted_thumbnail, is_chunked, total_size,
            title_size, text_size, created_at, updated_at, media_width,
            media_height, media_duration, encrypted_original_filename,
            encrypted_media_metadata, frame_locked, frame_color, frame_opacity,
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
            # Initial canvas loading skips decoded image/video thumbnails to
            # keep startup bounded, but audio thumbnails are the compact
            # waveform payload that the viewer needs for its first render.
            keep_audio_waveform = item_type == "audio"
            thumbnail = (
                self.crypto.decrypt(
                    encrypted_thumbnail,
                    aad=self.crypto.item_aad(item_id, "thumbnail"),
                )
                if (include_thumbnail or keep_audio_waveform)
                and encrypted_thumbnail else None
            )
            original_filename = (
                self.crypto.decrypt(
                    encrypted_original_filename,
                    aad=self.crypto.item_aad(item_id, "original_filename"),
                ).decode()
                if encrypted_original_filename else ""
            )
            media_metadata = (
                _decode_media_metadata(
                    self.crypto.decrypt(
                        encrypted_media_metadata,
                        aad=self.crypto.item_aad(item_id, "media_metadata"),
                    )
                )
                if encrypted_media_metadata else []
            )
        else:
            title = ""
            text = ""
            thumbnail = None
            original_filename = ""
            media_metadata = []
        return NodeItemDTO(
            id=item_id, type=item_type, title=title, x=x, y=y,
            width=width, height=height, text_content=text, thumbnail=thumbnail,
            is_chunked=bool(is_chunked), total_size=total_size,
            title_size=title_size, text_size=text_size,
            created_at=created_at or "", updated_at=updated_at or "",
            media_width=media_width or 0, media_height=media_height or 0,
            media_duration=media_duration or 0.0,
            original_filename=original_filename,
            media_metadata=media_metadata,
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
            "SELECT item_tags.item_id, item_tags.tag_id FROM item_tags "
            "JOIN items ON items.id=item_tags.item_id "
            "WHERE items.storage_state='ready' "
            "ORDER BY item_tags.item_id, item_tags.priority, item_tags.tag_id"
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
            JOIN items ON items.id = item_tags.item_id
            WHERE item_tags.item_id=? AND items.storage_state='ready'
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
        self.cursor.execute(
            "SELECT full_data FROM items "
            "WHERE id=? AND storage_state='ready'",
            (item_id,),
        )
        row = self.cursor.fetchone()
        if row and row[0]:
            return self.crypto.decrypt(
                row[0], aad=self.crypto.item_aad(item_id, "full_data")
            )
        return None

    def get_item_info(self, item_id):
        self.cursor.execute(
            "SELECT id, type, is_chunked, total_size, original_filename "
            "FROM items "
            "WHERE id=? AND storage_state='ready'",
            (item_id,),
        )
        row = self.cursor.fetchone()
        if row:
            original_filename = ""
            if row[4] and self.crypto:
                original_filename = self.crypto.decrypt(
                    row[4],
                    aad=self.crypto.item_aad(row[0], "original_filename"),
                ).decode()
            return NodeItemDTO(
                id=row[0], type=row[1], title="", x=0, y=0, width=0, height=0,
                is_chunked=bool(row[2]), total_size=row[3],
                original_filename=original_filename,
            )
        return None

    @staticmethod
    def _normalize_graph_node_ids(node_ids):
        if node_ids is None:
            return []
        if isinstance(node_ids, (str, bytes, int)):
            node_ids = [node_ids]
        try:
            values = list(node_ids)
        except TypeError as exc:
            raise TypeError("node_ids must be an iterable of integers") from exc

        normalized = []
        for node_id in values:
            try:
                value = int(node_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid node id: {node_id!r}") from exc
            if value <= 0:
                raise ValueError(f"Invalid node id: {node_id!r}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    def _fetch_graph_copy_items(self, item_ids):
        item_ids = list(item_ids)
        if not item_ids:
            return {}

        rows = []
        for start in range(0, len(item_ids), 900):
            batch = item_ids[start:start + 900]
            in_sql, in_params = self._in_clause(batch)
            self.cursor.execute(
                f"{self._GRAPH_COPY_ITEM_SELECT} "
                f"WHERE storage_state='ready' AND id IN {in_sql} ORDER BY id",
                in_params,
            )
            rows.extend(self.cursor.fetchall())
        return {
            int(row[0]): self._decode_graph_copy_item_row(row)
            for row in rows
        }

    def _decode_graph_copy_item_row(self, row):
        (
            item_id, item_type, x, y, width, height,
            is_chunked, total_size, title_size, text_size,
            created_at, updated_at, media_width, media_height, media_duration,
            frame_locked, frame_color,
            frame_opacity, has_thumbnail, has_full_data, has_text,
            has_original_filename, has_media_metadata,
        ) = row

        return {
            "source_id": int(item_id),
            "type": item_type or "",
            "x": float(x or 0),
            "y": float(y or 0),
            "width": float(width or 0),
            "height": float(height or 0),
            "is_chunked": bool(is_chunked),
            "total_size": int(total_size or 0),
            "title_size": int(title_size or 14),
            "text_size": int(text_size or 10),
            "created_at": created_at or "",
            "updated_at": updated_at or "",
            "media_width": int(media_width or 0),
            "media_height": int(media_height or 0),
            "media_duration": float(media_duration or 0),
            "frame_locked": bool(frame_locked),
            "frame_color": frame_color or "",
            "frame_opacity": float(
                0.21 if frame_opacity is None else frame_opacity
            ),
            "has_thumbnail": bool(has_thumbnail),
            "has_full_data": bool(has_full_data),
            "has_text": bool(has_text),
            "has_original_filename": bool(has_original_filename),
            "has_media_metadata": bool(has_media_metadata),
        }

    @staticmethod
    def _graph_node_center_inside_frame(node, frame):
        center_x = node["x"] + node["width"] / 2.0
        center_y = node["y"] + node["height"] / 2.0
        return (
            frame["x"] <= center_x <= frame["x"] + frame["width"]
            and frame["y"] <= center_y <= frame["y"] + frame["height"]
        )

    @classmethod
    def _graph_node_inside_frame(cls, node, frame):
        if node["type"] != "frame":
            return cls._graph_node_center_inside_frame(node, frame)

        node_left, node_right = sorted(
            (node["x"], node["x"] + node["width"])
        )
        node_top, node_bottom = sorted(
            (node["y"], node["y"] + node["height"])
        )
        frame_left, frame_right = sorted(
            (frame["x"], frame["x"] + frame["width"])
        )
        frame_top, frame_bottom = sorted(
            (frame["y"], frame["y"] + frame["height"])
        )
        return (
            frame_left <= node_left
            and node_right <= frame_right
            and frame_top <= node_top
            and node_bottom <= frame_bottom
            and (
                frame_left < node_left
                or node_right < frame_right
                or frame_top < node_top
                or node_bottom < frame_bottom
            )
        )

    def _fetch_graph_copy_tags(self, item_ids):
        tags_by_item = {}
        item_ids = list(item_ids)
        for start in range(0, len(item_ids), 900):
            batch = item_ids[start:start + 900]
            in_sql, in_params = self._in_clause(batch)
            self.cursor.execute(
                """
                SELECT item_tags.item_id, item_tags.tag_id, tags.name,
                       tags.color, item_tags.priority
                FROM item_tags
                JOIN tags ON tags.id = item_tags.tag_id
                JOIN items ON items.id = item_tags.item_id
                WHERE items.storage_state='ready'
                  AND item_tags.item_id IN %s
                ORDER BY item_tags.item_id, item_tags.priority, item_tags.tag_id
                """ % in_sql,
                in_params,
            )
            for item_id, tag_id, encrypted_name, color, priority in self.cursor.fetchall():
                if not encrypted_name or not self.crypto:
                    continue
                try:
                    name = self.crypto.decrypt(
                        encrypted_name,
                        aad=self.crypto.tag_aad(tag_id),
                    ).decode()
                except Exception:
                    continue
                if not name:
                    continue
                tags_by_item.setdefault(int(item_id), []).append(
                    {
                        "source_tag_id": int(tag_id),
                        "name": name,
                        "color": color or "",
                        "priority": int(priority or 0),
                    }
                )
        return tags_by_item

    def build_graph_copy_blueprint(self, node_ids):
        """Capture cheap graph metadata without reading media payloads.

        The returned blueprint keeps source IDs for deferred media reads and
        stores positions relative to the copied graph's top-left corner.
        Frame membership is intentionally represented by geometry because the
        database has no persistent parent/child relation for frames.
        """
        selected_ids = self._normalize_graph_node_ids(node_ids)
        if not selected_ids:
            return {
                "version": 1,
                "source_ids": [],
                "node_ids": [],
                "selection_ids": [],
                "origin": {"x": 0.0, "y": 0.0},
                "bounds": {"width": 0.0, "height": 0.0},
                "nodes": [],
                "connections": [],
            }

        self.cursor.execute(
            "SELECT id, type, x, y, width, height FROM items "
            "WHERE storage_state='ready' ORDER BY id"
        )
        geometry = {
            int(row[0]): {
                "source_id": int(row[0]),
                "type": row[1] or "",
                "x": float(row[2] or 0),
                "y": float(row[3] or 0),
                "width": float(row[4] or 0),
                "height": float(row[5] or 0),
            }
            for row in self.cursor.fetchall()
        }
        missing = [node_id for node_id in selected_ids if node_id not in geometry]
        if missing:
            raise ValueError(f"Node not found: {missing[0]}")

        included_ids = set(selected_ids)
        pending_frames = {
            node_id
            for node_id in selected_ids
            if geometry[node_id]["type"] == "frame"
        }
        processed_frames = set()
        while pending_frames:
            frame_ids = pending_frames - processed_frames
            if not frame_ids:
                break
            for frame_id in frame_ids:
                frame = geometry[frame_id]
                for candidate_id, candidate in geometry.items():
                    if candidate_id in included_ids:
                        continue
                    if not self._graph_node_inside_frame(candidate, frame):
                        continue
                    included_ids.add(candidate_id)
                    if candidate["type"] == "frame":
                        pending_frames.add(candidate_id)
            processed_frames.update(frame_ids)

        items_by_id = self._fetch_graph_copy_items(sorted(included_ids))
        items = [items_by_id[node_id] for node_id in sorted(included_ids)]
        if not items:
            return {
                "version": 1,
                "source_ids": selected_ids,
                "node_ids": [],
                "selection_ids": [],
                "origin": {"x": 0.0, "y": 0.0},
                "bounds": {"width": 0.0, "height": 0.0},
                "nodes": [],
                "connections": [],
            }

        origin_x = min(item["x"] for item in items)
        origin_y = min(item["y"] for item in items)
        max_x = max(item["x"] + item["width"] for item in items)
        max_y = max(item["y"] + item["height"] for item in items)

        frames = [item for item in items if item["type"] == "frame"]
        parent_frame_ids = {}
        for item in items:
            parent_frames = [
                frame for frame in frames
                if frame["source_id"] != item["source_id"]
                and self._graph_node_inside_frame(item, frame)
            ]
            parent = min(
                parent_frames,
                key=lambda frame: (
                    max(0.0, frame["width"]) * max(0.0, frame["height"]),
                    frame["source_id"],
                ),
                default=None,
            )
            parent_frame_ids[item["source_id"]] = (
                parent["source_id"] if parent is not None else None
            )

        for item in items:
            item["parent_frame_id"] = parent_frame_ids[item["source_id"]]
            item["relative_x"] = item.pop("x") - origin_x
            item["relative_y"] = item.pop("y") - origin_y
            item["tags"] = []

        tags_by_item = self._fetch_graph_copy_tags(sorted(included_ids))
        for item in items:
            item["tags"] = tags_by_item.get(item["source_id"], [])

        connections = []
        self.cursor.execute(
            "SELECT connections.id, connections.start_id, connections.end_id "
            "FROM connections "
            "JOIN items AS start_item ON start_item.id=connections.start_id "
            "JOIN items AS end_item ON end_item.id=connections.end_id "
            "WHERE start_item.storage_state='ready' "
            "AND end_item.storage_state='ready' ORDER BY connections.id"
        )
        for connection_id, start_id, end_id in self.cursor.fetchall():
            if start_id not in included_ids or end_id not in included_ids:
                continue
            connections.append(
                {
                    "source_connection_id": int(connection_id),
                    "start_id": int(start_id),
                    "end_id": int(end_id),
                }
            )

        return {
            "version": 1,
            "source_ids": selected_ids,
            "node_ids": [item["source_id"] for item in items],
            "selection_ids": list(selected_ids),
            "origin": {"x": origin_x, "y": origin_y},
            "bounds": {
                "width": max(0.0, max_x - origin_x),
                "height": max(0.0, max_y - origin_y),
            },
            "nodes": items,
            "connections": connections,
        }

    @staticmethod
    def _normalize_clone_tag_name(name):
        normalized = (name or "").strip().lstrip("@").casefold()
        if not normalized or len(normalized) > 32:
            return ""
        if not all(char.isalnum() or char in " _-" for char in normalized):
            return ""
        return normalized

    def _clone_tag_id(self, tag, tag_cache):
        normalized = self._normalize_clone_tag_name(tag.get("name"))
        if not normalized:
            return None
        cache_key = normalized.casefold()
        if cache_key in tag_cache:
            return tag_cache[cache_key]

        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "INSERT INTO tags (name, color, created_at) VALUES (?, ?, ?)",
            (b"", tag.get("color") or "", now),
        )
        tag_id = int(self.cursor.lastrowid)
        encrypted_name = self.crypto.encrypt(
            normalized.encode(), aad=self.crypto.tag_aad(tag_id)
        )
        self.cursor.execute(
            "UPDATE tags SET name=? WHERE id=?",
            (encrypted_name, tag_id),
        )
        tag_cache[cache_key] = tag_id
        return tag_id

    @staticmethod
    def _graph_clone_payload_size(node):
        if not node.get("is_chunked") and not node.get("has_full_data"):
            return 0
        return max(0, int(node.get("total_size") or 0))

    @staticmethod
    def _format_clone_byte_count(value):
        value = max(0, int(value or 0))
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        amount = float(value)
        unit = units[0]
        for candidate in units:
            unit = candidate
            if amount < 1024.0 or candidate == units[-1]:
                break
            amount /= 1024.0
        if unit == "B":
            return f"{value} {unit}"
        return f"{amount:.1f} {unit}"

    @staticmethod
    def _clone_progress_message(
        status,
        completed_nodes,
        node_count,
        current_bytes,
        total_bytes,
        show_bytes=True,
    ):
        message = f"{status} · Nodes {int(completed_nodes)}/{int(node_count)}"
        if show_bytes:
            current = NodeRepository._format_clone_byte_count(current_bytes)
            total = NodeRepository._format_clone_byte_count(total_bytes)
            message += f" · Bytes {current} / {total}"
        return message

    @classmethod
    def _emit_clone_progress(
        cls, progress_callback, state, status="Copying media", active=False
    ):
        if not progress_callback:
            return
        completed_nodes = state["completed_nodes"]
        if active and completed_nodes < state["node_count"]:
            completed_nodes += 1
        progress_callback(
            int(state["current_bytes"]),
            int(state["total_bytes"]),
            cls._clone_progress_message(
                status,
                completed_nodes,
                state["node_count"],
                state["current_bytes"],
                state["total_bytes"],
                show_bytes=state.get("has_payload", True),
            ),
        )

    def _add_clone_progress_bytes(
        self, state, copied_bytes, progress_callback, status="Copying media"
    ):
        copied_bytes = int(copied_bytes or 0)
        next_value = state["current_bytes"] + copied_bytes
        if next_value > state["total_bytes"]:
            raise ValueError(
                "Graph copy payload exceeds the prepared progress total"
            )
        state["current_bytes"] = next_value
        self._emit_clone_progress(
            progress_callback, state, status=status, active=True
        )

    def _insert_clone_chunk(self, target_id, chunk_index, chunk):
        self.cursor.execute(
            "INSERT INTO media_chunks (item_id, chunk_index, data) "
            "VALUES (?, ?, ?)",
            (
                target_id,
                int(chunk_index),
                self.crypto.encrypt(
                    chunk,
                    aad=self.crypto.chunk_aad(target_id, chunk_index),
                ),
            ),
        )

    def _checkpoint_clone_batch(self):
        """Commit staged data and let SQLite reuse completed WAL frames."""
        self.conn.commit()
        db_path = getattr(self.conn_manager, "db_path", ":memory:")
        if db_path != ":memory:":
            self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()

    def _check_graph_clone_disk_space(self, payload_total):
        db_path = getattr(self.conn_manager, "db_path", ":memory:")
        if db_path == ":memory:" or payload_total <= 0:
            return
        free_bytes = int(
            shutil.disk_usage(Path(db_path).resolve().parent).free
        )
        required_bytes = int(payload_total) + max(
            self._CLONE_DISK_RESERVE_BYTES,
            int(payload_total) // 10,
        )
        if free_bytes < required_bytes:
            raise InsufficientDiskSpaceError(
                "Graph copy requires at least "
                f"{required_bytes} free bytes; {free_bytes} available"
            )

    def _copy_chunked_media_for_clone(
        self,
        source_cursor,
        source_id,
        target_id,
        total_size,
        progress_state,
        progress_callback=None,
        cancel_check=None,
        commit_batches=True,
    ):
        expected_index = 0
        copied_size = 0
        while True:
            rows = source_cursor.execute(
                "SELECT chunk_index, data FROM media_chunks "
                "WHERE item_id=? AND chunk_index>=? "
                "ORDER BY chunk_index LIMIT ?",
                (
                    source_id,
                    expected_index,
                    self._CLONE_CHUNK_COMMIT_BATCH,
                ),
            ).fetchall()
            if not rows:
                break
            for chunk_index, encrypted_chunk in rows:
                if cancel_check and cancel_check():
                    raise OperationCancelledError("Graph paste cancelled")
                chunk_index = int(chunk_index)
                if chunk_index != expected_index:
                    raise ValueError(
                        f"Invalid media chunk sequence for item {source_id}: "
                        f"expected {expected_index}, got {chunk_index}"
                    )
                chunk = self.crypto.decrypt(
                    encrypted_chunk,
                    aad=self.crypto.chunk_aad(source_id, chunk_index),
                )
                self._insert_clone_chunk(target_id, expected_index, chunk)
                expected_index += 1
                copied_size += len(chunk)
                self._add_clone_progress_bytes(
                    progress_state,
                    len(chunk),
                    progress_callback,
                    status="Copying media",
                )
            if commit_batches:
                self._checkpoint_clone_batch()

        if copied_size != int(total_size or 0):
            raise ValueError(
                f"Incomplete media data for item {source_id}: "
                f"expected {int(total_size or 0)}, got {copied_size}"
            )

    @staticmethod
    def _legacy_full_data_plain_size(source_conn, source_id):
        blobopen = getattr(source_conn, "blobopen", None)
        if blobopen is None:
            raise RuntimeError(
                "Streaming legacy media requires sqlite3.Connection.blobopen"
            )
        with blobopen(
            "items", "full_data", int(source_id), readonly=True
        ) as blob:
            encrypted_size = len(blob)
        if encrypted_size < 28:
            raise ValueError(
                f"Invalid encrypted full_data for source node {source_id}"
            )
        return encrypted_size - 28

    def _copy_legacy_full_data_as_chunks(
        self,
        source_conn,
        source_id,
        target_id,
        total_size,
        progress_state,
        progress_callback=None,
        cancel_check=None,
        commit_batches=True,
    ):
        blobopen = getattr(source_conn, "blobopen", None)
        if blobopen is None:
            raise RuntimeError(
                "Streaming legacy media requires sqlite3.Connection.blobopen"
            )
        with blobopen(
            "items", "full_data", int(source_id), readonly=True
        ) as blob:
            encrypted_size = len(blob)
            if encrypted_size < 28:
                raise ValueError(
                    f"Invalid encrypted full_data for source node {source_id}"
                )
            nonce = blob.read(12)
            blob.seek(encrypted_size - 16)
            tag = blob.read(16)
            cipher_size = encrypted_size - 28
            if cipher_size != int(total_size or 0):
                raise ValueError(
                    f"Invalid full_data size for source node {source_id}: "
                    f"expected {int(total_size or 0)}, got {cipher_size}"
                )

        decryptor = Cipher(
            algorithms.AES(self.crypto.key), modes.GCM(nonce, tag)
        ).decryptor()
        decryptor.authenticate_additional_data(
            self.crypto.item_aad(source_id, "full_data")
        )

        remaining = cipher_size
        encrypted_offset = 12
        pending = bytearray()
        copied_size = 0
        chunk_index = 0
        uncommitted_chunks = 0
        while remaining:
            if cancel_check and cancel_check():
                raise OperationCancelledError("Graph paste cancelled")
            read_size = min(MEDIA_CHUNK_SIZE, remaining)
            # Reopen the source blob for every block. This releases its read
            # snapshot before each target commit/checkpoint.
            with blobopen(
                "items", "full_data", int(source_id), readonly=True
            ) as blob:
                if len(blob) != encrypted_size:
                    raise ValueError(
                        f"Source node {source_id} changed during graph copy"
                    )
                blob.seek(encrypted_offset)
                encrypted_part = blob.read(read_size)
            if len(encrypted_part) != read_size:
                raise ValueError(
                    f"Truncated encrypted full_data for source node {source_id}"
                )
            remaining -= len(encrypted_part)
            encrypted_offset += len(encrypted_part)
            pending.extend(decryptor.update(encrypted_part))
            while len(pending) >= MEDIA_CHUNK_SIZE:
                chunk = bytes(pending[:MEDIA_CHUNK_SIZE])
                del pending[:MEDIA_CHUNK_SIZE]
                self._insert_clone_chunk(target_id, chunk_index, chunk)
                chunk_index += 1
                uncommitted_chunks += 1
                copied_size += len(chunk)
                self._add_clone_progress_bytes(
                    progress_state,
                    len(chunk),
                    progress_callback,
                    status="Copying legacy media",
                )
                if (
                    commit_batches
                    and uncommitted_chunks >= self._CLONE_CHUNK_COMMIT_BATCH
                ):
                    self._checkpoint_clone_batch()
                    uncommitted_chunks = 0

        # Any authentication failure leaves only hidden staged rows, which the
        # caller removes (or startup recovery removes after a process crash).
        pending.extend(decryptor.finalize())
        while pending:
            if cancel_check and cancel_check():
                raise OperationCancelledError("Graph paste cancelled")
            chunk = bytes(pending[:MEDIA_CHUNK_SIZE])
            del pending[:MEDIA_CHUNK_SIZE]
            self._insert_clone_chunk(target_id, chunk_index, chunk)
            chunk_index += 1
            copied_size += len(chunk)
            self._add_clone_progress_bytes(
                progress_state,
                len(chunk),
                progress_callback,
                status="Copying legacy media",
            )

        if commit_batches:
            self._checkpoint_clone_batch()

        if copied_size != int(total_size or 0):
            raise ValueError(
                f"Incomplete legacy media for item {source_id}: "
                f"expected {int(total_size or 0)}, got {copied_size}"
            )

    def _open_graph_clone_source(self):
        """Open a read connection so source blobs are not held by the writer."""
        db_path = getattr(self.conn_manager, "db_path", ":memory:")
        if db_path == ":memory:":
            return self.conn, self.conn.cursor(), False
        source_conn = open_sqlite_connection(
            db_path,
            timeout=30.0,
            writable=False,
            must_exist=True,
        )
        source_conn.execute("PRAGMA query_only=ON")
        return source_conn, source_conn.cursor(), True

    def clone_graph(
        self,
        blueprint,
        offset_x=0.0,
        offset_y=0.0,
        progress_callback=None,
        cancel_check=None,
    ):
        """Materialise a deferred graph copy through hidden staged rows.

        The blueprint contains metadata only. Chunked media is copied one
        chunk at a time. Large legacy ``full_data`` blobs are streamed through
        SQLite's blob API and converted to chunked target media. Staging uses
        bounded commits; a short final transaction publishes the whole graph.
        """
        if not isinstance(blueprint, dict):
            raise TypeError("Graph copy blueprint must be a mapping")
        nodes = list(blueprint.get("nodes") or [])
        offset_x = float(offset_x or 0)
        offset_y = float(offset_y or 0)
        if not nodes:
            if progress_callback:
                progress_callback(
                    0,
                    0,
                    self._clone_progress_message(
                        "Nothing to copy",
                        0,
                        0,
                        0,
                        0,
                        show_bytes=False,
                    ),
                )
            return {
                "created_ids": [],
                "created_node_ids": [],
                "selected_ids": [],
                "selection": [],
                "id_map": {},
                "connection_ids": [],
                "created_connection_ids": [],
                "source_ids": [],
                "offset": {"x": offset_x, "y": offset_y},
                "offset_x": offset_x,
                "offset_y": offset_y,
            }

        source_ids = [int(node["source_id"]) for node in nodes]
        payload_total = sum(
            self._graph_clone_payload_size(node) for node in nodes
        )
        self._check_graph_clone_disk_space(payload_total)
        progress_state = {
            "current_bytes": 0,
            "total_bytes": payload_total or len(nodes),
            "completed_nodes": 0,
            "node_count": len(nodes),
            "has_payload": bool(payload_total),
        }
        if cancel_check and cancel_check():
            raise OperationCancelledError("Graph paste cancelled")
        self._emit_clone_progress(
            progress_callback,
            progress_state,
            status="Preparing graph copy",
        )

        id_map = {}
        created_ids = []
        connection_ids = []
        source_conn = None
        source_cursor = None
        source_is_separate = False
        pending_tags = []
        pending_connections = []
        operation_lock = acquire_database_operation_lock(
            getattr(self.conn_manager, "db_path", ":memory:")
        )
        try:
            source_conn, source_cursor, source_is_separate = (
                self._open_graph_clone_source()
            )
            for node in nodes:
                if cancel_check and cancel_check():
                    raise OperationCancelledError("Graph paste cancelled")
                source_id = int(node["source_id"])
                source_cursor.execute(
                    "SELECT type, title, text_content, thumbnail, "
                    "is_chunked, total_size, original_filename, media_metadata, "
                    "full_data IS NOT NULL "
                    "FROM items WHERE id=? AND storage_state=?",
                    (source_id, READY_STORAGE_STATE),
                )
                source_row = source_cursor.fetchone()
                if source_row is None:
                    raise ValueError(
                        f"Source node {source_id} no longer exists"
                    )
                (
                    source_type,
                    source_title,
                    source_text,
                    source_thumbnail,
                    is_chunked,
                    total_size,
                    source_filename,
                    source_media_metadata,
                    source_has_full_data,
                ) = source_row
                if source_type != node.get("type"):
                    raise ValueError(
                        f"Source node {source_id} changed type during graph copy"
                    )
                is_chunked = bool(is_chunked)
                total_size = int(total_size or 0)

                prepared_payload_size = (
                    self._graph_clone_payload_size(node)
                )
                if bool(node.get("is_chunked")) != is_chunked:
                    raise ValueError(
                        f"Source node {source_id} changed media storage "
                        "during graph copy"
                    )
                if bool(node.get("has_full_data")) != bool(
                    source_has_full_data
                ):
                    raise ValueError(
                        f"Source node {source_id} changed payload during "
                        "graph copy"
                    )
                if bool(node.get("has_media_metadata")) != bool(
                    source_media_metadata
                ):
                    raise ValueError(
                        f"Source node {source_id} changed metadata during "
                        "graph copy"
                    )

                large_legacy = False
                if source_has_full_data and not is_chunked:
                    source_payload_size = self._legacy_full_data_plain_size(
                        source_conn, source_id
                    )
                    if total_size and total_size != source_payload_size:
                        raise ValueError(
                            f"Invalid full_data size for source node "
                            f"{source_id}: expected {total_size}, got "
                            f"{source_payload_size}"
                        )
                    total_size = source_payload_size
                    large_legacy = total_size > MEDIA_CHUNK_SIZE

                if prepared_payload_size != total_size:
                    raise ValueError(
                        f"Source node {source_id} payload changed during "
                        "graph copy"
                    )

                target_is_chunked = is_chunked or large_legacy
                plain_full_data = None
                if source_has_full_data and not is_chunked and not large_legacy:
                    source_cursor.execute(
                        "SELECT full_data FROM items "
                        "WHERE id=? AND storage_state=?",
                        (source_id, READY_STORAGE_STATE),
                    )
                    full_data_row = source_cursor.fetchone()
                    if full_data_row is None or full_data_row[0] is None:
                        raise ValueError(
                            f"Source node {source_id} payload disappeared "
                            "during graph copy"
                        )
                    plain_full_data = self.crypto.decrypt(
                        full_data_row[0],
                        aad=self.crypto.item_aad(source_id, "full_data"),
                    )
                    if len(plain_full_data) != total_size:
                        raise ValueError(
                            f"Invalid full_data size for source node "
                            f"{source_id}: expected {total_size}, got "
                            f"{len(plain_full_data)}"
                        )
                x = float(node.get("relative_x", node.get("x", 0)) or 0)
                y = float(node.get("relative_y", node.get("y", 0)) or 0)
                created_at = datetime.now().isoformat(timespec="seconds")
                updated_at = created_at
                self.cursor.execute(
                    """
                    INSERT INTO items (
                        type, title, x, y, width, height, text_content,
                        thumbnail, full_data, is_chunked, total_size,
                        title_size, text_size, created_at, updated_at,
                        media_width, media_height, media_duration,
                        original_filename, media_metadata, frame_locked, frame_color,
                        frame_opacity, storage_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                               ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.get("type") or source_type,
                        b"",
                        x + offset_x,
                        y + offset_y,
                        float(node.get("width", 0) or 0),
                        float(node.get("height", 0) or 0),
                        None,
                        None,
                        None,
                        int(target_is_chunked),
                        total_size,
                        int(node.get("title_size", 14) or 14),
                        int(node.get("text_size", 10) or 10),
                        created_at,
                        updated_at,
                        int(node.get("media_width", 0) or 0),
                        int(node.get("media_height", 0) or 0),
                        float(node.get("media_duration", 0) or 0),
                        None,
                        None,
                        int(bool(node.get("frame_locked", False))),
                        node.get("frame_color") or "",
                        float(
                            0.21
                            if node.get("frame_opacity") is None
                            else node.get("frame_opacity")
                        ),
                        STAGED_STORAGE_STATE,
                    ),
                )
                target_id = int(self.cursor.lastrowid)
                id_map[source_id] = target_id
                created_ids.append(target_id)

                title = (
                    self.crypto.decrypt(
                        source_title,
                        aad=self.crypto.item_aad(source_id, "title"),
                    ).decode()
                    if source_title else ""
                )
                encrypted_title = self.crypto.encrypt(
                    title.encode(),
                    aad=self.crypto.item_aad(target_id, "title"),
                )
                text = (
                    self.crypto.decrypt(
                        source_text,
                        aad=self.crypto.item_aad(source_id, "text_content"),
                    ).decode()
                    if source_text is not None else ""
                )
                encrypted_text = (
                    self.crypto.encrypt(
                        text.encode(),
                        aad=self.crypto.item_aad(target_id, "text_content"),
                    )
                    if source_text is not None else None
                )
                encrypted_thumbnail = None
                if source_thumbnail is not None:
                    thumbnail = self.crypto.decrypt(
                        source_thumbnail,
                        aad=self.crypto.item_aad(source_id, "thumbnail"),
                    )
                    encrypted_thumbnail = self.crypto.encrypt(
                        thumbnail,
                        aad=self.crypto.item_aad(target_id, "thumbnail"),
                    )
                encrypted_filename = None
                filename = (
                    self.crypto.decrypt(
                        source_filename,
                        aad=self.crypto.item_aad(source_id, "original_filename"),
                    ).decode()
                    if source_filename is not None else ""
                )
                if source_filename is not None:
                    encrypted_filename = self.crypto.encrypt(
                        filename.encode(),
                        aad=self.crypto.item_aad(target_id, "original_filename"),
                    )
                encrypted_media_metadata = None
                if source_media_metadata is not None:
                    plain_media_metadata = self.crypto.decrypt(
                        source_media_metadata,
                        aad=self.crypto.item_aad(source_id, "media_metadata"),
                    )
                    encrypted_media_metadata = self.crypto.encrypt(
                        plain_media_metadata,
                        aad=self.crypto.item_aad(target_id, "media_metadata"),
                    )
                self.cursor.execute(
                    "UPDATE items SET title=?, text_content=?, thumbnail=?, "
                    "full_data=?, original_filename=?, media_metadata=? WHERE id=?",
                    (
                        encrypted_title,
                        encrypted_text,
                        encrypted_thumbnail,
                        (
                            self.crypto.encrypt(
                                plain_full_data,
                                aad=self.crypto.item_aad(
                                    target_id, "full_data"
                                ),
                            )
                            if plain_full_data is not None
                            else None
                        ),
                        encrypted_filename,
                        encrypted_media_metadata,
                        target_id,
                    ),
                )
                self._checkpoint_clone_batch()

                if is_chunked:
                    self._copy_chunked_media_for_clone(
                        source_cursor,
                        source_id,
                        target_id,
                        total_size,
                        progress_state,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check,
                        commit_batches=source_is_separate,
                    )
                elif large_legacy:
                    self._copy_legacy_full_data_as_chunks(
                        source_conn,
                        source_id,
                        target_id,
                        total_size,
                        progress_state,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check,
                        commit_batches=source_is_separate,
                    )
                elif plain_full_data is not None:
                    self._add_clone_progress_bytes(
                        progress_state,
                        len(plain_full_data),
                        progress_callback,
                        status="Copying media",
                    )
                self._checkpoint_clone_batch()

                for tag in node.get("tags") or []:
                    pending_tags.append((target_id, dict(tag)))

                if payload_total == 0:
                    progress_state["current_bytes"] += 1
                progress_state["completed_nodes"] += 1
                self._emit_clone_progress(
                    progress_callback,
                    progress_state,
                    status="Copied node",
                )

            for connection in blueprint.get("connections") or []:
                if cancel_check and cancel_check():
                    raise OperationCancelledError("Graph paste cancelled")
                start_id = id_map.get(int(connection["start_id"]))
                end_id = id_map.get(int(connection["end_id"]))
                if start_id is None or end_id is None or start_id == end_id:
                    continue
                pending_connections.append((start_id, end_id))

            if cancel_check and cancel_check():
                raise OperationCancelledError("Graph paste cancelled")
            if progress_state["current_bytes"] != progress_state["total_bytes"]:
                raise ValueError(
                    "Graph copy did not reach its prepared progress total"
                )
            self._emit_clone_progress(
                progress_callback,
                progress_state,
                status="Finalizing graph copy",
            )

            # From here cancellation is intentionally deferred: publishing
            # nodes, tags, and links must be one short atomic transaction.
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                tag_cache = {
                    tag.name.casefold(): int(tag.id)
                    for tag in self.get_all_tags()
                }
                for target_id, tag in pending_tags:
                    tag_id = self._clone_tag_id(tag, tag_cache)
                    if tag_id is None:
                        continue
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO item_tags "
                        "(item_id, tag_id, priority) VALUES (?, ?, ?)",
                        (
                            target_id,
                            tag_id,
                            int(tag.get("priority", 0) or 0),
                        ),
                    )

                for start_id, end_id in pending_connections:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO connections "
                        "(start_id, end_id) VALUES (?, ?)",
                        (start_id, end_id),
                    )
                    if self.cursor.rowcount:
                        connection_ids.append(int(self.cursor.lastrowid))

                for start in range(0, len(created_ids), 900):
                    batch = created_ids[start:start + 900]
                    placeholders = ",".join("?" for _ in batch)
                    self.cursor.execute(
                        "UPDATE items SET storage_state=? "
                        f"WHERE storage_state=? AND id IN ({placeholders})",
                        (READY_STORAGE_STATE, STAGED_STORAGE_STATE, *batch),
                    )
                    if self.cursor.rowcount != len(batch):
                        raise sqlite3.DatabaseError(
                            "A staged graph node disappeared before publication"
                        )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        except Exception:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            try:
                cleanup_staged_items(self.conn, created_ids)
            except sqlite3.Error:
                # Hidden rows remain recoverable on the next startup.
                pass
            raise
        finally:
            try:
                if source_cursor is not None:
                    source_cursor.close()
            finally:
                try:
                    if source_is_separate and source_conn is not None:
                        source_conn.close()
                finally:
                    operation_lock.release()

        selected_ids = [
            id_map[int(source_id)]
            for source_id in blueprint.get("selection_ids") or []
            if int(source_id) in id_map
        ]
        if not selected_ids:
            selected_ids = list(created_ids)

        return {
            "created_ids": created_ids,
            "created_node_ids": list(created_ids),
            "selected_ids": selected_ids,
            "selection": list(selected_ids),
            "id_map": id_map,
            "connection_ids": connection_ids,
            "created_connection_ids": list(connection_ids),
            "source_ids": source_ids,
            "offset": {"x": offset_x, "y": offset_y},
            "offset_x": offset_x,
            "offset_y": offset_y,
        }

    def update_pos(self, item_id, x, y):
        self.cursor.execute("UPDATE items SET x=?, y=? WHERE id=?", (x, y, item_id))
        self.conn.commit()

    def update_positions(self, positions):
        rows = [
            (float(position["x"]), float(position["y"]), int(position["id"]))
            for position in positions or ()
        ]
        if not rows:
            return
        self.cursor.executemany(
            "UPDATE items SET x=?, y=? WHERE id=?",
            rows,
        )
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

    def update_media_description(self, item_id, new_text, text_size=10):
        """Update only the encrypted Markdown description of a media node.

        Media descriptions intentionally do not rename the node.  ``NULL``
        legacy descriptions are exposed as an empty string by
        ``_decode_item_row``; an empty new description is stored as ``NULL``
        to keep old and new empty nodes equivalent without a schema change.
        """

        try:
            item_id = int(item_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid media item id") from exc
        if not isinstance(new_text, str):
            raise TypeError("Media description must be text")
        self.cursor.execute("SELECT type FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row is None:
            raise ValueError("Media item not found")
        if row[0] not in MEDIA_NODE_TYPES:
            raise ValueError("Descriptions are supported only for media nodes")
        try:
            normalized_size = max(1, int(text_size))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid media text size") from exc
        enc_text = (
            self.crypto.encrypt(
                new_text.encode("utf-8"),
                aad=self.crypto.item_aad(item_id, "text_content"),
            )
            if new_text
            else None
        )
        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute(
            "UPDATE items SET text_content=?, text_size=?, updated_at=? "
            "WHERE id=? AND type IN (?, ?, ?)",
            (
                enc_text,
                normalized_size,
                now,
                item_id,
                *sorted(MEDIA_NODE_TYPES),
            ),
        )
        if self.cursor.rowcount != 1:
            raise ValueError("Media item not found")
        self.conn.commit()

    def update_media_metadata(self, item_id, metadata):
        """Persist an encrypted metadata snapshot for an existing media item."""

        try:
            item_id = int(item_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid media item id") from exc
        if not isinstance(metadata, (list, tuple)):
            raise TypeError("Media metadata must be a list")
        normalized = [dict(entry) for entry in metadata if isinstance(entry, dict)]
        payload = _encode_media_metadata(normalized) or b"[]"
        encrypted = self.crypto.encrypt(
            payload,
            aad=self.crypto.item_aad(item_id, "media_metadata"),
        )
        self.cursor.execute(
            "UPDATE items SET media_metadata=? "
            "WHERE id=? AND storage_state='ready' AND type IN (?, ?, ?)",
            (encrypted, item_id, *sorted(MEDIA_NODE_TYPES)),
        )
        if self.cursor.rowcount != 1:
            raise ValueError("Media item not found")
        self.conn.commit()

    def rollback_changes(self):
        self.conn.rollback()

    def vacuum_database(
        self,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
    ):
        self.conn.commit()

        db_path = getattr(self.conn_manager, "db_path", ":memory:")
        before = read_database_space_stats(db_path)
        if db_path != ":memory:":
            free_bytes = shutil.disk_usage(
                Path(db_path).resolve().parent
            ).free
            required_bytes = int(before.main_bytes * 1.10)
            if free_bytes < required_bytes:
                error = InsufficientDiskSpaceError(
                    "Database optimization requires "
                    f"{required_bytes} free bytes; {free_bytes} available"
                )
                if on_error:
                    on_error(error)
                    return None
                raise error

        result_box = {}

        def do_vacuum(cursor, conn):
            if db_path != ":memory:":
                current = read_database_space_stats(db_path, conn)
                free_bytes = shutil.disk_usage(
                    Path(db_path).resolve().parent
                ).free
                required_bytes = int(current.main_bytes * 1.10)
                if free_bytes < required_bytes:
                    raise InsufficientDiskSpaceError(
                        "Database optimization requires "
                        f"{required_bytes} free bytes; {free_bytes} available"
                    )
            cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("db_maintenance_state", "vacuum"),
            )
            conn.commit()
            try:
                conn.execute("VACUUM")
                validate_database_integrity(conn)
                cursor.execute(
                    "DELETE FROM metadata WHERE key='db_maintenance_state'"
                )
                conn.commit()
                checkpoint = conn.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                wal_busy = bool(
                    checkpoint and int(checkpoint[0] or 0) != 0
                )
            except Exception:
                # Keep the marker: startup recovery must revalidate the DB.
                raise
            after = read_database_space_stats(db_path, conn)
            result_box["result"] = MaintenanceResult(
                status="completed",
                before=before,
                after=after,
                message=(
                    "Database optimized; WAL cleanup is still pending."
                    if wal_busy
                    else "Database optimized successfully."
                ),
            )

        def report_success():
            if on_success:
                on_success(result_box.get("result"))

        return self._execute_on_separate_connection(
            do_vacuum,
            on_start=on_start_vacuum,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=report_success,
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
                "SELECT connections.id, connections.start_id, "
                "connections.end_id FROM connections "
                "JOIN items AS start_item "
                "ON start_item.id=connections.start_id "
                "JOIN items AS end_item "
                "ON end_item.id=connections.end_id "
                "WHERE start_item.storage_state='ready' "
                "AND end_item.storage_state='ready' "
                "ORDER BY connections.id"
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
            self.conn.execute(
                "SELECT COUNT(*) FROM connections "
                "JOIN items AS start_item "
                "ON start_item.id=connections.start_id "
                "JOIN items AS end_item "
                "ON end_item.id=connections.end_id "
                "WHERE start_item.storage_state='ready' "
                "AND end_item.storage_state='ready'"
            ).fetchone()[0]
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
        progress_callback=None,
        on_success=None,
        on_error=None,
    ):
        self.cursor.execute(
            "SELECT type, total_size FROM items "
            "WHERE id=? AND storage_state='ready'",
            (item_id,),
        )
        row = self.cursor.fetchone()

        if row:
            item_type, total_size = row
            if item_type in PLAYABLE_NODE_TYPES:
                try:
                    from ..io.stream import close_streams_for_item
                    close_streams_for_item(item_id)
                except Exception:
                    pass

        def do_delete(cursor, conn):
            cursor.execute("BEGIN IMMEDIATE")
            total_chunks, total_bytes = cursor.execute(
                    "SELECT COUNT(*), COALESCE(SUM(length(data)), 0) "
                    "FROM media_chunks WHERE item_id=?",
                    (item_id,),
                ).fetchone()
            total_chunks = int(total_chunks or 0)
            total_bytes = int(total_bytes or 0)
            removed = 0
            removed_bytes = 0
            while True:
                chunk_rows = cursor.execute(
                        "SELECT id, length(data) FROM media_chunks WHERE item_id=? "
                        "ORDER BY id LIMIT 128",
                        (item_id,),
                    ).fetchall()
                ids = [int(row_id) for row_id, _size in chunk_rows]
                if not ids:
                    break
                in_sql, params = self._in_clause(ids)
                cursor.execute(
                    f"DELETE FROM media_chunks WHERE id IN {in_sql}", params
                )
                removed += len(ids)
                removed_bytes += sum(int(size or 0) for _row_id, size in chunk_rows)
                if progress_callback:
                    progress_callback(
                        removed_bytes,
                        max(total_bytes, 1),
                        f"Deleting media blocks {removed}/{total_chunks}",
                    )
            if progress_callback:
                progress_callback(
                    total_bytes, max(total_bytes, 1),
                    "Deleting related records..."
                )
            cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            if progress_callback:
                progress_callback(
                    total_bytes, max(total_bytes, 1),
                    "Committing deletion..."
                )

        return self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum,
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
        progress_callback=None,
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
                f"SELECT id, type, total_size FROM items "
                f"WHERE storage_state='ready' AND id IN {in_sql}",
                in_params,
            )
            rows.extend(self.cursor.fetchall())

        try:
            from ..io.stream import close_streams_for_item
        except Exception:
            close_streams_for_item = None

        for item_id, item_type, total_size in rows:
            if item_type in PLAYABLE_NODE_TYPES and close_streams_for_item:
                close_streams_for_item(item_id)

        def do_delete(cursor, conn):
            cursor.execute("BEGIN IMMEDIATE")
            total_chunks = 0
            total_bytes = 0
            for start in range(0, len(item_ids), 900):
                batch = item_ids[start:start + 900]
                in_sql, in_params = self._in_clause(batch)
                chunk_count, chunk_bytes = cursor.execute(
                        f"SELECT COUNT(*), COALESCE(SUM(length(data)), 0) "
                        f"FROM media_chunks "
                        f"WHERE item_id IN {in_sql}",
                        in_params,
                    ).fetchone()
                total_chunks += int(chunk_count or 0)
                total_bytes += int(chunk_bytes or 0)
            removed = 0
            removed_bytes = 0
            for start in range(0, len(item_ids), 900):
                batch = item_ids[start:start + 900]
                item_sql, item_params = self._in_clause(batch)
                while True:
                    chunk_rows = cursor.execute(
                            f"SELECT id, length(data) FROM media_chunks "
                            f"WHERE item_id IN {item_sql} "
                            "ORDER BY id LIMIT 128",
                            item_params,
                        ).fetchall()
                    chunk_ids = [
                        int(row_id) for row_id, _size in chunk_rows
                    ]
                    if not chunk_ids:
                        break
                    chunk_sql, chunk_params = self._in_clause(chunk_ids)
                    cursor.execute(
                        f"DELETE FROM media_chunks WHERE id IN {chunk_sql}",
                        chunk_params,
                    )
                    removed += len(chunk_ids)
                    removed_bytes += sum(
                        int(size or 0) for _row_id, size in chunk_rows
                    )
                    if progress_callback:
                        progress_callback(
                            removed_bytes,
                            max(total_bytes, 1),
                            f"Deleting media blocks {removed}/{total_chunks}",
                        )
            if progress_callback:
                progress_callback(
                    total_bytes, max(total_bytes, 1),
                    "Deleting related records..."
                )
            for start in range(0, len(item_ids), 900):
                batch = item_ids[start:start + 900]
                in_sql, in_params = self._in_clause(batch)
                cursor.execute(
                    f"DELETE FROM items WHERE id IN {in_sql}",
                    in_params,
                )
            if progress_callback:
                progress_callback(
                    total_bytes, max(total_bytes, 1),
                    "Committing deletion..."
                )

        return self._execute_on_separate_connection(
            do_delete,
            on_start=on_start_vacuum,
            on_finish=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
            label="DELETE_NODES_CASCADE",
        )
