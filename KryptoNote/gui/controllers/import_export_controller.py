import os

from PySide6.QtCore import QEventLoop, QObject, QSettings, QThread, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication

from ...config import Config
from ..services.media_import_service import MediaImportService, MediaImportWorker
from ..services.media_export_service import MediaExportService
from ..services.operation_coordinator import OperationCoordinator


class ImportExportController(QObject):
    """Handles media import (image/video) and export (media + markdown).

    Extracted from QmlCanvasController to reduce god-object complexity.
    """

    status_message = Signal(str, str)
    progress_updated = Signal(float, str)
    progress_finished = Signal(str)

    def __init__(self, node_model, service, auto_fit_callback, parent=None,
                 operation_coordinator=None):
        super().__init__(parent)
        self._node_model = node_model
        self._service = service
        self._auto_fit_callback = auto_fit_callback
        self._media_import_service = MediaImportService(service)
        self._media_export_service = MediaExportService(service)
        self._active_media_import_thread = None
        self._active_media_import_worker = None
        self._media_import_token = None
        self._operations = operation_coordinator or OperationCoordinator(self)
        self._synchronous_import_active = False
        self._settings = QSettings(Config.APP_NAME, Config.APP_NAME)

    def _last_dir(self, category):
        """Get last used directory for a category (image/video/export)."""
        return self._settings.value(f"last_dir/{category}", "")

    def _save_last_dir(self, category, path):
        """Save last used directory for a category."""
        directory = os.path.dirname(path) if os.path.isfile(path) else path
        self._settings.setValue(f"last_dir/{category}", directory)

    def get_viewport_center_func(self):
        """Override this to provide viewport center from canvas controller."""
        parent = self.parent()
        if parent and hasattr(parent, "get_viewport_center"):
            return parent.get_viewport_center()
        return [0.0, 0.0]

    @staticmethod
    def _format_file_size(size):
        gib = size / (1024 ** 3)
        if gib >= 1:
            return f"{gib:.2f} GiB"
        return f"{size / (1024 ** 2):.0f} MiB"

    def _warn_about_large_files(self, paths):
        large_files = self._media_import_service.get_large_files(paths)
        if not large_files:
            return

        details = [
            f"• {os.path.basename(path)} — {self._format_file_size(size)}"
            for path, size in large_files[:5]
        ]
        if len(large_files) > 5:
            details.append(f"• and {len(large_files) - 5} more")

        QMessageBox.warning(
            None,
            "Large Media Files",
            "There is no import size limit; these files will still be imported.\n\n"
            "Large media can use significant memory, make the application respond "
            "slowly, and take a long time to import:\n\n"
            + "\n".join(details),
        )

    def _add_imported_media_node(self, item):
        self._node_model.add_node(
            item.node_id, item.node_type, item.x, item.y, item.width, item.height,
            title=item.title, thumbnail_bytes=None,
            total_size=item.total_size,
            media_width=item.media_width, media_height=item.media_height,
            media_duration=item.media_duration,
        )
        self._auto_fit_callback(item.node_id, item.thumbnail_bytes)

    @Slot(str)
    def add_media_node(self, mtype, viewport_center=None):
        if self._operations.is_busy:
            QMessageBox.information(None, "Import", "Another database operation is active.")
            return

        if self.has_active_media_import():
            QMessageBox.information(None, "Import", "A media import is already running.")
            return

        center = viewport_center or self.get_viewport_center_func()
        center_x, center_y = center[0], center[1]

        paths, _ = QFileDialog.getOpenFileNames(
            None,
            f"Select {mtype.capitalize()}s",
            self._last_dir(mtype),
            self._media_import_service.file_filter_for(mtype),
        )
        if not paths:
            return
        self._save_last_dir(mtype, paths[0])

        valid_paths = []
        for path in paths:
            if self._media_import_service.validate_path(mtype, path):
                valid_paths.append(path)
            else:
                QMessageBox.critical(
                    None,
                    "Invalid File",
                    f"'{os.path.basename(path)}' is not a valid {mtype}.",
                )
        if not valid_paths:
            return
        self._warn_about_large_files(valid_paths)
        if mtype == "video":
            self._start_video_import(valid_paths, center_x, center_y)
        else:
            self._import_image_batch(valid_paths, center_x, center_y)

    def _start_video_import(self, paths, center_x, center_y):
        if self.has_active_media_import():
            QMessageBox.information(None, "Import", "Video import is already running.")
            return

        db_path = self._service.get_db_path()
        crypto_clone = self._service.create_crypto_clone()
        if not db_path or not crypto_clone:
            QMessageBox.critical(None, "Import Error", "Database is not ready.")
            return

        token = self._operations.begin("video_import", "Importing video...", blocking=True)
        if token is None:
            QMessageBox.information(None, "Import", "Another database operation is active.")
            return
        self._media_import_token = token
        thread = None
        try:
            thread = QThread(self)
            worker = MediaImportWorker(
                db_path,
                crypto_clone,
                "video",
                paths,
                center_x,
                center_y,
            )
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.progress.connect(self._on_async_media_import_progress)
            worker.item_imported.connect(self._on_async_media_item_imported)
            worker.finished.connect(self._on_async_media_import_finished)
            worker.cancelled.connect(self._on_async_media_import_cancelled)
            worker.failed.connect(self._on_async_media_import_failed)
            worker.finished.connect(thread.quit)
            worker.cancelled.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            worker.cancelled.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(
                lambda: self._clear_active_media_import(thread)
            )

            self._active_media_import_thread = thread
            self._active_media_import_worker = worker
            thread.start()
        except Exception as exc:
            self._active_media_import_thread = None
            self._active_media_import_worker = None
            self._finish_media_import()
            if thread is not None:
                thread.deleteLater()
            QMessageBox.critical(None, "Import Error", str(exc))

    @Slot(float, str)
    def _on_async_media_import_progress(self, value, message):
        self._operations.update(self._media_import_token, message)
        self.progress_updated.emit(value, message)

    @Slot(object)
    def _on_async_media_item_imported(self, item):
        self._add_imported_media_node(item)

    @Slot(int)
    def _on_async_media_import_finished(self, imported_count):
        self.status_message.emit(f"Imported {imported_count} video(s).", "normal")
        self._finish_media_import()
        self.progress_finished.emit("")

    @Slot()
    def _on_async_media_import_cancelled(self):
        self.status_message.emit("Video import cancelled.", "warning")
        self._finish_media_import()
        self.progress_finished.emit("")

    @Slot(str)
    def _on_async_media_import_failed(self, message):
        self.status_message.emit(f"Import failed: {message}", "error")
        self._finish_media_import()
        self.progress_finished.emit("")
        QMessageBox.critical(None, "Import Error", message)

    def _clear_active_media_import(self, thread):
        if self._active_media_import_thread is thread:
            self._active_media_import_thread = None
            self._active_media_import_worker = None
            self._finish_media_import()

    def _finish_media_import(self):
        token = self._media_import_token
        self._media_import_token = None
        if token is not None:
            self._operations.finish(token)

    def has_active_synchronous_import(self):
        return self._synchronous_import_active

    def has_active_background_jobs(self):
        thread = self._active_media_import_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._active_media_import_thread = None
            self._active_media_import_worker = None
            self._finish_media_import()
            return False

    def has_active_media_import(self):
        return self.has_active_synchronous_import() or self.has_active_background_jobs()

    def shutdown_background_jobs(self, timeout_ms=15000):
        """Cooperatively stop active imports before their QThread is destroyed."""
        thread = self._active_media_import_thread
        if thread is None:
            return True

        try:
            if not thread.isRunning():
                self._clear_active_media_import(thread)
                return True
            thread.requestInterruption()
            thread.quit()
            stopped = thread.wait(timeout_ms)
        except RuntimeError:
            stopped = True
        if stopped:
            QApplication.processEvents()
            self._clear_active_media_import(thread)
        return stopped

    @Slot(int)
    def export_node_to_disk(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return

        mtype = node.get("media_type", node.get("type", ""))
        title = node.get("title", "file")
        default_ext = ".jpg" if mtype == "image" else ".mp4"

        path, _ = QFileDialog.getSaveFileName(
            None, "Save File", os.path.join(self._last_dir("export"), title + default_ext)
        )
        if not path:
            return
        self._save_last_dir("export", path)

        try:
            self._media_export_service.export_node(node_id, path)
            self.status_message.emit(f"Exported to {os.path.basename(path)}", "normal")
        except ValueError as e:
            QMessageBox.warning(None, "Export", str(e))
        except Exception as e:
            QMessageBox.critical(None, "Export Error", f"Failed to export:\n{e}")

    def export_to_markdown(
        self,
        default_filename="kryptonote_export.md",
        selected_only=False,
        selected_ids=None,
    ):
        title = "Export Selected Notes to Markdown" if selected_only else "Export Notes to Markdown"
        path, _ = QFileDialog.getSaveFileName(
            None, title,
            os.path.join(self._last_dir("export"), default_filename),
            "Markdown Files (*.md)"
        )
        if not path:
            return
        self._save_last_dir("export", path)

        self.progress_updated.emit(0.0, "Exporting to Markdown...")
        QApplication.processEvents()

        try:
            self.progress_updated.emit(0.2, "Reading nodes...")
            QApplication.processEvents()
            items = self._service.get_all_items()
            if selected_only:
                selected_ids = set(selected_ids or [])
                items = [
                    item for item in items
                    if item.id in selected_ids and item.type == "text"
                ]

            self.progress_updated.emit(0.4, "Reading connections...")
            QApplication.processEvents()
            connections = self._service.get_all_connections()
            if selected_only:
                exported_ids = {item.id for item in items}
                connections = [
                    conn for conn in connections
                    if conn.start_id in exported_ids and conn.end_id in exported_ids
                ]

            self.progress_updated.emit(0.7, "Building Markdown...")
            QApplication.processEvents()
            from ...services.export_service import MarkdownExportService
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

    # ── Drag & Drop ─────────────────────────────────────────────────

    SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
    SUPPORTED_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

    @Slot(list, float, float)
    def import_files_by_paths(self, file_paths, center_x, center_y):
        """Import files dropped onto the canvas. Supports mixed types."""
        if self._operations.is_busy:
            QMessageBox.information(None, "Import", "Another database operation is active.")
            return

        if self.has_active_media_import():
            QMessageBox.information(None, "Import", "A media import is already running.")
            return

        image_paths = []
        video_paths = []
        invalid_paths = []

        for path in file_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in self.SUPPORTED_IMAGE_EXTS:
                image_paths.append(path)
            elif ext in self.SUPPORTED_VIDEO_EXTS:
                video_paths.append(path)
            else:
                invalid_paths.append(os.path.basename(path))

        if invalid_paths:
            names = ", ".join(invalid_paths[:5])
            if len(invalid_paths) > 5:
                names += f" (+{len(invalid_paths) - 5} more)"
            QMessageBox.warning(
                None, "Unsupported Files",
                f"Skipped unsupported files:\n{names}",
            )

        self._warn_about_large_files(image_paths + video_paths)

        if image_paths:
            self._import_image_batch(image_paths, center_x, center_y)

        if video_paths:
            self._start_video_import(video_paths, center_x, center_y)

    def _import_image_batch(self, paths, center_x, center_y):
        """Import a batch of image files (synchronous)."""
        if self.has_active_media_import():
            QMessageBox.information(
                None,
                "Import",
                "A media import is already running.",
            )
            return
        token = self._operations.begin("image_import", "Importing images...", blocking=True)
        if token is None:
            QMessageBox.information(None, "Import", "Another database operation is active.")
            return
        self._media_import_token = token

        self._synchronous_import_active = True

        def progress_cb(file_index, file_count, current, total, status):
            total = max(total, 1)
            value = (file_index + current / total) / max(file_count, 1)
            message = f"{status} image {file_index + 1}/{file_count}"
            self._operations.update(self._media_import_token, message)
            self.progress_updated.emit(value, message)
            QApplication.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
            )

        try:
            imported = self._media_import_service.import_paths(
                "image",
                paths,
                center_x,
                center_y,
                progress_callback=progress_cb,
                imported_callback=self._add_imported_media_node,
            )
            self.status_message.emit(f"Imported {len(imported)} image(s).", "normal")
        except Exception as exc:
            self.status_message.emit(f"Import failed: {exc}", "error")
            QMessageBox.critical(None, "Import Error", str(exc))
        finally:
            self._synchronous_import_active = False
            self._finish_media_import()
            self.progress_finished.emit("")
