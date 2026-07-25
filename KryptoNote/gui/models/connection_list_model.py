import math
from enum import IntEnum
from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, Slot, QByteArray,
)


class ConnectionRoles(IntEnum):
    ConnIdRole = Qt.ItemDataRole.UserRole + 100
    StartIdRole = Qt.ItemDataRole.UserRole + 101
    EndIdRole = Qt.ItemDataRole.UserRole + 102
    StartEdgeXRole = Qt.ItemDataRole.UserRole + 103
    StartEdgeYRole = Qt.ItemDataRole.UserRole + 104
    EndEdgeXRole = Qt.ItemDataRole.UserRole + 105
    EndEdgeYRole = Qt.ItemDataRole.UserRole + 106
    IsHighlightedRole = Qt.ItemDataRole.UserRole + 107
    IsDeletingRole = Qt.ItemDataRole.UserRole + 108
    DeleteFinalizesRole = Qt.ItemDataRole.UserRole + 109


class ConnectionListModel(QAbstractListModel):
    _HIT_GRID_SIZE = 128.0
    _MAX_SEGMENT_LENGTH = 24.0
    _MAX_CURVE_SEGMENTS = 64

    def __init__(self, node_model, parent=None):
        super().__init__(parent)
        self._connections = []
        self._id_to_index = {}
        self._node_model = node_model
        self._node_to_conns = {}
        self._conn_pairs = set()
        self._hit_grid = {}
        self._conn_segments = {}
        self._conn_hit_memberships = {}
        self._connection_style = "curved"
        self._node_model.dataChanged.connect(self._on_node_data_changed)

    def rowCount(self, parent=QModelIndex()):
        return len(self._connections)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._connections):
            return None
        conn = self._connections[index.row()]
        role_map = {
            ConnectionRoles.ConnIdRole: "conn_id",
            ConnectionRoles.StartIdRole: "start_id",
            ConnectionRoles.EndIdRole: "end_id",
            ConnectionRoles.StartEdgeXRole: "start_edge_x",
            ConnectionRoles.StartEdgeYRole: "start_edge_y",
            ConnectionRoles.EndEdgeXRole: "end_edge_x",
            ConnectionRoles.EndEdgeYRole: "end_edge_y",
            ConnectionRoles.IsHighlightedRole: "is_highlighted",
            ConnectionRoles.IsDeletingRole: "is_deleting",
            ConnectionRoles.DeleteFinalizesRole: "delete_finalizes",
        }
        key = role_map.get(role)
        return conn.get(key) if key else None

    def roleNames(self):
        return {
            ConnectionRoles.ConnIdRole: QByteArray(b"connId"),
            ConnectionRoles.StartIdRole: QByteArray(b"connStartId"),
            ConnectionRoles.EndIdRole: QByteArray(b"connEndId"),
            ConnectionRoles.StartEdgeXRole: QByteArray(b"connStartEdgeX"),
            ConnectionRoles.StartEdgeYRole: QByteArray(b"connStartEdgeY"),
            ConnectionRoles.EndEdgeXRole: QByteArray(b"connEndEdgeX"),
            ConnectionRoles.EndEdgeYRole: QByteArray(b"connEndEdgeY"),
            ConnectionRoles.IsHighlightedRole: QByteArray(b"connIsHighlighted"),
            ConnectionRoles.IsDeletingRole: QByteArray(b"connIsDeleting"),
            ConnectionRoles.DeleteFinalizesRole: QByteArray(b"connDeleteFinalizes"),
        }

    # Data Loading

    def load_from_service(self, service):
        self.begin_incremental_load()
        if hasattr(service, "iter_connection_batches"):
            batches = service.iter_connection_batches(200)
        else:
            batches = (service.get_all_connections(),)
        for connections in batches:
            self.append_connection_batch(connections)

    def begin_incremental_load(self):
        self.beginResetModel()
        self._connections.clear()
        self._id_to_index.clear()
        self._node_to_conns.clear()
        self._conn_pairs.clear()
        self._clear_hit_index()
        self.endResetModel()

    def append_connection_batch(self, connections):
        connections = list(connections)
        if not connections:
            return
        first_row = len(self._connections)
        last_row = first_row + len(connections) - 1
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        for connection in connections:
            edge = self._compute_edge_points(
                connection.start_id, connection.end_id
            )
            data = {
                "conn_id": connection.id,
                "start_id": connection.start_id,
                "end_id": connection.end_id,
                "start_edge_x": edge[0],
                "start_edge_y": edge[1],
                "end_edge_x": edge[2],
                "end_edge_y": edge[3],
                "is_highlighted": False,
                "is_deleting": False,
                "delete_finalizes": True,
            }
            self._id_to_index[connection.id] = len(self._connections)
            self._connections.append(data)
            self._add_to_node_map(
                connection.id, connection.start_id, connection.end_id
            )
            self._conn_pairs.add(
                (
                    min(connection.start_id, connection.end_id),
                    max(connection.start_id, connection.end_id),
                )
            )
            self._index_connection(data)
        self.endInsertRows()

    # CRUD

    def add_connection(self, conn_id, start_id, end_id):
        if conn_id in self._id_to_index:
            return False
        edge = self._compute_edge_points(start_id, end_id)
        row = len(self._connections)
        self.beginInsertRows(QModelIndex(), row, row)
        self._id_to_index[conn_id] = row
        self._connections.append({
            "conn_id": conn_id, "start_id": start_id, "end_id": end_id,
            "start_edge_x": edge[0], "start_edge_y": edge[1],
            "end_edge_x": edge[2], "end_edge_y": edge[3],
            "is_highlighted": False,
            "is_deleting": False,
            "delete_finalizes": True,
        })
        self._add_to_node_map(conn_id, start_id, end_id)
        self._conn_pairs.add((min(start_id, end_id), max(start_id, end_id)))
        self._index_connection(self._connections[-1])
        self.endInsertRows()
        return True

    def remove_connection(self, conn_id):
        idx = self._id_to_index.get(conn_id)
        if idx is None:
            return
        conn = self._connections[idx]
        pair = (min(conn["start_id"], conn["end_id"]), max(conn["start_id"], conn["end_id"]))
        self._unindex_connection(conn_id)
        self._remove_from_node_map(conn_id, conn["start_id"], conn["end_id"])
        self.beginRemoveRows(QModelIndex(), idx, idx)
        self._connections.pop(idx)
        del self._id_to_index[conn_id]
        for i in range(idx, len(self._connections)):
            self._id_to_index[self._connections[i]["conn_id"]] = i
        self.endRemoveRows()
        if not any(
            (min(item["start_id"], item["end_id"]), max(item["start_id"], item["end_id"])) == pair
            for item in self._connections
        ):
            self._conn_pairs.discard(pair)

    def _add_to_node_map(self, conn_id, start_id, end_id):
        for nid in (start_id, end_id):
            if nid not in self._node_to_conns:
                self._node_to_conns[nid] = set()
            self._node_to_conns[nid].add(conn_id)

    def _remove_from_node_map(self, conn_id, start_id, end_id):
        for nid in (start_id, end_id):
            if nid in self._node_to_conns:
                self._node_to_conns[nid].discard(conn_id)

    def remove_connections_for_node(self, node_id):
        to_remove = [
            c["conn_id"] for c in self._connections
            if c["start_id"] == node_id or c["end_id"] == node_id
        ]
        for cid in to_remove:
            self.remove_connection(cid)

    def mark_connections_for_node_deleting(self, node_id, deleting=True, finalize=False):
        for conn_id in list(self._node_to_conns.get(node_id, ())):
            self.set_deleting(conn_id, deleting, finalize=finalize)

    def connection_exists(self, start_id, end_id):
        return (min(start_id, end_id), max(start_id, end_id)) in self._conn_pairs

    @Slot(result=list)
    def get_connection_hit_segments(self):
        """Return connection edge points for QML eraser hit testing."""
        return [
            {
                "id": conn["conn_id"],
                "x1": conn["start_edge_x"],
                "y1": conn["start_edge_y"],
                "x2": conn["end_edge_x"],
                "y2": conn["end_edge_y"],
            }
            for conn in self._connections
        ]

    @Slot(float, float, float, result=int)
    def hit_test_connection(self, x, y, radius):
        """Return the nearest connection under a content-space point, or 0."""
        x = float(x)
        y = float(y)
        radius = max(float(radius or 0), 0.0)
        radius_sq = radius * radius
        grid_size = self._HIT_GRID_SIZE
        min_cell_x = math.floor((x - radius) / grid_size)
        max_cell_x = math.floor((x + radius) / grid_size)
        min_cell_y = math.floor((y - radius) / grid_size)
        max_cell_y = math.floor((y + radius) / grid_size)

        candidates = set()
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                candidates.update(self._hit_grid.get((cell_x, cell_y), ()))

        best_id = 0
        best_dist_sq = radius_sq
        for conn_id, segment_index in candidates:
            segments = self._conn_segments.get(conn_id)
            if not segments or segment_index >= len(segments):
                continue
            x1, y1, x2, y2 = segments[segment_index]
            dist_sq = self._distance_to_segment_squared(x, y, x1, y1, x2, y2)
            if dist_sq < best_dist_sq or (
                dist_sq == best_dist_sq and conn_id > best_id
            ):
                best_dist_sq = dist_sq
                best_id = conn_id

        return best_id

    @Slot(str)
    def set_connection_style(self, style):
        style = str(style).lower()
        if style not in ("curved", "straight") or style == self._connection_style:
            return
        self._connection_style = style
        self._clear_hit_index()
        for connection in self._connections:
            self._index_connection(connection)

    def _clear_hit_index(self):
        self._hit_grid.clear()
        self._conn_segments.clear()
        self._conn_hit_memberships.clear()

    def _unindex_connection(self, conn_id):
        for cell_key, segment_index in self._conn_hit_memberships.pop(conn_id, ()):
            bucket = self._hit_grid.get(cell_key)
            if bucket is None:
                continue
            bucket.discard((conn_id, segment_index))
            if not bucket:
                self._hit_grid.pop(cell_key, None)
        self._conn_segments.pop(conn_id, None)

    def _index_connection(self, conn):
        conn_id = conn["conn_id"]
        self._unindex_connection(conn_id)
        points = (
            conn["start_edge_x"], conn["start_edge_y"],
            conn["end_edge_x"], conn["end_edge_y"],
        )
        if self._connection_style == "straight":
            segments = self._straight_segments(*points)
        else:
            segments = self._curve_segments(*points)
        self._conn_segments[conn_id] = segments
        memberships = []
        grid_size = self._HIT_GRID_SIZE
        for segment_index, (x1, y1, x2, y2) in enumerate(segments):
            min_cell_x = math.floor(min(x1, x2) / grid_size)
            max_cell_x = math.floor(max(x1, x2) / grid_size)
            min_cell_y = math.floor(min(y1, y2) / grid_size)
            max_cell_y = math.floor(max(y1, y2) / grid_size)
            for cell_x in range(min_cell_x, max_cell_x + 1):
                for cell_y in range(min_cell_y, max_cell_y + 1):
                    cell_key = (cell_x, cell_y)
                    self._hit_grid.setdefault(cell_key, set()).add(
                        (conn_id, segment_index)
                    )
                    memberships.append((cell_key, segment_index))
        self._conn_hit_memberships[conn_id] = memberships

    @staticmethod
    def _straight_segments(p0x, p0y, p3x, p3y):
        return [(p0x, p0y, p3x, p3y)]

    @classmethod
    def _curve_segments(cls, p0x, p0y, p3x, p3y):
        dx = p3x - p0x
        p1x = p0x + dx * 0.4
        p1y = p0y
        p2x = p3x - dx * 0.4
        p2y = p3y
        estimated_length = math.hypot(dx, p3y - p0y) + abs(p3y - p0y) * 0.25
        steps = max(
            8,
            min(
                cls._MAX_CURVE_SEGMENTS,
                math.ceil(estimated_length / cls._MAX_SEGMENT_LENGTH),
            ),
        )
        segments = []
        prev_x = p0x
        prev_y = p0y
        for index in range(1, steps + 1):
            t = index / steps
            mt = 1.0 - t
            b0 = mt * mt * mt
            b1 = 3 * mt * mt * t
            b2 = 3 * mt * t * t
            b3 = t * t * t
            x = b0 * p0x + b1 * p1x + b2 * p2x + b3 * p3x
            y = b0 * p0y + b1 * p1y + b2 * p2y + b3 * p3y
            segments.append((prev_x, prev_y, x, y))
            prev_x = x
            prev_y = y
        return segments

    # Edge Point Computation

    def _compute_edge_points(self, start_id, end_id):
        """Same algorithm as ConnectionLine._calculate_edge_point()."""
        r1 = self._node_model.get_node_rect(start_id)
        r2 = self._node_model.get_node_rect(end_id)
        if r1 is None or r2 is None:
            return (0.0, 0.0, 0.0, 0.0)
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2
        c1x, c1y = x1 + w1 / 2, y1 + h1 / 2
        c2x, c2y = x2 + w2 / 2, y2 + h2 / 2
        n1 = self._node_model.get_node_data(start_id)
        n2 = self._node_model.get_node_data(end_id)
        inset1 = 0.0 if n1 and n1.get("type") == "frame" else 8.0
        inset2 = 0.0 if n2 and n2.get("type") == "frame" else 8.0
        p1 = self._clip_to_rect(
            c1x, c1y, c2x, c2y, w1 / 2, h1 / 2, inset1
        )
        p2 = self._clip_to_rect(
            c2x, c2y, c1x, c1y, w2 / 2, h2 / 2, inset2
        )
        return (p1[0], p1[1], p2[0], p2[1])

    @staticmethod
    def _clip_to_rect(cx, cy, tx, ty, hw, hh, endpoint_inset=8.0):
        dx, dy = tx - cx, ty - cy
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return (cx, cy)

        hw = max(1.0, hw - endpoint_inset)
        hh = max(1.0, hh - endpoint_inset)

        sx = abs(hw / dx) if dx != 0 else 1e6
        sy = abs(hh / dy) if dy != 0 else 1e6
        s = min(sx, sy)
        return (cx + dx * s, cy + dy * s)

    @classmethod
    def _distance_to_curve_squared(cls, px, py, p0x, p0y, p3x, p3y):
        return min(
            cls._distance_to_segment_squared(px, py, *segment)
            for segment in cls._curve_segments(p0x, p0y, p3x, p3y)
        )

    @staticmethod
    def _distance_to_segment_squared(px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq <= 0.0001:
            return (px - x1) * (px - x1) + (py - y1) * (py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        cx = x1 + t * dx
        cy = y1 + t * dy
        return (px - cx) * (px - cx) + (py - cy) * (py - cy)

    # Reactive Updates

    def _on_node_data_changed(self, top_left, bottom_right, roles):
        from .node_list_model import NodeRoles

        geometry_roles = {
            NodeRoles.XRole, NodeRoles.YRole,
            NodeRoles.WidthRole, NodeRoles.HeightRole,
        }
        highlight_roles = {NodeRoles.IsSelectedRole, NodeRoles.IsHoveredRole}
        geometry_changed = not roles or any(role in geometry_roles for role in roles)
        highlight_changed = not roles or any(role in highlight_roles for role in roles)
        if not geometry_changed and not highlight_changed:
            return

        changed_ids = set()
        for row in range(top_left.row(), bottom_right.row() + 1):
            node_id = self._node_model.get_node_id_at_row(row)
            if node_id is not None:
                changed_ids.add(node_id)
        if not changed_ids:
            return

        affected_conn_ids = set()
        for node_id in changed_ids:
            affected_conn_ids.update(self._node_to_conns.get(node_id, ()))

        for conn_id in affected_conn_ids:
            row = self._id_to_index.get(conn_id)
            if row is None:
                continue
            conn = self._connections[row]
            changed_roles = []

            if geometry_changed:
                edge = self._compute_edge_points(conn["start_id"], conn["end_id"])
                previous = (
                    conn["start_edge_x"], conn["start_edge_y"],
                    conn["end_edge_x"], conn["end_edge_y"],
                )
                if edge != previous:
                    conn["start_edge_x"], conn["start_edge_y"],                         conn["end_edge_x"], conn["end_edge_y"] = edge
                    self._index_connection(conn)
                    changed_roles.extend((
                        ConnectionRoles.StartEdgeXRole,
                        ConnectionRoles.StartEdgeYRole,
                        ConnectionRoles.EndEdgeXRole,
                        ConnectionRoles.EndEdgeYRole,
                    ))

            if highlight_changed:
                start_data = self._node_model.get_node_data(conn["start_id"])
                end_data = self._node_model.get_node_data(conn["end_id"])
                highlighted = bool(
                    (start_data and (
                        start_data.get("is_selected") or start_data.get("is_hovered")
                    ))
                    or (end_data and (
                        end_data.get("is_selected") or end_data.get("is_hovered")
                    ))
                )
                if highlighted != conn["is_highlighted"]:
                    conn["is_highlighted"] = highlighted
                    changed_roles.append(ConnectionRoles.IsHighlightedRole)

            if changed_roles:
                model_index = self.index(row, 0)
                self.dataChanged.emit(model_index, model_index, changed_roles)

    @Slot(int, bool)
    def set_highlighted(self, conn_id, highlighted):
        idx = self._id_to_index.get(conn_id)
        if idx is None:
            return
        conn = self._connections[idx]
        if conn["is_highlighted"] == highlighted:
            return
        conn["is_highlighted"] = highlighted
        mi = self.index(idx, 0)
        self.dataChanged.emit(mi, mi, [ConnectionRoles.IsHighlightedRole])

    def set_deleting(self, conn_id, deleting, finalize=True):
        idx = self._id_to_index.get(conn_id)
        if idx is None:
            return False
        conn = self._connections[idx]
        if conn["is_deleting"] == deleting and conn["delete_finalizes"] == finalize:
            return False
        conn["is_deleting"] = deleting
        conn["delete_finalizes"] = finalize
        mi = self.index(idx, 0)
        self.dataChanged.emit(
            mi,
            mi,
            [ConnectionRoles.IsDeletingRole, ConnectionRoles.DeleteFinalizesRole],
        )
        return True
