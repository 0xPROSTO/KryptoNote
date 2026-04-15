from PySide6.QtCore import QPointF, QVariantAnimation
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QMenu, QGraphicsItem, QStyle

from KryptoNote.config import Config
from ..handles import ResizeHandle


class BaseNode(QGraphicsRectItem):
    def __init__(self, item_id, x, y, w, h, service):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(Config.COLOR_NODE_BG)))

        self.currentColor = QColor("#404040")
        pen = QPen(self.currentColor, 1)
        pen.setCosmetic(True)
        self.setPen(pen)

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.item_id = item_id
        self.service = service

        self.resizer = ResizeHandle(self)
        self.update_resizer_pos()

        self.connections = []
        self._is_hovered = False

        self.color_anim = QVariantAnimation()
        self.color_anim.setDuration(120)
        self.color_anim.valueChanged.connect(self._on_color_changed)

    def _on_color_changed(self, color):
        self.currentColor = color
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)

    def paint(self, painter, option, widget):
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def update_pen(self):
        is_hovered = self._is_hovered
        is_selected = self.isSelected()

        highlighted = is_hovered or is_selected
        target_color = QColor(Config.COLOR_LINK_HIGHLIGHT) if highlighted else QColor("#404040")
        target_width = 2.5 if highlighted else 1.0

        if self.currentColor != target_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(self.currentColor)
            self.color_anim.setEndValue(target_color)
            self.color_anim.start()

        pen = self.pen()
        if pen.width() != target_width:
            pen.setWidthF(target_width)
            self.setPen(pen)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        super().hoverEnterEvent(event)
        self.update_pen()
        for line in self.connections:
            if hasattr(line, 'update_pen'):
                line.update_pen()

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        super().hoverLeaveEvent(event)
        self.update_pen()
        for line in self.connections:
            if hasattr(line, 'update_pen'):
                line.update_pen()

    def add_connection(self, line):
        if line not in self.connections:
            self.connections.append(line)

    def remove_connection(self, line):
        if line in self.connections:
            self.connections.remove(line)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if Config.SNAP_TO_GRID:
                new_x = round(value.x() / Config.GRID_SIZE) * Config.GRID_SIZE
                new_y = round(value.y() / Config.GRID_SIZE) * Config.GRID_SIZE
                value = QPointF(new_x, new_y)
            return value

        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for line in self.connections:
                line.update_position()

        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update_pen()
            for line in self.connections:
                if hasattr(line, 'update_pen'):
                    line.update_pen()
        return super().itemChange(change, value)

    def update_resizer_pos(self):
        r = self.rect()
        self.resizer.setPos(r.width() - 10, r.height() - 10)

    def handle_resize(self, new_pos):
        new_w = max(100, new_pos.x())
        new_h = max(50, new_pos.y())
        if Config.SNAP_TO_GRID:
            new_w = round(new_w / Config.GRID_SIZE) * Config.GRID_SIZE
            new_h = round(new_h / Config.GRID_SIZE) * Config.GRID_SIZE

        self.setRect(0, 0, new_w, new_h)
        self.update_resizer_pos()
        self.update_content_layout()

        for line in self.connections:
            line.update_position()

    def finalize_resize(self):
        r = self.rect()
        self.service.update_size(self.item_id, r.width(), r.height())

    def update_content_layout(self):
        pass

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.service.update_pos(self.item_id, self.x(), self.y())
        for line in self.connections:
            line.update_position()

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #333; color: white; }")
        self.extend_context_menu(menu)
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.delete_node()

    def extend_context_menu(self, menu):
        pass

    def delete_node(self):
        for line in list(self.connections):
            line.remove_from_scene_only()

        self.service.delete_node_cascade(self.item_id)

        if self.scene():
            self.scene().removeItem(self)
