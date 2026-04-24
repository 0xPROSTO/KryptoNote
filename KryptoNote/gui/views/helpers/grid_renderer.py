from PySide6.QtCore import Qt, QLineF
from PySide6.QtGui import QPainter, QColor, QPen

from ....config import Config


class GridRenderer:
    @staticmethod
    def draw_grid(view, painter, rect):
        painter.save()

        fill_rect = rect.adjusted(-5, -5, 5, 5)
        painter.fillRect(fill_rect, QColor(Config.BACKGROUND_COLOR))
        scale = view.transform().m11()
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
        # Clip lines to visible rect with small margin instead of 2M pixel lines
        y_lo = top - 10
        y_hi = bottom + 10
        x_lo = left - 10
        x_hi = right + 10

        for x in range(left_grid, right + grid_size, grid_size):
            if x % grid_main == 0:
                lines_main.append(QLineF(x, y_lo, x, y_hi))
            elif scale >= 0.5:
                lines.append(QLineF(x, y_lo, x, y_hi))

        for y in range(top_grid, bottom + grid_size, grid_size):
            if y % grid_main == 0:
                lines_main.append(QLineF(x_lo, y, x_hi, y))
            elif scale >= 0.5:
                lines.append(QLineF(x_lo, y, x_hi, y))

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
