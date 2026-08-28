import os
import sys

from .core.constants import MEDIA_CHUNK_SIZE
from .gui.theme import Theme

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


class AppConfig:

    APP_NAME = "ZeroXX-KryptoNote"
    VERSION = "3.10.2"
    COMPANY_NAME = "ZeroXWare"

    CHUNK_SIZE = MEDIA_CHUNK_SIZE

    # Path logic
    IS_FROZEN = getattr(sys, "frozen", False)
    BASE_DIR = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    DB_PATH = os.path.join(BASE_DIR, "cases")
    ICON_PATH = os.path.join(CURRENT_DIR, "gui", "assets", "icon.png")

    # Grid geometry
    GRID_SIZE_MAIN = 500
    GRID_SIZE = 100

    # Node defaults
    NODE_DEFAULT_WIDTH = 200
    NODE_DEFAULT_HEIGHT = 150
    NODE_MEDIA_SIZE = 220
    NODE_AUDIO_WIDTH = 360
    NODE_AUDIO_HEIGHT = 108
    FRAME_DEFAULT_WIDTH = 600
    FRAME_DEFAULT_HEIGHT = 400
    FRAME_DEFAULT_OPACITY = 0.21

    LOD_TEXT_HIDE_THRESHOLD = 0.22


class RuntimeState:
    SNAP_TO_GRID = False


class _ThemeColors:
    GRID_COLOR = Theme.Palette.GRID_SUB
    GRID_COLOR_MAIN = Theme.Palette.GRID_MAIN
    BACKGROUND_COLOR = Theme.Palette.BG_CANVAS

    COLOR_NODE_BG = Theme.Palette.BG_NODE
    COLOR_TEXT_TITLE = Theme.Palette.TEXT_MAIN
    COLOR_TEXT_BODY = Theme.Palette.TEXT_DIM
    COLOR_ACCENT = Theme.Palette.ACCENT_MAIN
    COLOR_SECURE_LABEL = Theme.Palette.GREEN_SECURE
    COLOR_LINK_LINE = Theme.Palette.BORDER_DEFAULT
    COLOR_LINK_HIGHLIGHT = Theme.Palette.ACCENT_MAIN


class Config(AppConfig, RuntimeState, _ThemeColors):
    pass
