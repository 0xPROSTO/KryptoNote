from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class AboutDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.support_requested = False

        self.configure_dialog_chrome("About")

        self.setFixedSize(306, 504)
        self.setStyleSheet(Theme.Styles.get_about_dialog_qss())

        self.init_ui()
        self._setup_window_drag(drag_handles=[self.container])

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

        self.github_button = self._link_button("GitHub Repository")
        self.github_button.clicked.connect(self._open_github)

        self.support_button = self._link_button("Support the author")
        self.support_button.clicked.connect(self._request_support)

        actions = QWidget()
        actions.setObjectName("about_actions")
        actions_layout = QGridLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setHorizontalSpacing(8)
        actions_layout.setVerticalSpacing(0)
        actions_layout.setColumnStretch(0, 1)
        actions_layout.setColumnStretch(2, 1)
        actions_layout.addWidget(
            self.github_button,
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        separator = QLabel("|")
        separator.setObjectName("about_action_separator")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions_layout.addWidget(separator, 0, 1)
        actions_layout.addWidget(
            self.support_button,
            0,
            2,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        content_layout.addWidget(actions)
        content_layout.addStretch()

        self.desc_label = QLabel("Secure Management System\nbased on interactive graph")
        self.desc_label.setObjectName("desc_label")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.desc_label)

        container_layout.addWidget(content, 1)
        main_layout.addWidget(self.container)

    @staticmethod
    def _link_button(text):
        button = QPushButton(text)
        button.setObjectName("about_action_link")
        button.setFlat(True)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        button.setAccessibleName(text)
        return button

    def _open_github(self):
        QDesktopServices.openUrl(QUrl("https://github.com/0xPROSTO/KryptoNote"))

    def _request_support(self):
        self.support_requested = True
        self.accept()


class SupportDialog(FramelessWindowDragMixin, QDialog):
    SUPPORT_WALLETS = (
        (
            "TRON",
            "USDT-TRX20/TRX",
            "TRiQ9vhum5Md7E4HAtUUojqP43xBBGfWST",
        ),
        (
            "TON",
            "GRAM",
            "UQBz3dYE2PN7BscpPM2AEYrvmzPbFPeduryBIt20hXYJHw61",
        ),
        (
            "BTC",
            "",
            "bc1q7f7ad3r9hxa6qtwps734zmngtc72ta37f77sx8",
        ),
        (
            "ETH",
            "",
            "0x5feEa3504a81899E908d55e5C13661f91382C278",
        ),
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        self.configure_dialog_chrome("Support")
        self.setFixedSize(560, 466)
        self.setStyleSheet(Theme.Styles.get_about_dialog_qss())

        self._copy_buttons = []
        self.init_ui()
        self._setup_window_drag(drag_handles=[self.container])

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
        header_layout.setContentsMargins(8, 8, 8, 0)
        header_layout.setSpacing(0)

        title_spacer = QWidget()
        title_spacer.setFixedWidth(40)
        header_layout.addWidget(title_spacer)

        title = QLabel("Support the author")
        title.setObjectName("support_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title, 1)

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
        content_layout.setContentsMargins(22, 4, 22, 18)
        content_layout.setSpacing(12)

        intro = QLabel(
            "If KryptoNote is useful to you, you can support its development "
            "with cryptocurrency."
        )
        intro.setObjectName("support_intro")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(intro)

        for network, asset, address in self.SUPPORT_WALLETS:
            content_layout.addWidget(self._wallet_card(network, asset, address))

        container_layout.addWidget(content, 1)
        main_layout.addWidget(self.container)

    def _wallet_card(self, network, asset, address):
        card = QFrame()
        card.setObjectName("wallet_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 10)
        card_layout.setSpacing(6)

        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(7)

        network_label = QLabel(network)
        network_label.setObjectName("wallet_network")
        heading_layout.addWidget(network_label)
        if asset:
            asset_label = QLabel(f"({asset})")
            asset_label.setObjectName("wallet_asset")
            heading_layout.addWidget(asset_label)
        heading_layout.addStretch()
        card_layout.addLayout(heading_layout)

        address_layout = QHBoxLayout()
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(8)

        address_field = QLineEdit(address)
        address_field.setObjectName("wallet_address")
        address_field.setReadOnly(True)
        address_field.setCursorPosition(0)
        address_field.setAccessibleName(f"{network} address")
        address_layout.addWidget(address_field, 1)

        copy_button = QPushButton("Copy")
        copy_button.setObjectName("wallet_copy")
        copy_button.setAutoDefault(False)
        copy_button.setAccessibleName(f"Copy {network} address")
        copy_button.clicked.connect(
            lambda _checked=False, button=copy_button, value=address: self._copy_address(
                button, value
            )
        )
        self._copy_buttons.append(copy_button)
        address_layout.addWidget(copy_button)
        card_layout.addLayout(address_layout)
        return card

    def _copy_address(self, active_button, address):
        QGuiApplication.clipboard().setText(address)
        for button in self._copy_buttons:
            button.setText("Copy")
        active_button.setText("Copied")
