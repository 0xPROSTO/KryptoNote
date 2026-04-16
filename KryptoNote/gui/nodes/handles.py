from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPen, QCursor, QPainterPath, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from KryptoNote.gui.theme import Theme


class ResizeHandle(QGraphicsObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self._rect = QRectF(0, 0, 12, 12)

    def boundingRect(self):
        return self._rect

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        w, h = self._rect.width(), self._rect.height()
        padding = 2
        path.moveTo(w - padding, padding)
        path.lineTo(w - padding, h - padding)
        path.lineTo(padding, h - padding)
        path.closeSubpath()
        color = (
            Theme.Palette.ACCENT_MAIN if self._is_hovered else Theme.Palette.TEXT_MUTED
        )
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawPath(path)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mouseMoveEvent(self, event):
        if self.parentItem():
            self.parentItem().handle_resize(self.pos() + event.pos())

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.parentItem():
            self.parentItem().finalize_resize()
