from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme import Theme
from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class KeybindsDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.configure_dialog_chrome("All Keybinds")
        self.setFixedSize(900, 660)
        self.setStyleSheet(self._style())

        self._init_ui()
        self._setup_window_drag(drag_height=72, drag_handles=[self._drag_handle])

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("about_container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(26, 22, 26, 26)
        container_layout.setSpacing(12)

        header = QWidget()
        self._drag_handle = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("All Keybinds")
        title.setObjectName("keybinds_title")
        header_layout.addWidget(title, 1)

        btn_close = QPushButton()
        btn_close.setIcon(SvgIcons.get_icon("close"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setToolTip("Close")
        btn_close.setAccessibleName("Close")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedSize(40, 40)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)
        container_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("keybinds_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("keybinds_content")
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(20)

        left_col = self._column_widget(self._left_sections())
        right_col = self._column_widget(self._right_sections())
        columns.addWidget(left_col, 1)
        columns.addWidget(right_col, 1)

        scroll.setWidget(content)
        container_layout.addWidget(scroll, 1)
        main_layout.addWidget(container)

    def _column_widget(self, sections):
        column = QWidget()
        column.setObjectName("keybinds_column")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        for section in sections:
            layout.addWidget(self._section_widget(*section))
        layout.addStretch()
        return column

    def _section_widget(self, title, rows, mode_text=None):
        frame = QFrame()
        frame.setObjectName("keybinds_section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        heading = QLabel(title)
        heading.setObjectName("keybinds_heading")
        layout.addWidget(heading)

        if mode_text:
            mode = QLabel(mode_text)
            mode.setObjectName("keybinds_mode")
            mode.setWordWrap(True)
            mode.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(mode)

        for keys, description in rows:
            key_label = QLabel(" ".join(self._key(key) for key in keys))
            key_label.setObjectName("keybinds_keys")
            key_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(key_label)

            desc_label = QLabel(description)
            desc_label.setObjectName("keybinds_desc")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

            line = QFrame()
            line.setObjectName("keybinds_line")
            line.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(line)

        return frame

    @staticmethod
    def _key(text):
        return (
            "<span style='background-color:#26282b; color:#ffffff; "
            "border:1px solid #464b52; border-radius:5px; "
            "padding:2px 7px; font-weight:700;'>"
            f"{text}</span>"
        )

    @staticmethod
    def _left_sections():
        return [
            (
                "General",
                [
                    (["Ctrl", "S"], "Save database changes. In the text editor this saves the edited note instead."),
                    (["Ctrl", "F"], "Open the search panel and focus the search field."),
                    (["Ctrl", "A"], "Select all nodes on the canvas."),
                    (["Arrow keys"], "Hold to move the canvas viewport smoothly."),
                    (["Enter"], "Run search. Press again to jump through results one by one."),
                    (["Esc"], "Clear canvas selection, close the active search panel, or cancel the active text editor."),
                    (["G"], "Toggle snap to grid."),
                ],
            ),
            (
                "Create",
                [
                    (["Ctrl", "N"], "Create a new text note at the viewport center."),
                    (["Ctrl", "M"], "Import image media nodes."),
                    (["Ctrl", "Shift", "M"], "Import video media nodes."),
                ],
            ),
            (
                "Clipboard & History",
                [
                    (["Ctrl", "C"], "Copy selected nodes to the internal clipboard."),
                    (["Ctrl", "V"], "Paste nodes from the internal clipboard."),
                    (["Ctrl", "Shift", "C"], "Copy selected text and photos to the system clipboard."),
                    (["Ctrl", "Shift", "V"], "Paste system text or an image as nodes."),
                    (["Ctrl", "Z"], "Undo the last duplicate or internal paste."),
                    (["Ctrl", "Y"], "Redo the last undone duplicate or internal paste."),
                    (["Ctrl", "Shift", "Z"], "Redo on platforms using the alternate shortcut."),
                ],
            ),
            (
                "Editor",
                [
                    (["Ctrl", "S"], "Save text editor changes and close the editor."),
                    (["Ctrl", "Enter"], "Save text editor changes and close the editor."),
                    (["Enter"], "When the title field is focused, move focus to the body text."),
                    (["Esc"], "Cancel edits. If the draft is empty, delete the draft note."),
                ],
            ),
        ]

    def _right_sections(self):
        return [
            (
                "Mouse",
                [
                    (["LMB", "drag"], "Move nodes normally. Move a frame only by its border; locked frames carry contained nodes."),
                    (["MMB", "drag"], "Pan the canvas."),
                    (["Right click"], "Open node or link context menu."),
                    (["Resize handle", "drag"], "Resize a node or frame from its bottom-right corner."),
                    (["Ctrl", "mouse wheel"], "Zoom around the cursor."),
                ],
            ),
            (
                "Selection Mode",
                [
                    (["Ctrl", "LMB", "drag"], "Draw a rubber-band selection rectangle."),
                    (["Ctrl", "click node"], "Add or remove a node from the current selection."),
                    (["Delete"], "Delete selected nodes with confirmation."),
                    (["Shift", "Delete"], "Delete selected nodes without confirmation."),
                ],
                f'Selection mode is active while holding {self._key("Ctrl")}. Drag on empty canvas to draw a selection rectangle.',
            ),
            (
                "Link Mode",
                [
                    (["Shift", "click nodes"], "Hold Shift and click two nodes to create a link between them."),
                    (["Shift", "RMB", "drag"], "Hold Shift, hold right mouse button, and move over links to erase them. Do not just click: keep the button held and sweep over links."),
                ],
                f'Link mode is active while holding {self._key("Shift")}. For erasing links with {self._key("Shift")} {self._key("RMB")}, hold the right mouse button and move over links.',
            ),
        ]

    @staticmethod
    def _style():
        return Theme.Styles.get_about_dialog_qss() + """
            QLabel#keybinds_title {
                background: transparent;
                border: none;
                color: #e6158b;
                font-size: 28px;
                font-weight: 900;
            }
            QScrollArea#keybinds_scroll,
            QWidget#keybinds_content,
            QWidget#keybinds_column {
                background: #1e1e1e;
                border: none;
            }
            QFrame#keybinds_section {
                background: #1e1e1e;
                border: 1px solid #34383d;
                border-radius: 8px;
            }
            QLabel#keybinds_heading {
                color: #e6158b;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#keybinds_mode {
                color: #a8adb5;
                font-size: 13px;
            }
            QLabel#keybinds_keys {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#keybinds_desc {
                color: #d9dde3;
                font-size: 13px;
            }
            QFrame#keybinds_line {
                color: #34383d;
                background: #34383d;
                border: none;
                max-height: 1px;
            }
            QScrollArea#keybinds_scroll QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 2px 8px 0;
            }
            QScrollArea#keybinds_scroll QScrollBar::handle:vertical {
                background: #5a5a5a;
                border-radius: 4px;
                min-height: 32px;
            }
            QScrollArea#keybinds_scroll QScrollBar::add-line:vertical,
            QScrollArea#keybinds_scroll QScrollBar::sub-line:vertical {
                height: 0;
            }
        """
