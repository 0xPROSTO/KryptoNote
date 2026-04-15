from PySide6.QtCore import Qt, Signal, QPointF, QLineF
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QMessageBox, QLabel

from ..nodes import BaseNode, ConnectionLine
from ...config import Config


class InfiniteCanvasView(QGraphicsView):
    mouse_moved = Signal(QPointF)
    node_clicked_signal = Signal(object)
    connection_right_clicked_signal = Signal(object)

    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)

        self.is_erasing = False
        self._last_emitted_coords = (None, None)

        self.overlay_label = QLabel(self)
        self.overlay_label.setStyleSheet("""
            background-color: rgba(35, 35, 35, 180);
            color: #aaaaaa; 
            font-family: Segoe UI, sans-serif; 
            font-size: 12px;
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #444444;
        """)
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_overlay()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay()

    def _update_overlay(self):
        snap_state = "ON" if getattr(Config, 'SNAP_TO_GRID', False) else "OFF"
        self.overlay_label.setText(f"Snap: {snap_state}")
        self.overlay_label.adjustSize()
        x = self.viewport().width() - self.overlay_label.width() - 15
        y = self.viewport().height() - self.overlay_label.height() - 15
        self.overlay_label.move(x, y)

    def drawBackground(self, painter, rect):
        painter.save()

        fill_rect = rect.adjusted(-5, -5, 5, 5)
        painter.fillRect(fill_rect, QColor(Config.BACKGROUND_COLOR))

        scale = self.transform().m11()
        if scale < 0.15:
            painter.restore()
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        grid_size = Config.GRID_SIZE
        grid_main = Config.GRID_SIZE_MAIN

        left = int(rect.left())
        top = int(rect.top())
        right = int(rect.right())
        bottom = int(rect.bottom())

        left_grid = left - (left % grid_size)
        top_grid = top - (top % grid_size)

        lines = []
        lines_main = []

        fixed_lim = 1000000

        for x in range(left_grid, right + grid_size, grid_size):
            if x % grid_main == 0:
                lines_main.append(QLineF(x, -fixed_lim, x, fixed_lim))
            elif scale >= 0.5:
                lines.append(QLineF(x, -fixed_lim, x, fixed_lim))

        for y in range(top_grid, bottom + grid_size, grid_size):
            if y % grid_main == 0:
                lines_main.append(QLineF(-fixed_lim, y, fixed_lim, y))
            elif scale >= 0.5:
                lines.append(QLineF(-fixed_lim, y, fixed_lim, y))

        grid_color = QColor(Config.GRID_COLOR)
        grid_color_main = QColor(Config.GRID_COLOR_MAIN)

        if scale < 0.5:
            alpha = int(max(0, min(255, (scale - 0.15) / 0.35 * 255)))
            grid_color_main.setAlpha(alpha)

        if lines:
            pen = QPen(grid_color)
            pen.setWidth(0)
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.drawLines(lines)

        if lines_main:
            pen_main = QPen(grid_color_main)
            pen_main.setWidth(0)
            pen_main.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen_main)
            painter.drawLines(lines_main)

        painter.restore()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.is_erasing = True
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
                self.erase_under_mouse(event.pos())
                event.accept()
                return
            else:
                super().mousePressEvent(event)
                return

        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            item = self.itemAt(event.pos())
            if event.button() == Qt.MouseButton.LeftButton:
                if isinstance(item, BaseNode):
                    self.node_clicked_signal.emit(item)
                    return
                if item and item.parentItem() and isinstance(item.parentItem(), BaseNode):
                    self.node_clicked_signal.emit(item.parentItem())
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())

        ix, iy = int(scene_pos.x()), int(scene_pos.y())
        if (ix, iy) != self._last_emitted_coords:
            self._last_emitted_coords = (ix, iy)
            self.mouse_moved.emit(scene_pos)

        if self.is_erasing:
            self.erase_under_mouse(event.pos())
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.is_erasing:
            self.is_erasing = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().unsetCursor()
            return

        super().mouseReleaseEvent(event)

    def erase_under_mouse(self, pos):
        items = self.items(pos)
        for item in items:
            if isinstance(item, ConnectionLine):
                item.delete_connection()
                break

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor

            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
            else:
                zoom_factor = zoom_out_factor

            current_scale = self.transform().m11()
            if 0.1 < current_scale * zoom_factor < 5.0:
                self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Delete:
            items = self.scene().selectedItems()
            if items:
                confirm = QMessageBox.question(self, "Delete",
                                               f"Delete {len(items)} items?",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

                if confirm == QMessageBox.StandardButton.Yes:
                    for item in items:
                        if hasattr(item, 'delete_node'):
                            item.delete_node()
                        elif hasattr(item, 'delete_connection'):
                            item.delete_connection()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            if not self.is_erasing:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        if not self.is_erasing:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().focusOutEvent(event)
