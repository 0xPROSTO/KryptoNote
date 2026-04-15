from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
from .base import BaseNode
from PySide6.QtWidgets import QGraphicsTextItem
from PySide6.QtGui import QColor, QFont
from KryptoNote.config import Config

class TextNode(BaseNode):
    def __init__(self, item_id, x, y, w, h, title, text, service):
        super().__init__(item_id, x, y, w, h, service)
        self.title = title
        self.text_content = text if text else ""

        self.title_item = QGraphicsTextItem(self.title, self)
        self.title_item.setDefaultTextColor(QColor(Config.COLOR_TEXT_TITLE))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        self.title_item.setFont(title_font)
        self.title_item.setPos(10, 5)

        self.body_item = QGraphicsTextItem(self.text_content, self)
        self.body_item.setDefaultTextColor(QColor(Config.COLOR_TEXT_BODY))
        self.body_item.setPos(10, 30)

        self.update_content_layout()

    def update_content_layout(self):
        target_width = self.rect().width() - 20
        self.title_item.setTextWidth(target_width)
        self.body_item.setTextWidth(target_width)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse(): return

        dialog = NoteEditorDialog(self.title, self.text_content)
        if dialog.exec():
            new_title, new_text = dialog.get_data()

            self.title = new_title.strip() or "Untitled"
            self.text_content = new_text

            self.title_item.setPlainText(self.title)
            self.body_item.setPlainText(self.text_content)

            self.service.update_text_content(self.item_id, self.title, self.text_content)

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))