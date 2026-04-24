import os
import re
from datetime import datetime

from ..core.database.models import NodeItemDTO, ConnectionDTO


class MarkdownExportService:
    """Exports text nodes and their connections to a structured Markdown file."""

    def export(self, items: list[NodeItemDTO], connections: list[ConnectionDTO], output_path: str):
        text_nodes = [n for n in items if n.type == "text"]
        if not text_nodes:
            raise ValueError("No text nodes to export.")

        node_map = {n.id: n for n in text_nodes}
        adj = self._build_adjacency(connections, node_map)

        lines = self._render_header(text_nodes, connections)
        lines.append("")

        for node in text_nodes:
            lines.extend(self._render_node(node, adj, node_map))
            lines.append("")

        content = "\n".join(lines)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    @staticmethod
    def _build_adjacency(
        connections: list[ConnectionDTO], node_map: dict[int, NodeItemDTO]
    ) -> dict[int, list[int]]:
        adj: dict[int, list[int]] = {}
        for conn in connections:
            if conn.start_id in node_map and conn.end_id in node_map:
                adj.setdefault(conn.start_id, []).append(conn.end_id)
                adj.setdefault(conn.end_id, []).append(conn.start_id)
        return adj

    @staticmethod
    def _node_display_name(node: NodeItemDTO) -> str:
        if node.title and node.title.strip():
            return node.title.strip()
        if node.text_content:
            first_line = node.text_content.strip().split("\n")[0][:60]
            clean = re.sub(r'[#*_`>\[\]()]', '', first_line).strip()
            return clean if clean else f"Note #{node.id}"
        return f"Note #{node.id}"

    @staticmethod
    def _node_anchor(node: NodeItemDTO) -> str:
        name = MarkdownExportService._node_display_name(node)
        anchor = name.lower()
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        anchor = re.sub(r'[\s]+', '-', anchor)
        return anchor

    def _render_header(self, nodes: list[NodeItemDTO], connections: list[ConnectionDTO]) -> list[str]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# KryptoNote Export",
            f"",
            f"> Exported: {timestamp}  ",
            f"> Nodes: {len(nodes)} | Connections: {len(connections)}",
            "",
            "---",
        ]
        return lines

    def _render_node(
        self, node: NodeItemDTO, adj: dict[int, list[int]], node_map: dict[int, NodeItemDTO]
    ) -> list[str]:
        lines = []
        display_name = self._node_display_name(node)

        lines.append(f"## {display_name}")
        lines.append("")

        body = node.text_content.strip() if node.text_content else ""
        if body:
            lines.append(body)
            lines.append("")

        linked_ids = adj.get(node.id, [])
        if linked_ids:
            lines.append("**Linked notes:**")
            for lid in linked_ids:
                linked_node = node_map.get(lid)
                if linked_node:
                    link_name = self._node_display_name(linked_node)
                    anchor = self._node_anchor(linked_node)
                    lines.append(f"- [{link_name}](#{anchor})")
            lines.append("")

        lines.append("---")
        return lines
