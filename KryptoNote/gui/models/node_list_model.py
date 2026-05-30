
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


class NodeListModel(QAbstractListModel):

    node_position_changed = Signal(int, float, float)  # node_id, x, y
    node_size_changed = Signal(int, float, float)      # node_id, w, h

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self._id_to_index = {}
        self._selected_ids = set()


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
        }

        key = role_map.get(role)
        if key == "content":
            return process_markdown_for_pyside(node.get("content", ""))
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
        }

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsEditable
        return default_flags

    # Data Loading

    def load_from_service(self, service):
        """
        Bulk-load all nodes from NodeService.
        Called once after DB decryption.
        """
        self.beginResetModel()
        self._nodes.clear()
        self._id_to_index.clear()
        self._selected_ids.clear()

        items = service.get_all_items()
        for item in items:
            thumb_image = None
            if item.thumbnail:
                thumb_image = QImage.fromData(item.thumbnail)

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
                "media_type": item.type if item.type in ("image", "video") else "",
                "total_size": int(item.total_size or 0),
                "created_at": item.created_at or "",
                "updated_at": item.updated_at or item.created_at or "",
                "media_width": int(item.media_width or 0),
                "media_height": int(item.media_height or 0),
                "media_duration": float(item.media_duration or 0.0),
            }
            self._refresh_metadata_fields(node_data)
            self._id_to_index[item.id] = len(self._nodes)
            self._nodes.append(node_data)

        self.endResetModel()

    # CRUD Operations

    def add_node(self, node_id, node_type, x, y, w, h,
                 title="", content="", thumbnail_bytes=None,
                 title_size=14, text_size=10, auto_fit_pending=False,
                 draft=False, created_at="", updated_at="", total_size=0,
                 media_width=0, media_height=0, media_duration=0.0):
        thumb_image = None
        if thumbnail_bytes:
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
            "media_type": node_type if node_type in ("image", "video") else "",
            "total_size": int(total_size or 0),
            "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
            "updated_at": updated_at or created_at or datetime.now().isoformat(timespec="seconds"),
            "media_width": int(media_width or 0),
            "media_height": int(media_height or 0),
            "media_duration": float(media_duration or 0.0),
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

    @Slot(int, float, float)
    def preview_position(self, node_id, x, y):
        """Update QML geometry during drag without writing to the database."""
        self._set_position(node_id, x, y, persist=False)

    @Slot(int, float, float)
    def update_position(self, node_id, x, y):
        """Persist final node position after drag release."""
        self._set_position(node_id, x, y, persist=True)

    def get_node_id_at_row(self, row):
        """Return the node ID at the given model row, or None."""
        if 0 <= row < len(self._nodes):
            return self._nodes[row]["id"]
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

            model_idx = self.index(idx, 0)
            self.dataChanged.emit(
                model_idx, model_idx, [NodeRoles.WidthRole, NodeRoles.HeightRole]
            )

        if persist:
            self.node_size_changed.emit(node_id, w, h)

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

    # ── Selection Management ────────────────────────────────────────

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
        if not self._selected_ids:
            return

        for node_id in list(self._selected_ids):
            idx = self._id_to_index.get(node_id)
            if idx is not None:
                self._nodes[idx]["is_selected"] = False
                model_idx = self.index(idx, 0)
                self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsSelectedRole])
        self._selected_ids.clear()

    @Slot()
    def select_all(self):
        """Select every node on the canvas."""
        if len(self._selected_ids) == len(self._nodes):
            return

        for idx, node in enumerate(self._nodes):
            if node["is_selected"]:
                continue
            node["is_selected"] = True
            self._selected_ids.add(node["id"])
            model_idx = self.index(idx, 0)
            self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsSelectedRole])

    @Slot()
    def clear_hovered(self):
        """Clear hover state for all nodes after canvas-level interactions."""
        for idx, node in enumerate(self._nodes):
            if not node["is_hovered"]:
                continue
            node["is_hovered"] = False
            model_idx = self.index(idx, 0)
            self.dataChanged.emit(model_idx, model_idx, [NodeRoles.IsHoveredRole])

    @Slot(int, bool)
    def set_hovered(self, node_id, hovered):
        idx = self._id_to_index.get(node_id)
        if idx is None:
            return

        node = self._nodes[idx]
        if node["is_hovered"] == hovered:
            return

        node["is_hovered"] = hovered
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
    def search_nodes(self, query):
        q = (query or "").strip().lower()
        if not q:
            return []

        results = []
        for node in self._nodes:
            title = node.get("title", "")
            content = node.get("content", "")
            if q not in title.lower() and q not in content.lower():
                continue
            results.append({
                "nodeId": node["id"],
                "type": node["type"],
                "title": title,
                "content": process_markdown_for_pyside(content),
                "meta": node.get("meta_summary", ""),
            })
        return results

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
        if node.get("type") in ("image", "video"):
            lines.append(f"File size: {self._format_size(node.get('total_size', 0))}")
            if node.get("media_width") and node.get("media_height"):
                lines.append(f"Resolution: {node['media_width']} x {node['media_height']}")
            if node.get("media_duration"):
                lines.append(f"Duration: {self._format_duration(node['media_duration'])}")
        elif node.get("type") == "text":
            lines.append(f"Characters: {len(node.get('content', ''))}")
        return lines

    def _refresh_metadata_fields(self, node):
        node["content_size"] = self._calculate_content_size(node)
        node["created_at_display"] = self._format_datetime(node.get("created_at"))
        node["updated_at_display"] = self._format_datetime(node.get("updated_at"))
        if node.get("type") in ("image", "video"):
            parts = [node["created_at_display"]]
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
    def _calculate_content_size(node):
        if node.get("type") == "text":
            return (
                len((node.get("title") or "").encode("utf-8"))
                + len((node.get("content") or "").encode("utf-8"))
            )
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
