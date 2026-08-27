from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class AboutDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.configure_dialog_chrome("About")

        self.setFixedSize(306, 504)
        self.setStyleSheet(Theme.Styles.get_about_dialog_qss())

        self.init_ui()
        self._setup_window_drag(drag_handles=[self.container])

    def _window_drag_is_interactive(self, watched):
        if watched is self.github_link:
            return True
        return super()._window_drag_is_interactive(watched)

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

        self.btn_close = DialogCloseButton()
        self.btn_close.setIconSize(QSize(18, 18))
        self.btn_close.setToolTip("Close")
        self.btn_close.setAccessibleName("Close")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(40, 40)
        self.btn_close.clicked.connect(self.close)
        header_layout.addWidget(self.btn_close)

        container_layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 0, 10, 10)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(10)

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
            '<a href="https://github.com/0xPROSTO/KryptoNote" '
            f'style="color: {Theme.Palette.ACCENT_MAIN}; '
            'text-decoration: none;">GitHub Repository</a>'
        )
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
