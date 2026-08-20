from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class KeybindsDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._section_entries = []
        self.configure_dialog_chrome("Keyboard Shortcuts")
        self.setFixedSize(900, 680)
        self.setStyleSheet(self._style())

        self._init_ui()
        self._setup_window_drag(
            drag_height=68,
            drag_handles=[self._drag_handle],
        )

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("keybinds_container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 20, 24, 22)
        container_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("keybinds_header")
        self._drag_handle = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        title_block = QWidget()
        title_block.setObjectName("keybinds_title_block")
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title = QLabel("Keyboard shortcuts")
        title.setObjectName("keybinds_title")
        title_layout.addWidget(title)

        subtitle = QLabel(
            "Find commands, canvas gestures, and editor controls."
        )
        subtitle.setObjectName("keybinds_subtitle")
        title_layout.addWidget(subtitle)
        header_layout.addWidget(title_block, 1)

        btn_close = QPushButton()
        btn_close.setIcon(SvgIcons.get_icon("close"))
        btn_close.setIconSize(QSize(16, 16))
        btn_close.setToolTip("Close")
        btn_close.setAccessibleName("Close keyboard shortcuts")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedSize(34, 34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignTop)
        container_layout.addWidget(header)
        container_layout.addSpacing(16)

        self._search = QLineEdit()
        self._search.setObjectName("keybinds_search")
        self._search.setPlaceholderText("Search shortcuts")
        self._search.setAccessibleName("Search keyboard shortcuts")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(38)
        self._search.addAction(
            SvgIcons.get_icon("search"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search.textChanged.connect(self._filter_shortcuts)
        container_layout.addWidget(self._search)
        container_layout.addSpacing(14)

        separator = QFrame()
        separator.setObjectName("keybinds_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        container_layout.addWidget(separator)
        container_layout.addSpacing(12)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("keybinds_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        content.setObjectName("keybinds_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(14)

        for section in self._sections():
            section_widget, entry = self._section_widget(*section)
            self._section_entries.append(entry)
            content_layout.addWidget(section_widget)

        self._empty_state = QLabel("No shortcuts match your search.")
        self._empty_state.setObjectName("keybinds_empty")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setMinimumHeight(180)
        self._empty_state.hide()
        content_layout.addWidget(self._empty_state)
        content_layout.addStretch()

        self._scroll.setWidget(content)
        container_layout.addWidget(self._scroll, 1)
        main_layout.addWidget(container)

        self._find_shortcut = QShortcut(
            QKeySequence(QKeySequence.StandardKey.Find), self
        )
        self._find_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._find_shortcut.activated.connect(self._focus_search)
        self._search.setFocus(Qt.FocusReason.OtherFocusReason)

    def _section_widget(self, title, rows, mode_text=None):
        frame = QFrame()
        frame.setObjectName("keybinds_section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 8)
        layout.setSpacing(0)

        section_header = QWidget()
        section_header.setObjectName("keybinds_section_header")
        header_layout = QHBoxLayout(section_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("keybinds_heading")
        header_layout.addWidget(heading, 1)

        count_label = QLabel(self._count_text(len(rows)))
        count_label.setObjectName("keybinds_count")
        header_layout.addWidget(count_label)
        layout.addWidget(section_header)

        if mode_text:
            layout.addSpacing(8)
            mode = QLabel(mode_text)
            mode.setObjectName("keybinds_mode")
            mode.setWordWrap(True)
            layout.addWidget(mode)

        layout.addSpacing(6)
        row_entries = []
        for index, (keys, description) in enumerate(rows):
            row = self._shortcut_row(
                keys,
                description,
                show_divider=index < len(rows) - 1,
            )
            layout.addWidget(row)
            searchable = " ".join(
                (title, mode_text or "", " ".join(keys), description)
            ).casefold()
            row_entries.append((row, searchable))

        return frame, {
            "frame": frame,
            "count": count_label,
            "rows": row_entries,
        }

    def _shortcut_row(self, keys, description, *, show_divider):
        row = QWidget()
        row.setObjectName("keybinds_row")
        row.setAccessibleName(f"{' plus '.join(keys)}: {description}")
        outer_layout = QVBoxLayout(row)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        body = QWidget()
        body.setObjectName("keybinds_row_body")
        row_layout = QHBoxLayout(body)
        row_layout.setContentsMargins(0, 9, 0, 9)
        row_layout.setSpacing(18)

        desc_label = QLabel(description)
        desc_label.setObjectName("keybinds_desc")
        desc_label.setWordWrap(True)
        desc_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        row_layout.addWidget(desc_label, 1)

        key_group = QWidget()
        key_group.setObjectName("keybinds_key_group")
        key_group.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Preferred,
        )
        key_layout = QHBoxLayout(key_group)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(4)

        for index, key in enumerate(keys):
            if index:
                joiner = QLabel("+")
                joiner.setObjectName("keybinds_joiner")
                joiner.setAlignment(Qt.AlignmentFlag.AlignCenter)
                key_layout.addWidget(joiner)

            keycap = QLabel(key)
            keycap.setObjectName("keybinds_keycap")
            keycap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_layout.addWidget(keycap)

        row_layout.addWidget(
            key_group,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        outer_layout.addWidget(body)

        if show_divider:
            line = QFrame()
            line.setObjectName("keybinds_line")
            line.setFrameShape(QFrame.Shape.HLine)
            outer_layout.addWidget(line)

        return row

    def _filter_shortcuts(self, text):
        query = text.strip().casefold()
        visible_sections = 0

        for section in self._section_entries:
            visible_rows = 0
            for row, searchable in section["rows"]:
                visible = not query or query in searchable
                row.setVisible(visible)
                visible_rows += int(visible)

            section["frame"].setVisible(visible_rows > 0)
            section["count"].setText(self._count_text(visible_rows))
            visible_sections += int(visible_rows > 0)

        self._empty_state.setVisible(visible_sections == 0)
        if query:
            self._scroll.verticalScrollBar().setValue(0)

    def _focus_search(self):
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search.selectAll()

    @staticmethod
    def _count_text(count):
        suffix = "shortcut" if count == 1 else "shortcuts"
        return f"{count} {suffix}"

    @staticmethod
    def _sections():
        return [
            (
                "Canvas & navigation",
                [
                    (["Ctrl", "S"], "Save database changes."),
                    (["Ctrl", "F"], "Open the search panel and focus its query field."),
                    (["Ctrl", "A"], "Select every node on the canvas."),
                    (["Arrow keys"], "Hold to pan the canvas viewport smoothly."),
                    (["G"], "Toggle snap to grid."),
                    (["Esc"], "Clear selection or close the active canvas surface."),
                ],
            ),
            (
                "Command palette",
                [
                    (["Ctrl", "Space"], "Open or close the command palette."),
                    (["Right Shift ×2"], "Press twice quickly to toggle the command palette."),
                    (["Up / Down"], "Move through commands and search results."),
                    (["Home / End"], "Jump to the first or last available result."),
                    (["Page Up / Page Down"], "Move through the result list one page at a time."),
                    (["Tab"], "Complete the selected command name."),
                    (["Enter"], "Run the selected command or open a search result."),
                    (["Esc"], "Close the command palette."),
                ],
            ),
            (
                "Create",
                [
                    (["Ctrl", "N"], "Create a text note at the viewport center."),
                    (["Ctrl", "M"], "Import image media nodes."),
                    (["Ctrl", "Shift", "M"], "Import video media nodes."),
                ],
            ),
            (
                "Clipboard & history",
                [
                    (["Ctrl", "C"], "Copy selected nodes to the internal clipboard."),
                    (["Ctrl", "V"], "Paste nodes from the internal clipboard."),
                    (["Ctrl", "Shift", "C"], "Copy selected text and photos to the system clipboard."),
                    (["Ctrl", "Shift", "V"], "Paste system text or an image as nodes."),
                    (["Ctrl", "Z"], "Undo the last graph action."),
                    (["Ctrl", "Y"], "Redo the last undone graph action."),
                    (["Ctrl", "Shift", "Z"], "Use the alternate redo shortcut."),
                ],
            ),
            (
                "Editing",
                [
                    (["Ctrl", "S"], "Save editor changes and close the editor."),
                    (["Ctrl", "Enter"], "Save editor changes and close the editor."),
                    (["Enter"], "Move from the title field to the body text."),
                    (["Esc"], "Cancel edits; empty draft notes are removed."),
                ],
            ),
            (
                "Mouse & canvas",
                [
                    (["LMB", "drag"], "Move nodes; drag a frame by its border."),
                    (["MMB", "drag"], "Pan the canvas."),
                    (["Right click"], "Open a node or link context menu."),
                    (["Resize handle", "drag"], "Resize a node or frame."),
                    (["Ctrl", "mouse wheel"], "Zoom around the cursor."),
                ],
            ),
            (
                "Selection & links",
                [
                    (["Ctrl", "LMB", "drag"], "Draw a selection rectangle on empty canvas."),
                    (["Ctrl", "click node"], "Add or remove a node from the selection."),
                    (["Delete"], "Delete selected nodes with confirmation."),
                    (["Shift", "Delete"], "Delete selected nodes without confirmation."),
                    (["Shift", "click nodes"], "Click two nodes to create a link."),
                    (["Shift", "RMB", "drag"], "Sweep over links to erase them."),
                ],
                "Hold Ctrl for multi-selection. Hold Shift for linking and link erasing.",
            ),
            (
                "Media viewer",
                [
                    (["Space"], "Play or pause video and audio."),
                    (["Left / Right"], "Seek backward or forward by five seconds."),
                    (["M"], "Mute or unmute playback."),
                    (["Ctrl", "S"], "Save media description changes."),
                    (["Enter"], "Confirm a media title rename."),
                    (["Esc"], "Cancel editing or close the media viewer."),
                ],
            ),
        ]

    @staticmethod
    def _style():
        palette = Theme.Palette
        return f"""
            QDialog {{
                background: transparent;
                color: {palette.TEXT_MAIN};
                font-family: 'Segoe UI';
            }}
            QWidget#keybinds_container {{
                background: {palette.BG_PANEL};
                border: 1px solid {palette.BORDER_DEFAULT};
                border-radius: 12px;
            }}
            QWidget#keybinds_header,
            QWidget#keybinds_title_block,
            QWidget#keybinds_content,
            QWidget#keybinds_section_header,
            QWidget#keybinds_row,
            QWidget#keybinds_row_body,
            QWidget#keybinds_key_group {{
                background: transparent;
                border: none;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLabel#keybinds_title {{
                color: {palette.TEXT_MAIN};
                font-size: 20px;
                font-weight: 600;
            }}
            QLabel#keybinds_subtitle {{
                color: {palette.TEXT_MUTED};
                font-size: 12px;
            }}
            QPushButton#btn_close {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 0;
            }}
            QPushButton#btn_close:hover {{
                background: {palette.BG_CONTROL_HOVER};
                border-color: {palette.BORDER_DEFAULT};
            }}
            QPushButton#btn_close:pressed {{
                background: {palette.BG_CONTROL_PRESSED};
            }}
            QPushButton#btn_close:focus {{
                border-color: {palette.ACCENT_MAIN};
            }}
            QLineEdit#keybinds_search {{
                color: {palette.TEXT_MAIN};
                background: {palette.BG_INPUT};
                border: 1px solid {palette.BORDER_DEFAULT};
                border-radius: 7px;
                padding: 0 10px;
                font-size: 13px;
                selection-color: {palette.TEXT_MAIN};
                selection-background-color: {palette.ACCENT_LOW};
            }}
            QLineEdit#keybinds_search:hover {{
                border-color: {palette.BORDER_HOVER};
            }}
            QLineEdit#keybinds_search:focus {{
                border-color: {palette.ACCENT_MAIN};
            }}
            QFrame#keybinds_separator,
            QFrame#keybinds_line {{
                color: {palette.BORDER_SUBTLE};
                background: {palette.BORDER_SUBTLE};
                border: none;
                min-height: 1px;
                max-height: 1px;
            }}
            QScrollArea#keybinds_scroll,
            QScrollArea#keybinds_scroll > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
            QFrame#keybinds_section {{
                background: {palette.BG_NODE};
                border: 1px solid {palette.BORDER_SUBTLE};
                border-radius: 8px;
            }}
            QLabel#keybinds_heading {{
                color: {palette.TEXT_MAIN};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#keybinds_count {{
                color: {palette.TEXT_MUTED};
                font-size: 11px;
            }}
            QLabel#keybinds_mode {{
                color: {palette.TEXT_DIM};
                background: {palette.BG_CONTROL};
                border: 1px solid {palette.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 7px 9px;
                font-size: 12px;
            }}
            QLabel#keybinds_desc {{
                color: {palette.TEXT_DIM};
                font-size: 13px;
            }}
            QLabel#keybinds_keycap {{
                color: {palette.TEXT_MAIN};
                background: {palette.BG_INPUT};
                border: 1px solid {palette.BORDER_DEFAULT};
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#keybinds_joiner {{
                color: {palette.TEXT_MUTED};
                font-size: 11px;
                padding: 0 1px;
            }}
            QLabel#keybinds_empty {{
                color: {palette.TEXT_MUTED};
                font-size: 13px;
            }}
            QScrollArea#keybinds_scroll QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 2px;
            }}
            QScrollArea#keybinds_scroll QScrollBar::handle:vertical {{
                background: {palette.BORDER_HOVER};
                border-radius: 4px;
                min-height: 36px;
            }}
            QScrollArea#keybinds_scroll QScrollBar::handle:vertical:hover {{
                background: {palette.TEXT_MUTED};
            }}
            QScrollArea#keybinds_scroll QScrollBar::add-line:vertical,
            QScrollArea#keybinds_scroll QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollArea#keybinds_scroll QScrollBar::add-page:vertical,
            QScrollArea#keybinds_scroll QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """
