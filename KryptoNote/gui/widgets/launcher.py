import os

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QPushButton,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QMessageBox,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.overlays.launcher_overlay import LauncherOverlay


class ProjectLauncher(QDialog):
    def __init__(self, base_dir=None):
        super().__init__()
        self.setWindowTitle(Config.APP_NAME)
        self.resize(400, 500)
        self.base_dir = base_dir if base_dir else Config.DB_PATH
        self.selected_file = None
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        Theme.apply_to(self, Theme.Styles.get_launcher_qss)

        self._overlay_callback = None
        self.launcher_overlay = LauncherOverlay(parent=self, auto_show=False)
        self.launcher_overlay.inputSubmitted.connect(self._handle_overlay_input)
        self.launcher_overlay.anim.finished.connect(self._on_overlay_fade_finished)
        self._overlay_visible = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel("Select project")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText("New project name...")

        btn_create = QPushButton("+ Create")
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
        btn_del.setObjectName("btn_danger")
        btn_del.setAutoDefault(False)
        btn_del.clicked.connect(self.delete_project)

        btn_open = QPushButton("Open case")
        btn_open.setObjectName("btn_success")
        btn_open.setDefault(True)
        btn_open.setAutoDefault(True)
        btn_open.clicked.connect(self.accept_selection)

        actions_layout.addWidget(btn_del, 1)
        actions_layout.addWidget(btn_open, 2)
        layout.addLayout(actions_layout)

    def _handle_overlay_input(self, text, ok):
        if self._overlay_callback:
            self._overlay_callback(text, ok)

    def _set_background_enabled(self, enabled):
        self.list_widget.setEnabled(enabled)
        self.new_name_input.setEnabled(enabled)
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
        if os.path.exists(self.base_dir):
            files = [f for f in os.listdir(self.base_dir) if f.endswith(".zrx")]
            for f in files:
                self.list_widget.addItem(f)

            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)

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
                        os.remove(full_path)
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
            self._try_authenticate(db_path)

        elif self.new_name_input.text():
            self.create_project()

    def create_project(self):
        name = self.new_name_input.text().strip()
        if not name:
            return
        if not name.endswith(".zrx"):
            name += ".zrx"
        db_path = os.path.join(self.base_dir, name)
        if os.path.exists(db_path):
            QMessageBox.warning(self, "Error", "Project already exists!")
            return
        self._try_authenticate(db_path)

    def _try_authenticate(self, db_path):
        from PySide6.QtWidgets import QApplication
        from KryptoNote.core.database import DatabaseConnection, NodeRepository
        from KryptoNote.core.crypto import CryptoManager
        from KryptoNote.services.node_service import NodeService
        from KryptoNote.services.auth_service import AuthService

        self.auth_data = None
        if getattr(self, '_auth_active', False):
            return
        self._auth_active = True
        db_name = os.path.basename(db_path)

        try:
            db_conn = DatabaseConnection(db_path)
            crypto = CryptoManager()
            salt = db_conn.get_salt()
        except Exception as e:
            self._auth_active = False
            try:
                if 'db_conn' in locals() and hasattr(db_conn, 'conn'):
                    db_conn.conn.close()
            except Exception:
                pass
            QMessageBox.critical(self, "Database Error", f"Failed to load '{db_name}'. The file may be corrupted.\nError: {e}")
            return

        is_new = salt is None
        state = {"first_pwd": None}

        self._overlay_callback = None

        btn_open = self.findChild(QPushButton, "btn_success")
        if btn_open:
            btn_open.setDefault(False)
            btn_open.setAutoDefault(False)

        def _dismiss():
            self._auth_active = False
            self._overlay_callback = None
            try:
                db_conn.conn.close()
            except Exception:
                pass
            self.launcher_overlay.fade_out()
            self.list_widget.setFocus()

        def _success():
            self._overlay_callback = None
            repo = NodeRepository(db_conn, crypto)
            service = NodeService(repo)
            self.auth_data = (db_path, db_conn, crypto, repo, service)

            self.launcher_overlay.anim.finished.connect(
                self.accept, Qt.ConnectionType.SingleShotConnection
            )
            self.launcher_overlay.fade_out()

        def _on_input(pwd, ok):
            if not ok or not pwd:
                _dismiss()
                return

            if is_new:
                if state["first_pwd"] is None:
                    state["first_pwd"] = pwd
                    self.launcher_overlay.show_overlay("confirm", db_name)
                    return
                if pwd != state["first_pwd"]:
                    state["first_pwd"] = None
                    self.launcher_overlay.show_overlay("create", db_name)
                    self.launcher_overlay.show_error("Passwords do not match")
                    return
                AuthService.initialize_v2_project(db_conn, crypto, pwd)
                _success()
            else:
                auth_check = db_conn.get_auth_check()
                if not auth_check:
                    _dismiss()
                    return
                migration_started = False
                try:
                    if AuthService.is_v2_database(db_conn):
                        AuthService.unlock_v2_database(db_conn, crypto, pwd, salt)
                    else:
                        migration_started = True
                        self.launcher_overlay.show_message(
                            "Migrating Database",
                            "Please wait. Your database is being migrated to the new encryption model. "
                            "Do not close the program until this finishes.",
                        )
                        QApplication.processEvents()
                        AuthService.unlock_and_migrate_legacy(db_conn, crypto, pwd, salt)

                    if crypto.decrypt(db_conn.get_auth_check()) == AuthService.AUTH_CHECK_PLAINTEXT:
                        _success()
                        return
                except Exception as e:
                    if migration_started:
                        self.launcher_overlay.show_overlay("enter", db_name)
                        self.launcher_overlay.show_error(f"Migration failed: {e}")
                        return
                self.launcher_overlay.show_error("Incorrect password")

        self._overlay_callback = _on_input
        self._set_background_enabled(False)
        self._overlay_visible = True
        self.launcher_overlay.show_overlay("create" if is_new else "enter", db_name)
