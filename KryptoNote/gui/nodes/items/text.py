from PySide6.QtGui import QColor, QFont, QFontMetricsF
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.node_editor_dialog import NoteEditorDialog
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

    def _compute_ideal_size(self):
        body_font = QFont(Theme.Typography.FONT_BODY, self.text_size)
        title_font = QFont(Theme.Typography.FONT_DISPLAY, self.title_size, QFont.Weight.Bold)
        body_fm = QFontMetricsF(body_font)
        title_fm = QFontMetricsF(title_font)

        avg_char_w = body_fm.averageCharWidth()
        ideal_text_w = avg_char_w * self.IDEAL_CHARS_PER_LINE

        lines = (self.text_content or "").split("\n")
        has_lists = any(
            l.lstrip().startswith(("- ", "* ", "+ "))
            or (len(l.lstrip()) > 2 and l.lstrip()[0].isdigit() and l.lstrip()[1] in ".)")
            for l in lines if l.strip()
        )

        max_line_w = 0.0
        for line in lines:
            w = body_fm.horizontalAdvance(line)
            if w > max_line_w:
                max_line_w = w

        title_w = title_fm.horizontalAdvance(self.title) if self.title else 0.0

        list_indent = avg_char_w * 4 if has_lists else 0.0

        content_w = max(max_line_w + list_indent, title_w)
        text_area_w = min(ideal_text_w, content_w) if content_w > 0 else ideal_text_w
        text_area_w = max(text_area_w, title_w)

        node_w = text_area_w + self.CONTENT_MARGIN * 2
        node_w = max(self.MIN_WIDTH, min(self.MAX_WIDTH, node_w))

        inner_w = node_w - self.CONTENT_MARGIN * 2

        self.title_item.setTextWidth(inner_w)
        title_h = self.title_item.boundingRect().height() if self.title else 0.0

        self.body_item.setTextWidth(inner_w)
        body_doc = self.body_item.document()
        body_doc.setTextWidth(inner_w)
        body_h = body_doc.size().height()

        total_h = (
            self.TITLE_PADDING_TOP
            + title_h
            + (self.TITLE_BODY_GAP if self.title else 0)
            + body_h
            + self.BOTTOM_PADDING
        )
        node_h = max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, total_h))

        return round(node_w), round(node_h)

    def auto_fit(self):
        w, h = self._compute_ideal_size()
        self.setRect(0, 0, w, h)
        self.update_resizer_pos()
        self.update_content_layout()
        for line in self.connections:
            line.update_position()
        self.service.update_size(self.item_id, w, h)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse():
            return
        dialog = NoteEditorDialog(self.title, self.text_content, self.title_size, self.text_size)
        if dialog.exec():
            new_title, new_text, new_title_size, new_text_size = dialog.get_data()

            self.title = new_title.strip()
            self.text_content = new_text
            self.title_size = new_title_size
            self.text_size = new_text_size

            self.title_item.setPlainText(self.title)
            self.title_item.setFont(QFont(Theme.Typography.FONT_DISPLAY, self.title_size, QFont.Weight.Bold))

            self.body_item.setFont(QFont(Theme.Typography.FONT_BODY, self.text_size))
            self.body_item.document().setMarkdown(process_markdown_for_pyside(self.text_content))

            self.update_content_layout()

            # --- Smart Auto-Fit only on first creation ---
            if self._auto_fit_pending:
                self.auto_fit()
                self._auto_fit_pending = False

            self.service.update_text_content(
                self.item_id, self.title, self.text_content, self.title_size, self.text_size
            )
        else:
            if not self.title.strip() and not self.text_content.strip():
                self.delete_node()

    def extend_context_menu(self, menu):
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.mouseDoubleClickEvent(None))
        fit_action = menu.addAction("Auto-Fit")
        fit_action.triggered.connect(self.auto_fit)
