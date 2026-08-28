from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont, QPen, QRegion
from PySide6.QtWidgets import QWidget

from ...theme.palette import Palette


class ArrayListOverlay(QWidget):
    snap_clicked = Signal()
    zoom_clicked = Signal()
    stats_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.snap_state = "OFF"
        self.zoom_pct = "100%"
        self.stats_text = "Nodes: 0 | Links: 0 | Size: 0 B"
        self.row_h = 24
        self.snap_w = 75
        self.zoom_w = 90
        self.stats_w = 210
        self.p_left = 8.0
        self._hovered_row = None
        self._pressed_row = None
        self.setFixedSize(int(self.stats_w + self.p_left), self.row_h * 3)
        self._sync_mask()

    def set_snap_status(self, state):
        self.snap_state = "ON" if state else "OFF"
        self.update()

    def set_zoom_status(self, scale):
        new_pct = f"{int(scale * 100)}%"
        if self.zoom_pct != new_pct:
            self.zoom_pct = new_pct
            self.update()

    def set_stats(self, node_count, link_count, size_label):
        text = f"Nodes: {node_count} | Links: {link_count} | Size: {size_label}"
        if self.stats_text != text:
            self.stats_text = text
            self.update()

    def mousePressEvent(self, event):
        row = self._hit_row(event.position())
        if event.button() == Qt.MouseButton.LeftButton and row is not None:
            self._pressed_row = row
            self.update()
            event.accept()
            return
        event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        pressed_row = self._pressed_row
        self._pressed_row = None
        row = self._hit_row(event.position())
        self.update()
        if pressed_row is None:
            event.ignore()
            return
        if row == pressed_row:
            {
                "snap": self.snap_clicked,
                "zoom": self.zoom_clicked,
                "stats": self.stats_clicked,
            }[row].emit()
        event.accept()

    def mouseMoveEvent(self, event):
        self._update_hover(event.position())
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        self._update_hover(event.position())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered_row = None
        self._pressed_row = None
        self.setToolTip("")
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_mask()

    def _hit_row(self, pos):
        if not self._shape_path().contains(pos):
            return None
        if 0 <= pos.y() < self.row_h:
            return "snap"
        if self.row_h <= pos.y() < self.row_h * 2:
            return "zoom"
        if self.row_h * 2 <= pos.y() < self.row_h * 3:
            return "stats"
        return None

    def _update_hover(self, pos):
        row = self._hit_row(pos)
        if row != self._hovered_row:
            self._hovered_row = row
            self.update()
        if row is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(
                {
                    "snap": "Toggle snap to grid (G)",
                    "zoom": "Set an exact zoom level (Ctrl+0 resets)",
                    "stats": "Open Knowledge Dashboard",
                }[row]
            )
        else:
            self.setToolTip("")
            self.unsetCursor()

    def _shape_path(self, offset=0.5):
        r = 4.0
        overlap = 2.0
        w_stats = float(self.stats_w)
        h = float(self.row_h)
        total_w = w_stats + self.p_left
        total_h = 3 * h
        stats_x = self.p_left
        snap_x = total_w - float(self.snap_w)
        zoom_x = total_w - float(self.zoom_w)

        path = QPainterPath()
        path.moveTo(total_w - offset, offset)
        path.lineTo(snap_x + r, offset)
        path.quadTo(snap_x + offset, offset, snap_x + offset, r)
        path.lineTo(snap_x + offset, h - r)
        path.quadTo(snap_x + offset, h - offset, snap_x - r, h - offset)
        path.lineTo(zoom_x + r, h - offset)
        path.quadTo(zoom_x + offset, h - offset, zoom_x + offset, h + r)
        path.lineTo(zoom_x + offset, 2 * h - r)
        path.quadTo(zoom_x + offset, 2 * h - offset, zoom_x - r, 2 * h - offset)
        path.lineTo(stats_x + r, 2 * h - offset)
        path.quadTo(stats_x + offset, 2 * h - offset, stats_x + offset, 2 * h + r)
        path.lineTo(stats_x + offset, total_h - overlap - r)
        path.quadTo(
            stats_x + offset,
            total_h - overlap - offset,
            stats_x - r,
            total_h - overlap - offset,
        )
        path.lineTo(stats_x - r, total_h - offset)
        path.lineTo(total_w - offset, total_h - offset)
        path.lineTo(total_w - offset, offset)
        return path

    def _border_path(self, offset=0.5):
        r = 4.0
        overlap = 2.0
        w_stats = float(self.stats_w)
        h = float(self.row_h)
        total_w = w_stats + self.p_left
        total_h = 3 * h
        stats_x = self.p_left
        snap_x = total_w - float(self.snap_w)
        zoom_x = total_w - float(self.zoom_w)

        path = QPainterPath()
        path.moveTo(total_w, offset)
        path.lineTo(snap_x + r, offset)
        path.quadTo(snap_x + offset, offset, snap_x + offset, r)
        path.lineTo(snap_x + offset, h - r)
        path.quadTo(snap_x + offset, h - offset, snap_x - r, h - offset)
        path.lineTo(zoom_x + r, h - offset)
        path.quadTo(zoom_x + offset, h - offset, zoom_x + offset, h + r)
        path.lineTo(zoom_x + offset, 2 * h - r)
        path.quadTo(zoom_x + offset, 2 * h - offset, zoom_x - r, 2 * h - offset)
        path.lineTo(stats_x + r, 2 * h - offset)
        path.quadTo(stats_x + offset, 2 * h - offset, stats_x + offset, 2 * h + r)
        path.lineTo(stats_x + offset, total_h - overlap - r)
        path.quadTo(
            stats_x + offset,
            total_h - overlap - offset,
            stats_x - r,
            total_h - overlap - offset,
        )
        return path

    def _sync_mask(self):
        total_w = int(self.stats_w + self.p_left)
        snap_x = total_w - self.snap_w
        zoom_x = total_w - self.zoom_w
        aa_pad = 6
        mask = QRegion(
            QRect(snap_x - aa_pad, 0, self.snap_w + aa_pad + 2, self.row_h + aa_pad)
        )
        mask = mask.united(
            QRegion(
                QRect(
                    zoom_x - aa_pad,
                    self.row_h - aa_pad,
                    self.zoom_w + aa_pad + 2,
                    self.row_h + aa_pad * 2,
                )
            )
        )
        mask = mask.united(
            QRegion(
                QRect(
                    0,
                    self.row_h * 2 - aa_pad,
                    self.width(),
                    self.row_h + aa_pad + 2,
                )
            )
        )
        self.setMask(mask)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = self._shape_path()
        painter.fillPath(path, QColor(Palette.BG_PANEL))

        interactive_row = self._pressed_row or self._hovered_row
        if interactive_row is not None:
            row_index = {"snap": 0, "zoom": 1, "stats": 2}[interactive_row]
            tint = QColor(Palette.ACCENT_LOW)
            tint.setAlpha(130 if self._pressed_row is not None else 78)
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(
                QRectF(0, row_index * self.row_h, self.width(), self.row_h),
                tint,
            )
            painter.restore()

        pen = QPen(QColor(Palette.BORDER_DEFAULT))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(self._border_path(offset=0.5))

        total_w = float(self.stats_w) + self.p_left
        snap_x = total_w - float(self.snap_w)
        zoom_x = total_w - float(self.zoom_w)
        stats_x = self.p_left

        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(
            QColor(
                Palette.TEXT_ACCENT
                if self._hovered_row == "snap" or self._pressed_row == "snap"
                else Palette.TEXT_MUTED
            )
        )
        painter.drawText(
            int(snap_x),
            0,
            self.snap_w,
            self.row_h,
            Qt.AlignmentFlag.AlignCenter,
            f"SNAP: {self.snap_state}",
        )
        painter.setPen(
            QColor(
                Palette.TEXT_ACCENT
                if self._hovered_row == "zoom" or self._pressed_row == "zoom"
                else Palette.TEXT_MUTED
            )
        )
        painter.drawText(
            int(zoom_x),
            self.row_h,
            self.zoom_w,
            self.row_h,
            Qt.AlignmentFlag.AlignCenter,
            f"ZOOM: {self.zoom_pct}",
        )
        painter.setPen(
            QColor(
                Palette.TEXT_ACCENT
                if self._hovered_row == "stats" or self._pressed_row == "stats"
                else Palette.TEXT_MUTED
            )
        )
        painter.drawText(
            int(stats_x),
            self.row_h * 2,
            self.stats_w,
            self.row_h,
            Qt.AlignmentFlag.AlignCenter,
            self.stats_text,
        )
