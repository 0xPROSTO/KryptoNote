import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    # System
    APP_NAME = "ZeroXX-KryptoNote"
    VERSION = "1.2.0"
    CHUNK_SIZE = 4 * 1024 * 1024
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = "cases/"
    ICON_PATH = os.path.join(CURRENT_DIR, "gui", "assets", "icon.png")

    # Visuals
    GRID_SIZE = 100
    GRID_COLOR = "#3c3c3c"
    BACKGROUND_COLOR = "#121212"

    # Nodes
    NODE_DEFAULT_WIDTH = 200
    NODE_DEFAULT_HEIGHT = 150
    NODE_MEDIA_SIZE = 220
    SNAP_TO_GRID = False

    # Colors
    COLOR_NODE_BG = "#2d2d2d"
    COLOR_TEXT_TITLE = "#e0e0e0"
    COLOR_TEXT_BODY = "#eeeeee"
    COLOR_ACCENT = "#ffaa00"
    COLOR_SECURE_LABEL = "#00FF00"
    COLOR_LINK_LINE = "#ff4444"

    STYLE_MAIN_WINDOW = """
        QToolBar { background: #1e1e1e; border-bottom: 1px solid #333; } 
        QToolButton { color: #ddd; }
        QStatusBar { background: #1e1e1e; color: #777; }
    """

    STYLE_LAUNCHER = """
        QDialog { background-color: #1e1e1e; color: white; }
        QListWidget { background-color: #252525; color: #ddd; border: 1px solid #333; font-size: 14px; }
        QListWidget::item { padding: 5px; }
        QListWidget::item:selected { background-color: #3d3d3d; }
        QLineEdit { background-color: #252525; color: white; border: 1px solid #333; padding: 5px; }
        QPushButton { background-color: #333; color: white; border: none; padding: 8px; }
        QPushButton:hover { background-color: #444; }
        QLabel { color: #aaa; }
    """

    STYLE_PLAYER = """
        QDialog { background-color: #000; }
        QWidget { color: white; }
        QSlider::groove:horizontal { border: 1px solid #333; height: 4px; background: #333; margin: 0px; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #666; border-radius: 2px; }
        QSlider::handle:horizontal { background: #ddd; border: 1px solid #ccc; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        QSlider::handle:horizontal:hover { background: #fff; }
        QLabel { font-family: Segoe UI, sans-serif; font-size: 12px; color: #ccc; }
    """