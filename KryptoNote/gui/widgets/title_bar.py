from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
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
from KryptoNote.gui.theme import Theme


class TitleBarButton(QPushButton):
    _LABELS = {
        "min": "Minimize",
        "max": "Maximize",
        "close": "Close",
    }

    def __init__(self, btn_type, hover_color=None, parent=None):
        super().__init__("", parent)
        self._btn_type = btn_type  # 'min', 'max', 'close'
        self._hover_color = hover_color or Theme.Palette.BTN_HOVER_DEFAULT
        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._sync_accessibility()
        self._apply_style()

    def _apply_style(self):
        pressed_color = (
            Theme.Palette.ACCENT_HOVER
            if self._btn_type == "close"
            else Theme.Palette.BG_CONTROL_PRESSED
        )
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
            }}
            QPushButton:hover {{
                background-color: {self._hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
            QPushButton:focus {{
                border-color: {Theme.Palette.ACCENT_MAIN};
            }}
        """)

    def set_hover_color(self, color):
        self._hover_color = color
        self._apply_style()
        self.update()

    def _sync_accessibility(self):
        label = self._LABELS[self._btn_type]
        if self._btn_type == "max" and self.window().isMaximized():
            label = "Restore"
        self.setAccessibleName(label)
        self.setToolTip(label)

    def sync_window_state(self):
        self._sync_accessibility()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_hovered = self.underMouse()
        color = Theme.Palette.TEXT_MAIN if is_hovered else Theme.Palette.TEXT_DIM

        pen = QPen(QColor(color))
        pen.setWidthF(1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self._btn_type == 'min':
            painter.drawLine(cx - 5, cy, cx + 5, cy)
        elif self._btn_type == 'max':
            if self.window().isMaximized():
                painter.drawRect(QRectF(cx - 3, cy - 5, 8, 8))
                painter.drawRect(QRectF(cx - 5, cy - 3, 8, 8))
            else:
                rect = QRectF(cx - 5, cy - 5, 10, 10)
                painter.drawRoundedRect(rect, 2.8, 2.8)
        elif self._btn_type == 'close':
            s = 5.0 # Total span 10px
            painter.drawLine(cx - s, cy - s, cx + s, cy + s)
            painter.drawLine(cx + s, cy - s, cx - s, cy + s)


class CustomTitleBar(QWidget):
    TITLE_BAR_HEIGHT = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.TITLE_BAR_HEIGHT)
        self.setAutoFillBackground(True)
        self.setObjectName("CustomTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(Theme.Styles.get_title_bar_qss())

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_widget = QWidget()
        self.left_layout = QHBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(12, 0, 0, 0)
        self.left_layout.setSpacing(0)

        self.icon_label = QLabel()
        pixmap = QPixmap(Config.ICON_PATH)
        if not pixmap.isNull():
            self.icon_label.setPixmap(
                pixmap.scaled(
                    22,
                    22,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self.icon_label.setFixedSize(40, self.TITLE_BAR_HEIGHT)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_layout.addWidget(self.icon_label)

        self.menu_bar = QMenuBar()
        self.menu_bar.setFixedHeight(self.TITLE_BAR_HEIGHT)
        self.menu_bar.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )
        self.left_layout.addWidget(self.menu_bar)
        layout.addWidget(self.left_widget, 0, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel("")
        self.title_label.setObjectName("window_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label, 0, 1, Qt.AlignmentFlag.AlignCenter)

        self.right_widget = QWidget()
        self.right_layout = QHBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        self.btn_minimize = TitleBarButton('min', hover_color=Theme.Palette.BTN_HOVER_DEFAULT)
        self.btn_maximize = TitleBarButton('max', hover_color=Theme.Palette.BTN_HOVER_DEFAULT)
        self.btn_close = TitleBarButton('close', hover_color=Theme.Palette.ACCENT_MAIN)

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

    def refresh_theme(self):
        self.setStyleSheet(Theme.Styles.get_title_bar_qss())
        self.btn_minimize.set_hover_color(Theme.Palette.BTN_HOVER_DEFAULT)
        self.btn_maximize.set_hover_color(Theme.Palette.BTN_HOVER_DEFAULT)
        self.btn_close.set_hover_color(Theme.Palette.ACCENT_MAIN)
        self.update()

    def sync_window_state(self):
        self.btn_maximize.sync_window_state()

    def _on_minimize(self):
        self.window().showMinimized()

    def _on_maximize(self):
        if self.window().isMaximized():
            self.window().showNormal()

        else:
            self.window().showMaximized()
        self.sync_window_state()

    def _on_close(self):
        self.window().close()

    def mouseDoubleClickEvent(self, event):
        self._on_maximize()
        super().mouseDoubleClickEvent(event)
