from PySide6.QtGui import QFont, QFontMetricsF

from KryptoNote.gui.theme import Theme
from .base import NodeComponent


class AutoFitComponent(NodeComponent):
    def __init__(
        self, 
        min_width=120, 
        max_width=500, 
        min_height=60, 
        max_height=800, 
        ideal_chars_per_line=50, 
        bottom_padding=20
    ):
        super().__init__()
        self.min_width = min_width
        self.max_width = max_width
        self.min_height = min_height
        self.max_height = max_height
        self.ideal_chars_per_line = ideal_chars_per_line
        self.bottom_padding = bottom_padding
        self._auto_fit_pending = False
        
    def on_attached(self, node):
        super().on_attached(node)
        
    def on_event(self, event_type: str, *args, **kwargs):
        if event_type == "auto_fit":
            self.auto_fit()
        elif event_type == "set_auto_fit_pending":
            self._auto_fit_pending = kwargs.get("pending", True)
        elif event_type == "check_pending_fit":
            if self._auto_fit_pending:
                self.auto_fit()
                self._auto_fit_pending = False
                
    def _compute_ideal_size(self):
        node = self.node
        title = getattr(node, "title", getattr(node, "node_title", ""))
        title_size = getattr(node, "title_size", 14)
        title_font = QFont(Theme.Typography.FONT_DISPLAY, title_size, QFont.Weight.Bold)
        title_fm = QFontMetricsF(title_font)
        title_w = title_fm.horizontalAdvance(title) if title else 0.0

        content_margin = getattr(node, "CONTENT_MARGIN", 12)
        title_padding_top = getattr(node, "TITLE_PADDING_TOP", 8)
        title_body_gap = getattr(node, "TITLE_BODY_GAP", 6)

        if hasattr(node, "full_pixmap"):
            footer_h = node.label.boundingRect().height() if hasattr(node, "label") else 20
            
            img_w = node.full_pixmap.width() if node.full_pixmap else 0
            img_h = node.full_pixmap.height() if node.full_pixmap else 0
            aspect_ratio = img_h / img_w if img_w > 0 else 1.0
            
            node_w = max(self.min_width, title_w + 30)
            target_img_w = img_w * 0.4
            if target_img_w > node_w:
                node_w = min(target_img_w, self.max_width)
                node_w = max(node_w, title_w + 30)
                
            node_w = min(self.max_width, node_w)
            
            available_w = node_w - 20
            
            if hasattr(node, "title_item") and title:
                node.title_item.setTextWidth(available_w)
                title_h = node.title_item.boundingRect().height()
            else:
                title_h = 20
                
            node_h = int(available_w * aspect_ratio) + title_h + footer_h + 10
            node_h = max(self.min_height, min(self.max_height, node_h))
            
            return round(node_w), round(node_h)

        elif hasattr(node, "text_content"):
            text_content = getattr(node, "text_content", "")
            text_size = getattr(node, "text_size", 10)
            
            body_font = QFont(Theme.Typography.FONT_BODY, text_size)
            body_fm = QFontMetricsF(body_font)
            
            avg_char_w = body_fm.averageCharWidth()
            ideal_text_w = avg_char_w * self.ideal_chars_per_line
            
            lines = (text_content or "").split("\n")
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
                    
            list_indent = avg_char_w * 4 if has_lists else 0.0
            
            content_w = max(max_line_w + list_indent, title_w)
            text_area_w = min(ideal_text_w, content_w) if content_w > 0 else ideal_text_w
            text_area_w = max(text_area_w, title_w)
            
            node_w = text_area_w + content_margin * 2
            node_w = max(self.min_width, min(self.max_width, node_w))
            
            inner_w = node_w - content_margin * 2
            
            if hasattr(node, "title_item") and title:
                node.title_item.setTextWidth(inner_w)
                title_h = node.title_item.boundingRect().height()
            else:
                title_h = 0.0
                
            if hasattr(node, "body_item"):
                node.body_item.setTextWidth(inner_w)
                body_doc = node.body_item.document()
                body_doc.setTextWidth(inner_w)
                body_h = body_doc.size().height()
            else:
                body_h = 0.0
                
            total_h = (
                title_padding_top
                + title_h
                + (title_body_gap if title else 0)
                + body_h
                + self.bottom_padding
            )
            node_h = max(self.min_height, min(self.max_height, total_h))
            
            return round(node_w), round(node_h)
            
        return int(node.rect().width()), int(node.rect().height())
        
    def auto_fit(self):
        if not hasattr(self.node, "setRect"):
            return
            
        w, h = self._compute_ideal_size()
        self.node.setRect(0, 0, w, h)
        
        if hasattr(self.node, "update_resizer_pos"):
            self.node.update_resizer_pos()
            
        if hasattr(self.node, "update_content_layout"):
            self.node.update_content_layout()
            
        if hasattr(self.node, "connections"):
            for line in self.node.connections:
                if hasattr(line, "update_position"):
                    line.update_position()
                    
        if hasattr(self.node, "service") and hasattr(self.node, "item_id"):
            self.node.service.update_size(self.node.item_id, w, h)
