
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
    def __init__(self, node_model, parent=None):
        super().__init__(parent)
        self._connections = []
        self._id_to_index = {}
        self._node_model = node_model
        self._node_to_conns = {}
        self._conn_pairs = set()
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
        self.beginResetModel()
        self._connections.clear()
        self._id_to_index.clear()
        self._conn_pairs.clear()
        for c in service.get_all_connections():
            edge = self._compute_edge_points(c.start_id, c.end_id)
            self._id_to_index[c.id] = len(self._connections)
            self._connections.append({
                "conn_id": c.id, "start_id": c.start_id, "end_id": c.end_id,
                "start_edge_x": edge[0], "start_edge_y": edge[1],
                "end_edge_x": edge[2], "end_edge_y": edge[3],
                "is_highlighted": False,
                "is_deleting": False,
                "delete_finalizes": True,
            })
            self._add_to_node_map(c.id, c.start_id, c.end_id)
            self._conn_pairs.add((min(c.start_id, c.end_id), max(c.start_id, c.end_id)))
        self.endResetModel()

    # CRUD

    def add_connection(self, conn_id, start_id, end_id):
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
        self.endInsertRows()

    def remove_connection(self, conn_id):
        idx = self._id_to_index.get(conn_id)
        if idx is None:
            return
        conn = self._connections[idx]
        self._conn_pairs.discard((min(conn["start_id"], conn["end_id"]), max(conn["start_id"], conn["end_id"])))
        self._remove_from_node_map(conn_id, conn["start_id"], conn["end_id"])
        self.beginRemoveRows(QModelIndex(), idx, idx)
        self._connections.pop(idx)
        del self._id_to_index[conn_id]
        for i in range(idx, len(self._connections)):
            self._id_to_index[self._connections[i]["conn_id"]] = i
        self.endRemoveRows()

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

    def mark_connections_for_node_deleting(self, node_id):
        for conn_id in list(self._node_to_conns.get(node_id, ())):
            self.set_deleting(conn_id, True, finalize=False)

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
        radius = max(float(radius or 0), 0.0)
        radius_sq = radius * radius
        best_id = 0
        best_dist_sq = radius_sq

        for conn in self._connections:
            x1 = conn["start_edge_x"]
            y1 = conn["start_edge_y"]
            x2 = conn["end_edge_x"]
            y2 = conn["end_edge_y"]

            if (
                x < min(x1, x2) - radius
                or x > max(x1, x2) + radius
                or y < min(y1, y2) - radius
                or y > max(y1, y2) + radius
            ):
                continue

            dist_sq = self._distance_to_curve_squared(x, y, x1, y1, x2, y2)
            if dist_sq <= best_dist_sq:
                best_dist_sq = dist_sq
                best_id = conn["conn_id"]

        return best_id

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
        p1 = self._clip_to_rect(c1x, c1y, c2x, c2y, w1 / 2, h1 / 2)
        p2 = self._clip_to_rect(c2x, c2y, c1x, c1y, w2 / 2, h2 / 2)
        return (p1[0], p1[1], p2[0], p2[1])

    @staticmethod
    def _clip_to_rect(cx, cy, tx, ty, hw, hh):
        dx, dy = tx - cx, ty - cy
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return (cx, cy)

        endpoint_inset = 8.0
        hw = max(1.0, hw - endpoint_inset)
        hh = max(1.0, hh - endpoint_inset)

        sx = abs(hw / dx) if dx != 0 else 1e6
        sy = abs(hh / dy) if dy != 0 else 1e6
        s = min(sx, sy)
        return (cx + dx * s, cy + dy * s)

    @classmethod
    def _distance_to_curve_squared(cls, px, py, p0x, p0y, p3x, p3y):
        dx = p3x - p0x
        p1x = p0x + dx * 0.4
        p1y = p0y
        p2x = p3x - dx * 0.4
        p2y = p3y

        min_dist_sq = float("inf")
        prev_x = p0x
        prev_y = p0y
        steps = 80
        for i in range(1, steps + 1):
            t = i / steps
            mt = 1.0 - t
            b0 = mt * mt * mt
            b1 = 3 * mt * mt * t
            b2 = 3 * mt * t * t
            b3 = t * t * t
            x = b0 * p0x + b1 * p1x + b2 * p2x + b3 * p3x
            y = b0 * p0y + b1 * p1y + b2 * p2y + b3 * p3y
            dist_sq = cls._distance_to_segment_squared(px, py, prev_x, prev_y, x, y)
            min_dist_sq = min(min_dist_sq, dist_sq)
            prev_x = x
            prev_y = y
        return min_dist_sq

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
        affected = {
            NodeRoles.XRole, NodeRoles.YRole,
            NodeRoles.WidthRole, NodeRoles.HeightRole,
            NodeRoles.IsSelectedRole, NodeRoles.IsHoveredRole,
        }
        if not any(r in affected for r in roles):
            return

        changed_ids = set()
        for row in range(top_left.row(), bottom_right.row() + 1):
            nid = self._node_model.get_node_id_at_row(row)
            if nid is not None:
                changed_ids.add(nid)
        if not changed_ids:
            return

        affected_conn_ids = set()
        for nid in changed_ids:
            if nid in self._node_to_conns:
                affected_conn_ids.update(self._node_to_conns[nid])

        for conn_id in affected_conn_ids:
            i = self._id_to_index.get(conn_id)
            if i is None: continue
            conn = self._connections[i]

            edge = self._compute_edge_points(conn["start_id"], conn["end_id"])
            conn["start_edge_x"] = edge[0]
            conn["start_edge_y"] = edge[1]
            conn["end_edge_x"] = edge[2]
            conn["end_edge_y"] = edge[3]

            sd = self._node_model.get_node_data(conn["start_id"])
            ed = self._node_model.get_node_data(conn["end_id"])
            hl = False
            if sd and (sd.get("is_selected") or sd.get("is_hovered")):
                hl = True
            if ed and (ed.get("is_selected") or ed.get("is_hovered")):
                hl = True
            conn["is_highlighted"] = hl

            mi = self.index(i, 0)
            self.dataChanged.emit(mi, mi, [
                ConnectionRoles.StartEdgeXRole, ConnectionRoles.StartEdgeYRole,
                ConnectionRoles.EndEdgeXRole, ConnectionRoles.EndEdgeYRole,
                ConnectionRoles.IsHighlightedRole,
            ])

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
            return
        conn = self._connections[idx]
        if conn["is_deleting"] == deleting and conn["delete_finalizes"] == finalize:
            return
        conn["is_deleting"] = deleting
        conn["delete_finalizes"] = finalize
        mi = self.index(idx, 0)
        self.dataChanged.emit(
            mi,
            mi,
            [ConnectionRoles.IsDeletingRole, ConnectionRoles.DeleteFinalizesRole],
        )
