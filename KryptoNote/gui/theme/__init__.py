from .palette import Palette
from .style_factory import StyleFactory
from .typography import Typography


class Theme:
    Palette = Palette
    Typography = Typography
    Styles = StyleFactory
    RADIUS = 4
    BORDER_WIDTH = 1.1

    @staticmethod
    def apply_to(widget, style_func):
        qss = style_func() if callable(style_func) else ""
        widget.setStyleSheet(qss)
