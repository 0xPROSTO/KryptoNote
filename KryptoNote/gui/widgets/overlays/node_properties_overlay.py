from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGridLayout,
)

from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.widgets.overlays.dim_overlay import DimOverlay


class NodePropertiesOverlay(DimOverlay):
    """Modal overlay displaying node metadata over the canvas.

    Reuses DimOverlay for background dimming and input blocking.
    """

    def __init__(self, metadata_lines, parent=None):
        super().__init__(parent, block_input=True, auto_show=False)
        self.setObjectName("node_props_overlay")

        # Inherited from DimOverlay: geometry, event filter, fade animation.

        # ── Card ──
        card = QFrame(self)
        card.setObjectName("props_card")
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame#props_card {{
                background-color: {Palette.BG_PANEL};
                border: 1px solid {Palette.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            QLabel#props_title {{
                color: {Palette.ACCENT_MAIN};
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI Semibold';
                background: transparent;
            }}
            QLabel#props_key {{
                color: {Palette.TEXT_DIM};
                font-size: 11px;
                font-weight: bold;
                font-family: 'Segoe UI';
                background: transparent;
            }}
            QLabel#props_value {{
                color: {Palette.TEXT_MAIN};
                font-size: 12px;
                font-family: 'Segoe UI';
                background: transparent;
            }}
            QFrame#props_separator {{
                background-color: {Palette.BORDER_DEFAULT};
                border: none;
                max-height: 1px;
            }}
            QPushButton#btn_close {{
                background-color: {Palette.BG_NODE};
                color: {Palette.TEXT_MAIN};
                border: 1px solid {Palette.BORDER_DEFAULT};
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton#btn_close:hover {{
                border-color: {Palette.ACCENT_MAIN};
                background-color: {Palette.BORDER_HOVER};
            }}
        """)
        self._card = card

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        # Title
        title = QLabel("NODE PROPERTIES")
        title.setObjectName("props_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setObjectName("props_separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Properties grid
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        for row_idx, line in enumerate(metadata_lines):
            if ":" in line:
                key, value = line.split(":", 1)
                key_label = QLabel(key.strip())
                key_label.setObjectName("props_key")
                val_label = QLabel(value.strip())
                val_label.setObjectName("props_value")
                val_label.setWordWrap(True)
                val_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                grid.addWidget(key_label, row_idx, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(val_label, row_idx, 1, Qt.AlignmentFlag.AlignTop)
            else:
                full_label = QLabel(line)
                full_label.setObjectName("props_value")
                full_label.setWordWrap(True)
                grid.addWidget(full_label, row_idx, 0, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

        # Close button
        btn_close = QPushButton("CLOSE")
        btn_close.setObjectName("btn_close")
        btn_close.clicked.connect(self._on_close)
        layout.addWidget(btn_close)

        self._center_card()

        self.show()
        self.raise_()
        self.fade_in()

        self.setFocus()

    # ── Actions ──

    def _on_close(self):
        self.fade_out()

    def mousePressEvent(self, event):
        event.accept()

    def _center_card(self):
        if not hasattr(self, '_card'):
            return
        if self.parent():
            px = (self.width() - self._card.width()) // 2
            py = (self.height() - self._card.height()) // 2
            self._card.move(px, py)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_card()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)
