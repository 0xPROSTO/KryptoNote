import datetime
import os
from collections import Counter

from ..core.constants import MEDIA_NODE_TYPES
from ..core.database.operations import read_database_space_stats


class KnowledgeStatsService:
    """Build dashboard stats from already loaded nodes and local DB files."""

    @staticmethod
    def build_overlay(nodes, link_count, db_path):
        """Build cheap stats for the always-visible arraylist overlay."""
        nodes = list(nodes or [])
        node_count = len(nodes)
        link_count = int(link_count or 0)
        space = read_database_space_stats(db_path)
        db_size = space.physical_bytes
        content_size = KnowledgeStatsService.content_size(nodes)
        return {
            "node_count": node_count,
            "link_count": link_count,
            "db_size": db_size,
            "db_size_label": KnowledgeStatsService.format_size(db_size),
            "db_main_size": space.main_bytes,
            "db_main_size_label": KnowledgeStatsService.format_size(
                space.main_bytes
            ),
            "db_wal_size": space.wal_bytes,
            "db_wal_size_label": KnowledgeStatsService.format_size(
                space.wal_bytes
            ),
            "db_shm_size": space.shm_bytes,
            "db_shm_size_label": KnowledgeStatsService.format_size(
                space.shm_bytes
            ),
            "db_reusable_size": space.reusable_bytes,
            "db_reusable_size_label": KnowledgeStatsService.format_size(
                space.reusable_bytes
            ),
            "content_size": content_size,
            "content_size_label": KnowledgeStatsService.format_size(content_size),
        }

    @staticmethod
    def build(nodes, link_count, db_path, connections=None):
        nodes = list(nodes or [])
        connections = list(connections or [])
        node_count = len(nodes)
        link_count = int(link_count or 0)
        type_counts = Counter(str(node.get("type") or "unknown") for node in nodes)
        type_stats = [
            {
                "type": node_type,
                "count": count,
                "percent": (count / node_count * 100.0) if node_count else 0.0,
                "percent_label": KnowledgeStatsService.format_percent(
                    (count / node_count * 100.0) if node_count else 0.0
                ),
            }
            for node_type, count in sorted(type_counts.items())
        ]
        content_size = KnowledgeStatsService.content_size(nodes)
        media_size = sum(int(node.get("total_size") or 0) for node in nodes)
        text_nodes = [node for node in nodes if node.get("type") == "text"]
        # ``text_chars``/``text_words`` are description metrics: media
        # Markdown descriptions count alongside ordinary text-node content.
        described_nodes = [
            node for node in nodes
            if node.get("type") == "text" or node.get("type") in MEDIA_NODE_TYPES
        ]
        text_chars = sum(len(node.get("content") or "") for node in described_nodes)
        text_words = sum(
            len((node.get("content") or "").split()) for node in described_nodes
        )
        connected_node_ids = KnowledgeStatsService.connected_node_ids(connections)
        if not connected_node_ids and link_count:
            connected_node_ids = set()
        orphan_nodes = max(0, node_count - len(connected_node_ids))
        space = read_database_space_stats(db_path)
        db_size = space.physical_bytes
        backup = KnowledgeStatsService.latest_backup(db_path)
        created_at = KnowledgeStatsService.project_created_at(nodes, db_path)
        updated_at = KnowledgeStatsService.last_modified_at(nodes, db_path)

        return {
            "node_count": node_count,
            "link_count": link_count,
            "db_size": db_size,
            "db_size_label": KnowledgeStatsService.format_size(db_size),
            "db_main_size": space.main_bytes,
            "db_main_size_label": KnowledgeStatsService.format_size(
                space.main_bytes
            ),
            "db_wal_size": space.wal_bytes,
            "db_wal_size_label": KnowledgeStatsService.format_size(
                space.wal_bytes
            ),
            "db_shm_size": space.shm_bytes,
            "db_shm_size_label": KnowledgeStatsService.format_size(
                space.shm_bytes
            ),
            "db_reusable_size": space.reusable_bytes,
            "db_reusable_size_label": KnowledgeStatsService.format_size(
                space.reusable_bytes
            ),
            "content_size": content_size,
            "content_size_label": KnowledgeStatsService.format_size(content_size),
            "media_size": media_size,
            "media_size_label": KnowledgeStatsService.format_size(media_size),
            "type_counts": dict(sorted(type_counts.items())),
            "type_stats": type_stats,
            "text_node_count": len(text_nodes),
            "media_node_count": sum(
                1 for node in nodes if node.get("type") in MEDIA_NODE_TYPES
            ),
            "text_chars": text_chars,
            "text_chars_label": f"{text_chars:,}".replace(",", " "),
            "text_words": text_words,
            "text_words_label": f"{text_words:,}".replace(",", " "),
            "connected_node_count": len(connected_node_ids),
            "orphan_node_count": orphan_nodes,
            "avg_links_per_node": (link_count / node_count) if node_count else 0.0,
            "avg_links_per_node_label": f"{(link_count / node_count):.2f}" if node_count else "0.00",
            "project_created_label": KnowledgeStatsService.format_datetime(created_at),
            "last_modified_label": KnowledgeStatsService.format_datetime(updated_at),
            "last_backup": backup,
            "last_backup_label": KnowledgeStatsService.format_backup_time(
                backup.get("mtime") if backup else None
            ),
        }

    @staticmethod
    def content_size(nodes):
        total = 0
        for node in nodes or []:
            cached_size = node.get("content_size")
            if cached_size is not None:
                total += int(cached_size or 0)
                continue
            node_type = node.get("type")
            if node_type == "text" or node_type in MEDIA_NODE_TYPES:
                total += len((node.get("title") or "").encode("utf-8"))
                total += len((node.get("content") or "").encode("utf-8"))
                if node_type in MEDIA_NODE_TYPES:
                    total += int(node.get("total_size") or 0)
            else:
                total += int(node.get("total_size") or 0)
        return total

    @staticmethod
    def connected_node_ids(connections):
        node_ids = set()
        for conn in connections:
            start_id = conn.get("start_id") if isinstance(conn, dict) else getattr(conn, "start_id", None)
            end_id = conn.get("end_id") if isinstance(conn, dict) else getattr(conn, "end_id", None)
            if start_id is not None:
                node_ids.add(start_id)
            if end_id is not None:
                node_ids.add(end_id)
        return node_ids

    @staticmethod
    def project_created_at(nodes, db_path):
        values = [
            parsed for parsed in (
                KnowledgeStatsService.parse_datetime(node.get("created_at"))
                for node in nodes
            )
            if parsed is not None
        ]
        if values:
            return min(values)
        return KnowledgeStatsService.file_datetime(db_path, created=True)

    @staticmethod
    def last_modified_at(nodes, db_path):
        values = [
            parsed for parsed in (
                KnowledgeStatsService.parse_datetime(
                    node.get("updated_at") or node.get("created_at")
                )
                for node in nodes
            )
            if parsed is not None
        ]
        if values:
            return max(values)
        return KnowledgeStatsService.file_datetime(db_path, created=False)

    @staticmethod
    def parse_datetime(value):
        if not value:
            return None
        try:
            return datetime.datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    def file_datetime(db_path, created=False):
        if not db_path or db_path == ":memory:" or not os.path.exists(db_path):
            return None
        try:
            timestamp = os.path.getctime(db_path) if created else os.path.getmtime(db_path)
        except OSError:
            return None
        return datetime.datetime.fromtimestamp(timestamp)

    @staticmethod
    def database_size(db_path):
        if not db_path or db_path == ":memory:":
            return 0
        try:
            if os.path.exists(db_path):
                return os.path.getsize(db_path)
        except OSError:
            pass
        return 0

    @staticmethod
    def latest_backup(db_path):
        if not db_path or db_path == ":memory:":
            return None

        db_dir = os.path.dirname(db_path)
        backup_dir = os.path.join(db_dir, "backup")
        base, ext = os.path.splitext(os.path.basename(db_path))
        if not os.path.isdir(backup_dir):
            return None

        latest = None
        try:
            for name in os.listdir(backup_dir):
                if not name.startswith(f"{base}_") or not name.endswith(ext):
                    continue
                path = os.path.join(backup_dir, name)
                mtime = os.path.getmtime(path)
                if latest is None or mtime > latest["mtime"]:
                    latest = {"path": path, "mtime": mtime}
        except OSError:
            return None
        return latest

    @staticmethod
    def format_size(size):
        size = int(size or 0)
        value = float(size)
        units = ("B", "KB", "MB", "GB")
        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    @staticmethod
    def format_backup_time(timestamp):
        if timestamp is None:
            return "Never"
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def format_datetime(value):
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def format_percent(value):
        if value >= 10:
            return f"{value:.0f}%"
        if value > 0:
            return f"{value:.1f}%"
        return "0%"
