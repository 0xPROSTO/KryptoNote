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
