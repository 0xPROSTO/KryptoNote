import base64
import json
import mimetypes
import os
import re
import sqlite3
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config
from ..core.exceptions import OperationCancelledError
from .export_viewer import render_viewer, render_viewer_parts


EXPORT_SCHEMA = "zeroxx-kryptonote-export/v1"
STANDALONE_WARNING_BYTES = 256 * 1024 * 1024


@dataclass(slots=True)
class ExportMedia:
    node_id: int
    node_type: str
    path: str
    thumbnail_path: str
    original_filename: str
    extension: str
    mime_type: str
    total_size: int
    is_chunked: bool
    has_thumbnail: bool


@dataclass(slots=True)
class ExportGraph:
    manifest: dict
    media: list[ExportMedia]
    thumbnail_reader: object = field(default=None, repr=False)

    @property
    def media_bytes(self):
        return sum(max(0, media.total_size) for media in self.media)

    def read_thumbnail(self, media):
        if not media.has_thumbnail or self.thumbnail_reader is None:
            return None
        return self.thumbnail_reader(media)


class GraphExportService:
    """Build and export one immutable, decrypted view of a case."""

    def __init__(
        self,
        db_path,
        crypto,
        appearance=None,
        case_name=None,
        selected_ids=None,
        cancel_check=None,
        progress_callback=None,
    ):
        self.db_path = str(db_path)
        self.crypto = crypto
        self.appearance = dict(appearance or {})
        self.case_name = case_name or Path(self.db_path).stem
        self.selected_ids = (
            frozenset(int(node_id) for node_id in selected_ids)
            if selected_ids is not None else None
        )
        self.cancel_check = cancel_check or (lambda: False)
        self.progress_callback = progress_callback or (lambda _value, _message: None)

    @staticmethod
    def estimate_standalone_size(db_path, selected_ids=None):
        """Fast upper estimate without decrypting payloads."""
        with GraphExportService._connect_readonly(db_path) as connection:
            selected_ids = (
                tuple(sorted({int(node_id) for node_id in selected_ids}))
                if selected_ids is not None else None
            )
            if selected_ids is not None:
                if not selected_ids:
                    return 2 * 1024 * 1024
                media_bytes = 0
                thumbnail_bytes = 0
                for start in range(0, len(selected_ids), 900):
                    batch = selected_ids[start:start + 900]
                    placeholders = ",".join("?" for _ in batch)
                    row = connection.execute(
                        "SELECT COALESCE(SUM(total_size), 0), "
                        "COALESCE(SUM(length(thumbnail)), 0) "
                        "FROM items WHERE storage_state='ready' "
                        f"AND id IN ({placeholders})",
                        batch,
                    ).fetchone()
                    media_bytes += int(row[0] or 0)
                    thumbnail_bytes += int(row[1] or 0)
            else:
                media_bytes, thumbnail_bytes = connection.execute(
                    "SELECT COALESCE(SUM(total_size), 0), "
                    "COALESCE(SUM(length(thumbnail)), 0) FROM items "
                    "WHERE storage_state='ready'"
                ).fetchone()
        binary_bytes = int(media_bytes or 0) + int(thumbnail_bytes or 0)
        return int(binary_bytes * 4 / 3) + 2 * 1024 * 1024

    def export(self, output_path, export_format, password=None):
        output_path = Path(output_path)
        part_path = output_path.with_name(output_path.name + ".part")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if part_path.exists():
            part_path.unlink()
        try:
            self._check_cancelled()
            self._progress(0.0, "Reading graph snapshot...")
            with self._connect_readonly(self.db_path) as connection:
                connection.execute("BEGIN")
                try:
                    graph = self.build_graph(connection)
                    self._check_cancelled()
                    if export_format == "zip":
                        self._write_zip(
                            graph,
                            part_path,
                            connection,
                            password=password,
                        )
                    elif export_format == "html":
                        self._write_standalone_html(
                            graph, part_path, connection
                        )
                    elif export_format == "pdf":
                        from .pdf_export_service import PdfExportService

                        self._progress(0.2, "Rendering PDF report...")
                        PdfExportService(
                            cancel_check=self.cancel_check,
                            progress_callback=self.progress_callback,
                        ).export(graph, part_path)
                    else:
                        raise ValueError(
                            f"Unsupported export format: {export_format}"
                        )
                finally:
                    connection.rollback()
            self._check_cancelled()
            os.replace(part_path, output_path)
            self._progress(1.0, "Export complete")
            return str(output_path)
        except Exception:
            try:
                part_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def build_graph(self, connection=None):
        if connection is None:
            with self._connect_readonly(self.db_path) as owned_connection:
                owned_connection.execute("BEGIN")
                try:
                    graph = self._build_graph(owned_connection)
                    graph.thumbnail_reader = self._read_thumbnail_fresh
                    return graph
                finally:
                    owned_connection.rollback()
        return self._build_graph(connection)

    def _build_graph(self, connection):
            tags = self._read_tags(connection)
            tags_by_node = self._read_node_tags(connection, tags)
            all_connections = [
                {"id": row[0], "start_id": row[1], "end_id": row[2]}
                for row in connection.execute(
                    "SELECT connections.id, connections.start_id, "
                    "connections.end_id FROM connections "
                    "JOIN items AS start_item "
                    "ON start_item.id=connections.start_id "
                    "JOIN items AS end_item "
                    "ON end_item.id=connections.end_id "
                    "WHERE start_item.storage_state='ready' "
                    "AND end_item.storage_state='ready' "
                    "ORDER BY connections.id"
                )
            ]
            exported_ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM items "
                    "WHERE storage_state='ready' ORDER BY id"
                )
                if self.selected_ids is None
                or int(row[0]) in self.selected_ids
            }
            row_cursor = connection.execute(
                "SELECT id, type, title, x, y, width, height, text_content, "
                "thumbnail IS NOT NULL, is_chunked, total_size, title_size, text_size, "
                "created_at, updated_at, media_width, media_height, "
                "media_duration, original_filename, frame_locked, "
                "frame_color, frame_opacity "
                "FROM items WHERE storage_state='ready' ORDER BY id"
            )
            connections = [
                link for link in all_connections
                if link["start_id"] in exported_ids and link["end_id"] in exported_ids
            ]
            adjacency = {}
            for link in connections:
                adjacency.setdefault(link["start_id"], []).append(link["end_id"])
                adjacency.setdefault(link["end_id"], []).append(link["start_id"])

            nodes = []
            media_records = []
            row_count = len(exported_ids)
            exported_index = 0
            for row in row_cursor:
                if int(row[0]) not in exported_ids:
                    continue
                self._check_cancelled()
                (
                    node_id, node_type, encrypted_title, x, y, width, height,
                    encrypted_text, has_thumbnail, is_chunked, total_size,
                    title_size, text_size, created_at, updated_at, media_width,
                    media_height, media_duration, encrypted_original_filename,
                    frame_locked, frame_color, frame_opacity,
                ) = row
                title = self._decrypt_text(
                    encrypted_title,
                    self.crypto.item_aad(node_id, "title"),
                )
                text = self._decrypt_text(
                    encrypted_text,
                    self.crypto.item_aad(node_id, "text_content"),
                )
                original_filename = self._decrypt_text(
                    encrypted_original_filename,
                    self.crypto.item_aad(
                        node_id, "original_filename"
                    ),
                )
                node_tags = [
                    {"id": tag["id"], "name": tag["name"], "color": tag["color"]}
                    for tag in tags_by_node.get(node_id, [])
                ]
                node = {
                    "id": int(node_id),
                    "type": node_type,
                    "title": title,
                    "content": text if node_type == "text" else "",
                    "position": {"x": float(x or 0), "y": float(y or 0)},
                    "size": {"width": float(width or 0), "height": float(height or 0)},
                    "font": {
                        "title_size": int(title_size or 14),
                        "text_size": int(text_size or 10),
                    },
                    "created_at": created_at or "",
                    "updated_at": updated_at or "",
                    "locked": bool(frame_locked)
                              if node_type == "frame" else False,
                    "frame_appearance": {
                        "color": self._safe_frame_color(frame_color),
                        "opacity": float(
                            0.21
                            if frame_opacity is None
                            else frame_opacity
                        ),
                    } if node_type == "frame" else None,
                    "tags": node_tags,
                    "linked_node_ids": sorted(adjacency.get(node_id, [])),
                }
                if node_type in {"image", "video"}:
                    media_size = int(total_size or 0)
                    if not is_chunked and media_size == 0:
                        media_size = self._read_non_chunked_media_size(
                            connection, node_id
                        )
                    extension = self._media_extension(
                        connection,
                        node_id,
                        node_type,
                        original_filename,
                        title,
                        bool(is_chunked),
                    )
                    folder = "images" if node_type == "image" else "videos"
                    media_path = f"media/{folder}/node-{node_id}{extension}"
                    thumbnail_path = (
                        f"thumbnails/node-{node_id}.jpg"
                        if has_thumbnail else ""
                    )
                    mime_type = mimetypes.guess_type(media_path)[0] or "application/octet-stream"
                    record = ExportMedia(
                        node_id=int(node_id),
                        node_type=node_type,
                        path=media_path,
                        thumbnail_path=thumbnail_path,
                        original_filename=original_filename,
                        extension=extension,
                        mime_type=mime_type,
                        total_size=media_size,
                        is_chunked=bool(is_chunked),
                        has_thumbnail=bool(has_thumbnail),
                    )
                    media_records.append(record)
                    node["media"] = {
                        "path": media_path,
                        "thumbnail": thumbnail_path,
                        "mime_type": mime_type,
                        "original_filename": original_filename,
                        "size": media_size,
                        "width": int(media_width or 0),
                        "height": int(media_height or 0),
                        "duration": float(media_duration or 0),
                    }
                nodes.append(node)
                exported_index += 1
                if row_count:
                    self._progress(
                        0.02 + 0.08 * (exported_index / row_count),
                        f"Reading nodes {exported_index}/{row_count}...",
                    )

            used_tag_ids = {
                int(tag["id"])
                for node in nodes
                for tag in node.get("tags", [])
            }
            manifest = {
                "schema": EXPORT_SCHEMA,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "application": {"name": Config.APP_NAME, "version": Config.VERSION},
                "case": {
                    "name": self.case_name,
                    "scope": "selected" if self.selected_ids is not None else "all",
                },
                "appearance": self.appearance,
                "nodes": nodes,
                "connections": connections,
                "tags": [
                    tag for tag in tags.values() if int(tag["id"]) in used_tag_ids
                ],
            }
            return ExportGraph(
                manifest=manifest,
                media=media_records,
                thumbnail_reader=lambda media: self._read_thumbnail(
                    connection, media
                ),
            )

    def _write_zip(self, graph, path, connection, password=None):
        manifest_json = json.dumps(
            graph.manifest, ensure_ascii=False, indent=2
        ).encode("utf-8")
        readme = self._render_readme(graph.manifest).encode("utf-8")
        viewer = render_viewer(graph.manifest).encode("utf-8")
        if password:
            try:
                import pyzipper
            except ImportError as exc:
                raise RuntimeError(
                    "Protected ZIP export requires pyzipper==0.4.0"
                ) from exc
            archive = pyzipper.AESZipFile(
                path,
                "w",
                compression=pyzipper.ZIP_DEFLATED,
                allowZip64=True,
            )
            archive.setpassword(password.encode("utf-8"))
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            deflated = pyzipper.ZIP_DEFLATED
            stored = pyzipper.ZIP_STORED
        else:
            archive = zipfile.ZipFile(
                path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            )
            deflated = zipfile.ZIP_DEFLATED
            stored = zipfile.ZIP_STORED

        total = max(1, graph.media_bytes)
        completed = 0
        try:
            with archive:
                archive.writestr("graph.json", manifest_json, compress_type=deflated)
                archive.writestr("README.md", readme, compress_type=deflated)
                archive.writestr("index.html", viewer, compress_type=deflated)
                for media in graph.media:
                    self._check_cancelled()
                    thumbnail = graph.read_thumbnail(media)
                    if thumbnail:
                        archive.writestr(
                            media.thumbnail_path,
                            thumbnail,
                            compress_type=stored,
                        )
                    previous_compression = archive.compression
                    archive.compression = stored
                    try:
                        with archive.open(media.path, "w", force_zip64=True) as target:
                            written = 0
                            for chunk in self._iter_media_bytes(
                                connection, media
                            ):
                                self._check_cancelled()
                                target.write(chunk)
                                written += len(chunk)
                                completed += len(chunk)
                                self._progress(
                                    0.1 + 0.88 * min(1.0, completed / total),
                                    f"Archiving media {completed}/{total} bytes...",
                                )
                        if written != media.total_size:
                            raise IOError(
                                f"Media node {media.node_id} is incomplete: "
                                f"expected {media.total_size}, wrote {written}"
                            )
                    finally:
                        archive.compression = previous_compression
        except Exception:
            try:
                archive.close()
            except Exception:
                pass
            raise

    def _write_standalone_html(self, graph, path, connection):
        before, after = render_viewer_parts(graph.manifest)
        total = max(1, graph.media_bytes)
        completed = 0
        with open(path, "w", encoding="utf-8", newline="") as output:
            output.write(before)
            for media in graph.media:
                self._check_cancelled()
                thumbnail = graph.read_thumbnail(media)
                if thumbnail:
                    output.write(
                        f'<script id="embedded-thumb-{media.node_id}" '
                        'type="application/octet-stream" data-mime="image/jpeg">'
                    )
                    self._write_base64(output, (thumbnail,))
                    output.write("</script>\n")
                output.write(
                    f'<script id="embedded-media-{media.node_id}" '
                    f'type="application/octet-stream" data-mime="{media.mime_type}">'
                )

                def chunks():
                    nonlocal completed
                    for chunk in self._iter_media_bytes(
                        connection, media
                    ):
                        completed += len(chunk)
                        self._progress(
                            0.1 + 0.88 * min(1.0, completed / total),
                            f"Embedding media {completed}/{total} bytes...",
                        )
                        yield chunk

                self._write_base64(output, chunks())
                output.write("</script>\n")
            output.write(after)

    def _iter_media_bytes(self, connection, media):
        if media.is_chunked:
            cursor = connection.execute(
                "SELECT media_chunks.chunk_index, media_chunks.data "
                "FROM media_chunks JOIN items "
                "ON items.id=media_chunks.item_id "
                "WHERE media_chunks.item_id=? "
                "AND items.storage_state='ready' "
                "ORDER BY media_chunks.chunk_index",
                (media.node_id,),
            )
            for chunk_index, encrypted_chunk in cursor:
                self._check_cancelled()
                yield self.crypto.decrypt(
                    encrypted_chunk,
                    aad=self.crypto.chunk_aad(
                        media.node_id, chunk_index
                    ),
                )
            return
        row = connection.execute(
            "SELECT full_data FROM items "
            "WHERE id=? AND storage_state='ready'", (media.node_id,)
        ).fetchone()
        if not row or not row[0]:
            if media.total_size == 0:
                return
            raise ValueError(
                f"No media data found for node {media.node_id}"
            )
        yield self.crypto.decrypt(
            row[0],
            aad=self.crypto.item_aad(media.node_id, "full_data"),
        )

    @staticmethod
    def _write_base64(output, chunks):
        carry = b""
        for chunk in chunks:
            data = carry + bytes(chunk)
            complete = len(data) - (len(data) % 3)
            if complete:
                output.write(base64.b64encode(data[:complete]).decode("ascii"))
            carry = data[complete:]
        if carry:
            output.write(base64.b64encode(carry).decode("ascii"))

    def _read_tags(self, connection):
        result = {}
        for tag_id, encrypted_name, color in connection.execute(
            "SELECT id, name, color FROM tags ORDER BY id"
        ):
            name = self._decrypt_text(
                encrypted_name, self.crypto.tag_aad(tag_id)
            )
            if name:
                result[int(tag_id)] = {
                    "id": int(tag_id), "name": name, "color": color,
                }
        return result

    @staticmethod
    def _read_node_tags(connection, tags):
        result = {}
        for node_id, tag_id in connection.execute(
            "SELECT item_tags.item_id, item_tags.tag_id FROM item_tags "
            "JOIN items ON items.id=item_tags.item_id "
            "WHERE items.storage_state='ready' "
            "ORDER BY item_tags.item_id, item_tags.priority, item_tags.tag_id"
        ):
            tag = tags.get(int(tag_id))
            if tag:
                result.setdefault(int(node_id), []).append(tag)
        return result

    def _media_extension(
        self, connection, node_id, node_type, original_filename, title, is_chunked
    ):
        allowed = {
            "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"},
            "video": {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".m4v"},
        }
        for candidate in (original_filename, title):
            suffix = Path(candidate or "").suffix.lower()
            if suffix in allowed.get(node_type, set()):
                return suffix
        prefix = self._read_media_prefix(connection, node_id, is_chunked)
        detected = self._extension_from_signature(prefix, node_type)
        return detected or ".bin"

    def _read_media_prefix(self, connection, node_id, is_chunked):
        if is_chunked:
            row = connection.execute(
                "SELECT media_chunks.data FROM media_chunks JOIN items "
                "ON items.id=media_chunks.item_id "
                "WHERE media_chunks.item_id=? "
                "AND items.storage_state='ready' "
                "ORDER BY media_chunks.chunk_index LIMIT 1",
                (node_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT full_data FROM items "
                "WHERE id=? AND storage_state='ready'", (node_id,)
            ).fetchone()
        if not row or not row[0]:
            return b""
        aad = (
            self.crypto.chunk_aad(node_id, 0)
            if is_chunked
            else self.crypto.item_aad(node_id, "full_data")
        )
        return self.crypto.decrypt(row[0], aad=aad)[:64]

    def _read_non_chunked_media_size(self, connection, node_id):
        row = connection.execute(
            "SELECT full_data FROM items "
            "WHERE id=? AND storage_state='ready'", (node_id,)
        ).fetchone()
        if not row or not row[0]:
            return 0
        return len(
            self.crypto.decrypt(
                row[0],
                aad=self.crypto.item_aad(node_id, "full_data"),
            )
        )

    @staticmethod
    def _extension_from_signature(data, node_type):
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if data.startswith(b"BM"):
            return ".bmp"
        if data.startswith((b"II*\x00", b"MM\x00*")):
            return ".tif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
            return ".avi"
        if data.startswith(b"\x1aE\xdf\xa3"):
            return ".webm" if node_type == "video" else None
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return ".mov" if data[8:12] == b"qt  " else ".mp4"
        return None

    def _decrypt_text(self, value, aad):
        if not value:
            return ""
        return self.crypto.decrypt(
            value, aad=aad
        ).decode("utf-8", errors="replace")

    def _read_thumbnail(self, connection, media):
        row = connection.execute(
            "SELECT thumbnail FROM items "
            "WHERE id=? AND storage_state='ready'", (media.node_id,)
        ).fetchone()
        if not row or not row[0]:
            return None
        return self.crypto.decrypt(
            row[0],
            aad=self.crypto.item_aad(media.node_id, "thumbnail"),
        )

    def _read_thumbnail_fresh(self, media):
        with self._connect_readonly(self.db_path) as connection:
            return self._read_thumbnail(connection, media)

    @staticmethod
    def _safe_frame_color(value):
        color = str(value or "")
        return color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else ""

    @staticmethod
    @contextmanager
    def _connect_readonly(db_path):
        path = Path(db_path).resolve()
        uri = f"{path.as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _markdown_text(value):
        return str(value or "").replace("\r\n", "\n").replace("\r", "\n")

    def _render_readme(self, manifest):
        nodes = sorted(
            manifest.get("nodes", []),
            key=lambda node: (
                node["position"]["y"], node["position"]["x"], node["id"]
            ),
        )
        node_map = {node["id"]: node for node in nodes}
        lines = [
            f"# {self._markdown_text(self.case_name)}",
            "",
            f"Export schema: `{EXPORT_SCHEMA}`  ",
            f"Nodes: {len(nodes)} | Connections: {len(manifest.get('connections', []))}",
            "",
        ]
        for node in nodes:
            title = self._markdown_text(node.get("title")) or f"Node {node['id']}"
            lines.extend([
                f'<a id="node-{node["id"]}"></a>',
                f"## Node {node['id']}: {title}",
                "",
                f"- Type: `{node.get('type', '')}`",
                f"- Position: `{node['position']['x']}, {node['position']['y']}`",
                f"- Size: `{node['size']['width']} x {node['size']['height']}`",
                f"- Created: `{node.get('created_at') or '-'}`",
                f"- Updated: `{node.get('updated_at') or '-'}`",
            ])
            if node.get("tags"):
                lines.append("- Tags: " + ", ".join(
                    f"`@{tag['name']}`" for tag in node["tags"]
                ))
            if node.get("type") == "frame":
                lines.append(
                    "- Lock: `" + (
                        "locked" if node.get("locked") else "unlocked"
                    ) + "`"
                )
                frame_appearance = node.get("frame_appearance") or {}
                lines.append(
                    "- Background: `"
                    + (frame_appearance.get("color") or "theme default")
                    + f" @ {round(float(frame_appearance.get('opacity', 0.21)) * 100)}%`"
                )
            linked = [node_map.get(link_id) for link_id in node.get("linked_node_ids", [])]
            linked = [target for target in linked if target]
            if linked:
                link_items = []
                for target in linked:
                    label = self._markdown_text(target.get("title")) or f"Node {target['id']}"
                    link_items.append(f"[{label}](#node-{target['id']})")
                links = ", ".join(link_items)
                lines.append(f"- Connected: {links}")
            media = node.get("media")
            if media:
                label = self._markdown_text(media.get("original_filename")) or Path(media["path"]).name
                lines.extend([
                    f"- Original file: `{label}`",
                    f"- Media: [{Path(media['path']).name}]({media['path']})",
                    f"- Media size: `{media.get('size', 0)}` bytes",
                    f"- Dimensions: `{media.get('width', 0)} x {media.get('height', 0)}`",
                    f"- Duration: `{media.get('duration', 0)}` seconds",
                ])
                if media.get("thumbnail"):
                    lines.append(f"- Thumbnail: [preview]({media['thumbnail']})")
            lines.append("")
            if node.get("type") == "text" and node.get("content"):
                lines.extend([self._markdown_text(node["content"]), ""])
            lines.extend(["---", ""])
        return "\n".join(lines)

    def _check_cancelled(self):
        if self.cancel_check():
            raise OperationCancelledError("Export cancelled")

    def _progress(self, value, message):
        self.progress_callback(max(0.0, min(1.0, float(value))), str(message))
