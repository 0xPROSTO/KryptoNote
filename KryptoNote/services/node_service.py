import json
import sqlite3
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, QSize
from PySide6.QtGui import QImageReader

from ..core.constants import MEDIA_CHUNK_SIZE
from ..core.database.models import NodeItemDTO, ConnectionDTO
from ..core.io.stream import BlockEncryptedStream
from .graph_clipboard_service import GraphClipboardService


class NodeService:
    _PROJECT_APPEARANCE_KEY = "appearance_profile_v1"

    def __init__(self, repo):
        self.repo = repo
        self._graph_clipboard = GraphClipboardService(repo)

    def get_all_items(self, include_thumbnails=True) -> list[NodeItemDTO]:
        return self.repo.get_all_items(include_thumbnails=include_thumbnails)

    def get_items_by_ids(
        self, item_ids, include_thumbnails=True
    ) -> list[NodeItemDTO]:
        return self.repo.get_items_by_ids(
            item_ids, include_thumbnails=include_thumbnails
        )

    def iter_item_batches(self, batch_size=200, include_thumbnails=False):
        return self.repo.iter_item_batches(
            batch_size=batch_size, include_thumbnails=include_thumbnails
        )

    def get_item_count(self):
        return self.repo.get_item_count()

    def search_items(self, query: str) -> list[NodeItemDTO]:
        """In-memory search across decrypted node titles and text content."""
        q = query.lower()
        return [
            item for item in self.repo.get_all_items(include_thumbnails=False)
            if q in (item.title or "").lower() or q in (item.text_content or "").lower()
        ]

    def get_all_connections(self) -> list[ConnectionDTO]:
        return self.repo.get_all_connections()

    def iter_connection_batches(self, batch_size=200):
        return self.repo.iter_connection_batches(batch_size=batch_size)

    def get_connection_count(self):
        return self.repo.get_connection_count()

    def get_all_tags(self):
        return self.repo.get_all_tags()

    def ensure_tag(self, name, color):
        return self.repo.ensure_tag(name, color)

    def update_tag(self, tag_id, name, color):
        self.repo.update_tag(tag_id, name, color)

    def get_item_tags_map(self):
        return self.repo.get_item_tags_map()

    def get_item_tags(self, item_id):
        return self.repo.get_item_tags(item_id)

    def set_item_tag(self, item_id, tag_id, enabled):
        self.repo.set_item_tag(item_id, tag_id, enabled)

    def set_item_tag_order(self, item_id, tag_ids):
        self.repo.set_item_tag_order(item_id, tag_ids)

    def add_item(
            self, item_type, x, y, w, h, title="", text=None, thumb=None,
            data=None, title_size=14, text_size=10, media_width=0,
            media_height=0, media_duration=0.0, original_filename="",
            frame_locked=False, frame_color="", frame_opacity=0.21,
            commit=True,
    ):
        return self.repo.add_item(
            item_type, x, y, w, h, title, text, thumb, data, title_size,
            text_size, media_width, media_height, media_duration,
            original_filename, frame_locked, frame_color, frame_opacity,
            commit,
        )

    def add_streamed_media(
            self, item_type, x, y, w, h, title, thumb, file_path,
            progress_callback=None, media_width=0, media_height=0,
            media_duration=0.0, original_filename=""
    ):
        return self.repo.add_streamed_media(
            item_type, x, y, w, h, title, thumb, file_path, progress_callback,
            media_width, media_height, media_duration, original_filename
        )

    def add_connection(self, start_id, end_id, commit=True):
        return self.repo.add_connection(start_id, end_id, commit=commit)

    def copy_graph(self, node_ids):
        return self._graph_clipboard.copy_graph(node_ids)

    def prepare_paste_graph(
        self,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
    ):
        return self._graph_clipboard.prepare_paste(
            offset, offset_y, offset_x=offset_x
        )

    def prepare_duplicate_graph(
        self,
        node_ids,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
    ):
        return self._graph_clipboard.prepare_duplicate(
            node_ids,
            offset,
            offset_y,
            offset_x=offset_x,
        )

    # Short names are kept for service integrations that do not use the
    # graph-prefixed synchronous API names.
    prepare_paste = prepare_paste_graph
    prepare_duplicate = prepare_duplicate_graph

    def paste_graph(
        self,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
        progress_callback=None,
        cancel_check=None,
    ):
        return self._graph_clipboard.paste_graph(
            offset,
            offset_y,
            offset_x=offset_x,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def duplicate_graph(
        self,
        node_ids,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
        progress_callback=None,
        cancel_check=None,
    ):
        return self._graph_clipboard.duplicate_graph(
            node_ids,
            offset,
            offset_y,
            offset_x=offset_x,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def clear_clipboard(self):
        self._graph_clipboard.clear_clipboard()

    def has_clipboard(self):
        return self._graph_clipboard.has_clipboard()

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
        return self.repo.delete_node_cascade(
            item_id,
            on_start_vacuum=on_start_vacuum,
            on_finish_vacuum=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            progress_callback=progress_callback,
            on_success=on_success,
            on_error=on_error,
        )

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
        return self.repo.delete_nodes_cascade(
            item_ids,
            on_start_vacuum=on_start_vacuum,
            on_finish_vacuum=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            progress_callback=progress_callback,
            on_success=on_success,
            on_error=on_error,
        )

    def delete_connection(self, conn_id):
        self.repo.delete_connection(conn_id)

    def update_pos(self, item_id, x, y):
        self.repo.update_pos(item_id, x, y)

    def update_size(self, item_id, w, h):
        self.repo.update_size(item_id, w, h)

    def update_item_title(self, item_id, title):
        self.repo.update_item_title(item_id, title)

    def update_frame_locked(self, item_id, locked):
        self.repo.update_frame_locked(item_id, locked)

    def update_frame_properties(
            self, item_id, title, frame_color, frame_opacity
    ):
        self.repo.update_frame_properties(
            item_id, title, frame_color, frame_opacity
        )

    def update_text_content(self, item_id, title, new_text, title_size=14, text_size=10):
        self.repo.update_text_content(item_id, title, new_text, title_size, text_size)

    def get_chunk(self, item_id, chunk_index):
        return self.repo.get_chunk(item_id, chunk_index)

    def get_full_data(self, item_id):
        return self.repo.get_full_data(item_id)

    def get_item_info(self, item_id):
        return self.repo.get_item_info(item_id)

    def get_item_data(self, item_id):
        item = self.get_item_info(item_id)
        if item and item.is_chunked:
            total_size = int(item.total_size or 0)
            if total_size == 0:
                return b""
            chunk_count = (total_size + MEDIA_CHUNK_SIZE - 1) // MEDIA_CHUNK_SIZE
            data = bytearray()
            for chunk_index in range(chunk_count):
                chunk = self.get_chunk(item_id, chunk_index)
                if chunk is None:
                    raise ValueError(f"Missing media chunk {chunk_index} for item {item_id}")
                data.extend(chunk)
            if len(data) != total_size:
                raise ValueError(
                    f"Incomplete media data for item {item_id}: expected {total_size}, got {len(data)}"
                )
            return bytes(data)
        return self.get_full_data(item_id)

    def open_item_stream(self, item_id):
        """Open a seekable decrypted stream without materialising all chunks."""
        item = self.get_item_info(item_id)
        if item is None:
            raise ValueError(f"Media item {item_id} does not exist")
        if not item.is_chunked:
            raise ValueError(f"Media item {item_id} is not stored as a chunked stream")
        db_path = self.get_db_path()
        if not db_path:
            raise ValueError("Database path is unavailable")
        stream = BlockEncryptedStream(
            db_path,
            self.create_crypto_clone(),
            item_id,
            int(item.total_size or 0),
            MEDIA_CHUNK_SIZE,
        )
        if not stream.isOpen():
            error = stream.errorString() or "unable to open encrypted stream"
            stream.close()
            raise OSError(error)
        return stream

    def read_image_preview(self, item_id, target_size, clip_rect=None):
        """Decode a bounded preview directly from encrypted storage."""
        max_decode_bytes = 256 * 1024 * 1024
        QImageReader.setAllocationLimit(256)
        device = None
        try:
            item = self.get_item_info(item_id)
            if item is None:
                raise ValueError(f"Image item {item_id} does not exist")
            if item.is_chunked:
                device = self.open_item_stream(item_id)
            else:
                payload = self.get_full_data(item_id)
                if not payload:
                    raise ValueError("Image data is empty")
                byte_array = QByteArray(payload)
                device = QBuffer(byte_array)
                if not device.open(QIODevice.OpenModeFlag.ReadOnly):
                    raise OSError(device.errorString() or "unable to open image buffer")
                device._encrypted_payload = byte_array

            reader = QImageReader(device)
            reader.setAutoTransform(True)
            source_size = reader.size()
            if not source_size.isValid() or source_size.isEmpty():
                raise ValueError(
                    device.errorString()
                    or reader.errorString()
                    or "invalid image dimensions"
                )

            requested = self._coerce_preview_size(target_size)
            source_rect = QRect(0, 0, source_size.width(), source_size.height())
            if clip_rect is not None:
                clip = self._coerce_clip_rect(clip_rect).intersected(source_rect)
                if clip.isEmpty():
                    raise ValueError("Preview clip rectangle is outside the image")
                reader.setClipRect(clip)
                decode_width, decode_height = clip.width(), clip.height()
            else:
                decode_width, decode_height = source_size.width(), source_size.height()

            scale = min(
                1.0,
                requested.width() / decode_width,
                requested.height() / decode_height,
                (max_decode_bytes / (decode_width * decode_height * 4)) ** 0.5,
            )
            scaled_size = QSize(
                max(1, int(decode_width * scale)),
                max(1, int(decode_height * scale)),
            )
            if scaled_size.width() * scaled_size.height() * 4 > max_decode_bytes:
                raise ValueError("Image preview exceeds the 256 MiB decode limit")
            if scaled_size != QSize(decode_width, decode_height):
                reader.setScaledSize(scaled_size)

            image = reader.read()
            if image.isNull():
                raise ValueError(
                    device.errorString()
                    or reader.errorString()
                    or "unable to decode image preview"
                )
            return image
        finally:
            if device is not None:
                device.close()

    @staticmethod
    def _coerce_preview_size(target_size):
        if isinstance(target_size, QSize):
            size = QSize(target_size)
        elif isinstance(target_size, int):
            size = QSize(target_size, target_size)
        else:
            try:
                width, height = target_size
            except (TypeError, ValueError) as exc:
                raise ValueError("target_size must be an int, QSize or (width, height)") from exc
            size = QSize(int(width), int(height))
        if not size.isValid() or size.isEmpty():
            raise ValueError("target_size must be positive")
        return size.boundedTo(QSize(4096, 4096))

    @staticmethod
    def _coerce_clip_rect(clip_rect):
        if isinstance(clip_rect, QRect):
            return QRect(clip_rect)
        try:
            x, y, width, height = clip_rect
        except (TypeError, ValueError) as exc:
            raise ValueError("clip_rect must be QRect or (x, y, width, height)") from exc
        return QRect(int(x), int(y), int(width), int(height))

    def read_thumbnail(self, item_id):
        """Decrypt one thumbnail through an isolated read-only connection."""
        db_path = self.get_db_path()
        if db_path == ":memory:":
            self.repo.cursor.execute(
                "SELECT thumbnail FROM items "
                "WHERE id=? AND storage_state='ready'", (item_id,)
            )
            row = self.repo.cursor.fetchone()
            return (
                self.repo.crypto.decrypt(
                    row[0],
                    aad=self.repo.crypto.item_aad(item_id, "thumbnail"),
                )
                if row and row[0] else None
            )
        if not db_path:
            return None
        uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as connection:
            row = connection.execute(
                "SELECT thumbnail FROM items "
                "WHERE id=? AND storage_state='ready'", (item_id,)
            ).fetchone()
        if not row or not row[0]:
            return None
        crypto = self.create_crypto_clone()
        return crypto.decrypt(
            row[0], aad=crypto.item_aad(item_id, "thumbnail")
        )

    def commit_changes(self):
        self.repo.commit_changes()

    def rollback_changes(self):
        self.repo.rollback_changes()

    def vacuum_database(
            self,
            on_start_vacuum=None,
            on_finish_vacuum=None,
            on_waiting_lock=None,
            on_success=None,
            on_error=None,
    ):
        return self.repo.vacuum_database(
            on_start_vacuum=on_start_vacuum,
            on_finish_vacuum=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
        )

    def get_db_path(self):
        return getattr(self.repo.conn_manager, "db_path", None)

    def load_project_appearance(self):
        raw = self.repo.conn_manager.get_metadata(
            self._PROJECT_APPEARANCE_KEY
        )
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if len(raw) > 16_384:
                return None
            profile = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return None
        if not isinstance(profile, dict):
            return None
        scope = profile.get("scope")
        settings = profile.get("settings")
        if scope not in ("global", "project") or not isinstance(
            settings, dict
        ):
            return None
        return {"scope": scope, "settings": settings}

    def save_project_appearance(self, scope, settings):
        if scope not in ("global", "project"):
            raise ValueError("Unsupported appearance scope")
        if not isinstance(settings, dict):
            raise TypeError("Project appearance settings must be a mapping")
        payload = json.dumps(
            {
                "version": 1,
                "scope": scope,
                "settings": settings,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(payload) > 16_384:
            raise ValueError("Project appearance settings are too large")
        self.repo.conn_manager.set_metadata(
            self._PROJECT_APPEARANCE_KEY,
            payload,
            commit=True,
        )

    def create_crypto_clone(self):
        """Create a new CryptoManager with the same key for thread-safe use.

        Returns a full CryptoManager instance instead of raw key bytes
        to prevent secret leakage through the service API.
        """
        return self.repo.crypto.create_clone()
