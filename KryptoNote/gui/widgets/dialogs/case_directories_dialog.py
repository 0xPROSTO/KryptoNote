import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from KryptoNote.config import Config
from KryptoNote.gui.services.case_directory_service import CaseDirectoryService
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.widgets.dialog_motion import DialogMotionMixin


class CaseDirectoriesDialog(DialogMotionMixin, QDialog):
    def __init__(self, directories, active_directory, parent=None):
        super().__init__(parent)
        self._setup_dialog_motion()
        self.setWindowTitle("Case folders")
        self.resize(620, 360)
        self.setMinimumSize(520, 320)
        Theme.apply_to(self, Theme.Styles.get_launcher_qss)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        description = QLabel(
            "Switch between these folders in the launcher. "
            "New cases are created in the active folder."
        )
        description.setObjectName("directory_description")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.list_widget = QListWidget()
        self.list_widget.setAccessibleName("Case folders")
        self.list_widget.itemDoubleClicked.connect(self.change_directory)
        layout.addWidget(self.list_widget, 1)

        for directory in directories:
            self._add_item(directory)
        self._select_directory(active_directory)

        tools = QHBoxLayout()
        tools.setSpacing(6)

        add_button = QPushButton("Add")
        add_button.setIcon(SvgIcons.get_icon("add"))
        add_button.setAutoDefault(False)
        add_button.clicked.connect(self.add_directory)

        self.change_button = QPushButton("Change")
        self.change_button.setIcon(SvgIcons.get_icon("edit"))
        self.change_button.setAutoDefault(False)
        self.change_button.clicked.connect(self.change_directory)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setIcon(SvgIcons.get_icon("remove"))
        self.remove_button.setAutoDefault(False)
        self.remove_button.clicked.connect(self.remove_directory)

        tools.addWidget(add_button)
        tools.addWidget(self.change_button)
        tools.addWidget(self.remove_button)
        tools.addStretch(1)
        layout.addLayout(tools)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName(
            "btn_success"
        )
        layout.addWidget(buttons)

        self.list_widget.currentRowChanged.connect(self._update_buttons)
        self._update_buttons()

    @property
    def directories(self):
        return [
            self.list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.list_widget.count())
        ]

    @property
    def active_directory(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else self.directories[0]

    def _add_item(self, directory):
        normalized = CaseDirectoryService.normalize_path(directory)
        item = QListWidgetItem(os.path.normpath(normalized))
        item.setData(Qt.ItemDataRole.UserRole, normalized)
        item.setToolTip(normalized)
        self.list_widget.addItem(item)
        return item

    def _find_directory_row(self, directory):
        key = os.path.normcase(CaseDirectoryService.normalize_path(directory))
        for row in range(self.list_widget.count()):
            value = self.list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if os.path.normcase(value) == key:
                return row
        return -1

    def _select_directory(self, directory):
        row = self._find_directory_row(directory)
        self.list_widget.setCurrentRow(max(0, row))

    def _choose_directory(self, initial_directory):
        return QFileDialog.getExistingDirectory(
            self,
            "Choose case folder",
            initial_directory,
            QFileDialog.Option.ShowDirsOnly,
        )

    def add_directory(self):
        current = self.active_directory if self.list_widget.count() else Config.BASE_DIR
        directory = self._choose_directory(current)
        if not directory:
            return
        existing_row = self._find_directory_row(directory)
        if existing_row >= 0:
            self.list_widget.setCurrentRow(existing_row)
            return
        item = self._add_item(directory)
        self.list_widget.setCurrentItem(item)

    def change_directory(self, *_args):
        item = self.list_widget.currentItem()
        if item is None:
            return
        directory = self._choose_directory(item.data(Qt.ItemDataRole.UserRole))
        if not directory:
            return

        existing_row = self._find_directory_row(directory)
        current_row = self.list_widget.currentRow()
        if existing_row >= 0 and existing_row != current_row:
            self.list_widget.takeItem(current_row)
            if existing_row > current_row:
                existing_row -= 1
            self.list_widget.setCurrentRow(existing_row)
            return

        normalized = CaseDirectoryService.normalize_path(directory)
        item.setText(os.path.normpath(normalized))
        item.setData(Qt.ItemDataRole.UserRole, normalized)
        item.setToolTip(normalized)

    def remove_directory(self):
        if self.list_widget.count() <= 1:
            return
        current_row = self.list_widget.currentRow()
        self.list_widget.takeItem(current_row)
        self.list_widget.setCurrentRow(
            min(current_row, self.list_widget.count() - 1)
        )

    def _update_buttons(self, *_args):
        has_selection = self.list_widget.currentItem() is not None
        self.change_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection and self.list_widget.count() > 1)
