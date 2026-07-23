import math

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
)

from ..core.exceptions import OperationCancelledError


class PdfExportService:
    """Render a static A4 graph overview and a readable node catalog."""

    RESOLUTION = 144

    def __init__(self, cancel_check=None, progress_callback=None):
        self.cancel_check = cancel_check or (lambda: False)
        self.progress_callback = progress_callback or (lambda _value, _message: None)
        self.page_number = 0

    def export(self, graph, output_path):
        writer = QPdfWriter(str(output_path))
        writer.setResolution(self.RESOLUTION)
        writer.setTitle(f"{graph.manifest.get('case', {}).get('name', 'KryptoNote')} - Graph report")
        writer.setCreator("ZeroXX-KryptoNote")
        writer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Landscape,
            QMarginsF(10, 10, 10, 10),
            QPageLayout.Unit.Millimeter,
        ))
        painter = QPainter()
        if not painter.begin(writer):
            raise IOError("Could not start PDF writer")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        try:
            self._draw_overview(painter, writer, graph)
            self._draw_catalog(painter, writer, graph)
        finally:
            painter.end()
        return str(output_path)

    def _page_rect(self, writer):
        return QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))

    def _draw_overview(self, painter, writer, graph):
        self._check_cancelled()
        self.page_number = 1
        page = self._page_rect(writer)
        appearance = graph.manifest.get("appearance", {})
        palette = appearance.get("palette", {})
        canvas_color = QColor(palette.get("bg_canvas", "#121212"))
        text_color = QColor(palette.get("text_main", "#efefef"))
        muted_color = QColor(palette.get("text_muted", "#92979f"))
        node_color = QColor(palette.get("bg_node", "#26282b"))
        border_color = QColor(palette.get("border_default", "#3a3e43"))
        link_color = QColor(palette.get("accent_main", "#e6158b"))

        painter.fillRect(page, canvas_color)
        title_font = QFont("Segoe UI", 14, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(text_color)
        case_name = graph.manifest.get("case", {}).get("name") or "KryptoNote Export"
        painter.drawText(QRectF(page.left(), page.top(), page.width(), 40), case_name)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(muted_color)
        summary = (
            f"{len(graph.manifest.get('nodes', []))} nodes  |  "
            f"{len(graph.manifest.get('connections', []))} connections"
        )
        painter.drawText(
            QRectF(page.left(), page.top() + 36, page.width(), 26), summary
        )
        content = QRectF(page.left(), page.top() + 70, page.width(), page.height() - 96)
        nodes = graph.manifest.get("nodes", [])
        if not nodes:
            painter.setFont(QFont("Segoe UI", 12))
            painter.setPen(muted_color)
            painter.drawText(content, Qt.AlignmentFlag.AlignCenter, "The graph is empty")
            self._draw_footer(painter, page, muted_color)
            return

        min_x = min(float(node["position"]["x"]) for node in nodes)
        min_y = min(float(node["position"]["y"]) for node in nodes)
        max_x = max(float(node["position"]["x"]) + max(1.0, float(node["size"]["width"])) for node in nodes)
        max_y = max(float(node["position"]["y"]) + max(1.0, float(node["size"]["height"])) for node in nodes)
        graph_width = max(1.0, max_x - min_x)
        graph_height = max(1.0, max_y - min_y)
        scale = min(content.width() / graph_width, content.height() / graph_height)
        scale = min(scale, 2.5)
        origin_x = content.left() + (content.width() - graph_width * scale) / 2
        origin_y = content.top() + (content.height() - graph_height * scale) / 2

        rects = {}
        for node in nodes:
            rects[node["id"]] = QRectF(
                origin_x + (float(node["position"]["x"]) - min_x) * scale,
                origin_y + (float(node["position"]["y"]) - min_y) * scale,
                max(1.0, float(node["size"]["width"]) * scale),
                max(1.0, float(node["size"]["height"]) * scale),
            )

        connection_width = max(0.8, float(appearance.get("connection_width", 1.5)) * scale)
        painter.setPen(QPen(link_color, connection_width))
        curved = appearance.get("connection_style", "curved") != "straight"
        for link in graph.manifest.get("connections", []):
            first = rects.get(link["start_id"])
            second = rects.get(link["end_id"])
            if first is None or second is None:
                continue
            endpoint_inset = max(0.0, 8.0 * scale)
            first_edge = first.adjusted(
                endpoint_inset, endpoint_inset, -endpoint_inset, -endpoint_inset
            )
            second_edge = second.adjusted(
                endpoint_inset, endpoint_inset, -endpoint_inset, -endpoint_inset
            )
            if first_edge.width() < 2 or first_edge.height() < 2:
                first_edge = first
            if second_edge.width() < 2 or second_edge.height() < 2:
                second_edge = second
            start = self._edge_point(first_edge, second.center())
            end = self._edge_point(second_edge, first.center())
            if curved:
                path = QPainterPath(start)
                delta = (end.x() - start.x()) * 0.4
                path.cubicTo(
                    QPointF(start.x() + delta, start.y()),
                    QPointF(end.x() - delta, end.y()),
                    end,
                )
                painter.drawPath(path)
            else:
                painter.drawLine(start, end)

        media_by_node = {item.node_id: item for item in graph.media}
        for index, node in enumerate(nodes):
            self._check_cancelled()
            rect = rects[node["id"]]
            painter.fillRect(rect, node_color)
            painter.setPen(QPen(border_color, max(0.8, scale)))
            painter.drawRect(rect)
            inset = max(3.0, min(10.0, 5.0 * scale))
            inner = rect.adjusted(inset, inset, -inset, -inset)
            painter.setClipRect(inner)
            painter.setPen(text_color)
            title_size = max(5.0, min(12.0, float(node.get("font", {}).get("title_size", 14)) * min(scale, 1.0)))
            title_font = QFont(
                "Segoe UI", int(round(title_size)), QFont.Weight.DemiBold
            )
            painter.setFont(title_font)
            title_height = QFontMetricsF(title_font).height() + 2
            title = node.get("title") or f"Node {node['id']}"
            painter.drawText(
                QRectF(inner.left(), inner.top(), inner.width(), title_height),
                Qt.TextFlag.TextSingleLine,
                QFontMetricsF(title_font).elidedText(
                    title, Qt.TextElideMode.ElideRight, int(inner.width())
                ),
            )
            body = QRectF(
                inner.left(), inner.top() + title_height,
                inner.width(), max(0.0, inner.height() - title_height),
            )
            if node.get("type") == "text":
                body_font = QFont(
                    "Segoe UI",
                    int(round(max(5.0, min(9.0, 7.0 * min(scale, 1.0))))),
                )
                painter.setFont(body_font)
                painter.setPen(muted_color)
                painter.drawText(
                    body,
                    Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    node.get("content") or "",
                )
            else:
                media = media_by_node.get(node["id"])
                if media and media.thumbnail:
                    image = QImage.fromData(media.thumbnail)
                    if not image.isNull():
                        target = self._fit_rect(image.width(), image.height(), body)
                        painter.drawImage(target, image)
            painter.setClipping(False)
            self.progress_callback(
                0.2 + 0.15 * ((index + 1) / max(1, len(nodes))),
                f"Rendering graph {index + 1}/{len(nodes)}...",
            )
        self._draw_footer(painter, page, muted_color)

    def _draw_catalog(self, painter, writer, graph):
        nodes = sorted(
            graph.manifest.get("nodes", []),
            key=lambda node: (
                node["position"]["y"], node["position"]["x"], node["id"]
            ),
        )
        if not nodes:
            return
        palette = graph.manifest.get("appearance", {}).get("palette", {})
        text_color = QColor(palette.get("text_main", "#202124"))
        dim_color = QColor(palette.get("text_dim", "#4f555b"))
        muted_color = QColor(palette.get("text_muted", "#6f767e"))
        accent_color = QColor(palette.get("accent_main", "#b00068"))
        background = QColor("#ffffff")
        if text_color.lightnessF() > 0.72:
            text_color = QColor("#202124")
            dim_color = QColor("#454a50")
            muted_color = QColor("#6c7278")
            accent_color = QColor("#a00060")
        media_by_node = {item.node_id: item for item in graph.media}
        node_map = {node["id"]: node for node in nodes}

        page, content, y = self._new_catalog_page(
            painter, writer, background, text_color, muted_color,
            graph.manifest.get("case", {}).get("name") or "KryptoNote Export",
        )

        def new_page():
            nonlocal page, content, y
            page, content, y = self._new_catalog_page(
                painter, writer, background, text_color, muted_color,
                graph.manifest.get("case", {}).get("name") or "KryptoNote Export",
            )

        for index, node in enumerate(nodes):
            self._check_cancelled()
            media_record = media_by_node.get(node["id"])
            minimum_space = (
                430 if media_record and media_record.thumbnail else 150
            )
            if y > content.top() + 2 and content.bottom() - y < minimum_space:
                new_page()
            painter.setPen(accent_color)
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
            title = node.get("title") or f"Node {node['id']}"
            y = self._draw_lines(
                painter, writer, title, content, y, 13, accent_color,
                background, text_color, muted_color,
                new_page_callback=new_page,
                weight=QFont.Weight.DemiBold,
            )
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(muted_color)
            type_label = node.get("type", "unknown")
            meta = [
                f"Node {node['id']}  |  {type_label}",
                f"Position {node['position']['x']}, {node['position']['y']}  |  "
                f"Size {node['size']['width']} x {node['size']['height']}",
                f"Created {node.get('created_at') or '-'}  |  Updated {node.get('updated_at') or '-'}",
            ]
            if node.get("tags"):
                meta.append("Tags: " + ", ".join(f"@{tag['name']}" for tag in node["tags"]))
            linked = [node_map.get(link_id) for link_id in node.get("linked_node_ids", [])]
            linked = [target for target in linked if target]
            if linked:
                meta.append("Connected: " + ", ".join(
                    target.get("title") or f"Node {target['id']}" for target in linked
                ))
            media = node.get("media")
            if media:
                meta.append(
                    f"Media {media.get('width', 0)} x {media.get('height', 0)}  |  "
                    f"{media.get('size', 0)} bytes  |  {media.get('duration', 0):.2f} s"
                )
                if media.get("original_filename"):
                    meta.append(f"Original file: {media['original_filename']}")
            for line in meta:
                y = self._draw_lines(
                    painter, writer, line, content, y, 8, muted_color,
                    background, text_color, muted_color,
                    new_page_callback=new_page,
                )
            y += 8

            if media_record and media_record.thumbnail:
                image = QImage.fromData(media_record.thumbnail)
                if not image.isNull():
                    desired_height = min(260.0, max(100.0, content.height() * 0.30))
                    if content.bottom() - y < desired_height + 20:
                        new_page()
                    target_area = QRectF(
                        content.left(), y, min(content.width() * 0.55, 520), desired_height
                    )
                    target = self._fit_rect(image.width(), image.height(), target_area)
                    painter.drawImage(target, image)
                    y = target.bottom() + 14

            if node.get("type") == "text":
                body = node.get("content") or ""
                if body:
                    y = self._draw_lines(
                        painter, writer, body, content, y, 9, dim_color,
                        background, text_color, muted_color,
                        new_page_callback=new_page,
                    )
                    y += 12
            if y + 18 > content.bottom():
                new_page()
            painter.setPen(QPen(QColor("#d7dadd"), 1))
            painter.drawLine(QPointF(content.left(), y), QPointF(content.right(), y))
            y += 18
            self.progress_callback(
                0.35 + 0.63 * ((index + 1) / max(1, len(nodes))),
                f"Rendering catalog {index + 1}/{len(nodes)}...",
            )

    def _new_catalog_page(
        self, painter, writer, background, text_color, muted_color, case_name
    ):
        self._check_cancelled()
        if not writer.newPage():
            raise IOError("Could not create a PDF page")
        self.page_number += 1
        page = self._page_rect(writer)
        painter.fillRect(page, background)
        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(page.left(), page.top(), page.width(), 30),
            Qt.TextFlag.TextSingleLine,
            f"{case_name} - Node catalog",
        )
        self._draw_footer(painter, page, muted_color)
        content = QRectF(
            page.left(), page.top() + 42, page.width(), page.height() - 78
        )
        return page, content, content.top()

    def _draw_lines(
        self, painter, writer, text, content, y, point_size, color,
        background, text_color, muted_color, new_page_callback, weight=QFont.Weight.Normal,
    ):
        font = QFont("Segoe UI", point_size, weight)
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetricsF(font)
        line_height = metrics.lineSpacing() * 1.15
        for paragraph in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            lines = self._wrap_paragraph(paragraph, metrics, content.width())
            for line in lines:
                self._check_cancelled()
                if y + line_height > content.bottom():
                    new_page_callback()
                    y = content.top()
                    painter.setFont(font)
                    painter.setPen(color)
                painter.drawText(
                    QPointF(content.left(), y + metrics.ascent()), line
                )
                y += line_height
        return y

    @staticmethod
    def _wrap_paragraph(text, metrics, width):
        if not text:
            return [""]
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if metrics.horizontalAdvance(word) <= width:
                current = word
                continue
            fragment = ""
            for char in word:
                if fragment and metrics.horizontalAdvance(fragment + char) > width:
                    lines.append(fragment)
                    fragment = char
                else:
                    fragment += char
            current = fragment
        if current or not lines:
            lines.append(current)
        return lines

    def _draw_footer(self, painter, page, color):
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(color)
        painter.drawText(
            QRectF(page.left(), page.bottom() - 22, page.width(), 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"Page {self.page_number}",
        )

    @staticmethod
    def _fit_rect(source_width, source_height, target):
        if source_width <= 0 or source_height <= 0:
            return target
        factor = min(target.width() / source_width, target.height() / source_height)
        width = source_width * factor
        height = source_height * factor
        return QRectF(
            target.left() + (target.width() - width) / 2,
            target.top() + (target.height() - height) / 2,
            width,
            height,
        )

    @staticmethod
    def _edge_point(rect, target):
        center = rect.center()
        dx = target.x() - center.x()
        dy = target.y() - center.y()
        if math.isclose(dx, 0.0, abs_tol=0.01) and math.isclose(dy, 0.0, abs_tol=0.01):
            return center
        scale_x = (rect.width() / 2) / abs(dx) if abs(dx) > 0.01 else math.inf
        scale_y = (rect.height() / 2) / abs(dy) if abs(dy) > 0.01 else math.inf
        factor = min(scale_x, scale_y)
        return QPointF(center.x() + dx * factor, center.y() + dy * factor)

    def _check_cancelled(self):
        if self.cancel_check():
            raise OperationCancelledError("Export cancelled")
