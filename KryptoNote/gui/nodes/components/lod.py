from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsTextItem

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from .base import NodeComponent


class LodComponent(NodeComponent):
    def __init__(self, threshold=None, fade_band=None):
        super().__init__()
        self.threshold = threshold if threshold is not None else Config.LOD_TEXT_HIDE_THRESHOLD
        self.fade_band = fade_band if fade_band is not None else self.threshold * 0.15
        self._lod_label = None
        self._lod_state = "full"
        self._beacon_dirty = True
        self._cached_beacon_font_size = None
        self._cached_beacon_node_size = None
        
    def on_attached(self, node):
        super().on_attached(node)
        
    def on_event(self, event_type: str, *args, **kwargs):
        if event_type == "apply_lod":
            lod = kwargs.get("lod", 1.0)
            self.apply_lod(lod)
        elif event_type == "layout_changed":
            self._beacon_dirty = True
            
    def _ensure_lod_label(self):
        if self._lod_label is None:
            self._lod_label = QGraphicsTextItem(parent=self.node)
            self._lod_label.setDefaultTextColor(
                QColor(
                    Theme.Palette.ACCENT_HIGHLIGHT
                    if hasattr(Theme.Palette, "ACCENT_HIGHLIGHT")
                    else Theme.Palette.ACCENT_MAIN
                )
            )
            self._lod_label.setOpacity(0.0)
            self._beacon_dirty = True
        return self._lod_label
        
    def _rebuild_beacon_layout(self):
        if not self._beacon_dirty:
            return
        self._beacon_dirty = False
        
        label = self._ensure_lod_label()
        
        title = getattr(self.node, "title", None) or getattr(self.node, "node_title", None)
        text_content = getattr(self.node, "text_content", "")
        
        if title:
            text = title
        else:
            text = "…"
            for line in (text_content or "").split("\n"):
                stripped = line.strip().lstrip("-*+#> 0123456789.)")
                if stripped:
                    text = stripped[:40] + ("…" if len(stripped) > 40 else "")
                    break
                    
        label.setPlainText(text)
        
        r = self.node.rect()
        content_margin = getattr(self.node, "CONTENT_MARGIN", 12)
        title_padding_top = getattr(self.node, "TITLE_PADDING_TOP", 8)
        
        available_w = r.width() - content_margin * 2
        available_h = r.height() - title_padding_top * 2
        
        if available_w <= 0 or available_h <= 0:
            return

        node_size = (r.width(), r.height())
        if (self._cached_beacon_font_size is not None 
                and self._cached_beacon_node_size == node_size):
            best_size = self._cached_beacon_font_size
        else:
            lo, hi = 8, 72
            best_size = lo
            while lo <= hi:
                mid = (lo + hi) // 2
                font = QFont(Theme.Typography.FONT_DISPLAY, mid, QFont.Weight.Bold)
                label.setFont(font)
                label.setTextWidth(available_w)
                doc_h = label.document().size().height()
                if doc_h <= available_h:
                    best_size = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            self._cached_beacon_font_size = best_size
            self._cached_beacon_node_size = node_size
                
        font = QFont(Theme.Typography.FONT_DISPLAY, best_size, QFont.Weight.Bold)
        label.setFont(font)
        label.setTextWidth(available_w)
        
        doc_h = label.document().size().height()
        y_offset = title_padding_top + max(0, (available_h - doc_h) / 2)
        label.setPos(content_margin, y_offset)
        
    def apply_lod(self, lod):
        title = getattr(self.node, "title", None) or getattr(self.node, "node_title", None)
        if not title:
            if self._lod_state != "full":
                self._lod_state = "full"
                if hasattr(self.node, "body_item"):
                    self.node.body_item.setOpacity(1.0)
                if hasattr(self.node, "label"):
                    self.node.label.setOpacity(1.0)
                if self._lod_label:
                    self._lod_label.setOpacity(0.0)
            return

        if lod >= self.threshold + self.fade_band:
            if self._lod_state != "full":
                self._lod_state = "full"
                if hasattr(self.node, "title_item"):
                    self.node.title_item.setOpacity(1.0)
                if hasattr(self.node, "body_item"):
                    self.node.body_item.setOpacity(1.0)
                if hasattr(self.node, "label"):
                    self.node.label.setOpacity(1.0)
                if self._lod_label:
                    self._lod_label.setOpacity(0.0)

        elif lod <= self.threshold:
            if self._lod_state != "beacon":
                self._lod_state = "beacon"
                self._rebuild_beacon_layout()
                if hasattr(self.node, "title_item"):
                    self.node.title_item.setOpacity(0.0)
                if hasattr(self.node, "body_item"):
                    self.node.body_item.setOpacity(0.0)
                if hasattr(self.node, "label"):
                    self.node.label.setOpacity(0.0)
                self._ensure_lod_label().setOpacity(1.0)

        else:
            t = (lod - self.threshold) / self.fade_band
            self._lod_state = "fading"
            self._rebuild_beacon_layout()

            if hasattr(self.node, "title_item"):
                self.node.title_item.setOpacity(t)
            if hasattr(self.node, "body_item"):
                self.node.body_item.setOpacity(t)
            if hasattr(self.node, "label"):
                self.node.label.setOpacity(t)
            self._ensure_lod_label().setOpacity(1.0 - t)
