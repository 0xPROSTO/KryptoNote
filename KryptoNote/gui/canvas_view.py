from PyQt6.QtWidgets import QGraphicsView, QMessageBox
from PyQt6.QtGui import QPainter, QColor, QPen, QMouseEvent
from PyQt6.QtCore import Qt, pyqtSignal, QPointF

from .nodes import BaseNode, ConnectionLine

from ..config import Config


class InfiniteCanvasView(QGraphicsView):
    mouse_moved = pyqtSignal(QPointF)
    node_clicked_signal = pyqtSignal(object)  # Передает саму ноду
    connection_right_clicked_signal = pyqtSignal(object)  # Передает связь

    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        grid_size = Config.GRID_SIZE
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        pen = QPen(QColor(Config.GRID_COLOR))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)

        for x in range(left, int(rect.right()), grid_size):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), grid_size):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        self.mouse_moved.emit(scene_pos)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            item = self.itemAt(event.pos())

            if event.button() == Qt.MouseButton.LeftButton:
                if isinstance(item, BaseNode):
                    self.node_clicked_signal.emit(item)
                    return

                if item and item.parentItem() and isinstance(item.parentItem(), BaseNode):
                    self.node_clicked_signal.emit(item.parentItem())
                    return

            elif event.button() == Qt.MouseButton.RightButton:
                if isinstance(item, ConnectionLine):
                    self.connection_right_clicked_signal.emit(item)
                    return

        super().mousePressEvent(event)

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
        if event.key() == Qt.Key.Key_Delete:
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