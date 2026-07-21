from PySide6.QtCore import QPoint, QSize, Qt, QSignalBlocker, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.gui.theme.icons import SvgIcons
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.theme.style_factory import StyleFactory
from KryptoNote.gui.theme.theme_manager import (
    ACCENT_PRESETS,
    DEFAULT_ACCENT,
    TONE_ANCHORS,
    TONE_IDS,
    TONE_LABELS,
    ThemeManager,
    contrast_ratio,
    get_theme_manager,
)


class ThemedComboBox(QComboBox):
    """Combo box with a palette-aware arrow instead of the native glyph."""

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = Palette.TEXT_DIM if self.isEnabled() else Palette.TEXT_DISABLED
        pen = QPen(QColor(color), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        center_x = self.width() - 16
        center_y = self.height() // 2
        painter.drawLine(center_x - 4, center_y - 2, center_x, center_y + 2)
        painter.drawLine(center_x, center_y + 2, center_x + 4, center_y - 2)


class ThemeDialog(QDialog):
    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self._manager = manager or get_theme_manager()
        self._original = self._manager.settings
        self._draft = self._original
        self._applied = False
        self._dragging = False
        self._drag_start = QPoint()
        self._pending_color = None

        self.setObjectName("theme_dialog")
        self.setWindowTitle("Theme & Appearance")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(720, 520)
        self.setMinimumSize(640, 520)

        self._color_timer = QTimer(self)
        self._color_timer.setSingleShot(True)
        self._color_timer.setInterval(33)
        self._color_timer.timeout.connect(self._flush_custom_color)

        self._build_ui()
        self._manager.appearanceChanged.connect(self._refresh_theme)
        self._sync_controls()
        self._refresh_theme()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("theme_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)
        outer.addWidget(container)

        header = QWidget()
        header.setObjectName("theme_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Theme & Appearance")
        title.setObjectName("theme_title")
        header_layout.addWidget(title, 1)

        close_button = QPushButton()
        close_button.setObjectName("theme_close")
        close_button.setIcon(SvgIcons.get_icon("close"))
        close_button.setIconSize(QSize(18, 18))
        close_button.setToolTip("Cancel and close")
        close_button.setAccessibleName("Cancel theme changes and close")
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)
        self._close_button = close_button
        layout.addWidget(header)

        settings = QWidget()
        settings.setObjectName("theme_settings")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(7)
        self._build_tone_section(settings_layout)
        self._separator(settings_layout)
        self._build_accent_section(settings_layout)
        self._separator(settings_layout)
        self._build_connections_section(settings_layout)
        self._separator(settings_layout)
        self._build_grid_section(settings_layout)
        layout.addWidget(settings, 1)

        footer = QWidget()
        footer.setObjectName("theme_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        reset_all = QPushButton("Reset all")
        reset_all.setAccessibleName("Reset all appearance settings")
        reset_all.clicked.connect(self._reset_all)
        footer_layout.addWidget(reset_all)
        footer_layout.addStretch()

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        footer_layout.addWidget(cancel)

        apply_button = QPushButton("Apply")
        apply_button.setObjectName("theme_apply")
        apply_button.setDefault(True)
        apply_button.clicked.connect(self._apply_and_accept)
        footer_layout.addWidget(apply_button)
        layout.addWidget(footer)

    def _build_tone_section(self, layout):
        self._section_header(layout, "Brightness", self._reset_tone)
        grid = QGridLayout()
        grid.setSpacing(6)
        self._tone_group = QButtonGroup(self)
        self._tone_group.setExclusive(True)
        self._tone_buttons = {}
        for index, tone in enumerate(TONE_IDS):
            button = QPushButton(TONE_LABELS[tone])
            button.setCheckable(True)
            button.setAccessibleName(f"Theme brightness {TONE_LABELS[tone]}")
            button.clicked.connect(
                lambda checked=False, value=tone: checked
                and self._set_draft(tone=value)
            )
            self._tone_group.addButton(button)
            self._tone_buttons[tone] = button
            grid.addWidget(button, index // 4, index % 4)
        layout.addLayout(grid)

    def _build_accent_section(self, layout):
        self._section_header(layout, "Accent color", self._reset_accent)
        grid = QGridLayout()
        grid.setSpacing(8)
        self._accent_group = QButtonGroup(self)
        self._accent_group.setExclusive(True)
        self._accent_buttons = {}
        for index, (name, color) in enumerate(ACCENT_PRESETS.items()):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setAccessibleName(f"Accent preset {name}")
            button.clicked.connect(
                lambda checked=False, value=color: checked
                and self._set_draft(accent_seed=value)
            )
            self._accent_group.addButton(button)
            self._accent_buttons[color] = button
            grid.addWidget(button, 0, index)
        layout.addLayout(grid)

        self._custom_color_button = QPushButton()
        self._custom_color_button.clicked.connect(self._choose_custom_color)
        layout.addWidget(self._custom_color_button)

    def _build_connections_section(self, layout):
        self._section_header(layout, "Connections", self._reset_connections)

        controls = QWidget()
        controls.setObjectName("theme_settings")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        shape = QWidget()
        shape.setObjectName("theme_settings")
        shape_layout = QVBoxLayout(shape)
        shape_layout.setContentsMargins(0, 0, 0, 0)
        shape_layout.setSpacing(5)
        shape_label = QLabel("Shape")
        shape_label.setProperty("controlLabel", True)
        shape_layout.addWidget(shape_label)
        style_row, self._style_group, self._style_buttons = self._choice_row(
            (("Curved", "curved"), ("Straight", "straight")),
            "Connection shape",
            lambda value: self._set_draft(connection_style=value),
        )
        shape_layout.addWidget(style_row)
        controls_layout.addWidget(shape, 1)

        thickness = QWidget()
        thickness.setObjectName("theme_settings")
        thickness_layout = QVBoxLayout(thickness)
        thickness_layout.setContentsMargins(0, 0, 0, 0)
        thickness_layout.setSpacing(5)
        thickness_label = QLabel("Thickness at 100%")
        thickness_label.setProperty("controlLabel", True)
        thickness_layout.addWidget(thickness_label)
        self._thickness = ThemedComboBox()
        self._thickness.setObjectName("theme_thickness")
        self._thickness.addItem("Thin — 1.1 px", "thin")
        self._thickness.addItem("Normal — 1.5 px", "normal")
        self._thickness.addItem("Thick — 2.2 px", "thick")
        self._thickness.currentIndexChanged.connect(self._on_thickness_changed)
        thickness_layout.addWidget(self._thickness)
        controls_layout.addWidget(thickness, 1)

        layout.addWidget(controls)

    def _build_grid_section(self, layout):
        self._section_header(layout, "Grid intensity", self._reset_grid)
        row, self._grid_group, self._grid_buttons = self._choice_row(
            (
                ("Off", "off"),
                ("Subtle", "subtle"),
                ("Normal", "normal"),
                ("Strong", "strong"),
                ("Maximum", "maximum"),
            ),
            "Grid intensity",
            lambda value: self._set_draft(grid_intensity=value),
        )
        layout.addWidget(row)

    def _choice_row(self, choices, accessible_prefix, callback):
        widget = QWidget()
        widget.setObjectName("theme_settings")
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        group = QButtonGroup(self)
        group.setExclusive(True)
        buttons = {}
        for label, value in choices:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAccessibleName(f"{accessible_prefix}: {label}")
            button.clicked.connect(
                lambda checked=False, item=value: checked and callback(item)
            )
            group.addButton(button)
            buttons[value] = button
            row.addWidget(button, 1)
        return widget, group, buttons

    @staticmethod
    def _separator(layout):
        separator = QFrame()
        separator.setObjectName("theme_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

    @staticmethod
    def _section_header(layout, title, reset_callback):
        row = QHBoxLayout()
        label = QLabel(title)
        label.setProperty("sectionTitle", True)
        row.addWidget(label)
        row.addStretch()
        reset = QPushButton("Reset")
        reset.setProperty("sectionReset", True)
        reset.setAccessibleName(f"Reset {title.lower()} to default")
        reset.clicked.connect(reset_callback)
        row.addWidget(reset)
        layout.addLayout(row)

    def _set_draft(self, **changes):
        self._draft = self._draft.updated(**changes)
        self._manager.preview(self._draft)
        self._sync_controls()

    def _on_thickness_changed(self, index):
        value = self._thickness.itemData(index)
        if value:
            self._set_draft(connection_thickness=value)

    def _reset_tone(self):
        self._set_draft(tone="dark_2")

    def _reset_accent(self):
        self._set_draft(accent_seed=DEFAULT_ACCENT)

    def _reset_connections(self):
        self._set_draft(connection_style="curved", connection_thickness="normal")

    def _reset_grid(self):
        self._set_draft(grid_intensity="normal")

    def _reset_all(self):
        self._draft = ThemeManager.defaults()
        self._manager.preview(self._draft)
        self._sync_controls()

    def _choose_custom_color(self):
        previous = self._draft.accent_seed
        dialog = QColorDialog(QColor(previous), self)
        dialog.setWindowTitle("Custom accent color")
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.currentColorChanged.connect(self._queue_custom_color)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self._queue_custom_color(dialog.selectedColor())
            self._flush_custom_color()
        else:
            self._color_timer.stop()
            self._pending_color = None
            self._set_draft(accent_seed=previous)

    def _queue_custom_color(self, color):
        if not color.isValid():
            return
        self._pending_color = color.name(QColor.NameFormat.HexRgb)
        if not self._color_timer.isActive():
            self._color_timer.start()

    def _flush_custom_color(self):
        if self._pending_color is None:
            return
        color, self._pending_color = self._pending_color, None
        self._set_draft(accent_seed=color)

    def _sync_controls(self):
        blockers = []
        for button in (
            list(self._tone_buttons.values())
            + list(self._accent_buttons.values())
            + list(self._style_buttons.values())
            + list(self._grid_buttons.values())
        ):
            blockers.append(QSignalBlocker(button))

        self._tone_buttons[self._draft.tone].setChecked(True)
        for color, button in self._accent_buttons.items():
            button.setChecked(self._draft.accent_seed == color)
        self._style_buttons[self._draft.connection_style].setChecked(True)
        self._grid_buttons[self._draft.grid_intensity].setChecked(True)

        blockers.append(QSignalBlocker(self._thickness))
        index = self._thickness.findData(self._draft.connection_thickness)
        if index >= 0:
            self._thickness.setCurrentIndex(index)

        self._custom_color_button.setText(
            f"Custom color…   {self._draft.accent_seed.upper()}"
        )
        self._style_swatch_buttons()

    def _style_swatch_buttons(self):
        active_border = Palette.ACCENT_MAIN
        for tone, button in self._tone_buttons.items():
            background = TONE_ANCHORS[tone]
            foreground = (
                "#111111"
                if contrast_ratio("#111111", background)
                >= contrast_ratio("#ffffff", background)
                else "#ffffff"
            )
            border = active_border if tone == self._draft.tone else Palette.BORDER_DEFAULT
            width = 2 if tone == self._draft.tone else 1
            button.setStyleSheet(
                f"QPushButton {{ background:{background}; color:{foreground}; "
                f"border:{width}px solid {border}; border-radius:5px; }} "
                f"QPushButton:hover {{ border:2px solid {Palette.BORDER_HOVER}; }} "
                f"QPushButton:focus {{ border:2px solid {Palette.TEXT_MAIN}; }}"
            )

        for color, button in self._accent_buttons.items():
            values = self._manager.palette_for(
                self._draft.updated(accent_seed=color)
            )
            selected = color == self._draft.accent_seed
            border = Palette.TEXT_MAIN if selected else Palette.BORDER_DEFAULT
            width = 2 if selected else 1
            button.setStyleSheet(
                f"QPushButton {{ background:{values['ACCENT_MAIN']}; "
                f"color:{values['ON_ACCENT']}; border:{width}px solid {border}; "
                "border-radius:5px; } "
                f"QPushButton:hover {{ border:2px solid {Palette.BORDER_HOVER}; }} "
                f"QPushButton:focus {{ border:2px solid {values['ON_ACCENT']}; }}"
            )

    def _refresh_theme(self, *_args):
        self.setStyleSheet(StyleFactory.get_theme_dialog_qss())
        self._close_button.setIcon(SvgIcons.get_icon("close"))
        self._style_swatch_buttons()

    def _apply_and_accept(self):
        self._color_timer.stop()
        self._flush_custom_color()
        self._manager.commit(self._draft)
        self._applied = True
        super().accept()

    def reject(self):
        self._color_timer.stop()
        self._pending_color = None
        if not self._applied:
            self._manager.preview(self._original)
            self._draft = self._original
        super().reject()

    def closeEvent(self, event):
        if not self._applied:
            self._manager.preview(self._original)
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 70:
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

