from PySide6.QtGui import QFont, QFontMetricsF, QImage, QTextDocument

from ...utils.text_utils import process_markdown_for_pyside
from ..theme import Theme


class AutoFitService:
    """Pure sizing logic for QML-rendered nodes."""

    def __init__(self):
        self.text_min_w = 120
        self.text_max_w = 760
        self.text_min_h = 60
        self.text_max_h = 800
        self.text_ideal_chars = 72
        self.content_margin = 12
        self.title_padding_top = 8
        self.title_body_gap = 6
        self.bottom_padding = 8

        self.media_min_w = 120
        self.media_max_w = 500
        self.media_min_h = 60
        self.media_max_h = 800

    def fit_text(self, node):
        title = node.get("title", "")
        content = node.get("content", "")
        title_size = node.get("title_size", 14) or 14
        text_size = node.get("text_size", 10) or 10

        text_family = Theme.Typography.current_text_family()
        title_font = QFont(text_family, title_size, QFont.Weight.Bold)
        title_fm = QFontMetricsF(title_font)
        title_w = title_fm.horizontalAdvance(title) * 1.05 if title else 0.0  # QML renders ~5% wider

        body_font = QFont(text_family, text_size)
        body_fm = QFontMetricsF(body_font)

        avg_char_w = body_fm.averageCharWidth()
        ideal_text_w = avg_char_w * self.text_ideal_chars

        lines = (content or "").split("\n")
        has_lists = self._has_markdown_lists(lines)

        max_line_w = max(
            (body_fm.horizontalAdvance(line) for line in lines),
            default=0.0,
        )

        list_indent = avg_char_w * 4 if has_lists else 0.0
        content_w = max(max_line_w + list_indent, title_w)
        text_area_w = min(ideal_text_w, content_w) if content_w > 0 else ideal_text_w
        text_area_w = max(text_area_w, title_w)

        plain_len = len(content.strip())
        if plain_len >= 80 or has_lists or len(lines) > 2:
            min_reading_w = avg_char_w * 58
        elif plain_len >= 35:
            min_reading_w = avg_char_w * 44
        else:
            min_reading_w = 0.0

        if min_reading_w:
            text_area_w = max(text_area_w, min(min_reading_w, ideal_text_w))

        base_w = text_area_w + self.content_margin * 2
        base_w = max(self.text_min_w, min(self.text_max_w, base_w))

        def fit_for_width(width):
            inner_width = max(1.0, width - self.content_margin * 2)
            title_h = (
                self._document_height(title, title_font, inner_width, markdown=False)
                if title else 0.0
            )
            if self._looks_like_markdown(content):
                body_h = self._document_height(content, body_font, inner_width, markdown=True)
            else:
                body_h = self._wrapped_plain_height(content, body_fm, inner_width)
            total_h = (
                self.title_padding_top
                + title_h
                + (self.title_body_gap if title and content else 0)
                + body_h
                + self.bottom_padding
            )
            return max(self.text_min_h, min(self.text_max_h, total_h))

        best_w = base_w
        best_h = fit_for_width(best_w)
        best_score = float("inf")
        target_aspect = 2.35 if plain_len >= 80 or len(lines) > 2 else 1.8
        start_w = max(self.text_min_w, int(base_w // 20) * 20)
        for width in range(start_w, int(self.text_max_w) + 1, 20):
            height = fit_for_width(float(width))
            aspect = width / max(height, 1.0)
            score = abs(aspect - target_aspect) * 120.0 + height * 0.35 + width * 0.04
            if score < best_score:
                best_score = score
                best_w = float(width)
                best_h = height

        return float(round(best_w)), float(round(best_h))

    def fit_media(self, node, thumbnail):
        thumb_image = self._coerce_image(thumbnail)
        if thumb_image is None or thumb_image.isNull():
            return 220.0, 220.0

        img_w = thumb_image.width()
        img_h = thumb_image.height()
        aspect = img_h / img_w if img_w > 0 else 1.0

        title = node.get("title", "")
        title_font = QFont(Theme.Typography.FONT_DISPLAY, 12, QFont.Weight.Bold)
        title_fm = QFontMetricsF(title_font)
        title_w = title_fm.horizontalAdvance(title) if title else 0.0
        title_h = title_fm.height() + 10
        footer_h = 20

        target_img_w = img_w * 0.4
        node_w = max(self.media_min_w, title_w + 30)
        if target_img_w > node_w:
            node_w = min(target_img_w, self.media_max_w)
            node_w = max(node_w, title_w + 30)
        node_w = min(self.media_max_w, node_w)

        available_w = node_w - 20
        node_h = int(available_w * aspect) + title_h + footer_h + 10
        node_h = max(self.media_min_h, min(self.media_max_h, node_h))
        return float(round(node_w)), float(round(node_h))

    def _document_height(self, text, font, inner_width, markdown=False):
        if not text:
            return 0.0
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(font)
        doc.setTextWidth(inner_width)
        if markdown:
            # Markdown parity with old PySide renderer: single Enter is preserved.
            doc.setMarkdown(process_markdown_for_pyside(text))
        else:
            doc.setPlainText(text)
        return doc.size().height()

    def _wrapped_plain_height(self, text, metrics, inner_width):
        if not text:
            return 0.0
        height = 0.0
        for raw_line in text.split("\n"):
            line = raw_line if raw_line else " "
            line_w = metrics.horizontalAdvance(line)
            wraps = max(1, int((line_w + inner_width - 1) // inner_width))
            height += wraps * metrics.lineSpacing()
        return height

    def _coerce_image(self, thumbnail):
        if isinstance(thumbnail, QImage):
            return thumbnail
        if thumbnail:
            image = QImage.fromData(thumbnail)
            return image if not image.isNull() else None
        return None

    def _looks_like_markdown(self, content):
        return any(mark in content for mark in ("#", "*", "`", "[", "]", "- ", "+ "))

    def _has_markdown_lists(self, lines):
        return any(
            line.lstrip().startswith(("- ", "* ", "+ "))
            or (
                len(line.lstrip()) > 2
                and line.lstrip()[0].isdigit()
                and line.lstrip()[1] in ".)"
            )
            for line in lines
            if line.strip()
        )
