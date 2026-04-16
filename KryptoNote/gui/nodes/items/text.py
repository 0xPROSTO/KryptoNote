from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
from .base import BaseNode


class TextNode(BaseNode):
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
        self.title_item.setPos(12, 8)
        self.body_item = QGraphicsTextItem(parent=self)
        self.body_item.setPlainText(self.text_content)
        self.body_item.setDefaultTextColor(QColor(Theme.Palette.TEXT_MAIN))
        self.body_item.setFont(QFont(Theme.Typography.FONT_BODY, self.text_size))
        self.body_item.document().setMarkdown(self._process_markdown_text(self.text_content))
        self.body_item.setPos(12, 35)
        self.update_content_layout()

    def update_content_layout(self):
        target_width = self.rect().width() - 24
        self.title_item.setTextWidth(target_width)
        self.body_item.setTextWidth(target_width)

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
            self.body_item.document().setMarkdown(self._process_markdown_text(self.text_content))

            self.service.update_text_content(
                self.item_id, self.title, self.text_content, self.title_size, self.text_size
            )

    def _process_markdown_text(self, text):
        if not text:
            return ""
        lines = text.split('\n')
        processed = []
        in_code_block = False
        for line in lines:
            stripped = line.rstrip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                processed.append(line)
            elif in_code_block:
                processed.append(line)
            else:
                if stripped:
                    processed.append(stripped + "  ")
                else:
                    processed.append("")
        return '\n'.join(processed)

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))
