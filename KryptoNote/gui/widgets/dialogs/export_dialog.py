from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ...theme.icons import SvgIcons
from ...theme.style_factory import StyleFactory


class _FormatChoice(QFrame):
    def __init__(self, extension, title, description, parent=None):
        super().__init__(parent)
        self.setObjectName("export_format_choice")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        extension_label = QLabel(extension.upper())
        extension_label.setObjectName("export_format_extension")
        extension_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        extension_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(extension_label, 0, Qt.AlignmentFlag.AlignTop)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(3)

        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(7)
        self.radio = QRadioButton(title)
        self.radio.setProperty("formatChoice", True)
        self.radio.setAccessibleName(f"{title}. {description}")
        heading_layout.addWidget(self.radio)
        heading_layout.addStretch(1)
        copy_layout.addLayout(heading_layout)

        description_label = QLabel(description)
        description_label.setObjectName("export_format_description")
        description_label.setWordWrap(True)
        description_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy_layout.addWidget(description_label)
        layout.addLayout(copy_layout, 1)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.radio.setChecked(True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_selected(self, selected):
        selected = bool(selected)
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ExportDialog(QDialog):
    FORMATS = {
        "zip": {
            "extension_label": ".zip",
            "title": "Complete archive",
            "description": "Graph, data and original media",
            "extension": ".zip",
            "filter": "ZIP Archives (*.zip)",
            "suffix": "Complete",
        },
        "html": {
            "extension_label": ".html",
            "title": "Browser preview",
            "description": "Interactive offline file with embedded media",
            "extension": ".html",
            "filter": "HTML Files (*.html)",
            "suffix": "Preview",
        },
        "md": {
            "extension_label": ".md",
            "title": "Markdown",
            "description": "Text notes and connections without media",
            "extension": ".md",
            "filter": "Markdown Files (*.md)",
            "suffix": "Text",
        },
    }

    def __init__(
        self,
        case_name,
        default_directory,
        date_label,
        selected_count=0,
        selected_text_count=0,
        html_estimates=None,
        parent=None,
    ):
        super().__init__(parent)
        self._case_name = case_name or "Untitled"
        self._default_directory = Path(default_directory or Path.home())
        self._date_label = date_label
        self._selected_count = max(0, int(selected_count))
        self._selected_text_count = max(0, int(selected_text_count))
        self._html_estimates = dict(html_estimates or {})
        self._path_was_edited = False
        self._last_generated_path = ""
        self._dragging = False
        self._drag_start = QPoint()

        self.setObjectName("export_dialog")
        self.setWindowTitle("Export")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(720)

        self._build_ui()
        self.setStyleSheet(StyleFactory.get_export_dialog_qss())
        self._format_buttons["zip"].setChecked(True)
        self._scope_buttons["all"].setChecked(True)
        self._sync_controls(force_path=True)
        self.resize(720, self.sizeHint().height())

    @property
    def request(self):
        export_format = self._selected_format()
        return {
            "format": export_format,
            "selected_only": self._selected_scope() == "selected",
            "path": self._path_edit.text().strip(),
            "encrypt": export_format == "zip" and self._encrypt_check.isChecked(),
            "password": (
                self._password_edit.text()
                if export_format == "zip" and self._encrypt_check.isChecked()
                else None
            ),
        }

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setVerticalSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        container = QWidget()
        container.setObjectName("export_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(16)
        outer.addWidget(container)

        header = QWidget()
        header.setObjectName("export_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_copy = QVBoxLayout()
        header_copy.setContentsMargins(0, 0, 0, 0)
        header_copy.setSpacing(3)
        title = QLabel("Export case")
        title.setObjectName("export_title")
        header_copy.addWidget(title)
        subtitle = QLabel(
            f"Create a portable copy of {self._case_name}."
        )
        subtitle.setObjectName("export_subtitle")
        subtitle.setWordWrap(True)
        header_copy.addWidget(subtitle)
        header_layout.addLayout(header_copy, 1)

        close_button = QPushButton()
        close_button.setObjectName("export_close")
        close_button.setIcon(SvgIcons.get_icon("close"))
        close_button.setIconSize(QSize(18, 18))
        close_button.setToolTip("Cancel and close")
        close_button.setAccessibleName("Cancel export and close")
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)
        layout.addWidget(header)

        format_header = QHBoxLayout()
        format_header.setContentsMargins(0, 0, 0, 0)
        format_header.addWidget(self._section_label("Export format"))
        format_header.addStretch(1)
        format_help = QLabel("Choose how the case will be packaged")
        format_help.setObjectName("export_section_hint")
        format_header.addWidget(format_help)
        layout.addLayout(format_header)

        formats = QFrame()
        formats.setObjectName("export_format_grid")
        formats_layout = QHBoxLayout(formats)
        formats_layout.setContentsMargins(0, 0, 0, 0)
        formats_layout.setSpacing(10)
        self._format_group = QButtonGroup(self)
        self._format_group.setExclusive(True)
        self._format_buttons = {}
        self._format_choices = {}
        for export_format, metadata in self.FORMATS.items():
            choice = _FormatChoice(
                metadata["extension_label"],
                metadata["title"],
                metadata["description"],
            )
            choice.radio.toggled.connect(self._sync_controls)
            self._format_group.addButton(choice.radio)
            self._format_buttons[export_format] = choice.radio
            self._format_choices[export_format] = choice
            formats_layout.addWidget(choice, 1)
        layout.addWidget(formats)

        layout.addWidget(self._section_label("Export options"))
        options_panel = QFrame()
        options_panel.setObjectName("export_options_panel")
        options_row = QHBoxLayout(options_panel)
        options_row.setContentsMargins(14, 12, 14, 13)
        options_row.setSpacing(16)

        scope_block = QWidget()
        scope_block.setObjectName("export_option_block")
        scope_layout = QVBoxLayout(scope_block)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.setSpacing(8)
        scope_layout.addWidget(self._section_label("Content"))
        scope_buttons = QHBoxLayout()
        scope_buttons.setSpacing(6)
        self._scope_group = QButtonGroup(self)
        self._scope_group.setExclusive(True)
        self._scope_buttons = {}
        for label, value in (
            ("All nodes", "all"),
            (f"Selected ({self._selected_count})", "selected"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("scopeChoice", True)
            button.toggled.connect(self._sync_controls)
            self._scope_group.addButton(button)
            self._scope_buttons[value] = button
            scope_buttons.addWidget(button, 1)
        self._scope_buttons["selected"].setEnabled(self._selected_count > 0)
        scope_layout.addLayout(scope_buttons)
        self._scope_hint = QLabel()
        self._scope_hint.setObjectName("export_hint")
        self._scope_hint.setWordWrap(True)
        scope_layout.addWidget(self._scope_hint)
        options_row.addWidget(scope_block, 1)

        vertical_separator = QFrame()
        vertical_separator.setObjectName("export_vertical_separator")
        vertical_separator.setFrameShape(QFrame.Shape.VLine)
        options_row.addWidget(vertical_separator)

        self._format_panel = QWidget()
        self._format_panel.setObjectName("export_option_block")
        format_layout = QVBoxLayout(self._format_panel)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(8)
        self._format_options_title = self._section_label("Archive protection")
        format_layout.addWidget(self._format_options_title)
        self._encrypt_check = QCheckBox("Protect archive with a password")
        self._encrypt_check.setAccessibleDescription(
            "Encrypts the ZIP archive using AES-256."
        )
        self._encrypt_check.toggled.connect(self._sync_controls)
        format_layout.addWidget(self._encrypt_check)

        self._password_row = QWidget()
        password_layout = QHBoxLayout(self._password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        password_widget, self._password_edit = self._password_input("Password")
        confirm_widget, self._confirm_edit = self._password_input("Confirm password")
        password_layout.addWidget(password_widget, 1)
        password_layout.addWidget(confirm_widget, 1)
        format_layout.addWidget(self._password_row)

        self._format_hint = QLabel()
        self._format_hint.setObjectName("export_hint")
        self._format_hint.setWordWrap(True)
        format_layout.addWidget(self._format_hint)
        options_row.addWidget(self._format_panel, 1)
        layout.addWidget(options_panel)

        save_header = QHBoxLayout()
        save_header.setContentsMargins(0, 0, 0, 0)
        save_header.addWidget(self._section_label("Save to"))
        save_header.addStretch(1)
        self._destination_hint = QLabel()
        self._destination_hint.setObjectName("export_section_hint")
        save_header.addWidget(self._destination_hint)
        layout.addLayout(save_header)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path_edit = QLineEdit()
        self._path_edit.setObjectName("export_path")
        self._path_edit.setPlaceholderText("Choose an export file")
        self._path_edit.textEdited.connect(self._mark_path_edited)
        path_row.addWidget(self._path_edit, 1)
        browse = QPushButton("Choose file…")
        browse.setObjectName("export_browse")
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        self._validation = QLabel()
        self._validation.setObjectName("export_validation")
        self._validation.setWordWrap(True)
        self._validation.hide()
        layout.addWidget(self._validation)

        layout.addWidget(self._separator())
        footer = QWidget()
        footer.setObjectName("export_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        self._export_summary = QLabel()
        self._export_summary.setObjectName("export_summary")
        footer_layout.addWidget(self._export_summary)
        footer_layout.addStretch(1)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("export_cancel")
        cancel.clicked.connect(self.reject)
        footer_layout.addWidget(cancel)
        self._export_button = QPushButton("Export")
        self._export_button.setObjectName("export_apply")
        self._export_button.setDefault(True)
        self._export_button.clicked.connect(self._validate_and_accept)
        footer_layout.addWidget(self._export_button)
        layout.addWidget(footer)

    @staticmethod
    def _section_label(text):
        label = QLabel(text)
        label.setProperty("sectionTitle", True)
        return label

    @staticmethod
    def _separator():
        separator = QFrame()
        separator.setObjectName("export_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator

    @staticmethod
    def _password_input(label_text):
        container = QWidget()
        container.setObjectName("export_password_field")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("export_field_label")
        layout.addWidget(label)
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText("Enter password")
        field.setAccessibleName(label_text)
        field.setMaxLength(256)
        label.setBuddy(field)
        layout.addWidget(field)
        return container, field

    def _selected_format(self):
        for export_format, button in self._format_buttons.items():
            if button.isChecked():
                return export_format
        return "zip"

    def _selected_scope(self):
        return "selected" if self._scope_buttons["selected"].isChecked() else "all"

    def _sync_controls(self, *_args, force_path=False):
        export_format = self._selected_format()
        selected = self._selected_scope() == "selected"
        zip_mode = export_format == "zip"
        encrypted = zip_mode and self._encrypt_check.isChecked()

        self._format_options_title.setText(
            "Archive protection" if zip_mode else "About this format"
        )
        self._encrypt_check.setVisible(zip_mode)
        self._password_row.setVisible(encrypted)

        if zip_mode:
            self._format_hint.setText(
                "AES-256 encrypted archives may require 7-Zip or WinZip. "
                "The password is never saved."
                if encrypted
                else "Not protected. Anyone with the archive can read its text and media."
            )
        elif export_format == "html":
            estimate = self._html_estimates.get("selected" if selected else "all", 0)
            estimate_label = self._format_size(estimate) if estimate else "unknown size"
            self._format_hint.setText(
                f"Estimated size: {estimate_label}. Media is embedded for offline use."
            )
        else:
            self._format_hint.setText(
                "Only text nodes are exported; images and videos are omitted."
            )

        if selected:
            count = self._selected_text_count if export_format == "md" else self._selected_count
            noun = "text node" if export_format == "md" else "node"
            self._scope_hint.setText(f"Will export {count} selected {noun}{'' if count == 1 else 's'}.")
        elif export_format == "md":
            self._scope_hint.setText("All text nodes will be exported.")
        else:
            self._scope_hint.setText("The complete case will be exported.")

        for choice_format, choice in self._format_choices.items():
            choice.set_selected(choice_format == export_format)

        metadata = self.FORMATS[export_format]
        scope_label = (
            f"{self._selected_count} selected"
            if selected
            else "All nodes"
        )
        self._destination_hint.setText(metadata["extension"].upper())
        self._export_summary.setText(f"{metadata['title']}  ·  {scope_label}")
        self._export_button.setText(f"Export {metadata['extension']}")

        if force_path or not self._path_was_edited or self._path_edit.text() == self._last_generated_path:
            self._set_generated_path(export_format)
        elif self._path_edit.text().strip():
            self._path_edit.setText(
                self._normalized_path(self._path_edit.text(), export_format)
            )
        QTimer.singleShot(0, self._fit_to_content)

    def _fit_to_content(self):
        layout = self.layout()
        if layout is None:
            return
        layout.activate()
        self.updateGeometry()
        target_width = max(self.minimumWidth(), self.width() or 720)
        self.resize(target_width, self.sizeHint().height())

    def _set_generated_path(self, export_format):
        metadata = self.FORMATS[export_format]
        filename = (
            f"{self._case_name}-KryptoNote-{metadata['suffix']}-"
            f"{self._date_label}{metadata['extension']}"
        )
        path = str(self._default_directory / filename)
        self._last_generated_path = path
        self._path_edit.setText(path)

    def _mark_path_edited(self, _text):
        self._path_was_edited = True

    def _browse(self):
        export_format = self._selected_format()
        metadata = self.FORMATS[export_format]
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export",
            self._normalized_path(self._path_edit.text(), export_format),
            metadata["filter"],
        )
        if not path:
            return
        self._path_was_edited = True
        self._path_edit.setText(self._normalized_path(path, export_format))

    def _normalized_path(self, value, export_format):
        metadata = self.FORMATS[export_format]
        path = Path(value.strip() or self._default_directory)
        if path.suffix.lower() != metadata["extension"]:
            path = path.with_suffix(metadata["extension"])
        return str(path)

    def _validate_and_accept(self):
        export_format = self._selected_format()
        selected = self._selected_scope() == "selected"
        if selected and self._selected_count == 0:
            self._show_error("Select at least one node first.")
            return
        if selected and export_format == "md" and self._selected_text_count == 0:
            self._show_error("The selection contains no text nodes.")
            return
        path = self._path_edit.text().strip()
        if not path:
            self._show_error("Choose where to save the export.")
            return
        path = self._normalized_path(path, export_format)
        if Path(path).exists() and Path(path).is_dir():
            self._show_error("Choose a file, not a directory.")
            return
        self._path_edit.setText(path)
        if export_format == "zip" and self._encrypt_check.isChecked():
            password = self._password_edit.text()
            if not password:
                self._show_error("Enter an archive password.")
                return
            if password != self._confirm_edit.text():
                self._show_error("Passwords do not match.")
                return
        self._validation.hide()
        self.accept()

    def _show_error(self, message):
        self._validation.setText(message)
        self._validation.show()
        QTimer.singleShot(0, self._fit_to_content)

    @staticmethod
    def _format_size(size):
        value = float(max(0, int(size or 0)))
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return "0 B"

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 64:
            self._dragging = True
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)
