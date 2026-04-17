from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(306, 504)
        self.setStyleSheet(Theme.Styles.get_about_dialog_qss())

        self._dragging = False
        self._drag_start_pos = QPoint()

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.container.setObjectName("about_container")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 5, 5, 0)
        header_layout.addStretch()

        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(40, 40)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)
        header_layout.addWidget(self.btn_close)

        container_layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 0, 10, 10)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(10)

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setObjectName("logo_label")
        pixmap = QPixmap(Config.ICON_PATH)
        if not pixmap.isNull():
            self.logo_label.setPixmap(pixmap.scaledToWidth(
                200,
                Qt.TransformationMode.SmoothTransformation
            ))
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.logo_label)

        # Metas
        self.app_name_label = QLabel(Config.APP_NAME)
        self.app_name_label.setObjectName("app_name")
        self.app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.app_name_label)

        self.author_label = QLabel("Created by ZeroX")
        self.author_label.setObjectName("author_label")
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.author_label)

        self.version_label = QLabel(f"Version {Config.VERSION}")
        self.version_label.setObjectName("version_label")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.version_label)

        self.github_link = QLabel(
            '<a href="https://github.com/0xPROSTO/KryptoNote" style="color: #e6158b; text-decoration: none;">GitHub Repository</a>')
        self.github_link.setObjectName("github_link")
        self.github_link.setOpenExternalLinks(True)
        self.github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.github_link)

        content_layout.addStretch()

        self.desc_label = QLabel("Secure Management System\nbased on interactive graph")
        self.desc_label.setObjectName("desc_label")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.desc_label)

        container_layout.addWidget(content, 1)
        main_layout.addWidget(self.container)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(diff)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
