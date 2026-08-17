import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from ...config import Config
from ...core.constants import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_NODE_TYPES,
    VIDEO_EXTENSIONS,
)
from ..services.media_import_service import MediaImportService, MediaImportWorker
from ..services.media_export_service import MediaExportService
from ..services.graph_export_worker import GraphExportWorker
from ..services.operation_coordinator import OperationCoordinator
from ...utils.media_proc import supported_audio_extensions
from ..theme.palette import Palette
from ..theme.theme_manager import CONNECTION_WIDTHS, get_theme_manager
from ..widgets.dialogs.export_dialog import ExportDialog


class ImportExportController(QObject):
    """Handle image/video/audio imports and graph/Markdown exports.

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
        self._active_graph_export_thread = None
        self._active_graph_export_worker = None
        self._graph_export_token = None
        self._operations = operation_coordinator or OperationCoordinator(self)
        self._settings = QSettings(Config.APP_NAME, Config.APP_NAME)

    def _last_dir(self, category):
        """Get last used directory for a media or export category."""
        return self._settings.value(f"last_dir/{category}", "")

    def _save_last_dir(self, category, path):
        """Save last used directory for a category."""
        directory = path if os.path.isdir(path) else os.path.dirname(path)
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
            title=item.title,
            thumbnail_bytes=(
                item.thumbnail_bytes if item.node_type == "audio" else None
            ),
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
        self._start_media_import(
            [(mtype, path) for path in valid_paths],
            center_x,
            center_y,
        )

    def _start_media_import(self, jobs, center_x, center_y):
        if self.has_active_media_import():
            QMessageBox.information(
                None, "Import", "A media import is already running."
            )
            return

        db_path = self._service.get_db_path()
        crypto_clone = self._service.create_crypto_clone()
        if not db_path or not crypto_clone:
            QMessageBox.critical(None, "Import Error", "Database is not ready.")
            return

        token = self._operations.begin(
            "media_import", "Importing media...", blocking=True
        )
        if token is None:
            QMessageBox.information(None, "Import", "Another database operation is active.")
            return
        self._media_import_token = token
        thread = None
        try:
            self._service.commit_changes()
            thread = QThread(self)
            worker = MediaImportWorker(
                db_path,
                crypto_clone,
                jobs,
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

    @Slot(object)
    def _on_async_media_import_progress(self, progress):
        message = progress.message
        self._operations.update(self._media_import_token, message)
        self.progress_updated.emit(
            min(0.995, progress.fraction), message
        )

    @Slot(object)
    def _on_async_media_item_imported(self, item):
        self._add_imported_media_node(item)

    @Slot(int)
    def _on_async_media_import_finished(self, imported_count):
        self.status_message.emit(
            f"Imported {imported_count} media file(s).", "normal"
        )
        self._finish_media_import()
        self.progress_finished.emit("")

    @Slot()
    def _on_async_media_import_cancelled(self):
        self.status_message.emit("Media import cancelled.", "warning")
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

    def cancel_media_import(self):
        thread = self._active_media_import_thread
        if thread is None:
            return False
        try:
            if not thread.isRunning():
                return False
            thread.requestInterruption()
            self._operations.update(
                self._media_import_token,
                "Cancelling media import safely...",
            )
            return True
        except RuntimeError:
            return False

    def has_active_synchronous_import(self):
        return False

    def has_active_background_jobs(self):
        active = False
        for kind, thread in (
            ("media", self._active_media_import_thread),
            ("export", self._active_graph_export_thread),
        ):
            if thread is None:
                continue
            try:
                active = thread.isRunning() or active
            except RuntimeError:
                if kind == "media":
                    self._active_media_import_thread = None
                    self._active_media_import_worker = None
                    self._finish_media_import()
                else:
                    self._active_graph_export_thread = None
                    self._active_graph_export_worker = None
                    self._finish_graph_export()
        return active

    def has_active_media_import(self):
        thread = self._active_media_import_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._clear_active_media_import(thread)
            return False

    def shutdown_background_jobs(self, timeout_ms=15000):
        """Cooperatively stop active imports/exports before QThreads are destroyed."""
        threads = [
            thread for thread in (
                self._active_media_import_thread,
                self._active_graph_export_thread,
            ) if thread is not None
        ]
        if not threads:
            return True
        stopped = True
        for thread in threads:
            try:
                if thread.isRunning():
                    thread.requestInterruption()
                    thread.quit()
                    stopped = thread.wait(timeout_ms) and stopped
            except RuntimeError:
                pass
        if stopped:
            QApplication.processEvents()
            for thread in threads:
                self._clear_active_media_import(thread)
                self._clear_active_graph_export(thread)
        return stopped

    @Slot(int)
    def export_node_to_disk(self, node_id):
        node = self._node_model.get_node_data(node_id)
        if not node:
            return

        mtype = node.get("media_type", node.get("type", ""))
        title = node.get("title", "file")
        original_filename = ""
        try:
            item_info = self._service.get_item_info(node_id)
            original_filename = getattr(item_info, "original_filename", "") or ""
        except Exception:
            item_info = None
        original_suffix = Path(original_filename).suffix.lower()
        fallback_ext = {
            "image": ".jpg",
            "video": ".mp4",
            "audio": ".ogg",
        }.get(mtype, ".bin")
        default_ext = original_suffix or fallback_ext
        default_name = title or "file"
        if Path(default_name).suffix.lower() != default_ext:
            default_name += default_ext

        path, _ = QFileDialog.getSaveFileName(
            None,
            "Save File",
            os.path.join(self._last_dir("export"), default_name),
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

        self._export_markdown_path(
            path,
            selected_only=selected_only,
            selected_ids=selected_ids,
        )

    def _export_markdown_path(self, path, selected_only=False, selected_ids=None):

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
                    if item.id in selected_ids
                    and (item.type == "text" or item.type in MEDIA_NODE_TYPES)
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

    def open_export_dialog(self):
        if self._operations.is_busy or self.has_active_background_jobs():
            QMessageBox.information(None, "Export", "Another database operation is active.")
            return
        db_path = self._service.get_db_path()
        if not db_path:
            QMessageBox.critical(None, "Export Error", "Database is not ready.")
            return

        selected_ids = self._node_model.get_selected_ids()
        selected_text_count = sum(
            1
            for node_id in selected_ids
            if (
                (self._node_model.get_node_data(node_id) or {}).get("type") == "text"
                or (self._node_model.get_node_data(node_id) or {}).get("type") in MEDIA_NODE_TYPES
            )
        )
        from ...services.graph_export_service import GraphExportService

        try:
            html_estimates = {
                "all": GraphExportService.estimate_standalone_size(db_path),
                "selected": GraphExportService.estimate_standalone_size(
                    db_path, selected_ids=selected_ids
                ),
            }
        except Exception:
            html_estimates = {}

        owner = QApplication.activeWindow()
        default_directory = self._last_dir("export") or str(Path(db_path).parent)
        dialog = ExportDialog(
            case_name=Path(db_path).stem,
            default_directory=default_directory,
            date_label=datetime.now().strftime("%Y-%m-%d"),
            selected_count=len(selected_ids),
            selected_text_count=selected_text_count,
            html_estimates=html_estimates,
            parent=owner,
        )
        if owner is not None and hasattr(owner, "_exec_dimmed_dialog"):
            result = owner._exec_dimmed_dialog("export", dialog)
        else:
            result = dialog.exec()
        if result != QDialog.DialogCode.Accepted:
            return
        self._start_export_request(dialog.request, selected_ids, html_estimates)

    def _start_export_request(self, request, selected_ids, html_estimates):
        export_format = request["format"]
        selected_only = bool(request["selected_only"])
        path = request["path"]
        export_ids = list(selected_ids) if selected_only else None

        if os.path.exists(path):
            answer = QMessageBox.question(
                None,
                "Replace Export",
                f"'{os.path.basename(path)}' already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if export_format == "zip" and not request["encrypt"]:
            answer = QMessageBox.question(
                None,
                "Unencrypted Export",
                "The ZIP contains decrypted text, photos, videos and audio. Anyone with "
                "the archive can read them. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if export_format == "html":
            from ...services.graph_export_service import STANDALONE_WARNING_BYTES

            estimate = html_estimates.get("selected" if selected_only else "all", 0)
            if estimate > STANDALONE_WARNING_BYTES:
                answer = QMessageBox.question(
                    None,
                    "Large Standalone HTML",
                    f"Estimated HTML size is {self._format_file_size(estimate)}. "
                    "Some browsers may load it slowly or run out of memory. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

        self._save_last_dir("export", path)
        if export_format == "md":
            self._export_markdown_path(
                path,
                selected_only=selected_only,
                selected_ids=export_ids,
            )
            return
        self._start_graph_export(
            export_format,
            path,
            password=request["password"],
            selected_ids=export_ids,
        )

    def export_complete_archive(self, default_filename, protected=False):
        password = None
        if protected:
            QMessageBox.information(
                None,
                "Protected Archive",
                "The archive will use AES-256 encryption. Windows Explorer may not "
                "open it; use 7-Zip or WinZip when necessary.",
            )
            password = self._request_archive_password()
            if password is None:
                return
        else:
            answer = QMessageBox.question(
                None,
                "Unencrypted Export",
                "The ZIP contains decrypted text, photos, videos and audio. Anyone with "
                "the archive can read them. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._choose_and_start_graph_export(
            "zip",
            default_filename,
            "Export Protected Complete Archive" if protected else "Export Complete Archive",
            "ZIP Archives (*.zip)",
            password=password,
        )

    def export_standalone_html(self, default_filename):
        db_path = self._service.get_db_path()
        if not db_path:
            QMessageBox.critical(None, "Export Error", "Database is not ready.")
            return
        from ...services.graph_export_service import (
            GraphExportService,
            STANDALONE_WARNING_BYTES,
        )
        try:
            estimate = GraphExportService.estimate_standalone_size(db_path)
        except Exception as exc:
            QMessageBox.critical(None, "Export Error", str(exc))
            return
        if estimate > STANDALONE_WARNING_BYTES:
            answer = QMessageBox.question(
                None,
                "Large Standalone HTML",
                f"Estimated HTML size is {self._format_file_size(estimate)}. "
                "Some browsers may load it slowly or run out of memory. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._choose_and_start_graph_export(
            "html",
            default_filename,
            "Export Standalone Browser Preview",
            "HTML Files (*.html)",
        )

    def export_pdf_report(self, default_filename):
        self._choose_and_start_graph_export(
            "pdf",
            default_filename,
            "Export PDF Report",
            "PDF Files (*.pdf)",
        )

    @staticmethod
    def _request_archive_password():
        password, ok = QInputDialog.getText(
            None,
            "Protected Archive",
            "Archive password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        if not password:
            QMessageBox.warning(None, "Protected Archive", "Password cannot be empty.")
            return None
        confirmation, ok = QInputDialog.getText(
            None,
            "Protected Archive",
            "Confirm password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        if confirmation != password:
            QMessageBox.warning(None, "Protected Archive", "Passwords do not match.")
            return None
        return password

    def _choose_and_start_graph_export(
        self, export_format, default_filename, title, file_filter, password=None
    ):
        if self._operations.is_busy or self.has_active_background_jobs():
            QMessageBox.information(None, "Export", "Another database operation is active.")
            return
        path, _ = QFileDialog.getSaveFileName(
            None,
            title,
            os.path.join(self._last_dir("export"), default_filename),
            file_filter,
        )
        if not path:
            return
        extension = {"zip": ".zip", "html": ".html", "pdf": ".pdf"}[export_format]
        if not path.lower().endswith(extension):
            path += extension
        self._save_last_dir("export", path)
        self._start_graph_export(export_format, path, password=password)

    def _appearance_snapshot(self):
        settings = get_theme_manager().settings
        palette = {
            "bg_canvas": Palette.BG_CANVAS,
            "bg_panel": Palette.BG_PANEL,
            "bg_node": Palette.BG_NODE,
            "bg_input": Palette.BG_INPUT,
            "bg_control": Palette.BG_CONTROL,
            "bg_control_hover": Palette.BG_CONTROL_HOVER,
            "border_default": Palette.BORDER_DEFAULT,
            "border_subtle": Palette.BORDER_SUBTLE,
            "text_main": Palette.TEXT_MAIN,
            "text_dim": Palette.TEXT_DIM,
            "text_muted": Palette.TEXT_MUTED,
            "accent_main": Palette.ACCENT_MAIN,
            "grid_main": Palette.GRID_MAIN,
            "grid_sub": Palette.GRID_SUB,
        }
        return {
            "tone": settings.tone,
            "accent_seed": settings.accent_seed,
            "connection_style": settings.connection_style,
            "connection_thickness": settings.connection_thickness,
            "connection_width": CONNECTION_WIDTHS[settings.connection_thickness],
            "connection_pattern": settings.connection_pattern,
            "connection_curve_formula": settings.connection_curve_formula,
            "connection_corner_style": settings.connection_corner_style,
            "connection_anchor_mode": settings.connection_anchor_mode,
            "grid_intensity": settings.grid_intensity,
            "palette": palette,
        }

    def _start_graph_export(
        self, export_format, path, password=None, selected_ids=None
    ):
        db_path = self._service.get_db_path()
        crypto = self._service.create_crypto_clone()
        if not db_path or not crypto:
            QMessageBox.critical(None, "Export Error", "Database is not ready.")
            return
        token = self._operations.begin(
            "graph_export", "Preparing export...", blocking=True
        )
        if token is None:
            QMessageBox.information(None, "Export", "Another database operation is active.")
            return
        self._graph_export_token = token
        thread = None
        try:
            self._service.commit_changes()
            thread = QThread(self)
            worker = GraphExportWorker(
                db_path,
                crypto,
                path,
                export_format,
                self._appearance_snapshot(),
                Path(db_path).stem,
                password=password,
                selected_ids=selected_ids,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._on_graph_export_progress)
            worker.finished.connect(self._on_graph_export_finished)
            worker.cancelled.connect(self._on_graph_export_cancelled)
            worker.failed.connect(self._on_graph_export_failed)
            worker.finished.connect(thread.quit)
            worker.cancelled.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            worker.cancelled.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda: self._clear_active_graph_export(thread))
            self._active_graph_export_thread = thread
            self._active_graph_export_worker = worker
            thread.start()
        except Exception as exc:
            self._active_graph_export_thread = None
            self._active_graph_export_worker = None
            self._finish_graph_export()
            if thread is not None:
                thread.deleteLater()
            QMessageBox.critical(None, "Export Error", str(exc))

    @Slot(float, str)
    def _on_graph_export_progress(self, value, message):
        self._operations.update(self._graph_export_token, message)
        self.progress_updated.emit(value, message)

    @Slot(str)
    def _on_graph_export_finished(self, path):
        self._finish_graph_export()
        self.progress_finished.emit("Ready")
        self.status_message.emit(f"Exported to {os.path.basename(path)}", "normal")
        QMessageBox.information(None, "Export Complete", f"Exported successfully to:\n{path}")

    @Slot()
    def _on_graph_export_cancelled(self):
        self._finish_graph_export()
        self.progress_finished.emit("Export cancelled")
        self.status_message.emit("Export cancelled.", "warning")

    @Slot(str)
    def _on_graph_export_failed(self, message):
        self._finish_graph_export()
        self.progress_finished.emit("Export failed")
        self.status_message.emit(f"Export failed: {message}", "error")
        QMessageBox.critical(None, "Export Error", message)

    def cancel_graph_export(self):
        thread = self._active_graph_export_thread
        if thread is None:
            return False
        try:
            if not thread.isRunning():
                return False
            thread.requestInterruption()
            self._operations.update(
                self._graph_export_token, "Cancelling export safely..."
            )
            return True
        except RuntimeError:
            return False

    def _clear_active_graph_export(self, thread):
        if self._active_graph_export_thread is thread:
            self._active_graph_export_thread = None
            self._active_graph_export_worker = None
            self._finish_graph_export()

    def _finish_graph_export(self):
        token = self._graph_export_token
        self._graph_export_token = None
        if token is not None:
            self._operations.finish(token)

    # ── Drag & Drop ─────────────────────────────────────────────────

    SUPPORTED_IMAGE_EXTS = set(IMAGE_EXTENSIONS)
    SUPPORTED_VIDEO_EXTS = set(VIDEO_EXTENSIONS)
    # Include Qt backend formats discovered at runtime.  Shared containers
    # remain video-first in ``import_files_by_paths`` below.
    SUPPORTED_AUDIO_EXTS = set(supported_audio_extensions())

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
        audio_paths = []
        invalid_paths = []

        for path in file_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in self.SUPPORTED_VIDEO_EXTS:
                # Video precedence keeps shared containers as video on drop.
                video_paths.append(path)
            elif ext in self.SUPPORTED_IMAGE_EXTS:
                image_paths.append(path)
            elif ext in self.SUPPORTED_AUDIO_EXTS:
                audio_paths.append(path)
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

        self._warn_about_large_files(image_paths + video_paths + audio_paths)

        jobs = [
            *(("image", path) for path in image_paths),
            *(("video", path) for path in video_paths),
            *(("audio", path) for path in audio_paths),
        ]
        if jobs:
            self._start_media_import(jobs, center_x, center_y)
