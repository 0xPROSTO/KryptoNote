import math
from enum import IntEnum
from PySide6.QtCore import (
    QAbstractListModel, QModelIndex, Qt, Slot, Signal, QByteArray,
)

from ...core.connection_geometry import (
    CONNECTION_ANCHOR_MODES,
    CONNECTION_CORNER_STYLES,
    CONNECTION_CURVE_FORMULAS,
    CONNECTION_STYLES,
    CORNERED_CONNECTION_STYLES,
    DEFAULT_CONNECTION_ANCHOR_MODE,
    DEFAULT_CONNECTION_CORNER_STYLE,
    DEFAULT_CONNECTION_CURVE_FORMULA,
    connection_segments,
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
    geometry_batch_changed = Signal(bool)

    _HIT_GRID_SIZE = 128.0
    _MAX_INDEXED_CELLS_PER_SEGMENT = 4096
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
        self._long_hit_segments = set()
        self._connection_style = "curved"
        self._connection_curve_formula = DEFAULT_CONNECTION_CURVE_FORMULA
        self._connection_corner_style = DEFAULT_CONNECTION_CORNER_STYLE
        self._connection_anchor_mode = DEFAULT_CONNECTION_ANCHOR_MODE
        self._geometry_batch_active = False
        self._node_model.dataChanged.connect(self._on_node_data_changed)
        self._node_model.positions_batch_changed.connect(
            self._on_node_geometry_batch_changed
        )
        self._node_model.sizes_batch_changed.connect(
            self._on_node_geometry_batch_changed
        )
        self._node_model.selection_batch_changed.connect(
            self._on_node_selection_batch_changed
        )

    def rowCount(self, parent=QModelIndex()):
        return len(self._connections)

    @property
    def geometry_batch_active(self):
        return self._geometry_batch_active

    def get_connection_data_at_row(self, row):
        """Return raw row data for internal proxy models."""
        if 0 <= row < len(self._connections):
            return self._connections[row]
        return None

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
        candidates.update(self._long_hit_segments)

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
        self.set_connection_appearance(
            style,
            self._connection_curve_formula,
            self._connection_corner_style,
            self._connection_anchor_mode,
        )

    def set_connection_appearance(
        self,
        style,
        curve_formula,
        corner_style,
        anchor_mode,
    ):
        style = str(style).lower()
        curve_formula = str(curve_formula).lower()
        corner_style = str(corner_style).lower()
        anchor_mode = str(anchor_mode).lower()
        if (
            style not in CONNECTION_STYLES
            or curve_formula not in CONNECTION_CURVE_FORMULAS
            or corner_style not in CONNECTION_CORNER_STYLES
            or anchor_mode not in CONNECTION_ANCHOR_MODES
        ):
            return
        style_changed = style != self._connection_style
        formula_changed = (
            curve_formula != self._connection_curve_formula
        )
        corner_changed = corner_style != self._connection_corner_style
        anchor_changed = anchor_mode != self._connection_anchor_mode
        if not any(
            (style_changed, formula_changed, corner_changed, anchor_changed)
        ):
            return
        self._connection_style = style
        self._connection_curve_formula = curve_formula
        self._connection_corner_style = corner_style
        self._connection_anchor_mode = anchor_mode

        if anchor_changed:
            self._recompute_all_edge_points()
            return

        geometry_changed = (
            style_changed
            or (formula_changed and style == "curved")
            or (
                corner_changed
                and style in CORNERED_CONNECTION_STYLES
            )
        )
        if not geometry_changed:
            return
        self._clear_hit_index()
        for connection in self._connections:
            self._index_connection(connection)

    def _recompute_all_edge_points(self):
        self._clear_hit_index()
        for connection in self._connections:
            edge = self._compute_edge_points(
                connection["start_id"], connection["end_id"]
            )
            (
                connection["start_edge_x"],
                connection["start_edge_y"],
                connection["end_edge_x"],
                connection["end_edge_y"],
            ) = edge
            self._index_connection(connection)
        if self._connections:
            self._geometry_batch_active = True
            try:
                self.dataChanged.emit(
                    self.index(0, 0),
                    self.index(len(self._connections) - 1, 0),
                    [
                        ConnectionRoles.StartEdgeXRole,
                        ConnectionRoles.StartEdgeYRole,
                        ConnectionRoles.EndEdgeXRole,
                        ConnectionRoles.EndEdgeYRole,
                    ],
                )
            finally:
                self._geometry_batch_active = False
        self.geometry_batch_changed.emit(True)

    def _clear_hit_index(self):
        self._hit_grid.clear()
        self._conn_segments.clear()
        self._conn_hit_memberships.clear()
        self._long_hit_segments.clear()

    def _unindex_connection(self, conn_id):
        for cell_key, segment_index in self._conn_hit_memberships.pop(conn_id, ()):
            bucket = self._hit_grid.get(cell_key)
            if bucket is None:
                continue
            bucket.discard((conn_id, segment_index))
            if not bucket:
                self._hit_grid.pop(cell_key, None)
        self._conn_segments.pop(conn_id, None)
        self._long_hit_segments = {
            entry for entry in self._long_hit_segments if entry[0] != conn_id
        }

    def _index_connection(self, conn):
        conn_id = conn["conn_id"]
        self._unindex_connection(conn_id)
        points = (
            conn["start_edge_x"], conn["start_edge_y"],
            conn["end_edge_x"], conn["end_edge_y"],
        )
        segments = connection_segments(
            self._connection_style,
            *points,
            self._connection_curve_formula,
            self._connection_corner_style,
        )
        self._conn_segments[conn_id] = segments
        memberships = []
        grid_size = self._HIT_GRID_SIZE
        for segment_index, (x1, y1, x2, y2) in enumerate(segments):
            start_cell_x = math.floor(x1 / grid_size)
            start_cell_y = math.floor(y1 / grid_size)
            end_cell_x = math.floor(x2 / grid_size)
            end_cell_y = math.floor(y2 / grid_size)
            crossed_span = (
                abs(end_cell_x - start_cell_x)
                + abs(end_cell_y - start_cell_y)
                + 1
            )
            if crossed_span > self._MAX_INDEXED_CELLS_PER_SEGMENT:
                self._long_hit_segments.add((conn_id, segment_index))
                continue
            for cell_key in self._segment_grid_cells(
                x1, y1, x2, y2, grid_size
            ):
                self._hit_grid.setdefault(cell_key, set()).add(
                    (conn_id, segment_index)
                )
                memberships.append((cell_key, segment_index))
        self._conn_hit_memberships[conn_id] = memberships

    @staticmethod
    def _segment_grid_cells(x1, y1, x2, y2, grid_size):
        """Return only spatial cells crossed by a segment.

        Bounding-box indexing explodes quadratically for links whose endpoints
        are far apart. This grid traversal stays linear in the crossed distance
        while preserving the same world-space hit-test candidates.
        """
        cell_x = math.floor(x1 / grid_size)
        cell_y = math.floor(y1 / grid_size)
        end_x = math.floor(x2 / grid_size)
        end_y = math.floor(y2 / grid_size)
        cells = {(cell_x, cell_y)}
        if cell_x == end_x and cell_y == end_y:
            return cells

        dx = x2 - x1
        dy = y2 - y1
        step_x = 1 if dx > 0.0 else -1 if dx < 0.0 else 0
        step_y = 1 if dy > 0.0 else -1 if dy < 0.0 else 0
        t_delta_x = grid_size / abs(dx) if step_x else math.inf
        t_delta_y = grid_size / abs(dy) if step_y else math.inf

        if step_x > 0:
            next_boundary_x = (cell_x + 1) * grid_size
            t_max_x = (next_boundary_x - x1) / dx
        elif step_x < 0:
            next_boundary_x = cell_x * grid_size
            t_max_x = (next_boundary_x - x1) / dx
        else:
            t_max_x = math.inf

        if step_y > 0:
            next_boundary_y = (cell_y + 1) * grid_size
            t_max_y = (next_boundary_y - y1) / dy
        elif step_y < 0:
            next_boundary_y = cell_y * grid_size
            t_max_y = (next_boundary_y - y1) / dy
        else:
            t_max_y = math.inf

        while cell_x != end_x or cell_y != end_y:
            if t_max_x < t_max_y:
                cell_x += step_x
                t_max_x += t_delta_x
            elif t_max_y < t_max_x:
                cell_y += step_y
                t_max_y += t_delta_y
            else:
                next_x = cell_x + step_x
                next_y = cell_y + step_y
                # A segment through a grid corner is close to both adjacent
                # cells; retain them for radius-based queries at that corner.
                cells.add((next_x, cell_y))
                cells.add((cell_x, next_y))
                cell_x = next_x
                cell_y = next_y
                t_max_x += t_delta_x
                t_max_y += t_delta_y
            cells.add((cell_x, cell_y))
        return cells

    @staticmethod
    def _straight_segments(p0x, p0y, p3x, p3y):
        return connection_segments("straight", p0x, p0y, p3x, p3y)

    @classmethod
    def _curve_segments(cls, p0x, p0y, p3x, p3y):
        return connection_segments("curved", p0x, p0y, p3x, p3y)

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
        anchor = (
            self._side_center_anchor
            if self._connection_anchor_mode == "side_centers"
            else self._clip_to_rect
        )
        p1 = anchor(c1x, c1y, c2x, c2y, w1 / 2, h1 / 2, inset1)
        p2 = anchor(c2x, c2y, c1x, c1y, w2 / 2, h2 / 2, inset2)
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

    @staticmethod
    def _side_center_anchor(
        cx, cy, tx, ty, hw, hh, endpoint_inset=8.0
    ):
        dx, dy = tx - cx, ty - cy
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return (cx, cy)

        hw = max(1.0, hw - endpoint_inset)
        hh = max(1.0, hh - endpoint_inset)
        horizontal_weight = abs(dx) / hw
        vertical_weight = abs(dy) / hh
        if horizontal_weight >= vertical_weight:
            return (cx + (hw if dx >= 0.0 else -hw), cy)
        return (cx, cy + (hh if dy >= 0.0 else -hh))

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

    def _emit_geometry_rows_changed(self, rows):
        self._geometry_batch_active = True
        try:
            self._emit_rows_changed(rows, [
                ConnectionRoles.StartEdgeXRole,
                ConnectionRoles.StartEdgeYRole,
                ConnectionRoles.EndEdgeXRole,
                ConnectionRoles.EndEdgeYRole,
            ])
        finally:
            self._geometry_batch_active = False

    def _affected_connection_ids(self, node_ids):
        affected_conn_ids = set()
        for node_id in node_ids or ():
            try:
                node_id = int(node_id)
            except (TypeError, ValueError):
                continue
            affected_conn_ids.update(self._node_to_conns.get(node_id, ()))
        return affected_conn_ids

    def _on_node_geometry_batch_changed(self, node_ids, rebuild_hit_index):
        changed_rows = []
        for conn_id in self._affected_connection_ids(node_ids):
            row = self._id_to_index.get(conn_id)
            if row is None:
                continue
            conn = self._connections[row]
            edge = self._compute_edge_points(conn["start_id"], conn["end_id"])
            previous = (
                conn["start_edge_x"], conn["start_edge_y"],
                conn["end_edge_x"], conn["end_edge_y"],
            )
            if edge != previous:
                (
                    conn["start_edge_x"], conn["start_edge_y"],
                    conn["end_edge_x"], conn["end_edge_y"],
                ) = edge
                changed_rows.append(row)
            if rebuild_hit_index:
                self._index_connection(conn)

        self._emit_geometry_rows_changed(changed_rows)
        self.geometry_batch_changed.emit(bool(rebuild_hit_index))

    def _is_connection_highlighted(self, conn):
        start_data = self._node_model.get_node_data(conn["start_id"])
        end_data = self._node_model.get_node_data(conn["end_id"])
        return bool(
            (start_data and (
                start_data.get("is_selected") or start_data.get("is_hovered")
            ))
            or (end_data and (
                end_data.get("is_selected") or end_data.get("is_hovered")
            ))
        )

    def _on_node_selection_batch_changed(self, node_ids):
        changed_rows = []
        for conn_id in self._affected_connection_ids(node_ids):
            row = self._id_to_index.get(conn_id)
            if row is None:
                continue
            conn = self._connections[row]
            highlighted = self._is_connection_highlighted(conn)
            if highlighted == conn["is_highlighted"]:
                continue
            conn["is_highlighted"] = highlighted
            changed_rows.append(row)
        self._emit_rows_changed(
            changed_rows, [ConnectionRoles.IsHighlightedRole]
        )

    def _on_node_data_changed(self, top_left, bottom_right, roles):
        from .node_list_model import NodeRoles

        geometry_roles = {
            NodeRoles.XRole, NodeRoles.YRole,
            NodeRoles.WidthRole, NodeRoles.HeightRole,
        }
        highlight_roles = {NodeRoles.IsSelectedRole, NodeRoles.IsHoveredRole}
        geometry_changed = not roles or any(role in geometry_roles for role in roles)
        highlight_changed = not roles or any(role in highlight_roles for role in roles)
        if (
            geometry_changed
            and self._node_model.position_batch_active
            and roles
            and all(role in {NodeRoles.XRole, NodeRoles.YRole} for role in roles)
        ):
            geometry_changed = False
        if (
            geometry_changed
            and self._node_model.size_batch_active
            and roles
            and all(
                role in {NodeRoles.WidthRole, NodeRoles.HeightRole}
                for role in roles
            )
        ):
            geometry_changed = False
        if (
            highlight_changed
            and self._node_model.selection_batch_active
            and roles
            and all(role == NodeRoles.IsSelectedRole for role in roles)
        ):
            highlight_changed = False
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
                highlighted = self._is_connection_highlighted(conn)
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
