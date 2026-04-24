import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication

from ..nodes import ConnectionLine, NodeFactory
from ...config import Config
from ...services.export_service import MarkdownExportService
from ...utils.media_proc import create_thumbnail


class CanvasController(QObject):
    status_message = Signal(str, str)
    pending_commits_changed = Signal(bool)
    progress_updated = Signal(float, str)
    progress_finished = Signal(str)

    def __init__(self, scene, view, service):
        super().__init__()
        self.scene = scene
        self.view = view
        self.service = service
        self.nodes_map = {}
        self.pending_commits = False
        self.link_start_node = None

    def load_from_db(self):
        self.progress_updated.emit(0.0, "Decrypting database...")
        QApplication.processEvents()

        items = self.service.get_all_items()
        total = len(items)

        for i, item_data in enumerate(items):
            try:
                node = NodeFactory.create_node_from_db(item_data, self.service)
                self.scene.addItem(node)
                self.nodes_map[item_data.id] = node
            except Exception as e:
                print(f"Skipping broken node {item_data.id}: {e}")

            if total > 0:
                self.progress_updated.emit((i + 1) / total * 0.85, f"Loading nodes ({i + 1}/{total})")
                QApplication.processEvents()

        conns = self.service.get_all_connections()
        total_conns = len(conns)
        for ci, c in enumerate(conns):
            n1 = self.nodes_map.get(c.start_id)
            n2 = self.nodes_map.get(c.end_id)
            if n1 and n2:
                line = ConnectionLine(c.id, n1, n2, self.service)
                self.scene.addItem(line)
                n1.add_connection(line)
                n2.add_connection(line)

            if total_conns > 0:
                self.progress_updated.emit(0.85 + (ci + 1) / total_conns * 0.15, f"Loading connections ({ci + 1}/{total_conns})")
                QApplication.processEvents()

        self.progress_finished.emit("Ready")

    def get_center_pos(self):
        return self.view.mapToScene(self.view.viewport().rect().center())

    def add_text_node(self):
        title = ""
        pos = self.get_center_pos()
        node = NodeFactory.create_new_text(self.service, pos.x(), pos.y(), title)
        self.scene.addItem(node)
        self.nodes_map[node.item_id] = node
        node.mouseDoubleClickEvent(None)

    def add_media_node(self, mtype):
        if mtype == "image":
            file_filter = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        elif mtype == "video":
            file_filter = "Videos (*.mp4 *.avi *.mkv *.mov *.webm)"
        else:
            file_filter = "All Files (*)"

        paths, _ = QFileDialog.getOpenFileNames(
            None, f"Select {mtype.capitalize()}s", "", file_filter
        )
        if not paths:
            return
        valid_img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        valid_vid_exts = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

        main_win = self.view.window()

        if main_win and hasattr(main_win, 'show_blocking_progress') and mtype == "video":
            main_win.show_blocking_progress("Preparing video...")
            QApplication.processEvents()

        for i, path in enumerate(paths):
            ext = os.path.splitext(path)[1].lower()
            if mtype == "image" and ext not in valid_img_exts:
                QMessageBox.critical(
                    None,
                    "Invalid File",
                    f"The file '{os.path.basename(path)}' is not a valid image format.",
                )
                continue
            elif mtype == "video" and ext not in valid_vid_exts:
                QMessageBox.critical(
                    None,
                    "Invalid File",
                    f"The file '{os.path.basename(path)}' is not a valid video format.",
                )
                continue

            pos = self.get_center_pos()
            offset = i * 25
            x, y = pos.x() + offset, pos.y() + offset
            if getattr(Config, "SNAP_TO_GRID", False):
                x = round(x / Config.GRID_SIZE) * Config.GRID_SIZE
                y = round(y / Config.GRID_SIZE) * Config.GRID_SIZE

            self.progress_updated.emit(i / len(paths), f"Generating thumbnail for {mtype} {i + 1}/{len(paths)}...")
            QApplication.processEvents()

            thumb_bytes = create_thumbnail(path)
            title = os.path.basename(path)
            full_data = None

            def progress_cb(current, total, status="Encrypting"):
                progress_val = (i + current / total) / len(paths)
                self.progress_updated.emit(
                    progress_val,
                    f"{status} {mtype} {i + 1}/{len(paths)} ({current}/{total})"
                )
                QApplication.processEvents()

            self.progress_updated.emit(i / len(paths), f"Reading {mtype} {i + 1}/{len(paths)}...")
            QApplication.processEvents()

            if mtype != "video":
                try:
                    with open(path, "rb") as f:
                        full_data = f.read()
                except Exception as e:
                    print(f"Error reading image file: {e}")

            node = NodeFactory.create_new_media(
                self.service,
                x,
                y,
                mtype,
                title,
                thumb_bytes,
                full_data=full_data,
                file_path=path,
                progress_callback=progress_cb,
            )
            self.scene.addItem(node)
            self.nodes_map[node.item_id] = node

        if main_win and hasattr(main_win, 'hide_blocking_progress') and mtype == "video":
            main_win.hide_blocking_progress()

        self.progress_finished.emit("Ready")

    def handle_link_click(self, node):
        if self.link_start_node is None:
            self.link_start_node = node
            node.setSelected(True)
            self.status_message.emit(f"LINKING: Chain started. Click next...", "secure")
        else:
            if self.link_start_node != node:
                created = self.create_connection(self.link_start_node, node)
                if created:
                    self.status_message.emit(
                        f"LINKED! Chain moves to new node.", "secure"
                    )
                    self.link_start_node.setSelected(False)
                    self.link_start_node = node
                    self.link_start_node.setSelected(True)

    def create_connection(self, node_a, node_b):
        existing_conns = [
            c
            for c in node_a.connections
            if c.end_node == node_b or c.start_node == node_b
        ]
        if existing_conns:
            return False
        conn_id = self.service.add_connection(
            node_a.item_id, node_b.item_id, commit=False
        )
        self.pending_commits = True
        self.pending_commits_changed.emit(True)
        line = ConnectionLine(conn_id, node_a, node_b, self.service)
        self.scene.addItem(line)
        node_a.add_connection(line)
        node_b.add_connection(line)
        return True

    def quick_delete_connection(self, connection_item):
        if hasattr(connection_item, "animate_deletion"):
            connection_item.animate_deletion()
        else:
            connection_item.delete_connection()
        self.status_message.emit("Link deleted.", "normal")

    def commit_changes(self):
        if self.pending_commits:
            self.status_message.emit("Saving changes to database...", "secure")
            QApplication.processEvents()
            self.service.commit_changes()
            self.pending_commits = False
            self.pending_commits_changed.emit(False)
            self.status_message.emit("Ready", "normal")

    def toggle_link_mode(self, active):
        if not active:
            if self.link_start_node:
                self.link_start_node.setSelected(False)
                self.link_start_node = None
            self.commit_changes()

    def export_to_markdown(self, default_filename="kryptonote_export.md"):
        path, _ = QFileDialog.getSaveFileName(
            None, "Export Notes to Markdown", default_filename,
            "Markdown Files (*.md)"
        )
        if not path:
            return

        self.progress_updated.emit(0.0, "Exporting to Markdown...")
        QApplication.processEvents()

        try:
            self.progress_updated.emit(0.2, "Reading nodes...")
            QApplication.processEvents()
            items = self.service.get_all_items()

            self.progress_updated.emit(0.4, "Reading connections...")
            QApplication.processEvents()
            connections = self.service.get_all_connections()

            self.progress_updated.emit(0.7, "Building Markdown...")
            QApplication.processEvents()
            exporter = MarkdownExportService()
            exporter.export(items, connections, path)

            self.progress_finished.emit("Ready")
            QMessageBox.information(
                None, "Export Complete",
                f"Exported successfully to:\n{path}"
            )
        except ValueError as e:
            self.progress_finished.emit("Ready")
            QMessageBox.warning(None, "Export", str(e))
        except Exception as e:
            self.progress_finished.emit("Ready")
            QMessageBox.critical(None, "Export Error", f"Failed to export:\n{e}")
