from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor, QPainterPath, QIcon
from PySide6.QtSvg import QSvgRenderer

from .palette import Palette


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


class SvgIcons:
    """Loads the shared SVG set with Qt Widget state-aware colors."""

    _ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
    _LOGICAL_SIZE = 24
    _DEVICE_RATIO = 2.0

    @classmethod
    def path(cls, name: str) -> Path:
        safe_name = Path(name).name
        if not safe_name.endswith(".svg"):
            safe_name += ".svg"
        return cls._ICON_DIR / safe_name

    @classmethod
    def get_icon(
        cls,
        name: str,
        color: str | None = None,
        active_color: str | None = None,
        disabled_color: str | None = None,
    ) -> QIcon:
        return cls._get_icon_cached(
            name,
            color or Palette.TEXT_DIM,
            active_color or Palette.ACCENT_MAIN,
            disabled_color or Palette.TEXT_DISABLED,
        )

    @classmethod
    @lru_cache(maxsize=96)
    def _get_icon_cached(
        cls,
        name: str,
        color: str,
        active_color: str,
        disabled_color: str,
    ) -> QIcon:
        source = cls.path(name)
        if not source.is_file():
            return QIcon()

        icon = QIcon()
        states = (
            (QIcon.Mode.Normal, color),
            (QIcon.Mode.Active, active_color),
            (QIcon.Mode.Selected, active_color),
            (QIcon.Mode.Disabled, disabled_color),
        )
        for mode, state_color in states:
            pixmap = cls._render(source, state_color)
            if not pixmap.isNull():
                icon.addPixmap(pixmap, mode, QIcon.State.Off)
        return icon

    @classmethod
    def clear_cache(cls):
        cls._get_icon_cached.cache_clear()

    @classmethod
    def _render(cls, source: Path, color: str) -> QPixmap:
        svg = source.read_text(encoding="utf-8")
        svg = svg.replace("#ffffff", QColor(color).name())
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if not renderer.isValid():
            return QPixmap()

        pixel_size = round(cls._LOGICAL_SIZE * cls._DEVICE_RATIO)
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(cls._DEVICE_RATIO)
        painter = QPainter(pixmap)
        renderer.render(
            painter,
            QRectF(0, 0, cls._LOGICAL_SIZE, cls._LOGICAL_SIZE),
        )
        painter.end()
        return pixmap
