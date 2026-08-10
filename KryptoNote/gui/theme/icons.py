from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor, QIcon
from PySide6.QtSvg import QSvgRenderer

from .palette import Palette


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


class VectorIcons:
    """Backward-compatible adapter for the legacy widget player."""

    @staticmethod
    def get_icon(icon_type: str, color=Qt.GlobalColor.white) -> QIcon:
        resolved_color = QColor(color).name()
        return SvgIcons.get_icon(
            icon_type,
            color=resolved_color,
            active_color=resolved_color,
            disabled_color=resolved_color,
        )
