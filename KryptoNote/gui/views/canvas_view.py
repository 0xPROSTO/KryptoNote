from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QMessageBox

from .helpers.canvas_interaction import InertiaHandler, ZoomHandler
from .helpers.grid_renderer import GridRenderer
from ..nodes import BaseNode, ConnectionLine


class InfiniteCanvasView(QGraphicsView):
    mouse_moved = Signal(QPointF)
    node_clicked_signal = Signal(object)
    connection_right_clicked_signal = Signal(object)
    zoom_changed = Signal(float)

    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.is_erasing = False
        self._last_emitted_coords = (None, None)

        self.inertia = InertiaHandler(self)
        self.zoom_agent = ZoomHandler(self)
        self.zoom_agent.zoom_changed.connect(self._on_zoom_changed)

    def _on_zoom_changed(self, scale):
        """Broadcast zoom to the overlay AND update LOD on all nodes."""
        self.zoom_changed.emit(scale)
        for item in self.scene().items():
            if item.parentItem() is None and hasattr(item, "apply_lod"):
                item.apply_lod(scale)

    def drawBackground(self, painter, rect):
        GridRenderer.draw_grid(self, painter, rect)

    def mousePressEvent(self, event: QMouseEvent):
        self.inertia.stop()
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
                if (
                        item
                        and item.parentItem()
                        and isinstance(item.parentItem(), BaseNode)
                ):
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

        old_h = self.horizontalScrollBar().value()
        old_v = self.verticalScrollBar().value()
        super().mouseMoveEvent(event)
        if (
                event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton)
                and not self.is_erasing
        ):
            new_h = self.horizontalScrollBar().value()
            new_v = self.verticalScrollBar().value()
            if old_h != new_h or old_v != new_v:
                delta = QPointF(old_h - new_h, old_v - new_v)
                self.inertia.update_velocity(delta)
            else:
                self.inertia.decay_velocity()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.is_erasing:
            self.is_erasing = False
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().unsetCursor()
            return

        super().mouseReleaseEvent(event)
        if (
                event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton)
                and not self.is_erasing
        ):
            self.inertia.start_if_needed()

    def erase_under_mouse(self, pos):
        items = self.items(pos)
        for item in items:
            if isinstance(item, ConnectionLine):
                if hasattr(item, "animate_deletion"):
                    item.animate_deletion()
                else:
                    item.delete_connection()
                break

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.20
            zoom_out_factor = 1 / zoom_in_factor
            current_scale = self.transform().m11()
            if event.angleDelta().y() > 0:
                target = current_scale * zoom_in_factor
            else:
                target = current_scale * zoom_out_factor

            self.zoom_agent.scale_to(target, event.position().toPoint())
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Delete:
            items = self.scene().selectedItems()
            if items:
                confirm = QMessageBox.question(
                    self,
                    "Delete",
                    f"Delete {len(items)} items?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    for item in items:
                        if hasattr(item, "animate_deletion"):
                            item.animate_deletion()
                        elif hasattr(item, "delete_node"):
                            item.delete_node()
                        elif hasattr(item, "delete_connection"):
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
