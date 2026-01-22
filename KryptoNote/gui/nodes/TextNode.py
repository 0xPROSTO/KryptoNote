from .NodeEditorDialog import NoteEditorDialog
from .BaseNode import BaseNode
from PyQt6.QtWidgets import QGraphicsTextItem
from PyQt6.QtGui import QColor


class TextNode(BaseNode):
    def __init__(self, item_id, x, y, w, h, text, storage):
        super().__init__(item_id, x, y, w, h, storage)

        safe_text = text if text else "Double click to edit..."

        self.text_item = QGraphicsTextItem(safe_text, self)
        self.text_item.setDefaultTextColor(QColor("#eeeeee"))
        self.text_item.setPos(10, 10)
        self.update_content_layout()

    def update_content_layout(self):
        target_width = self.rect().width() - 20
        self.text_item.setTextWidth(target_width)

    def mouseDoubleClickEvent(self, event):
        try:
            if self.resizer.isUnderMouse(): return

            dialog = NoteEditorDialog(self.text_item.toPlainText())
            if dialog.exec():
                new_text = dialog.get_text()
                self.text_item.setPlainText(new_text)
                self.storage.update_text_content(self.item_id, new_text)
        except Exception as e:
            print(e)

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Редактировать")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))
