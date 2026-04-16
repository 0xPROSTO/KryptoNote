from PySide6.QtGui import QFont


class Typography:
    FONT_DISPLAY = "Segoe UI Semibold"
    FONT_BODY = "Segoe UI"
    FONT_MONO = "Consolas"
    SIZE_H1 = 14
    SIZE_H2 = 12
    SIZE_BODY = 10
    SIZE_SMALL = 9

    @staticmethod
    def get_font(size_key="SIZE_BODY", bold=False, italic=False, mono=False):
        font = QFont(Typography.FONT_MONO if mono else Typography.FONT_BODY)
        size = getattr(Typography, size_key, Typography.SIZE_BODY)
        font.setPointSize(size)
        font.setBold(bold)
        font.setItalic(italic)
        if size_key == "SIZE_H1" or size_key == "SIZE_H2":
            font.setFamily(Typography.FONT_DISPLAY)

        return font
