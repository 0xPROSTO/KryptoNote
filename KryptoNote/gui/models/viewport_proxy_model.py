"""Buffered viewport proxies used to keep QML Repeater delegate counts bounded."""

import math

from PySide6.QtCore import QSortFilterProxyModel, QTimer, Slot

from .connection_list_model import ConnectionRoles
from .node_list_model import NodeRoles


class _ViewportProxyModel(QSortFilterProxyModel):
    FILTER_ROLES = frozenset()
    VIEWPORT_PADDING_RATIO = 0.5
    MIN_VIEWPORT_PADDING = 256.0
    VIEWPORT_SHRINK_REBUILD_RATIO = 0.75

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._viewport_center_x = 0.0
        self._viewport_center_y = 0.0
        self._viewport_half_width = 0.0
        self._viewport_half_height = 0.0
        self._buffered_request_width = 0.0
        self._buffered_request_height = 0.0
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
        """Compatibility wrapper for the former edge-based QML contract."""
        left = float(left)
        top = float(top)
        width = max(0.0, float(right) - left)
        height = max(0.0, float(bottom) - top)
        self._update_viewport_centered(
            left + width / 2.0,
            top + height / 2.0,
            width,
            height,
        )

    @Slot(float, float, float, float)
    def updateViewportCentered(self, center_x, center_y, width, height):
        """Update from a world center plus local-sized viewport extents."""
        self._update_viewport_centered(
            float(center_x),
            float(center_y),
            max(0.0, float(width)),
            max(0.0, float(height)),
        )

    def _update_viewport_centered(self, center_x, center_y, width, height):
        if not all(map(math.isfinite, (center_x, center_y, width, height))):
            return

        half_width = width / 2.0
        half_height = height / 2.0
        if self._viewport_ready and self._contains_request(
            center_x, center_y, half_width, half_height
        ):
            width_shrank = (
                self._buffered_request_width > 0.0
                and width
                < self._buffered_request_width
                * self.VIEWPORT_SHRINK_REBUILD_RATIO
            )
            height_shrank = (
                self._buffered_request_height > 0.0
                and height
                < self._buffered_request_height
                * self.VIEWPORT_SHRINK_REBUILD_RATIO
            )
            if not width_shrank and not height_shrank:
                return
        padding_x = max(
            width * self.VIEWPORT_PADDING_RATIO,
            self.MIN_VIEWPORT_PADDING,
        )
        padding_y = max(
            height * self.VIEWPORT_PADDING_RATIO,
            self.MIN_VIEWPORT_PADDING,
        )
        self._viewport_center_x = center_x
        self._viewport_center_y = center_y
        self._viewport_half_width = half_width + padding_x
        self._viewport_half_height = half_height + padding_y
        self._buffered_request_width = width
        self._buffered_request_height = height
        self._viewport_ready = True
        self._filter_update_timer.stop()
        self._invalidate_filter()

    def _contains_request(
        self, center_x, center_y, half_width, half_height
    ):
        return (
            abs(center_x - self._viewport_center_x) + half_width
            <= self._viewport_half_width
            and abs(center_y - self._viewport_center_y) + half_height
            <= self._viewport_half_height
        )

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
        relative_x = x - self._viewport_center_x
        relative_y = y - self._viewport_center_y
        return (
            relative_x + width > -self._viewport_half_width
            and relative_x < self._viewport_half_width
            and relative_y + height > -self._viewport_half_height
            and relative_y < self._viewport_half_height
        )


class ConnectionViewportProxyModel(_ViewportProxyModel):
    GEOMETRY_ROLES = frozenset((
        int(ConnectionRoles.StartEdgeXRole),
        int(ConnectionRoles.StartEdgeYRole),
        int(ConnectionRoles.EndEdgeXRole),
        int(ConnectionRoles.EndEdgeYRole),
        int(ConnectionRoles.StartOriginXRole),
        int(ConnectionRoles.StartOriginYRole),
        int(ConnectionRoles.StartLocalXRole),
        int(ConnectionRoles.StartLocalYRole),
        int(ConnectionRoles.EndOriginXRole),
        int(ConnectionRoles.EndOriginYRole),
        int(ConnectionRoles.EndLocalXRole),
        int(ConnectionRoles.EndLocalYRole),
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
        start_origin_x = float(connection.get("start_origin_x") or 0.0)
        start_origin_y = float(connection.get("start_origin_y") or 0.0)
        end_origin_x = float(connection.get("end_origin_x") or 0.0)
        end_origin_y = float(connection.get("end_origin_y") or 0.0)
        relative_x1 = (
            start_origin_x - self._viewport_center_x
        ) + float(connection.get("start_local_x") or 0.0)
        relative_y1 = (
            start_origin_y - self._viewport_center_y
        ) + float(connection.get("start_local_y") or 0.0)
        relative_x2 = (
            end_origin_x - self._viewport_center_x
        ) + float(connection.get("end_local_x") or 0.0)
        relative_y2 = (
            end_origin_y - self._viewport_center_y
        ) + float(connection.get("end_local_y") or 0.0)
        left = min(relative_x1, relative_x2)
        right = max(relative_x1, relative_x2)
        top = min(relative_y1, relative_y2)
        bottom = max(relative_y1, relative_y2)
        if left == right:
            right += 1.0
        if top == bottom:
            bottom += 1.0
        return (
            right > -self._viewport_half_width
            and left < self._viewport_half_width
            and bottom > -self._viewport_half_height
            and top < self._viewport_half_height
        )
