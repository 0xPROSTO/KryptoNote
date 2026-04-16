import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
from KryptoNote.gui.theme import Theme


class Config:
    APP_NAME = "ZeroXX-KryptoNote"
    VERSION = "1.2.3"

    CHUNK_SIZE = 4 * 1024 * 1024

    if getattr(sys, "frozen", False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    DB_PATH = "cases/"
    ICON_PATH = os.path.join(CURRENT_DIR, "gui", "assets", "icon.png")

    GRID_SIZE_MAIN = 500
    GRID_SIZE = 100
    GRID_COLOR = "#1a1a1a"
    GRID_COLOR_MAIN = "#252525"
    BACKGROUND_COLOR = Theme.Palette.BG_CANVAS

    NODE_DEFAULT_WIDTH = 200
    NODE_DEFAULT_HEIGHT = 150
    NODE_MEDIA_SIZE = 220
    SNAP_TO_GRID = False

    COLOR_NODE_BG = Theme.Palette.BG_NODE
    COLOR_TEXT_TITLE = Theme.Palette.TEXT_MAIN
    COLOR_TEXT_BODY = Theme.Palette.TEXT_DIM
    COLOR_ACCENT = Theme.Palette.ACCENT_MAIN
    COLOR_SECURE_LABEL = "#00FF00"
    COLOR_LINK_LINE = Theme.Palette.BORDER_DEFAULT
    COLOR_LINK_HIGHLIGHT = Theme.Palette.ACCENT_MAIN

    STYLE_MAIN_WINDOW = Theme.Styles.get_main_window_qss()
    STYLE_LAUNCHER = Theme.Styles.get_launcher_qss()

    STYLE_PLAYER = f"""
        QDialog {{ background-color: {Theme.Palette.BG_CANVAS}; }} 
        QWidget {{ color: {Theme.Palette.TEXT_MAIN}; }} 
        QSlider::groove:horizontal {{ border: 1px solid {Theme.Palette.BORDER_DEFAULT}; height: 4px; background: {Theme.Palette.BG_INPUT}; margin: 0px; border-radius: 2px; }} 
        QSlider::sub-page:horizontal {{ background: {Theme.Palette.ACCENT_LOW}; border-radius: 2px; }} 
        QSlider::handle:horizontal {{ background: {Theme.Palette.TEXT_MAIN}; border: 1px solid {Theme.Palette.BORDER_DEFAULT}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }} 
        QSlider::handle:horizontal:hover {{ background: {Theme.Palette.ACCENT_HIGH}; }} 
        QLabel {{ font-family: {Theme.Typography.FONT_BODY}, sans-serif; font-size: 12px; color: {Theme.Palette.TEXT_DIM}; }} 
    """
