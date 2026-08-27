"""Buffered viewport proxies used to keep QML Repeater delegate counts bounded."""

from PySide6.QtCore import QRectF, QSortFilterProxyModel, QTimer, Slot

from .connection_list_model import ConnectionRoles
from .node_list_model import NodeRoles


class _ViewportProxyModel(QSortFilterProxyModel):
    FILTER_ROLES = frozenset()
    VIEWPORT_PADDING_RATIO = 0.5
    MIN_VIEWPORT_PADDING = 256.0
    VIEWPORT_SHRINK_REBUILD_RATIO = 0.75

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._viewport = QRectF()
        self._buffered_request = QRectF()
        self._viewport_ready = False
        self._filter_update_timer = QTimer(self)
        self._filter_update_timer.setSingleShot(True)
        self._filter_update_timer.setInterval(0)
        self._filter_update_timer.timeout.connect(self._invalidate_filter)
        self.setDynamicSortFilter(False)
        self.setSourceModel(source_model)
        source_model.rowsInserted.connect(self._invalidate_filter)
        source_model.rowsRemoved.connect(self._invalidate_filter)
        source_model.modelReset.connect(self._invalidate_filter)
        source_model.dataChanged.connect(self._on_source_data_changed)

    @Slot(float, float, float, float)
    def updateViewport(self, left, top, right, bottom):
        requested = QRectF(
            float(left),
            float(top),
            max(0.0, float(right) - float(left)),
            max(0.0, float(bottom) - float(top)),
        )
        if self._viewport_ready and self._viewport.contains(requested):
            width_shrank = (
                self._buffered_request.width() > 0.0
                and requested.width()
                < self._buffered_request.width()
                * self.VIEWPORT_SHRINK_REBUILD_RATIO
            )
            height_shrank = (
                self._buffered_request.height() > 0.0
                and requested.height()
                < self._buffered_request.height()
                * self.VIEWPORT_SHRINK_REBUILD_RATIO
            )
            if not width_shrank and not height_shrank:
                return
        padding_x = max(
            requested.width() * self.VIEWPORT_PADDING_RATIO,
            self.MIN_VIEWPORT_PADDING,
        )
        padding_y = max(
            requested.height() * self.VIEWPORT_PADDING_RATIO,
            self.MIN_VIEWPORT_PADDING,
        )
        self._viewport = requested.adjusted(
            -padding_x, -padding_y, padding_x, padding_y
        )
        self._buffered_request = QRectF(requested)
        self._viewport_ready = True
        self._filter_update_timer.stop()
        self._invalidate_filter()

    def _on_source_data_changed(self, _top_left, _bottom_right, roles):
        changed_roles = {int(role) for role in roles}
        if roles and not self.FILTER_ROLES.intersection(changed_roles):
            return
        if self._source_change_is_batched(changed_roles):
            return
        self._filter_update_timer.start()

    def _source_change_is_batched(self, _changed_roles):
        return False

    def _invalidate_filter(self, *_args):
        if hasattr(self, "beginFilterChange") and hasattr(self, "endFilterChange"):
            self.beginFilterChange()
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._viewport_ready:
            return False
        return self._accepts(source_row, source_parent)

    def _data(self, source_row, source_parent, role):
        index = self.sourceModel().index(source_row, 0, source_parent)
        return self.sourceModel().data(index, role)


class NodeViewportProxyModel(_ViewportProxyModel):
    GEOMETRY_ROLES = frozenset((
        int(NodeRoles.XRole),
        int(NodeRoles.YRole),
        int(NodeRoles.WidthRole),
        int(NodeRoles.HeightRole),
    ))
    FILTER_ROLES = GEOMETRY_ROLES.union((int(NodeRoles.IsDeletingRole),))

    def __init__(self, source_model, parent=None):
        self._transform_node_ids = set()
        super().__init__(source_model, parent)
        source_model.positions_batch_changed.connect(
            self._on_geometry_batch_changed
        )
        source_model.sizes_batch_changed.connect(
            self._on_geometry_batch_changed
        )

    def _source_change_is_batched(self, changed_roles):
        if not self.GEOMETRY_ROLES.intersection(changed_roles):
            return False
        source = self.sourceModel()
        return source.position_batch_active or source.size_batch_active

    def _on_geometry_batch_changed(self, _node_ids, rebuild_filter):
        if rebuild_filter:
            self._filter_update_timer.start()

    @Slot(list)
    def retainTransformNodes(self, node_ids):
        retained = set()
        for node_id in node_ids or ():
            try:
                retained.add(int(node_id))
            except (TypeError, ValueError):
                continue
        if retained == self._transform_node_ids:
            return
        self._transform_node_ids = retained
        self._filter_update_timer.stop()
        self._invalidate_filter()

    @Slot()
    def releaseTransformNodes(self):
        if not self._transform_node_ids:
            return
        self._transform_node_ids.clear()
        # Defer the rebuild until the QML controller has fully ended its
        # pointer session.  A synchronous delegate removal here can destroy
        # the active ResizeHandle while its release callback is unwinding.
        self._filter_update_timer.start()

    def _accepts(self, source_row, source_parent):
        node = self.sourceModel().get_node_data_at_row(source_row)
        if node is None:
            return False
        if node.get("id") in self._transform_node_ids:
            return True
        if node.get("is_deleting"):
            return True
        x = float(node.get("x") or 0.0)
        y = float(node.get("y") or 0.0)
        width = float(node.get("width") or 0.0)
        height = float(node.get("height") or 0.0)
        return (
            x + width > self._viewport.left()
            and x < self._viewport.right()
            and y + height > self._viewport.top()
            and y < self._viewport.bottom()
        )


class ConnectionViewportProxyModel(_ViewportProxyModel):
    GEOMETRY_ROLES = frozenset((
        int(ConnectionRoles.StartEdgeXRole),
        int(ConnectionRoles.StartEdgeYRole),
        int(ConnectionRoles.EndEdgeXRole),
        int(ConnectionRoles.EndEdgeYRole),
    ))
    FILTER_ROLES = GEOMETRY_ROLES.union((
        int(ConnectionRoles.IsDeletingRole),
    ))

    def __init__(self, source_model, parent=None):
        super().__init__(source_model, parent)
        source_model.geometry_batch_changed.connect(
            self._on_geometry_batch_changed
        )

    def _source_change_is_batched(self, changed_roles):
        return bool(
            self.GEOMETRY_ROLES.intersection(changed_roles)
            and self.sourceModel().geometry_batch_active
        )

    def _on_geometry_batch_changed(self, rebuild_filter):
        if rebuild_filter:
            self._filter_update_timer.start()

    def _accepts(self, source_row, source_parent):
        connection = self.sourceModel().get_connection_data_at_row(source_row)
        if connection is None:
            return False
        if connection.get("is_deleting"):
            return True
        x1 = float(connection.get("start_edge_x") or 0.0)
        y1 = float(connection.get("start_edge_y") or 0.0)
        x2 = float(connection.get("end_edge_x") or 0.0)
        y2 = float(connection.get("end_edge_y") or 0.0)
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        if left == right:
            right += 1.0
        if top == bottom:
            bottom += 1.0
        return (
            right > self._viewport.left()
            and left < self._viewport.right()
            and bottom > self._viewport.top()
            and top < self._viewport.bottom()
        )
