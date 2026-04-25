import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
from KryptoNote.gui.theme import Theme


class Config:
    APP_NAME = "ZeroXX-KryptoNote"
    VERSION = "2.3.10"
    COMPANY_NAME = "ZeroXWare"

    CHUNK_SIZE = 4 * 1024 * 1024

    # Path logic
    IS_FROZEN = getattr(sys, "frozen", False)
    BASE_DIR = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    DB_PATH = "cases/"
    ICON_PATH = os.path.join(CURRENT_DIR, "gui", "assets", "icon.png")

    GRID_SIZE_MAIN = 500
    GRID_SIZE = 100
    GRID_COLOR = Theme.Palette.GRID_SUB
    GRID_COLOR_MAIN = Theme.Palette.GRID_MAIN
    BACKGROUND_COLOR = Theme.Palette.BG_CANVAS

    NODE_DEFAULT_WIDTH = 200
    NODE_DEFAULT_HEIGHT = 150
    NODE_MEDIA_SIZE = 220
    SNAP_TO_GRID = False

    LOD_TEXT_HIDE_THRESHOLD = 0.22

    COLOR_NODE_BG = Theme.Palette.BG_NODE
    COLOR_TEXT_TITLE = Theme.Palette.TEXT_MAIN
    COLOR_TEXT_BODY = Theme.Palette.TEXT_DIM
    COLOR_ACCENT = Theme.Palette.ACCENT_MAIN
    COLOR_SECURE_LABEL = Theme.Palette.GREEN_SECURE
    COLOR_LINK_LINE = Theme.Palette.BORDER_DEFAULT
    COLOR_LINK_HIGHLIGHT = Theme.Palette.ACCENT_MAIN
