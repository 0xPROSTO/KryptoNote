import concurrent.futures
import os
import threading

from PySide6.QtCore import QEvent, QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
)

from KryptoNote.config import Config
from KryptoNote.gui.services.case_directory_service import CaseDirectoryService
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.services.operation_coordinator import OperationCoordinator
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.widgets.dialogs.case_directories_dialog import CaseDirectoriesDialog
from KryptoNote.gui.widgets.overlays.launcher_overlay import LauncherOverlay


class CaseDirectoryItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        selected = option.state & QStyle.StateFlag.State_Selected
        hovered = option.state & QStyle.StateFlag.State_MouseOver
        if not selected and not hovered:
            super().paint(painter, option, index)
            return

        painter.save()
        if selected:
            painter.setPen(QColor(Theme.Palette.ACCENT_MAIN))
            painter.setBrush(QColor(Theme.Palette.ACCENT_LOW))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(Theme.Palette.BG_CONTROL_HOVER))
        painter.drawRoundedRect(option.rect.adjusted(2, 1, -2, -1), 3, 3)
        painter.setPen(QColor(Theme.Palette.TEXT_MAIN))
        painter.drawText(
            option.rect.adjusted(10, 0, -8, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(index.data(Qt.ItemDataRole.DisplayRole)),
        )
        painter.restore()


class ProjectLauncher(QDialog):
    _auth_finished = Signal(object)
    _auth_migration_started = Signal()
    _auth_progress = Signal(int, int, str)
    def __init__(self, base_dir=None, settings=None):
        super().__init__()
        self.setWindowTitle(Config.APP_NAME)
        self.resize(500, 610)
        self.setMinimumSize(460, 560)

        default_directory = base_dir if base_dir else Config.DB_PATH
        self._directory_service = None
        if base_dir is not None and settings is None:
            self.case_directories = [
                CaseDirectoryService.normalize_path(default_directory)
            ]
            self.base_dir = self.case_directories[0]
        else:
            self._directory_service = CaseDirectoryService(
                default_directory,
                settings=settings,
            )
            self.case_directories, self.base_dir = self._directory_service.load()

        self.selected_file = None
        if os.path.normcase(self.base_dir) == os.path.normcase(
            CaseDirectoryService.normalize_path(Config.DB_PATH)
        ):
            os.makedirs(self.base_dir, exist_ok=True)

        Theme.apply_to(self, Theme.Styles.get_launcher_qss)

        self._overlay_callback = None
        self._auth_active = False
        self._auth_context = None
        self._auth_executor = None
        self._auth_cancel_event = None
        self._auth_operation_token = None
        self.operation_coordinator = OperationCoordinator(self)
        self._auth_finished.connect(self._on_auth_finished)
        self._auth_migration_started.connect(self._on_auth_migration_started)
        self._auth_progress.connect(self._on_auth_progress)
        self.launcher_overlay = LauncherOverlay(parent=self, auto_show=False)
        self.launcher_overlay.inputSubmitted.connect(self._handle_overlay_input)
        self.launcher_overlay.anim.finished.connect(self._on_overlay_fade_finished)
        self._overlay_visible = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        directory_label = QLabel("Case folder")
        layout.addWidget(directory_label)

        directory_layout = QHBoxLayout()
        directory_layout.setSpacing(6)
        self.directory_combo = QComboBox()
        self.directory_combo.setAccessibleName("Active case folder")
        self.directory_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.directory_combo.setMinimumContentsLength(24)
        self.directory_combo.setItemDelegate(CaseDirectoryItemDelegate(self))
        self.directory_combo.currentIndexChanged.connect(self._on_directory_changed)
        self.directory_combo.installEventFilter(self)
        directory_layout.addWidget(self.directory_combo, 1)

        self.folders_button = QPushButton("Manage")
        self.folders_button.setAccessibleName("Manage case folders")
        self.folders_button.setIcon(SvgIcons.get_icon("database"))
        self.folders_button.setIconSize(QSize(15, 15))
        self.folders_button.setObjectName("btn_folders")
        self.folders_button.setAutoDefault(False)
        self.folders_button.clicked.connect(self.manage_directories)
        directory_layout.addWidget(self.folders_button)
        layout.addLayout(directory_layout)

        self.directory_status = QLabel()
        self.directory_status.setObjectName("directory_status")
        self.directory_status.setWordWrap(True)
        self.directory_status.hide()
        layout.addWidget(self.directory_status)

        self._populate_directory_combo()

        project_label = QLabel("Select project")
        layout.addWidget(project_label)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        self.list_widget.installEventFilter(self)
        layout.addWidget(self.list_widget)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("New project name...")

        btn_create = QPushButton("Create")
        btn_create.setIcon(SvgIcons.get_icon("add"))
        btn_create.setIconSize(QSize(15, 15))
        btn_create.setObjectName("btn_create")
        btn_create.setAutoDefault(False)
        btn_create.clicked.connect(self.create_project)

        self.new_name_input.returnPressed.connect(self.create_project)
        tools_layout.addWidget(self.new_name_input, 1)
        tools_layout.addWidget(btn_create)
        layout.addLayout(tools_layout)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        btn_del = QPushButton("Delete")
        btn_del.setIcon(
            SvgIcons.get_icon(
                "delete",
                color=Theme.Palette.BTN_CANCEL_TEXT,
                active_color=Theme.Palette.BTN_CANCEL_TEXT,
            )
        )
        btn_del.setIconSize(QSize(15, 15))
        btn_del.setObjectName("btn_danger")
        btn_del.setAutoDefault(False)
        btn_del.clicked.connect(self.delete_project)

        btn_open = QPushButton("Open case")
        btn_open.setIcon(
            SvgIcons.get_icon(
                "open",
                color=Theme.Palette.BTN_APPLY_TEXT,
                active_color=Theme.Palette.BTN_APPLY_TEXT,
            )
        )
        btn_open.setIconSize(QSize(15, 15))
        btn_open.setObjectName("btn_success")
        btn_open.setDefault(True)
        btn_open.setAutoDefault(True)
        btn_open.clicked.connect(self.accept_selection)

        actions_layout.addWidget(btn_del, 1)
        actions_layout.addWidget(btn_open, 2)
        layout.addLayout(actions_layout)
        self.list_widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and watched in (
            self.directory_combo,
            self.list_widget,
        ):
            key = event.key()
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                direction = -1 if key == Qt.Key.Key_Left else 1
                next_index = self.directory_combo.currentIndex() + direction
                next_index = max(
                    0,
                    min(next_index, self.directory_combo.count() - 1),
                )
                self.directory_combo.setCurrentIndex(next_index)
                self.list_widget.setFocus(Qt.FocusReason.OtherFocusReason)
                return True

            if watched is self.directory_combo and key in (
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
            ):
                direction = -1 if key == Qt.Key.Key_Up else 1
                next_row = self.list_widget.currentRow() + direction
                next_row = max(0, min(next_row, self.list_widget.count() - 1))
                self.list_widget.setCurrentRow(next_row)
                self.list_widget.setFocus(Qt.FocusReason.OtherFocusReason)
                return True

        return super().eventFilter(watched, event)

    def _handle_overlay_input(self, text, ok):
        if self._overlay_callback:
            self._overlay_callback(text, ok)

    def _set_background_enabled(self, enabled):
        self.list_widget.setEnabled(enabled)
        self.new_name_input.setEnabled(enabled)
        self.directory_combo.setEnabled(enabled)
        self.folders_button.setEnabled(enabled)
        for btn in self.findChildren(QPushButton):
            if btn.objectName() in ["btn_create", "btn_danger", "btn_success"]:
                btn.setEnabled(enabled)

    def _on_overlay_fade_finished(self):
        if self.launcher_overlay.opacity_effect.opacity() == 0.0:
            self._set_background_enabled(True)
            self._overlay_visible = False
            btn_open = self.findChild(QPushButton, "btn_success")
            if btn_open:
                btn_open.setDefault(True)
                btn_open.setAutoDefault(True)

    def refresh_list(self):
        self.list_widget.clear()
        if not os.path.isdir(self.base_dir):
            self.directory_status.setText(
                "Folder is unavailable. Choose another folder or update this path."
            )
            self.directory_status.show()
            return

        try:
            files = sorted(
                f for f in os.listdir(self.base_dir) if f.endswith(".zrx")
            )
        except OSError as exc:
            self.directory_status.setText(f"Unable to read this folder: {exc}")
            self.directory_status.show()
            return

        self.directory_status.hide()
        for filename in files:
            self.list_widget.addItem(filename)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _directory_label(self, directory):
        default_path = CaseDirectoryService.normalize_path(Config.DB_PATH)
        if os.path.normcase(directory) == os.path.normcase(default_path):
            return os.path.join(".", "cases")
        return os.path.normpath(directory)

    def _populate_directory_combo(self):
        self.directory_combo.blockSignals(True)
        self.directory_combo.clear()
        active_key = os.path.normcase(self.base_dir)
        active_index = 0
        for index, directory in enumerate(self.case_directories):
            self.directory_combo.addItem(self._directory_label(directory), directory)
            self.directory_combo.setItemData(
                index, directory, Qt.ItemDataRole.ToolTipRole
            )
            if os.path.normcase(directory) == active_key:
                active_index = index
        self.directory_combo.setCurrentIndex(active_index)
        self.directory_combo.blockSignals(False)

    def _on_directory_changed(self, index):
        if index < 0:
            return
        directory = self.directory_combo.itemData(index)
        if not directory:
            return
        self.base_dir = directory
        self._save_directory_settings()
        self.refresh_list()

    def _save_directory_settings(self):
        if self._directory_service is not None:
            self.case_directories, self.base_dir = self._directory_service.save(
                self.case_directories,
                self.base_dir,
            )

    def manage_directories(self):
        dialog = CaseDirectoriesDialog(
            self.case_directories,
            self.base_dir,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.case_directories = dialog.directories
        self.base_dir = dialog.active_directory
        self._save_directory_settings()
        self._populate_directory_combo()
        self.refresh_list()

    def _remove_project_files(self, db_path):
        first_error = None
        for candidate in (db_path, db_path + "-wal", db_path + "-shm"):
            if not os.path.exists(candidate):
                continue
            try:
                os.remove(candidate)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error:
            raise first_error

    def delete_project(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        filename = item.text()

        self._overlay_callback = None

        btn_open = self.findChild(QPushButton, "btn_success")
        if btn_open:
            btn_open.setDefault(False)
            btn_open.setAutoDefault(False)

        self._set_background_enabled(False)
        self._overlay_visible = True

        def _on_delete(text, ok):
            self._overlay_callback = None

            def _after_fade():
                if ok and text == filename:
                    full_path = os.path.join(self.base_dir, filename)
                    try:
                        self._remove_project_files(full_path)
                        QMessageBox.information(self, "Success", "Project deleted.")
                        self.refresh_list()
                    except Exception as e:
                        QMessageBox.critical(self, "Error", str(e))
                elif ok:
                    QMessageBox.warning(
                        self, "Error", "Filename did not match. Deletion cancelled."
                    )

            self.launcher_overlay.anim.finished.connect(
                _after_fade, Qt.ConnectionType.SingleShotConnection
            )
            self.launcher_overlay.fade_out()

        self._overlay_callback = _on_delete
        self.launcher_overlay.show_overlay("delete", filename)


    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            db_path = os.path.join(self.base_dir, current_item.text())
            self._try_authenticate(db_path, mode="open")

        elif self.new_name_input.text():
            self.create_project()

    def create_project(self):
        name = self.new_name_input.text().strip()
        if not name:
            return
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Folder Error",
                f"Unable to use the selected case folder.\nError: {exc}",
            )
            return
        if not name.endswith(".zrx"):
            name += ".zrx"
        db_path = os.path.join(self.base_dir, name)
        if os.path.exists(db_path):
            QMessageBox.warning(self, "Error", "Project already exists!")
            return
        self._try_authenticate(db_path, mode="create")

    def _try_authenticate(self, db_path, mode):
        from KryptoNote.core.database import DatabaseConnection

        if mode not in {"create", "open"}:
            raise ValueError(f"Unsupported launcher mode: {mode}")
        if self._auth_active:
            return

        self.auth_data = None
        db_name = os.path.basename(db_path)
        is_new = mode == "create"
        try:
            if is_new:
                with open(db_path, "xb"):
                    pass
                salt = None
            else:
                salt = DatabaseConnection.read_metadata_readonly(
                    db_path, "auth_salt"
                )
                if salt is None:
                    raise ValueError("Missing authentication metadata")
        except Exception as exc:
            if is_new:
                self._cleanup_created_project(db_path)
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to load '{db_name}'. The file may be corrupted.\nError: {exc}",
            )
            return

        self._auth_active = True
        self._auth_context = {
            "db_path": db_path,
            "db_name": db_name,
            "is_new": is_new,
            "salt": salt,
            "first_password": None,
        }
        self._overlay_callback = self._on_password_input

        btn_open = self.findChild(QPushButton, "btn_success")
        if btn_open:
            btn_open.setDefault(False)
            btn_open.setAutoDefault(False)
        self._set_background_enabled(False)
        self._overlay_visible = True
        self.launcher_overlay.show_overlay("create" if is_new else "enter", db_name)

    def _on_password_input(self, password, accepted):
        context = self._auth_context
        if context is None:
            return
        if not accepted or not password:
            if self._auth_executor is not None:
                self._request_auth_cancel()
            else:
                self._dismiss_auth()
            return

        if context["is_new"]:
            if context["first_password"] is None:
                context["first_password"] = password
                self.launcher_overlay.show_overlay("confirm", context["db_name"])
                return
            if password != context["first_password"]:
                context["first_password"] = None
                self.launcher_overlay.show_overlay("create", context["db_name"])
                self.launcher_overlay.show_error("Passwords do not match")
                return

        self._start_auth_worker(password)

    def _start_auth_worker(self, password):
        from cryptography.exceptions import InvalidTag

        from KryptoNote.core.crypto import CryptoManager
        from KryptoNote.core.database import DatabaseConnection
        from KryptoNote.core.exceptions import AuthError, OperationCancelledError
        from KryptoNote.services.auth_service import AuthService

        if self._auth_executor is not None or self._auth_context is None:
            return
        context = dict(self._auth_context)
        context["first_password"] = None
        self._auth_context["first_password"] = None
        token = self.operation_coordinator.begin(
            "authentication", "Deriving encryption key...", blocking=True
        )
        if token is None:
            return
        self._auth_operation_token = token
        self._auth_cancel_event = threading.Event()
        cancel_check = self._auth_cancel_event.is_set
        finished_signal = self._auth_finished
        migration_signal = self._auth_migration_started
        progress_signal = self._auth_progress
        self._overlay_callback = lambda _text, _ok: self._request_auth_cancel()
        self.launcher_overlay.show_message(
            "Unlocking Project",
            "Deriving the encryption key...",
            cancellable=True,
        )

        def authenticate_in_worker():
            db_conn = None
            try:
                db_conn = DatabaseConnection(context["db_path"])
                crypto = CryptoManager()
                if context["is_new"]:
                    AuthService.initialize_v2_project(
                        db_conn, crypto, password, cancel_check=cancel_check
                    )
                else:
                    AuthService.unlock_existing_database(
                        db_conn,
                        crypto,
                        password,
                        context["salt"],
                        before_legacy_migration=migration_signal.emit,
                        cancel_check=cancel_check,
                        progress_callback=progress_signal.emit,
                    )
                if cancel_check():
                    raise OperationCancelledError("Operation cancelled")
                result = {"status": "success", "crypto": crypto}
            except InvalidTag:
                result = {"status": "wrong_password", "message": "Incorrect password"}
            except OperationCancelledError:
                result = {"status": "cancelled", "message": "Authentication cancelled"}
            except AuthError as exc:
                result = {"status": "auth_error", "message": str(exc)}
            except Exception as exc:
                result = {"status": "error", "message": str(exc)}
            finally:
                if db_conn is not None:
                    db_conn.close()
            finished_signal.emit(result)

        try:
            self._auth_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            self._auth_executor.submit(authenticate_in_worker)
        except Exception as exc:
            self._finish_auth_operation()
            self._dismiss_auth()
            QMessageBox.critical(self, "Database Error", str(exc))

    @Slot()
    def _on_auth_migration_started(self):
        token = self._auth_operation_token
        if token is not None:
            self.operation_coordinator.update(token, "Migrating encrypted data...")
        self.launcher_overlay.update_message(
            "Migrating Database",
            "Re-encrypting data. You can cancel safely; changes will be rolled back.",
        )

    @Slot(int, int, str)
    def _on_auth_progress(self, current, total, message):
        token = self._auth_operation_token
        if token is not None:
            self.operation_coordinator.update(token, message)
        if total > 0:
            message = f"{message} {current}/{total}"
        self.launcher_overlay.update_message("Migrating Database", message)

    @Slot(object)
    def _on_auth_finished(self, result):
        from KryptoNote.core.database import DatabaseConnection, NodeRepository
        from KryptoNote.services.node_service import NodeService

        context = self._auth_context
        was_cancelled = bool(
            self._auth_cancel_event is not None and self._auth_cancel_event.is_set()
        )
        self._finish_auth_operation()
        if context is None:
            return

        status = result.get("status")
        if status == "success" and not was_cancelled:
            db_conn = None
            repo = None
            try:
                db_conn = DatabaseConnection(context["db_path"])
                repo = NodeRepository(db_conn, result["crypto"])
                service = NodeService(repo)
                self.auth_data = (
                    context["db_path"], db_conn, result["crypto"], repo, service
                )
            except Exception as exc:
                if repo is not None:
                    repo.close(wait=False)
                if db_conn is not None:
                    db_conn.close()
                QMessageBox.critical(
                    self,
                    "Database Error",
                    f"Failed to prepare '{context['db_name']}'.\nError: {exc}",
                )
                self._dismiss_auth()
                return

            self._overlay_callback = None
            self._auth_context = None
            self._auth_active = False
            self.launcher_overlay.anim.finished.connect(
                self.accept, Qt.ConnectionType.SingleShotConnection
            )
            self.launcher_overlay.fade_out()
            return

        if status == "wrong_password" and not context["is_new"] and not was_cancelled:
            self._overlay_callback = self._on_password_input
            self.launcher_overlay.show_overlay("enter", context["db_name"])
            self.launcher_overlay.show_error("Incorrect password")
            return

        if status not in {"cancelled", "wrong_password"} and not was_cancelled:
            QMessageBox.critical(
                self,
                "Database Error",
                result.get("message") or "Authentication failed",
            )
        self._dismiss_auth()

    def _request_auth_cancel(self):
        cancel_event = self._auth_cancel_event
        if cancel_event is None:
            self._dismiss_auth()
            return
        cancel_event.set()
        token = self._auth_operation_token
        if token is not None:
            self.operation_coordinator.update(token, "Cancelling safely...")
        self.launcher_overlay.update_message(
            "Cancelling", "Waiting for the current cryptographic step to finish..."
        )

    def _finish_auth_operation(self):
        executor = self._auth_executor
        self._auth_executor = None
        if executor is not None:
            executor.shutdown(wait=False)
        token = self._auth_operation_token
        self._auth_operation_token = None
        if token is not None:
            self.operation_coordinator.finish(token)
        self._auth_cancel_event = None

    def _dismiss_auth(self):
        context = self._auth_context
        self._auth_context = None
        self._auth_active = False
        self._overlay_callback = None
        if context and context["is_new"]:
            self._cleanup_created_project(context["db_path"])
            self.refresh_list()
        self.launcher_overlay.fade_out()
        self.list_widget.setFocus()

    def _cleanup_created_project(self, db_path):
        try:
            self._remove_project_files(db_path)
        except Exception:
            pass

    def reject(self):
        if self._auth_executor is not None:
            self._request_auth_cancel()
            return
        if self._auth_active:
            self._dismiss_auth()
        super().reject()
