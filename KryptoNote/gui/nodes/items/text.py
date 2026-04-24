from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.gui.theme import Theme
from KryptoNote.utils.text_utils import process_markdown_for_pyside
from .base import BaseNode


class TextNode(BaseNode):
    TITLE_PADDING_TOP = 8
    TITLE_BODY_GAP = 6
    CONTENT_MARGIN = 12

    MIN_WIDTH = 120
    MAX_WIDTH = 500
    MIN_HEIGHT = 60
    MAX_HEIGHT = 800
    IDEAL_CHARS_PER_LINE = 50
    BOTTOM_PADDING = 20

    def __init__(self, item_id, x, y, w, h, title, text, service, title_size=14, text_size=10):
        super().__init__(item_id, x, y, w, h, service)
        self.title = title
        self.text_content = text if text else ""
        self.title_size = title_size
        self.text_size = text_size
        self._auto_fit_pending = False

        self.title_item = QGraphicsTextItem(self.title, self)
        self.title_item.setDefaultTextColor(
            QColor(
                Theme.Palette.ACCENT_HIGHLIGHT
                if hasattr(Theme.Palette, "ACCENT_HIGHLIGHT")
                else Theme.Palette.ACCENT_MAIN
            )
        )
        self.title_item.setFont(QFont(Theme.Typography.FONT_DISPLAY, self.title_size, QFont.Weight.Bold))
        self.title_item.setPos(self.CONTENT_MARGIN, self.TITLE_PADDING_TOP)
        self.body_item = QGraphicsTextItem(parent=self)
        self.body_item.setPlainText(self.text_content)
        self.body_item.setDefaultTextColor(QColor(Theme.Palette.TEXT_MAIN))
        self.body_item.setFont(QFont(Theme.Typography.FONT_BODY, self.text_size))
        self.body_item.document().setMarkdown(process_markdown_for_pyside(self.text_content))

        self.update_content_layout()

    def _calc_body_y(self):
        if self.title:
            title_height = self.title_item.boundingRect().height()
            return self.TITLE_PADDING_TOP + title_height + self.TITLE_BODY_GAP
        return self.TITLE_PADDING_TOP

    def update_content_layout(self):
        target_width = self.rect().width() - self.CONTENT_MARGIN * 2
        self.title_item.setTextWidth(target_width)
        self.body_item.setTextWidth(target_width)
        self.body_item.setPos(self.CONTENT_MARGIN, self._calc_body_y())
        self.dispatch_event("layout_changed")

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse():
            return
        self.dispatch_event("double_click", event=event)

    def extend_context_menu(self, menu):
        self.dispatch_event("extend_context_menu", menu=menu)
