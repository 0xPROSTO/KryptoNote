from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor, QPainterPath, QIcon


class VectorIcons:
    @staticmethod
    def get_icon(icon_type: str, color=Qt.GlobalColor.white) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()

        if icon_type == "play":
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            path.moveTo(11, 8)
            path.lineTo(25, 16)
            path.lineTo(11, 24)
            path.closeSubpath()
            painter.drawPath(path)

        elif icon_type == "pause":
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            path.addRoundedRect(10, 8, 4, 16, 1, 1)
            path.addRoundedRect(18, 8, 4, 16, 1, 1)
            painter.drawPath(path)

        elif icon_type == "volume":
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            path.moveTo(12, 12)
            path.lineTo(8, 12)
            path.lineTo(8, 20)
            path.lineTo(12, 20)
            path.lineTo(18, 26)
            path.lineTo(18, 6)
            path.closeSubpath()
            painter.drawPath(path)

            pen = QColor(color)
            painter.setPen(pen)
            pen = painter.pen()
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(15, 10, 8, 12), -45 * 16, 90 * 16)
            painter.drawArc(QRectF(13, 6, 14, 20), -45 * 16, 90 * 16)

        elif icon_type == "mute":
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            path.moveTo(12, 12)
            path.lineTo(8, 12)
            path.lineTo(8, 20)
            path.lineTo(12, 20)
            path.lineTo(18, 26)
            path.lineTo(18, 6)
            path.closeSubpath()
            painter.drawPath(path)

            pen = QColor(color)
            painter.setPen(pen)
            pen = painter.pen()
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(20, 12, 26, 18)
            painter.drawLine(26, 12, 20, 18)

        painter.end()
        return QIcon(pixmap)
