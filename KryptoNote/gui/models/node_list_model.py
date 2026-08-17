from enum import IntEnum
from datetime import datetime

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
    Slot,
    Signal,
    QByteArray,
)
from PySide6.QtGui import QImage

from ...core.constants import MEDIA_NODE_TYPES
from ...utils.media_proc import decode_audio_waveform
from ...utils.text_utils import process_markdown_for_pyside


class NodeRoles(IntEnum):
    """Custom roles exposed to QML via roleNames()."""
    IdRole = Qt.ItemDataRole.UserRole + 1
    TypeRole = Qt.ItemDataRole.UserRole + 2
    XRole = Qt.ItemDataRole.UserRole + 3
    YRole = Qt.ItemDataRole.UserRole + 4
    WidthRole = Qt.ItemDataRole.UserRole + 5
    HeightRole = Qt.ItemDataRole.UserRole + 6
    TitleRole = Qt.ItemDataRole.UserRole + 7
    ContentRole = Qt.ItemDataRole.UserRole + 8
    ThumbnailRole = Qt.ItemDataRole.UserRole + 9
    IsSelectedRole = Qt.ItemDataRole.UserRole + 10
    IsHoveredRole = Qt.ItemDataRole.UserRole + 11
    TitleSizeRole = Qt.ItemDataRole.UserRole + 12
    TextSizeRole = Qt.ItemDataRole.UserRole + 13
    MediaTypeRole = Qt.ItemDataRole.UserRole + 14
    IsDeletingRole = Qt.ItemDataRole.UserRole + 15
    CreatedAtRole = Qt.ItemDataRole.UserRole + 16
    UpdatedAtRole = Qt.ItemDataRole.UserRole + 17
    MetaSummaryRole = Qt.ItemDataRole.UserRole + 18
    TagsRole = Qt.ItemDataRole.UserRole + 19
    FrameLockedRole = Qt.ItemDataRole.UserRole + 20
    FrameColorRole = Qt.ItemDataRole.UserRole + 21
    FrameOpacityRole = Qt.ItemDataRole.UserRole + 22
    AudioWaveformRole = Qt.ItemDataRole.UserRole + 23
    MediaDurationRole = Qt.ItemDataRole.UserRole + 24


