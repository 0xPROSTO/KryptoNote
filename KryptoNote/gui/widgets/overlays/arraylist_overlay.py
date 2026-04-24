from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget

from ...theme.palette import Palette


class ArrayListOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.snap_state = "OFF"
        self.zoom_pct = "100%"
        self.row_h = 24
        self.snap_w = 75
        self.zoom_w = 90
        self.p_left = 8.0
        self.setFixedSize(int(self.zoom_w + self.p_left), self.row_h * 2)

    def set_snap_status(self, state):
        self.snap_state = "ON" if state else "OFF"
        self.update()

    def set_zoom_status(self, scale):
        new_pct = f"{int(scale * 100)}%"
        if self.zoom_pct != new_pct:
            self.zoom_pct = new_pct
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 4.0
        offset = 0.5
        overlap = 2.0
        w_inner = float(self.snap_w)
        w_outer = float(self.zoom_w)
        h = float(self.row_h)
        total_w = w_outer + self.p_left
        total_h = 2 * h
        p = self.p_left
        step_x = p + (w_outer - w_inner)
        path = QPainterPath()
        path.moveTo(total_w - offset, offset)
        path.lineTo(step_x + r, offset)
        path.quadTo(step_x + offset, offset, step_x + offset, r)
        path.lineTo(step_x + offset, h - r)
        path.quadTo(step_x + offset, h - offset, step_x - r, h - offset)
        path.lineTo(p + r, h - offset)
        path.quadTo(p + offset, h - offset, p + offset, h + r)
        path.lineTo(p + offset, total_h - overlap - r)
        path.quadTo(
            p + offset, total_h - overlap - offset, p - r, total_h - overlap - offset
        )
        path.lineTo(p - r, total_h - offset)
        path.lineTo(total_w - offset, total_h - offset)
        path.lineTo(total_w - offset, offset)
        painter.fillPath(path, QColor(Palette.BG_PANEL))
        pen = QPen(QColor(Palette.BORDER_DEFAULT))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        border_path = QPainterPath()
        border_path.moveTo(total_w, offset)
        border_path.lineTo(step_x + r, offset)
        border_path.quadTo(step_x + offset, offset, step_x + offset, r)
        border_path.lineTo(step_x + offset, h - r)
        border_path.quadTo(step_x + offset, h - offset, step_x - r, h - offset)
        border_path.lineTo(p + r, h - offset)
        border_path.quadTo(p + offset, h - offset, p + offset, h + r)
        border_path.lineTo(p + offset, total_h - overlap - r)
        border_path.quadTo(
            p + offset, total_h - overlap - offset, p - r, total_h - overlap - offset
        )
        painter.drawPath(border_path)
        painter.setPen(QColor(Palette.TEXT_MUTED))
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            int(step_x),
            0,
            self.snap_w,
            self.row_h,
            Qt.AlignmentFlag.AlignCenter,
            f"SNAP: {self.snap_state}",
        )
        painter.drawText(
            int(p),
            self.row_h,
            self.zoom_w,
            self.row_h,
            Qt.AlignmentFlag.AlignCenter,
            f"ZOOM: {self.zoom_pct}",
        )
