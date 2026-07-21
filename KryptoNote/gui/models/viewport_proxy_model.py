"""Buffered viewport proxies used to keep QML Repeater delegate counts bounded."""

from PySide6.QtCore import QRectF, QSortFilterProxyModel, QTimer, Slot

from .connection_list_model import ConnectionRoles
from .node_list_model import NodeRoles


class _ViewportProxyModel(QSortFilterProxyModel):
    FILTER_ROLES = frozenset()

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._viewport = QRectF()
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
        rect = QRectF(
            float(left),
            float(top),
            max(0.0, float(right) - float(left)),
            max(0.0, float(bottom) - float(top)),
        )
        if self._viewport_ready and rect == self._viewport:
            return
        self._viewport = rect
        self._viewport_ready = True
        self._invalidate_filter()

    def _on_source_data_changed(self, _top_left, _bottom_right, roles):
        changed_roles = {int(role) for role in roles}
        if roles and not self.FILTER_ROLES.intersection(changed_roles):
            return
        self._filter_update_timer.start()

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
    FILTER_ROLES = frozenset(
        (int(NodeRoles.IsDeletingRole), int(NodeRoles.IsSelectedRole))
    )

    def _accepts(self, source_row, source_parent):
        if self._data(source_row, source_parent, NodeRoles.IsDeletingRole):
            return True
        if self._data(source_row, source_parent, NodeRoles.IsSelectedRole):
            return True
        x = float(self._data(source_row, source_parent, NodeRoles.XRole) or 0.0)
        y = float(self._data(source_row, source_parent, NodeRoles.YRole) or 0.0)
        width = float(
            self._data(source_row, source_parent, NodeRoles.WidthRole) or 0.0
        )
        height = float(
            self._data(source_row, source_parent, NodeRoles.HeightRole) or 0.0
        )
        return self._viewport.intersects(QRectF(x, y, width, height))


class ConnectionViewportProxyModel(_ViewportProxyModel):
    FILTER_ROLES = frozenset((int(ConnectionRoles.IsDeletingRole),))

    def _accepts(self, source_row, source_parent):
        if self._data(
            source_row, source_parent, ConnectionRoles.IsDeletingRole
        ):
            return True
        if self._data(
            source_row, source_parent, ConnectionRoles.IsHighlightedRole
        ):
            return True
        x1 = float(
            self._data(source_row, source_parent, ConnectionRoles.StartEdgeXRole)
            or 0.0
        )
        y1 = float(
            self._data(source_row, source_parent, ConnectionRoles.StartEdgeYRole)
            or 0.0
        )
        x2 = float(
            self._data(source_row, source_parent, ConnectionRoles.EndEdgeXRole)
            or 0.0
        )
        y2 = float(
            self._data(source_row, source_parent, ConnectionRoles.EndEdgeYRole)
            or 0.0
        )
        bounds = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        if bounds.width() == 0:
            bounds.setWidth(1.0)
        if bounds.height() == 0:
            bounds.setHeight(1.0)
        return self._viewport.intersects(bounds)
