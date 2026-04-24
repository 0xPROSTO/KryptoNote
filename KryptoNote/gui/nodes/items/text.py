from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
from KryptoNote.utils.text_utils import process_markdown_for_pyside
from .base import BaseNode


class TextNode(BaseNode):
    TITLE_PADDING_TOP = 8
    TITLE_BODY_GAP = 6
    CONTENT_MARGIN = 12

    def __init__(self, item_id, x, y, w, h, title, text, service, title_size=14, text_size=10):
        super().__init__(item_id, x, y, w, h, service)
        self.title = title
        self.text_content = text if text else ""
        self.title_size = title_size
        self.text_size = text_size
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

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse():
            return
        dialog = NoteEditorDialog(self.title, self.text_content, self.title_size, self.text_size)
        if dialog.exec():
            new_title, new_text, new_title_size, new_text_size = dialog.get_data()

            self.title = new_title.strip() or "Untitled"
            self.text_content = new_text
            self.title_size = new_title_size
            self.text_size = new_text_size

            self.title_item.setPlainText(self.title)
            self.title_item.setFont(QFont(Theme.Typography.FONT_DISPLAY, self.title_size, QFont.Weight.Bold))

            self.body_item.setFont(QFont(Theme.Typography.FONT_BODY, self.text_size))
            self.body_item.document().setMarkdown(process_markdown_for_pyside(self.text_content))

            self.update_content_layout()

            self.service.update_text_content(
                self.item_id, self.title, self.text_content, self.title_size, self.text_size
            )

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))
