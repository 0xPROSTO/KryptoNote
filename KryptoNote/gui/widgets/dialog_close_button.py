"""State-aware close button shared by custom application dialogs."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QPushButton

from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.theme.palette import Palette


class DialogCloseButton(QPushButton):
    """Keep the close glyph aligned with hover, focus and disabled state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._keyboard_focused = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pressed.connect(self.refresh_icon)
        self.released.connect(self.refresh_icon)
        self.refresh_icon()

    def refresh_icon(self):
        if not self.isEnabled():
            color = Palette.TEXT_DISABLED
        elif self.isDown():
            color = Palette.ACCENT_HOVER
        elif self._hovered or self._keyboard_focused:
            color = Palette.ACCENT_MAIN
        else:
            color = Palette.TEXT_MUTED

        self.setIcon(
            SvgIcons.get_icon(
                "close",
                color=color,
                active_color=color,
                disabled_color=color,
            )
        )

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)
        self.refresh_icon()

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)
        self.refresh_icon()

    def focusInEvent(self, event):
        self._keyboard_focused = event.reason() in {
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        }
        super().focusInEvent(event)
        self.refresh_icon()

    def focusOutEvent(self, event):
        self._keyboard_focused = False
        super().focusOutEvent(event)
        self.refresh_icon()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {
            QEvent.Type.EnabledChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        }:
            self.refresh_icon()
