from PySide6.QtCore import QVariantAnimation, Qt, QPointF
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsLineItem, QMenu, QGraphicsItem, QStyle

from ...gui.theme import Theme


class ConnectionLine(QGraphicsLineItem):
    def __init__(self, conn_id, start_node, end_node, service):
        super().__init__()
        self.conn_id = conn_id
        self.start_node = start_node
        self.end_node = end_node
        self.service = service
        self.currentColor = QColor(Theme.Palette.BORDER_DEFAULT)
        pen = QPen(self.currentColor, 1.5)
        pen.setCosmetic(True)
        self.setPen(pen)

        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False

        self.color_anim = QVariantAnimation()
        self.color_anim.setDuration(120)
        self.color_anim.valueChanged.connect(self._on_color_changed)

        self.update_pen()
        self.update_position()

    def _on_color_changed(self, color):
        self.currentColor = color
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)

    def paint(self, painter, option, widget):
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        super().hoverEnterEvent(event)
        self.update_pen()

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        super().hoverLeaveEvent(event)
        self.update_pen()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update_pen()
        return super().itemChange(change, value)

    def update_pen(self):
        is_hovered = self._is_hovered
        is_selected = self.isSelected()
        is_node_selected = (self.start_node and self.start_node.isSelected()) or (
                self.end_node and self.end_node.isSelected()
        )
        is_start_hovered = (
            getattr(self.start_node, "_is_hovered", False) if self.start_node else False
        )
        is_end_hovered = (
            getattr(self.end_node, "_is_hovered", False) if self.end_node else False
        )
        is_node_hovered = is_start_hovered or is_end_hovered
        highlighted = is_hovered or is_selected or is_node_selected or is_node_hovered
        target_color = (
            QColor(Theme.Palette.ACCENT_MAIN)
            if highlighted
            else QColor(Theme.Palette.BORDER_DEFAULT)
        )
        target_width = 2.0 if highlighted else 1.5
        if self.color_anim.endValue() != target_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(self.currentColor)
            self.color_anim.setEndValue(target_color)
            self.color_anim.start()

        pen = self.pen()
        if pen.width() != target_width:
            pen.setWidth(target_width)
            self.setPen(pen)

    def update_position(self):
        if self.start_node and self.end_node:
            r1 = self.start_node.sceneBoundingRect()
            r2 = self.end_node.sceneBoundingRect()

            p1_center = r1.center()
            p2_center = r2.center()

            p1 = self._calculate_edge_point(p1_center, p2_center, r1)
            p2 = self._calculate_edge_point(p2_center, p1_center, r2)

            self.setLine(p1.x(), p1.y(), p2.x(), p2.y())

    def _calculate_edge_point(self, center, target, rect):
        dx = target.x() - center.x()
        dy = target.y() - center.y()

        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return center

        hw = rect.width() / 2
        hh = rect.height() / 2

        scale_x = abs(hw / dx) if dx != 0 else 1000000.0
        scale_y = abs(hh / dy) if dy != 0 else 1000000.0

        scale = min(scale_x, scale_y)

        return center + QPointF(dx * scale, dy * scale)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #333; color: white; }")
        delete_action = menu.addAction("Remove Link")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.animate_deletion()

    def animate_deletion(self):
        if hasattr(self, "_is_deleting") and getattr(self, "_is_deleting"):
            return
        self._is_deleting = True
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        self.del_anim = QVariantAnimation()
        self.del_anim.setDuration(240)
        self.del_anim.setStartValue(1.0)
        self.del_anim.setEndValue(0.0)

        def update_frame(val):
            self.setOpacity(val)
            if val > 0.67:
                pen = self.pen()
                pen.setColor(QColor(140, 140, 140))
                self.setPen(pen)
            self.update()

        self.del_anim.valueChanged.connect(update_frame)
        self.del_anim.finished.connect(self.delete_connection)
        self.del_anim.start()

    def delete_connection(self):
        self.service.delete_connection(self.conn_id)
        if self.start_node:
            self.start_node.remove_connection(self)
        if self.end_node:
            self.end_node.remove_connection(self)
        if self.scene():
            self.scene().removeItem(self)

    def remove_from_scene_only(self):
        if self.start_node:
            self.start_node.remove_connection(self)
        if self.end_node:
            self.end_node.remove_connection(self)
        if self.scene():
            self.scene().removeItem(self)