class NodeListModel(QAbstractListModel):

    node_position_changed = Signal(int, float, float)  # node_id, x, y
    node_positions_changed = Signal(object)            # [{id, x, y}, ...]
    positions_batch_changed = Signal(object, bool)     # node_ids, rebuild hit index
    sizes_batch_changed = Signal(object, bool)         # node_ids, rebuild hit index
    selection_batch_changed = Signal(object)           # changed node_ids
    node_size_changed = Signal(int, float, float)      # node_id, w, h

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self._id_to_index = {}
        self._selected_ids = set()
        self._hovered_ids = set()
        self._position_batch_active = False
        self._size_batch_active = False
        self._selection_batch_active = False


    def rowCount(self, parent=QModelIndex()):
        return len(self._nodes)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._nodes):
            return None

        node = self._nodes[index.row()]

        role_map = {
            NodeRoles.IdRole: "id",
            NodeRoles.TypeRole: "type",
            NodeRoles.XRole: "x",
            NodeRoles.YRole: "y",
            NodeRoles.WidthRole: "width",
            NodeRoles.HeightRole: "height",
            NodeRoles.TitleRole: "title",
            NodeRoles.ContentRole: "content",
            NodeRoles.ThumbnailRole: "thumbnail",
            NodeRoles.IsSelectedRole: "is_selected",
            NodeRoles.IsHoveredRole: "is_hovered",
            NodeRoles.TitleSizeRole: "title_size",
            NodeRoles.TextSizeRole: "text_size",
            NodeRoles.MediaTypeRole: "media_type",
            NodeRoles.IsDeletingRole: "is_deleting",
            NodeRoles.CreatedAtRole: "created_at_display",
            NodeRoles.UpdatedAtRole: "updated_at_display",
            NodeRoles.MetaSummaryRole: "meta_summary",
            NodeRoles.TagsRole: "tags",
            NodeRoles.FrameLockedRole: "frame_locked",
            NodeRoles.FrameColorRole: "frame_color",
            NodeRoles.FrameOpacityRole: "frame_opacity",
            NodeRoles.AudioWaveformRole: "audio_waveform",
            NodeRoles.MediaDurationRole: "media_duration",
        }

        key = role_map.get(role)
        if key == "content":
            return node.get("_canvas_preview", "")
        if key is not None:
            return node.get(key)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or index.row() >= len(self._nodes):
            return False

        node = self._nodes[index.row()]

        role_key_map = {
            NodeRoles.XRole: "x",
            NodeRoles.YRole: "y",
            NodeRoles.WidthRole: "width",
            NodeRoles.HeightRole: "height",
            NodeRoles.TitleRole: "title",
            NodeRoles.ContentRole: "content",
            NodeRoles.IsSelectedRole: "is_selected",
            NodeRoles.IsHoveredRole: "is_hovered",
        }

        key = role_key_map.get(role)
        if key is None:
            return False

        if node.get(key) == value:
            return False

        node[key] = value
        if key == "is_selected":
            if value:
                self._selected_ids.add(node["id"])
            else:
                self._selected_ids.discard(node["id"])
        elif key == "is_hovered":
            if value:
                self._hovered_ids.add(node["id"])
            else:
                self._hovered_ids.discard(node["id"])
        if key in ("title", "content"):
            self._refresh_metadata_fields(node)
        self.dataChanged.emit(index, index, [role])
        return True

    def roleNames(self):
        return {
            NodeRoles.IdRole: QByteArray(b"nodeId"),
            NodeRoles.TypeRole: QByteArray(b"nodeType"),
            NodeRoles.XRole: QByteArray(b"nodeX"),
            NodeRoles.YRole: QByteArray(b"nodeY"),
            NodeRoles.WidthRole: QByteArray(b"nodeWidth"),
            NodeRoles.HeightRole: QByteArray(b"nodeHeight"),
            NodeRoles.TitleRole: QByteArray(b"nodeTitle"),
            NodeRoles.ContentRole: QByteArray(b"nodeContent"),
            NodeRoles.ThumbnailRole: QByteArray(b"nodeThumbnail"),
            NodeRoles.IsSelectedRole: QByteArray(b"nodeIsSelected"),
            NodeRoles.IsHoveredRole: QByteArray(b"nodeIsHovered"),
            NodeRoles.TitleSizeRole: QByteArray(b"nodeTitleSize"),
            NodeRoles.TextSizeRole: QByteArray(b"nodeTextSize"),
            NodeRoles.MediaTypeRole: QByteArray(b"nodeMediaType"),
            NodeRoles.IsDeletingRole: QByteArray(b"nodeIsDeleting"),
            NodeRoles.CreatedAtRole: QByteArray(b"nodeCreatedAt"),
            NodeRoles.UpdatedAtRole: QByteArray(b"nodeUpdatedAt"),
            NodeRoles.MetaSummaryRole: QByteArray(b"nodeMetaSummary"),
            NodeRoles.TagsRole: QByteArray(b"nodeTags"),
            NodeRoles.FrameLockedRole: QByteArray(b"nodeFrameLocked"),
            NodeRoles.FrameColorRole: QByteArray(b"nodeFrameColor"),
            NodeRoles.FrameOpacityRole: QByteArray(b"nodeFrameOpacity"),
            NodeRoles.AudioWaveformRole: QByteArray(b"audioWaveform"),
            NodeRoles.MediaDurationRole: QByteArray(b"nodeMediaDuration"),
        }

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsEditable
        return default_flags

    # Data Loading

    def load_from_service(self, service):
        """Compatibility path for callers that still need synchronous loading."""
        tags_by_item = service.get_item_tags_map()
        self.begin_incremental_load()
        if hasattr(service, "iter_item_batches"):
            batches = service.iter_item_batches(200, include_thumbnails=True)
        else:
            batches = (service.get_all_items(),)
        for items in batches:
            self.append_item_batch(items, tags_by_item)

    def begin_incremental_load(self):
        self.beginResetModel()
        self._nodes.clear()
        self._id_to_index.clear()
        self._selected_ids.clear()
        self._hovered_ids.clear()
        self.endResetModel()

    def append_item_batch(self, items, tags_by_item=None):
        items = list(items)
        if not items:
            return
        tags_by_item = tags_by_item or {}
        first_row = len(self._nodes)
        last_row = first_row + len(items) - 1
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        for item in items:
            node_data = self._node_data_from_item(item, tags_by_item)
            self._id_to_index[item.id] = len(self._nodes)
            self._nodes.append(node_data)
        self.endInsertRows()

    def _node_data_from_item(self, item, tags_by_item):
        thumb_image = None
        audio_waveform = []
        # Audio thumbnails contain the versioned waveform payload, not an
        # image.  Never hand those bytes to QImage: doing so is both wasteful
        # and can make a valid audio node look like a broken image.
        if item.type == "audio":
            decoded = decode_audio_waveform(item.thumbnail)
            if decoded is not None:
                audio_waveform = list(decoded.peaks)
        elif item.thumbnail:
            image = QImage.fromData(item.thumbnail)
            if not image.isNull():
                thumb_image = image
        node_data = {
            "id": item.id,
            "type": item.type,
            "x": float(item.x),
            "y": float(item.y),
            "width": float(item.width) if item.width > 0 else 200.0,
            "height": float(item.height) if item.height > 0 else 150.0,
            "title": item.title or "",
            "content": item.text_content or "",
            "thumbnail": thumb_image,
            "is_selected": False,
            "is_hovered": False,
            "is_deleting": False,
            "auto_fit_pending": False,
            "draft": False,
            "title_size": item.title_size,
            "text_size": item.text_size,
            "media_type": item.type if item.type in MEDIA_NODE_TYPES else "",
            "audio_waveform": audio_waveform,
            "total_size": int(item.total_size or 0),
            "created_at": item.created_at or "",
            "updated_at": item.updated_at or item.created_at or "",
            "media_width": int(item.media_width or 0),
            "media_height": int(item.media_height or 0),
            "media_duration": float(item.media_duration or 0.0),
            "original_filename": item.original_filename or "",
            "media_metadata": [
                dict(entry) for entry in (item.media_metadata or [])
                if isinstance(entry, dict)
            ],
            "frame_locked": bool(getattr(item, "frame_locked", False)),
            "frame_color": getattr(item, "frame_color", "") or "",
            "frame_opacity": float(
                0.21
                if getattr(item, "frame_opacity", None) is None
                else item.frame_opacity
            ),
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in tags_by_item.get(item.id, [])
            ],
        }
        self._refresh_metadata_fields(node_data)
        return node_data

    # CRUD Operations

    def add_node(self, node_id, node_type, x, y, w, h,
                 title="", content="", thumbnail_bytes=None,
                 title_size=14, text_size=10, auto_fit_pending=False,
                 draft=False, created_at="", updated_at="", total_size=0,
                 media_width=0, media_height=0, media_duration=0.0,
                 original_filename="", media_metadata=None,
                 frame_locked=False, frame_color="", frame_opacity=0.21):
        thumb_image = None
        audio_waveform = []
        if node_type == "audio":
            decoded = decode_audio_waveform(thumbnail_bytes)
            if decoded is not None:
                audio_waveform = list(decoded.peaks)
        elif thumbnail_bytes:
            thumb_image = QImage.fromData(thumbnail_bytes)

        node_data = {
            "id": node_id,
            "type": node_type,
            "x": float(x),
            "y": float(y),
            "width": float(w),
            "height": float(h),
            "title": title,
            "content": content,
            "thumbnail": thumb_image,
            "is_selected": False,
            "is_hovered": False,
            "is_deleting": False,
            "auto_fit_pending": auto_fit_pending,
            "draft": draft,
            "title_size": title_size,
            "text_size": text_size,
            "media_type": node_type if node_type in MEDIA_NODE_TYPES else "",
            "audio_waveform": audio_waveform,
            "total_size": int(total_size or 0),
            "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
            "updated_at": updated_at or created_at or datetime.now().isoformat(timespec="seconds"),
            "media_width": int(media_width or 0),
            "media_height": int(media_height or 0),
            "media_duration": float(media_duration or 0.0),
            "original_filename": original_filename or "",
            "media_metadata": [
                dict(entry) for entry in (media_metadata or [])
                if isinstance(entry, dict)
            ],
            "frame_locked": bool(frame_locked),
            "frame_color": frame_color or "",
            "frame_opacity": float(frame_opacity),
            "tags": [],
        }
        self._refresh_metadata_fields(node_data)

        row = len(self._nodes)
        self.beginInsertRows(QModelIndex(), row, row)
        self._id_to_index[node_id] = row
        self._nodes.append(node_data)
        self.endInsertRows()

    def remove_node(self, node_id):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        self._selected_ids.discard(node_id)
        self._hovered_ids.discard(node_id)
        self.beginRemoveRows(QModelIndex(), idx, idx)
        self._nodes.pop(idx)
        del self._id_to_index[node_id]
        for i in range(idx, len(self._nodes)):
            self._id_to_index[self._nodes[i]["id"]] = i
        self.endRemoveRows()

    # Position & Size Updates

    def _set_position(self, node_id, x, y, persist=False):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        changed = node["x"] != x or node["y"] != y
        if not changed and not persist:
            return

        if changed:
            node["x"] = x
            node["y"] = y

            model_idx = self.index(idx, 0)
            self.dataChanged.emit(model_idx, model_idx, [NodeRoles.XRole, NodeRoles.YRole])

        if persist:
            self.node_position_changed.emit(node_id, x, y)

    @property
    def position_batch_active(self):
        return self._position_batch_active

    def _normalize_position_updates(self, updates):
        normalized = {}
        for update in updates or ():
            if not isinstance(update, dict):
                continue
            try:
                node_id = int(update["id"])
                x = float(update["x"])
                y = float(update["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if node_id in self._id_to_index:
                normalized[node_id] = {"id": node_id, "x": x, "y": y}
        return list(normalized.values())

    def _emit_rows_changed(self, rows, roles):
        rows = sorted(set(rows))
        if not rows:
            return

        range_start = previous = rows[0]
        for row in rows[1:]:
            if row == previous + 1:
                previous = row
                continue
            self.dataChanged.emit(
                self.index(range_start, 0), self.index(previous, 0), roles
            )
            range_start = previous = row
        self.dataChanged.emit(
            self.index(range_start, 0), self.index(previous, 0), roles
        )

    def _emit_position_rows_changed(self, rows):
        self._position_batch_active = True
        try:
            self._emit_rows_changed(
                rows, [NodeRoles.XRole, NodeRoles.YRole]
            )
        finally:
            self._position_batch_active = False

    def _set_positions(self, updates, persist):
        normalized = self._normalize_position_updates(updates)
        if not normalized:
            return

        changed_rows = []
        changed_ids = []
        for update in normalized:
            node_id = update["id"]
            idx = self._id_to_index[node_id]
            node = self._nodes[idx]
            x = update["x"]
            y = update["y"]
            if node["x"] == x and node["y"] == y:
                continue
            node["x"] = x
            node["y"] = y
            changed_rows.append(idx)
            changed_ids.append(node_id)

        self._emit_position_rows_changed(changed_rows)
        affected_ids = [update["id"] for update in normalized]
        batch_ids = affected_ids if persist else changed_ids
        if batch_ids:
            self.positions_batch_changed.emit(batch_ids, bool(persist))
        if persist:
            self.node_positions_changed.emit(normalized)

    @Slot(int, float, float)
    def preview_position(self, node_id, x, y):
        """Update QML geometry during drag without writing to the database."""
        self._set_position(node_id, x, y, persist=False)

    @Slot(list)
    def preview_positions(self, updates):
        """Preview a grouped drag with one model/connection update."""
        self._set_positions(updates, persist=False)

    @Slot(int, float, float)
    def update_position(self, node_id, x, y):
        """Persist final node position after drag release."""
        self._set_position(node_id, x, y, persist=True)

    @Slot(list)
    def update_positions(self, updates):
        """Finish a grouped drag and persist it as one batch."""
        self._set_positions(updates, persist=True)

    def get_node_id_at_row(self, row):
        """Return the node ID at the given model row, or None."""
        if 0 <= row < len(self._nodes):
            return self._nodes[row]["id"]
        return None

    def get_node_data_at_row(self, row):
        """Return raw row data for internal proxy models."""
        if 0 <= row < len(self._nodes):
            return self._nodes[row]
        return None

    def _set_size(self, node_id, w, h, persist=False):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        changed = node["width"] != w or node["height"] != h
        if not changed and not persist:
            return

        if changed:
            node["width"] = w
            node["height"] = h

            self._size_batch_active = True
            try:
                self._emit_rows_changed(
                    [idx], [NodeRoles.WidthRole, NodeRoles.HeightRole]
                )
            finally:
                self._size_batch_active = False

        if changed or persist:
            self.sizes_batch_changed.emit([node_id], bool(persist))
        if persist:
            self.node_size_changed.emit(node_id, w, h)

    @property
    def size_batch_active(self):
        return self._size_batch_active

    @Slot(int, float, float)
    def preview_size(self, node_id, w, h):
        """Update QML geometry during resize without writing to the database."""
        self._set_size(node_id, w, h, persist=False)

    @Slot(int, float, float)
    def update_size(self, node_id, w, h):
        """Persist final node size after resize release."""
        self._set_size(node_id, w, h, persist=True)

    @Slot(int, str, str)
    @Slot(int, str, str, int, int)
    def update_text_content(
            self, node_id, title, content, title_size=None, text_size=None,
            update_timestamp=True
    ):
        """Called when text node editor saves changes."""
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        node["title"] = title
        node["content"] = content
        if update_timestamp:
            node["updated_at"] = datetime.now().isoformat(timespec="seconds")
        if title_size is not None:
            node["title_size"] = title_size
        if text_size is not None:
            node["text_size"] = text_size
        self._refresh_metadata_fields(node)

        model_idx = self.index(idx, 0)
        self.dataChanged.emit(
            model_idx,
            model_idx,
            [
                NodeRoles.TitleRole,
                NodeRoles.ContentRole,
                NodeRoles.TitleSizeRole,
                NodeRoles.TextSizeRole,
                NodeRoles.UpdatedAtRole,
                NodeRoles.MetaSummaryRole,
            ],
        )

    @Slot(int, bool)
    def set_auto_fit_pending(self, node_id, pending):
        idx = self._id_to_index.get(node_id)
        if idx is not None:
            self._nodes[idx]["auto_fit_pending"] = bool(pending)

    @Slot(int, bool)
    def set_draft(self, node_id, draft):
        idx = self._id_to_index.get(node_id)
        if idx is not None:
            self._nodes[idx]["draft"] = bool(draft)

    @Slot(int, str)
    def update_title(self, node_id, title):
        """Called when node is renamed."""
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        node["title"] = title
        node["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._refresh_metadata_fields(node)

        model_idx = self.index(idx, 0)
        self.dataChanged.emit(
            model_idx,
            model_idx,
            [NodeRoles.TitleRole, NodeRoles.UpdatedAtRole, NodeRoles.MetaSummaryRole],
        )

    @Slot(int, bool)
    def set_frame_locked(self, node_id, locked):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return
        node = self._nodes[idx]
        if node.get("type") != "frame":
            return
        locked = bool(locked)
        if node.get("frame_locked", False) == locked:
            return
        node["frame_locked"] = locked
        node["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._refresh_metadata_fields(node)
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(
            model_idx,
            model_idx,
            [
                NodeRoles.FrameLockedRole,
                NodeRoles.UpdatedAtRole,
                NodeRoles.MetaSummaryRole,
            ],
        )

    def update_frame_properties(
            self,
            node_id,
            title,
            frame_color,
            frame_opacity,
            update_timestamp=True,
    ):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return
        node = self._nodes[idx]
        if node.get("type") != "frame":
            return

        node["title"] = title or ""
        node["frame_color"] = frame_color or ""
        node["frame_opacity"] = max(
            0.0, min(1.0, float(frame_opacity))
        )
        if update_timestamp:
            node["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._refresh_metadata_fields(node)

        roles = [
            NodeRoles.TitleRole,
            NodeRoles.FrameColorRole,
            NodeRoles.FrameOpacityRole,
            NodeRoles.MetaSummaryRole,
        ]
        if update_timestamp:
            roles.append(NodeRoles.UpdatedAtRole)
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, roles)

    # ── Selection Management ────────────────────────────────────────

    @property
    def selection_batch_active(self):
        return self._selection_batch_active

    def _normalize_node_ids(self, node_ids):
        normalized = set()
        for node_id in node_ids or ():
            try:
                node_id = int(node_id)
            except (TypeError, ValueError):
                continue
            if node_id in self._id_to_index:
                normalized.add(node_id)
        return normalized

    def _apply_selection(self, selected_ids):
        selected_ids = self._normalize_node_ids(selected_ids)
        changed_ids = self._selected_ids.symmetric_difference(selected_ids)
        if not changed_ids:
            return

        changed_rows = []
        for node_id in changed_ids:
            idx = self._id_to_index[node_id]
            self._nodes[idx]["is_selected"] = node_id in selected_ids
            changed_rows.append(idx)
        self._selected_ids = selected_ids

        self._selection_batch_active = True
        try:
            self._emit_rows_changed(
                changed_rows, [NodeRoles.IsSelectedRole]
            )
        finally:
            self._selection_batch_active = False
        self.selection_batch_changed.emit(list(changed_ids))

    @Slot(list)
    def set_selection(self, node_ids):
        self._apply_selection(node_ids)

    @Slot(list)
    def add_selection(self, node_ids):
        self._apply_selection(
            self._selected_ids.union(self._normalize_node_ids(node_ids))
        )

    @Slot(int, str)
    @Slot(int, str, int)
    def update_media_description(self, node_id, content, text_size=None):
        """Refresh a media Markdown description after it is persisted."""
        idx = self._id_to_index.get(int(node_id))
        if idx is None:
            return
        node = self._nodes[idx]
        if node.get("type") not in MEDIA_NODE_TYPES:
            return
        node["content"] = content or ""
        if text_size is not None:
            try:
                node["text_size"] = max(1, int(text_size))
            except (TypeError, ValueError):
                pass
        node["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._refresh_metadata_fields(node)
        model_idx = self.index(idx, 0)
        roles = [
            NodeRoles.ContentRole,
            NodeRoles.TextSizeRole,
            NodeRoles.UpdatedAtRole,
            NodeRoles.MetaSummaryRole,
        ]
        self.dataChanged.emit(model_idx, model_idx, roles)

    @Slot(int, object)
    def set_audio_waveform(self, node_id, peaks):
        idx = self._id_to_index.get(int(node_id))
        if idx is None:
            return
        node = self._nodes[idx]
        if node.get("type") != "audio":
            return
        try:
            normalized = [max(0.0, min(1.0, float(value))) for value in (peaks or [])]
        except (TypeError, ValueError):
            normalized = []
        if normalized == node.get("audio_waveform", []):
            return
        node["audio_waveform"] = normalized
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.AudioWaveformRole])

    @Slot(int, bool)
    def set_selected(self, node_id, selected):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        if node["is_selected"] == selected:
            return

        node["is_selected"] = selected
        if selected:
            self._selected_ids.add(node_id)
        else:
            self._selected_ids.discard(node_id)

        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsSelectedRole])

    @Slot(int)
    def toggle_selected(self, node_id):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return
        node = self._nodes[idx]
        is_sel = not node["is_selected"]
        node["is_selected"] = is_sel
        if is_sel:
            self._selected_ids.add(node_id)
        else:
            self._selected_ids.discard(node_id)

        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsSelectedRole])

    @Slot()
    def clear_selection(self):
        """Deselect all nodes."""
        self._apply_selection(())

    @Slot()
    def select_all(self):
        """Select every node on the canvas."""
        self._apply_selection(node["id"] for node in self._nodes)

    @Slot()
    def clear_hovered(self):
        """Clear hover state for all nodes after canvas-level interactions."""
        for node_id in list(self._hovered_ids):
            idx = self._id_to_index.get(node_id)
            if idx is None:
                continue
            node = self._nodes[idx]
            node["is_hovered"] = False
            model_idx = self.index(idx, 0)
            self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsHoveredRole])
        self._hovered_ids.clear()

    @Slot(int, bool)
    def set_hovered(self, node_id, hovered):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        if node["is_hovered"] == hovered:
            return

        node["is_hovered"] = hovered
        if hovered:
            self._hovered_ids.add(node_id)
        else:
            self._hovered_ids.discard(node_id)
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsHoveredRole])

    @Slot(int, bool)
    def set_deleting(self, node_id, deleting):
        """Mark a node as being deleted — triggers QML deletion animation."""
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return
        node = self._nodes[idx]
        if node["is_deleting"] == deleting:
            return
        node["is_deleting"] = deleting
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsDeletingRole])

    # ── Utility ─────────────────────────────────────────────────────

    def get_node_data(self, node_id):
        """Get raw dict for a node by ID. Used by ConnectionListModel."""
        idx = self._id_to_index.get(node_id)
        if idx is not None:
            return self._nodes[idx]
        return None

    def get_selected_ids(self):
        return [n["id"] for n in self._nodes if n["is_selected"]]

    @Slot(result=list)
    def get_selected_node_positions(self):
        """Return selected node positions for grouped QML drag."""
        return [
            {
                "id": node["id"],
                "x": node["x"],
                "y": node["y"],
            }
            for node in self._nodes
            if node["is_selected"]
        ]

    @Slot(int, result=list)
    def get_drag_node_positions(self, dragged_node_id):
        """Return selected items plus nodes contained by selected frames.

        Frame membership is intentionally spatial rather than persisted: a
        regular node belongs to every selected frame whose bounds contain its
        centre when the drag begins.
        """
        dragged = self.get_node_data(dragged_node_id)
        if not dragged:
            return []

        selected = [
            node for node in self._nodes if node["is_selected"]
        ]
        if not selected:
            selected = [dragged]

        drag_ids = {node["id"] for node in selected}
        frames = [
            node for node in selected
            if node["type"] == "frame" and node.get("frame_locked", False)
        ]
        if frames:
            for node in self._nodes:
                if node["type"] == "frame" or node.get("is_deleting"):
                    continue
                if any(
                    self._node_center_inside_frame(node, frame)
                    for frame in frames
                ):
                    drag_ids.add(node["id"])

        return [
            {"id": node["id"], "x": node["x"], "y": node["y"]}
            for node in self._nodes
            if node["id"] in drag_ids
        ]

    @Slot(int, result=int)
    def select_frame_contents(self, frame_id):
        """Select a frame and the regular nodes spatially contained by it."""
        frame = self.get_node_data(frame_id)
        if not frame or frame["type"] != "frame":
            return 0

        selected_ids = [frame_id]
        count = 0
        for node in self._nodes:
            if (
                node["type"] != "frame"
                and not node.get("is_deleting")
                and self._node_center_inside_frame(node, frame)
            ):
                selected_ids.append(node["id"])
                count += 1
        self.set_selection(selected_ids)
        return count

    @staticmethod
    def _node_center_inside_frame(node, frame):
        center_x = node["x"] + node["width"] / 2.0
        center_y = node["y"] + node["height"] / 2.0
        return (
            frame["x"] <= center_x <= frame["x"] + frame["width"]
            and frame["y"] <= center_y <= frame["y"] + frame["height"]
        )

    @Slot(float, float, float, float, result=list)
    def get_nodes_in_rect(self, x1, y1, x2, y2):
        """Return node IDs intersecting a content-space rectangle."""
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        return [
            node["id"]
            for node in self._nodes
            if (
                node["x"] + node["width"] > left
                and node["x"] < right
                and node["y"] + node["height"] > top
                and node["y"] < bottom
            )
        ]

    @Slot(int, result=list)
    def get_node_bounds(self, node_id):
        """Return [x, y, width, height] for a node ID, or [] if missing."""
        data = self.get_node_data(node_id)
        if not data:
            return []
        return [data["x"], data["y"], data["width"], data["height"]]

    def get_node_rect(self, node_id):
        """Return (x, y, w, h) tuple for a node. Used for connection edge calculation."""
        data = self.get_node_data(node_id)
        if data:
            return data["x"], data["y"], data["width"], data["height"]
        return None

    @Slot(str, result=list)
    @Slot(str, int, int, str, str, result=list)
    @Slot(str, int, int, str, str, str, result=list)
    def search_nodes(
            self, query, min_chars=0, max_chars=0,
            created_after="", created_before="", sort_key="relevance"
    ):
        tokens = (query or "").strip().casefold().split()
        tag_names = {
            token[1:] for token in tokens
            if token.startswith("@") and len(token) > 1
        }
        text_query = " ".join(
            token for token in tokens if not token.startswith("@")
        )
        matching_ids = {
            int(tag["id"])
            for node in self._nodes
            for tag in node.get("tags", [])
            if tag["name"].casefold() in tag_names
        }
        if tag_names and len(matching_ids) < len(tag_names):
            return []
        return self.search_nodes_by_filters(
            text_query, list(matching_ids), min_chars, max_chars,
            created_after, created_before, sort_key,
        )

    @Slot(str, list, int, int, str, str, str, result=list)
    @Slot(str, list, int, int, str, str, str, int, result=list)
    def search_nodes_by_filters(
            self, text, tag_ids, min_chars=0, max_chars=0,
            created_after="", created_before="", sort_key="relevance",
            limit=200,
    ):
        text_query = (text or "").strip().casefold()
        tag_filters = {int(tag_id) for tag_id in (tag_ids or [])}
        min_chars = max(0, int(min_chars or 0))
        max_chars = max(0, int(max_chars or 0))
        limit = max(1, min(int(limit or 200), 1000))
        after = self._parse_filter_date(created_after, end_of_day=False)
        before = self._parse_filter_date(created_before, end_of_day=True)

        if not any((text_query, tag_filters, min_chars, max_chars, after, before)):
            return []

        matches = []
        needs_date = after is not None or before is not None
        sortable_keys = {"newest", "oldest", "chars_desc", "chars_asc", "title"}
        requires_full_scan = sort_key in sortable_keys
        for node in self._nodes:
            if text_query and text_query not in node.get("_search_text", ""):
                continue
            if tag_filters:
                node_tags = {int(tag["id"]) for tag in node.get("tags", [])}
                if not tag_filters.issubset(node_tags):
                    continue
            if min_chars or max_chars:
                char_count = node.get("_char_count", 0)
                if min_chars and char_count < min_chars:
                    continue
                if max_chars and char_count > max_chars:
                    continue
            if needs_date:
                try:
                    created_at = datetime.fromisoformat(node.get("created_at", ""))
                except (TypeError, ValueError):
                    created_at = None
                if after and (not created_at or created_at < after):
                    continue
                if before and (not created_at or created_at > before):
                    continue
            matches.append(node)
            if not requires_full_scan and len(matches) >= limit:
                break

        sorters = {
            "newest": lambda node: node.get("created_at", ""),
            "oldest": lambda node: node.get("created_at", ""),
            "chars_desc": lambda node: node.get("_char_count", 0),
            "chars_asc": lambda node: node.get("_char_count", 0),
            "title": lambda node: node.get("title", "").casefold(),
        }
        if sort_key in sorters:
            matches.sort(
                key=sorters[sort_key],
                reverse=sort_key in ("newest", "chars_desc"),
            )

        results = []
        for node in matches[:limit]:
            char_count = node.get("_char_count", 0)
            tag_summary = " ".join(
                "@" + tag["name"] for tag in node.get("tags", [])
            )
            meta_parts = [
                node.get("created_at_display", "-"),
                f"{char_count} chars",
                tag_summary,
            ]
            results.append({
                "nodeId": node["id"],
                "type": node["type"],
                "title": node.get("title", ""),
                "preview": self._search_preview(node, text_query),
                "meta": "  ·  ".join(
                    part for part in meta_parts if part and part != "-"
                ),
                "charCount": char_count,
                "createdSort": node.get("created_at", ""),
            })
        return results

    @staticmethod
    def _search_preview(node, text_query, limit=400):
        content = node.get("content", "") or ""
        title_offset = len(node.get("title", "") or "") + 1
        folded = node.get("_search_text", "")
        match_index = (
            folded.find(text_query, title_offset) - title_offset
            if text_query else 0
        )
        if match_index <= 120:
            return node.get("_search_preview_default", "")[:limit]
        start = match_index - 120
        end = min(len(content), start + limit)
        excerpt = "…" + content[start:end]
        if end < len(content):
            excerpt += "…"
        return process_markdown_for_pyside(excerpt)[:limit]

    @staticmethod
    def _parse_filter_date(value, end_of_day=False):
        value = (value or "").strip()
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if len(value) == 10 and end_of_day:
                return parsed.replace(hour=23, minute=59, second=59)
            return parsed
        except ValueError:
            return None

    def set_node_tags(self, node_id, tags):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return
        self._nodes[idx]["tags"] = list(tags)
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx, [NodeRoles.TagsRole])

    def update_tag_definition(self, tag_id, name, color):
        for row, node in enumerate(self._nodes):
            changed = False
            for tag in node.get("tags", []):
                if tag["id"] == tag_id:
                    tag["name"] = name
                    tag["color"] = color
                    changed = True
            if changed:
                model_idx = self.index(row, 0)
                self.dataChanged.emit(model_idx, model_idx, [NodeRoles.TagsRole])

    @Slot(int, result=list)
    def get_node_metadata_lines(self, node_id):
        node = self.get_node_data(node_id)
        if not node:
            return []

        lines = [
            f"ID: {node['id']}",
            f"Type: {node.get('type', '')}",
            f"Title: {node.get('title', '') or '(untitled)'}",
            f"Created: {node.get('created_at_display', '-')}",
            f"Updated: {node.get('updated_at_display', '-')}",
            f"Position: {int(node.get('x', 0))}, {int(node.get('y', 0))}",
            f"Node size: {int(node.get('width', 0))} x {int(node.get('height', 0))}",
        ]
        if node.get("type") in MEDIA_NODE_TYPES:
            lines.append(f"File size: {self._format_size(node.get('total_size', 0))}")
            if node.get("original_filename"):
                lines.append(f"Original file: {node['original_filename']}")
            if node.get("media_width") and node.get("media_height"):
                lines.append(f"Resolution: {node['media_width']} x {node['media_height']}")
            if node.get("media_duration"):
                lines.append(f"Duration: {self._format_duration(node['media_duration'])}")
            reserved_labels = {
                "ID", "Type", "Title", "Created", "Updated", "Position",
                "Node size", "File size", "Original file", "Resolution",
                "Duration", "Tags", "Characters", "Words", "Lines",
                "Typography", "Lock", "Background", "Opacity",
            }
            for entry in node.get("media_metadata", []):
                if not isinstance(entry, dict):
                    continue
                label = str(entry.get("label") or entry.get("key") or "Metadata")
                label = label.replace(":", " · ").strip()
                if label in reserved_labels:
                    label = "Embedded " + label.lower()
                raw_values = entry.get("values", [])
                if not isinstance(raw_values, (list, tuple)):
                    raw_values = [raw_values]
                values = [
                    str(value).strip()
                    for value in raw_values
                    if str(value).strip()
                ]
                if label and values:
                    lines.append(f"{label}: " + "\n".join(values))
        if node.get("tags"):
            lines.append("Tags: " + ", ".join("@" + tag["name"] for tag in node["tags"]))
        if node.get("type") == "text":
            content = node.get("content", "") or ""
            word_count = len(content.split())
            line_count = content.count("\n") + 1 if content else 0
            title_size = int(node.get("title_size") or 14)
            text_size = int(node.get("text_size") or 10)
            lines.extend(
                [
                    f"Characters: {len(content)}",
                    f"Words: {word_count}",
                    f"Lines: {line_count}",
                    f"Typography: Title {title_size} pt · Body {text_size} pt",
                ]
            )
        elif node.get("type") == "frame":
            lines.append(
                "Lock: " + ("Locked" if node.get("frame_locked") else "Unlocked")
            )
            lines.append(
                "Background: "
                + (node.get("frame_color") or "Theme default")
            )
            lines.append(
                "Opacity: "
                + f"{round(float(node.get('frame_opacity', 0.21)) * 100)}%"
            )
        return lines

    def _refresh_metadata_fields(self, node):
        title = node.get("title") or ""
        content = node.get("content") or ""
        node["_char_count"] = len(title) + len(content)
        node["_search_text"] = f"{title}\n{content}".casefold()
        canvas_excerpt = content[:4000]
        if len(content) > 4000:
            canvas_excerpt += "\n…"
        node["_canvas_preview"] = process_markdown_for_pyside(canvas_excerpt)
        node["_search_preview_default"] = node["_canvas_preview"][:400]
        node["content_size"] = self._calculate_content_size(node)
        node["created_at_display"] = self._format_datetime(node.get("created_at"))
        node["updated_at_display"] = self._format_datetime(node.get("updated_at"))
        if node.get("type") in MEDIA_NODE_TYPES:
            artist = self._embedded_metadata_value(node, "Artist")
            parts = [artist or node["created_at_display"]]
            if node.get("media_duration"):
                parts.append(self._format_duration(node["media_duration"]))
            if node.get("total_size"):
                parts.append(self._format_size(node["total_size"]))
            if node.get("media_width") and node.get("media_height"):
                parts.append(f"{node['media_width']}x{node['media_height']}")
            node["meta_summary"] = " | ".join(part for part in parts if part and part != "-")
        else:
            node["meta_summary"] = ""

    @staticmethod
    def _embedded_metadata_value(node, label):
        for entry in node.get("media_metadata", []) or []:
            if not isinstance(entry, dict) or entry.get("label") != label:
                continue
            values = entry.get("values", [])
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _calculate_content_size(node):
        node_type = node.get("type")
        if node_type == "text" or node_type in MEDIA_NODE_TYPES:
            size = (
                len((node.get("title") or "").encode("utf-8"))
                + len((node.get("content") or "").encode("utf-8"))
            )
            if node_type in MEDIA_NODE_TYPES:
                size += int(node.get("total_size") or 0)
            return size
        return int(node.get("total_size") or 0)

    @staticmethod
    def _format_datetime(value):
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    @staticmethod
    def _format_size(size):
        size = int(size or 0)
        units = ("B", "KB", "MB", "GB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    @staticmethod
    def _format_duration(seconds):
        total = int(round(float(seconds or 0)))
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
