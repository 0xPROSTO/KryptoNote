from PySide6.QtCore import QPointF, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QBrush, QPen, QPainter
from PySide6.QtWidgets import QGraphicsRectItem, QMenu, QGraphicsItem

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from ..handles import ResizeHandle


class BaseNode(QGraphicsRectItem):
    def __init__(self, item_id, x, y, w, h, service):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        self.currentColor = QColor(Theme.Palette.BORDER_DEFAULT)
        self.currentBrush = QBrush(QColor(Theme.Palette.BG_NODE))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.item_id = item_id
        self.service = service
        self.resizer = ResizeHandle(self)
        self.update_resizer_pos()
        self.connections = []
        self._is_hovered = False
        self._is_deleting = False
        self._deletion_progress = 0.0

        self.color_anim = QVariantAnimation()
        self.color_anim.setDuration(120)
        self.color_anim.valueChanged.connect(self._on_color_changed)
        
        self.components = []
        
    def add_component(self, component):
        self.components.append(component)
        component.on_attached(self)
        
    def get_component(self, comp_class):
        for c in self.components:
            if isinstance(c, comp_class):
                return c
        return None
        
    def dispatch_event(self, event_type, *args, **kwargs):
        for c in self.components:
            c.on_event(event_type, *args, **kwargs)

    def _on_color_changed(self, color):
        self.currentColor = color
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget):
        rec = self.rect()
        radius = Theme.RADIUS
        painter.setBrush(self.currentBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rec, radius, radius)
        width = Theme.BORDER_WIDTH
        if self._is_hovered and not self.isSelected():
            width *= 1.5

        pen = QPen(self.currentColor, width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rec, radius, radius)

        if self._is_deleting and self._deletion_progress > 0:
            flash_opacity = 0
            if self._deletion_progress < 0.33:
                flash_opacity = int((self._deletion_progress / 0.33) * 180)
            else:
                flash_opacity = int(180 * (1.0 - (self._deletion_progress - 0.33) / 0.67))

            painter.setBrush(QColor(90, 90, 90, max(0, min(255, flash_opacity))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rec, radius, radius)

        if self.isSelected():
            highlight_pen = QPen(QColor(255, 255, 255, 15), 1)
            painter.setPen(highlight_pen)
            inner_rect = rec.adjusted(1.2, 1.2, -1.2, -1.2)
            painter.drawRoundedRect(inner_rect, radius - 1, radius - 1)

    def update_pen(self):
        is_hovered = self._is_hovered
        is_selected = self.isSelected()
        if is_selected:
            target_color = QColor(Theme.Palette.BORDER_SELECTED)

        elif is_hovered:
            target_color = QColor(Theme.Palette.ACCENT_MAIN)

        else:
            target_color = QColor(Theme.Palette.BORDER_DEFAULT)

        if self.color_anim.endValue() != target_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(self.currentColor)
            self.color_anim.setEndValue(target_color)
            self.color_anim.start()

        for line in self.connections:
            if hasattr(line, "update_pen"):
                line.update_pen()

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        super().hoverEnterEvent(event)
        self.update_pen()

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        super().hoverLeaveEvent(event)
        self.update_pen()

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
                if hasattr(line, "update_pen"):
                    line.update_pen()

        return super().itemChange(change, value)

    def update_resizer_pos(self):
        r = self.rect()
        self.resizer.setPos(r.width() - 14, r.height() - 14)

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
        
    def apply_lod(self, lod):
        self.dispatch_event("apply_lod", lod=lod)

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
            self.animate_deletion()

    def extend_context_menu(self, menu):
        pass

    def animate_deletion(self):
        if self._is_deleting:
            return
        self._is_deleting = True
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        for line in list(self.connections):
            if hasattr(line, "animate_deletion"):
                line.animate_deletion()

        self.del_anim = QVariantAnimation()
        self.del_anim.setDuration(240)
        self.del_anim.setStartValue(0.0)
        self.del_anim.setEndValue(1.0)

        def update_frame(val):
            self._deletion_progress = val
            self.setOpacity(1.0 - val)
            self.update()

        self.del_anim.valueChanged.connect(update_frame)
        self.del_anim.finished.connect(self.delete_node)
        self.del_anim.start()

    def delete_node(self):
        for line in list(self.connections):
            line.remove_from_scene_only()

        if self.scene():
            self.scene().removeItem(self)

        from PySide6.QtCore import QTimer
        srv = self.service
        i_id = self.item_id
        QTimer.singleShot(10, lambda: srv.delete_node_cascade(i_id))
