from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt6.QtGui import QColor, QBrush, QPen, QCursor
from PyQt6.QtCore import Qt


class ResizeHandle(QGraphicsRectItem):
    def __init__(self, parent):
        super().__init__(0, 0, 10, 10, parent)
        self.setBrush(QBrush(QColor("#555555")))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def mouseMoveEvent(self, event):
        if self.parentItem():
            self.parentItem().handle_resize(self.pos() + event.pos())

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.parentItem():
            self.parentItem().finalize_resize()
