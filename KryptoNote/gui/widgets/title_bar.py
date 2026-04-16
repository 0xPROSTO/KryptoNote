from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QMenuBar,
    QGridLayout,
)

from KryptoNote.config import Config


class TitleBarButton(QPushButton):
    def __init__(self, icon_text, hover_color="#3a3a3a", parent=None):
        super().__init__(icon_text, parent)
        self._hover_color = hover_color
        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{ 
                background: transparent;
                color: #aaaaaa;
                border: none;
                font-family: 'Segoe MDL2 Assets', 'Segoe UI Symbol';
                font-size: 10px;
            }} 
            QPushButton:hover {{ 
                background-color: {self._hover_color};
                color: #ffffff;
            }} 
        """)


class CustomTitleBar(QWidget):
    TITLE_BAR_HEIGHT = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.TITLE_BAR_HEIGHT)
        self.setAutoFillBackground(True)

        self.setStyleSheet("""
            CustomTitleBar {
                background-color: #181818;
                border-bottom: 1px solid #2a2a2a;
            }
        """)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_widget = QWidget()
        self.left_layout = QHBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        self.icon_label = QLabel()
        pixmap = QPixmap(Config.ICON_PATH)
        if not pixmap.isNull():
            self.icon_label.setPixmap(
                pixmap.scaled(
                    20,
                    20,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self.icon_label.setFixedSize(36, self.TITLE_BAR_HEIGHT)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_layout.addWidget(self.icon_label)

        self.menu_bar = QMenuBar()
        self.menu_bar.setFixedHeight(self.TITLE_BAR_HEIGHT)
        self.menu_bar.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background: transparent;
                color: #cccccc;
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                margin: 0;
                padding: 0;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 15px;
                margin: 0;
            }
            QMenuBar::item:selected {
                background-color: #333333;
                color: #ffffff;
            }
            QMenu {
                background-color: #1e1e1e;
                color: #dddddd;
                border: 1px solid #333;
                font-size: 13px;
                margin-top: 0;
            }
            QMenu::item {
                padding: 8px 32px;
            }
            QMenu::item:selected {
                background-color: #3b3b3b;
            }
            QMenu::separator {
                height: 1px;
                background: #333;
                margin: 4px 0;
            }
        """)
        self.left_layout.addWidget(self.menu_bar)
        layout.addWidget(self.left_widget, 0, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("""
            color: #888888;
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label, 0, 1, Qt.AlignmentFlag.AlignCenter)

        self.right_widget = QWidget()
        self.right_layout = QHBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        self.btn_minimize = TitleBarButton("\u2500")
        self.btn_maximize = TitleBarButton("\u25a1")
        self.btn_close = TitleBarButton("\u2715", hover_color="#c42b1c")

        self.btn_minimize.clicked.connect(self._on_minimize)
        self.btn_maximize.clicked.connect(self._on_maximize)
        self.btn_close.clicked.connect(self._on_close)

        self.right_layout.addWidget(self.btn_minimize)
        self.right_layout.addWidget(self.btn_maximize)
        self.right_layout.addWidget(self.btn_close)

        layout.addWidget(self.right_widget, 0, 2, Qt.AlignmentFlag.AlignRight)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 1)

    def set_title(self, text: str):
        self.title_label.setText(text)

    def _on_minimize(self):
        self.window().showMinimized()

    def _on_maximize(self):
        if self.window().isMaximized():
            self.window().showNormal()

        else:
            self.window().showMaximized()

    def _on_close(self):
        self.window().close()

    def mouseDoubleClickEvent(self, event):
        self._on_maximize()
        super().mouseDoubleClickEvent(event)
