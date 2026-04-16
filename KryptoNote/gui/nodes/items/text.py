from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
from .base import BaseNode


class TextNode(BaseNode):
    def __init__(self, item_id, x, y, w, h, title, text, service):
        super().__init__(item_id, x, y, w, h, service)
        self.title = title
        self.text_content = text if text else ""
        self.title_item = QGraphicsTextItem(self.title, self)
        self.title_item.setDefaultTextColor(
            QColor(
                Theme.Palette.ACCENT_HIGHLIGHT
                if hasattr(Theme.Palette, "ACCENT_HIGHLIGHT")
                else Theme.Palette.ACCENT_MAIN
            )
        )
        self.title_item.setFont(Theme.Typography.get_font("SIZE_H1", bold=True))
        self.title_item.setPos(12, 8)
        self.body_item = QGraphicsTextItem(self.text_content, self)
        self.body_item.setDefaultTextColor(QColor(Theme.Palette.TEXT_MAIN))
        self.body_item.setFont(Theme.Typography.get_font("SIZE_BODY"))
        self.body_item.setPos(12, 35)
        self.update_content_layout()

    def update_content_layout(self):
        target_width = self.rect().width() - 24
        self.title_item.setTextWidth(target_width)
        self.body_item.setTextWidth(target_width)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse():
            return
        dialog = NoteEditorDialog(self.title, self.text_content)
        if dialog.exec():
            new_title, new_text = dialog.get_data()

            self.title = new_title.strip() or "Untitled"
            self.text_content = new_text

            self.title_item.setPlainText(self.title)
            self.body_item.setPlainText(self.text_content)
            self.service.update_text_content(
                self.item_id, self.title, self.text_content
            )

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))
