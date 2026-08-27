from PySide6.QtCore import QRectF, QSize, Qt, QSignalBlocker, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from KryptoNote.core.connection_geometry import (
    connection_path_commands,
)
from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.theme.style_factory import StyleFactory
from KryptoNote.gui.theme.theme_manager import (
    ACCENT_PRESETS,
    AppearanceSettings,
    CONNECTION_WIDTHS,
    DEFAULT_ACCENT,
    DEFAULT_MOTION_MODE,
    TONE_ANCHORS,
    TONE_IDS,
    TONE_LABELS,
    ThemeManager,
    contrast_ratio,
    get_theme_manager,
)
from KryptoNote.gui.theme.typography import (
    SYSTEM_DEFAULT_FONT,
    resolve_font_family,
    system_font_family,
)
from KryptoNote.gui.widgets.dialog_close_button import DialogCloseButton
from KryptoNote.gui.widgets.frameless_window import FramelessWindowDragMixin


class ConnectionStyleButton(QPushButton):
    """Compact connection route preview used as a direct choice control."""

    def __init__(self, label, style, parent=None):
        super().__init__("", parent)
        self._label = label
        self._connection_style = style
        self._preview_width = 1.5
        self._preview_pattern = "solid"
        self._curve_formula = "horizontal"
        self._corner_style = "smooth"
        self.setCheckable(True)
        self.setProperty("connectionStyleButton", True)
        self.setAccessibleName(f"Connection route: {label}")
        self.setToolTip(f"Use {label.lower()} connections")
        self.setMinimumHeight(54)

    def set_preview_appearance(
        self, width, pattern, curve_formula, corner_style
    ):
        self._preview_width = float(width)
        self._preview_pattern = str(pattern)
        self._curve_formula = str(curve_formula)
        self._corner_style = str(corner_style)
        self.update()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(max(112, hint.width()), 54)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        line_color = (
            Palette.ACCENT_MAIN
            if self.isChecked()
            else Palette.TEXT_DIM
        )
        if not self.isEnabled():
            line_color = Palette.TEXT_DISABLED
        pen = QPen(QColor(line_color), self._preview_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if self._preview_pattern == "dashed":
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([5.0, 3.0])
        elif self._preview_pattern == "dotted":
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([1.0, 2.4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        start_x = 12.0
        end_x = max(start_x + 1.0, self.width() - 12.0)
        commands = connection_path_commands(
            self._connection_style,
            start_x,
            8.0,
            end_x,
            27.0,
            self._curve_formula,
            self._corner_style,
            0.22,
        )
        path = QPainterPath()
        for command in commands:
            if command[0] == "M":
                path.moveTo(command[1], command[2])
            elif command[0] == "L":
                path.lineTo(command[1], command[2])
            elif command[0] == "Q":
                path.quadTo(
                    command[1], command[2], command[3], command[4]
                )
            elif command[0] == "C":
                path.cubicTo(
                    command[1],
                    command[2],
                    command[3],
                    command[4],
                    command[5],
                    command[6],
                )
        painter.drawPath(path)

        painter.setPen(
            QColor(Palette.TEXT_MAIN if self.isEnabled() else Palette.TEXT_DISABLED)
        )
        painter.drawText(
            QRectF(4, 32, max(0, self.width() - 8), 18),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )


class ThemeDialog(FramelessWindowDragMixin, QDialog):
    def __init__(self, parent=None, manager=None, project_store=None):
        super().__init__(parent)
        self._manager = manager or get_theme_manager()
        self._project_store = project_store
        self._original_active = self._manager.settings
        self._global_original = self._manager.committed_settings
        self._original_font_family = self._manager.font_family
        self._font_draft = self._original_font_family
        self._original_motion_mode = self._manager.motion_mode
        self._motion_draft = self._original_motion_mode
        profile = (
            self._project_store.load_project_appearance()
            if self._project_store is not None
            else None
        )
        self._scope_original = (
            profile.get("scope", "global") if profile else "global"
        )
        if (
            self._scope_original not in ("global", "project")
            or self._project_store is None
        ):
            self._scope_original = "global"
        self._project_original = self._manager.validate(
            profile.get("settings", {})
            if profile
            else self._global_original
        )
        self._scope = self._scope_original
        self._drafts = {
            "global": self._global_original,
            "project": self._project_original,
        }
        self._draft = self._drafts[self._scope]
        self._applied = False
        self._pending_color = None

        self.setObjectName("theme_dialog")
        self.setWindowTitle("Settings")
        self.configure_dialog_chrome("Settings")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        target_width = 860 if available is None else min(860, available.width() - 32)
        target_height = 560 if available is None else min(560, available.height() - 32)
        self.setFixedSize(max(1, target_width), max(1, target_height))

        self._color_timer = QTimer(self)
        self._color_timer.setSingleShot(True)
        self._color_timer.setInterval(33)
        self._color_timer.timeout.connect(self._flush_custom_color)

        self._build_ui()
        self._manager.appearanceChanged.connect(self._refresh_theme)
        self._manager.preview(self._draft)
        self._sync_controls()
        self._refresh_theme()
        self._setup_window_drag(drag_height=72, drag_handles=[self._drag_handle])

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("theme_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(8)
        outer.addWidget(container)

        header = QWidget()
        self._drag_handle = header
        header.setObjectName("theme_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Settings")
        title.setObjectName("theme_title")
        header_layout.addWidget(title, 1)

        close_button = DialogCloseButton()
        close_button.setObjectName("theme_close")
        close_button.setIconSize(QSize(18, 18))
        close_button.setToolTip("Cancel and close settings")
        close_button.setAccessibleName("Cancel changes and close settings")
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)
        self._close_button = close_button
        layout.addWidget(header)

        body = QWidget()
        body.setObjectName("settings_body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        navigation = QWidget()
        navigation.setObjectName("settings_nav")
        navigation.setFixedWidth(168)
        navigation_layout = QVBoxLayout(navigation)
        navigation_layout.setContentsMargins(8, 8, 8, 8)
        navigation_layout.setSpacing(4)

        self._settings_nav_group = QButtonGroup(self)
        self._settings_nav_group.setExclusive(True)
        self._settings_nav_buttons = []
        for index, (label, accessible_label) in enumerate(
            (
                ("General", "General"),
                ("Theme && Appearance", "Theme & Appearance"),
                ("Canvas", "Canvas"),
            )
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("settingsNav", True)
            button.setAccessibleName(
                f"Settings category: {accessible_label}"
            )
            button.clicked.connect(
                lambda checked=False, page=index: checked
                and self._select_settings_page(page)
            )
            self._settings_nav_group.addButton(button)
            self._settings_nav_buttons.append(button)
            navigation_layout.addWidget(button)
        navigation_layout.addStretch()
        body_layout.addWidget(navigation)

        self._settings_pages = QStackedWidget()
        self._settings_pages.setObjectName("settings_pages")

        general, general_layout = self._settings_page("General")
        self._build_motion_section(general_layout)
        self._separator(general_layout)
        self._build_font_section(general_layout)
        general_layout.addStretch()
        self._settings_pages.addWidget(general)

        appearance, appearance_layout = self._settings_page(
            "Theme & Appearance",
            include_scope=True,
        )
        self._separator(appearance_layout)
        self._build_tone_section(appearance_layout)
        self._separator(appearance_layout)
        self._build_accent_section(appearance_layout)
        appearance_layout.addStretch()
        self._settings_pages.addWidget(appearance)

        canvas, canvas_layout = self._settings_page("Canvas")
        self._build_connections_section(canvas_layout)
        self._separator(canvas_layout)
        self._build_grid_section(canvas_layout)
        canvas_layout.addStretch()
        self._settings_pages.addWidget(canvas)

        body_layout.addWidget(self._settings_pages, 1)
        layout.addWidget(body, 1)
        self._settings_nav_buttons[0].setChecked(True)
        self._select_settings_page(0)

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

    def _settings_page(self, title, include_scope=False):
        page = QWidget()
        page.setObjectName("settings_page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 2, 4, 2)
        page_layout.setSpacing(8)

        heading_row = QHBoxLayout()
        heading_row.setContentsMargins(0, 0, 0, 0)
        heading_row.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName("settings_page_title")
        heading_row.addWidget(heading)
        if include_scope:
            self._build_scope_controls(heading_row)
        else:
            heading_row.addStretch()
        page_layout.addLayout(heading_row)
        return page, page_layout

    def _select_settings_page(self, index):
        index = max(0, min(int(index), self._settings_pages.count() - 1))
        self._settings_pages.setCurrentIndex(index)
        self._settings_nav_buttons[index].setChecked(True)

    def _build_scope_controls(self, row):
        row.addStretch()

        self._scope_group = QButtonGroup(self)
        self._scope_group.setExclusive(True)
        self._scope_buttons = {}
        for text, scope in (("Global", "global"), ("Project", "project")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setProperty("scopeSwitch", True)
            button.setAccessibleName(f"Appearance scope: {text}")
            button.clicked.connect(
                lambda checked=False, value=scope: checked
                and self._switch_scope(value)
            )
            self._scope_group.addButton(button)
            self._scope_buttons[scope] = button
            row.addWidget(button)
        self._scope_buttons["project"].setEnabled(
            self._project_store is not None
        )
        if self._project_store is None:
            self._scope_buttons["project"].setToolTip(
                "Project appearance is available when a project is open"
            )
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

    def _build_font_section(self, layout):
        self._section_header(layout, "Nodes font", self._reset_font)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        self._font_combo = QComboBox()
        self._font_combo.setObjectName("font_combo")
        self._font_combo.setAccessibleName("Global text node font")
        for display, value in self._manager.font_choices():
            self._font_combo.addItem(display, value)
            index = self._font_combo.count() - 1
            if value == SYSTEM_DEFAULT_FONT:
                preview_family = system_font_family()
            else:
                preview_family = value
            self._font_combo.setItemData(
                index,
                QFont(preview_family),
                Qt.ItemDataRole.FontRole,
            )
        if self._font_combo.findData(self._font_draft) < 0:
            self._font_combo.addItem(
                f"{self._font_draft} (unavailable)",
                self._font_draft,
            )
            self._font_combo.setItemData(
                self._font_combo.count() - 1,
                QFont(resolve_font_family(self._font_draft)),
                Qt.ItemDataRole.FontRole,
            )
        self._font_combo.currentIndexChanged.connect(self._on_font_changed)
        row.addWidget(self._font_combo, 1)
        layout.addLayout(row)

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

    def _build_motion_section(self, layout):
        self._section_header(layout, "Motion", self._reset_motion)
        row, self._motion_group, self._motion_buttons = self._choice_row(
            (
                ("System", "system"),
                ("Full", "full"),
                ("Reduced", "reduced"),
                ("Off", "off"),
            ),
            "Motion mode",
            self._set_motion_draft,
        )
        layout.addWidget(row)

    def _build_connections_section(self, layout):
        self._section_header(layout, "Connections", self._reset_connections)

        route_label = QLabel("Routing")
        route_label.setProperty("controlLabel", True)
        layout.addWidget(route_label)

        style_row = QWidget()
        style_row.setObjectName("theme_settings")
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.setSpacing(8)
        self._style_group = QButtonGroup(self)
        self._style_group.setExclusive(True)
        self._style_buttons = {}
        for label, value in (
            ("Curved", "curved"),
            ("Straight", "straight"),
            ("Elbow", "orthogonal"),
        ):
            button = ConnectionStyleButton(label, value)
            button.clicked.connect(
                lambda checked=False, item=value: checked
                and self._set_draft(connection_style=item)
            )
            self._style_group.addButton(button)
            self._style_buttons[value] = button
            style_layout.addWidget(button, 1)
        layout.addWidget(style_row)

        self._route_options = QStackedWidget()
        self._route_options.setObjectName("theme_route_options")
        self._route_option_indexes = {}

        curved_options = QWidget()
        curved_options.setObjectName("theme_settings")
        curved_layout = QHBoxLayout(curved_options)
        curved_layout.setContentsMargins(0, 3, 0, 3)
        curved_layout.setSpacing(12)
        curved_label = QLabel("Curve formula")
        curved_label.setProperty("controlLabel", True)
        curved_layout.addWidget(curved_label)
        (
            curve_formula_row,
            self._curve_formula_group,
            self._curve_formula_buttons,
        ) = self._choice_row(
            (
                ("Horizontal Bézier", "horizontal"),
                ("Adaptive Bézier", "adaptive"),
            ),
            "Connection curve formula",
            lambda value: self._set_draft(connection_curve_formula=value),
        )
        self._curve_formula_buttons["horizontal"].setToolTip(
            "Keeps the familiar left-to-right Bézier flow"
        )
        self._curve_formula_buttons["adaptive"].setToolTip(
            "Turns the control handles for vertical connections"
        )
        curved_layout.addWidget(curve_formula_row, 1)
        self._route_option_indexes["curved"] = (
            self._route_options.addWidget(curved_options)
        )

        straight_options = QWidget()
        straight_options.setObjectName("theme_settings")
        straight_layout = QHBoxLayout(straight_options)
        straight_layout.setContentsMargins(0, 0, 0, 0)
        straight_layout.addStretch()
        self._route_option_indexes["straight"] = (
            self._route_options.addWidget(straight_options)
        )

        corner_options = QWidget()
        corner_options.setObjectName("theme_settings")
        corner_layout = QHBoxLayout(corner_options)
        corner_layout.setContentsMargins(0, 3, 0, 3)
        corner_layout.setSpacing(12)
        corner_label = QLabel("Corner treatment")
        corner_label.setProperty("controlLabel", True)
        corner_layout.addWidget(corner_label)
        (
            corner_row,
            self._corner_group,
            self._corner_buttons,
        ) = self._choice_row(
            (
                ("Sharp", "sharp"),
                ("Tight radius", "tight"),
                ("Smooth", "smooth"),
            ),
            "Connection corner treatment",
            lambda value: self._set_draft(
                connection_corner_style=value
            ),
        )
        corner_layout.addWidget(corner_row, 1)
        corner_index = self._route_options.addWidget(corner_options)
        self._route_option_indexes["orthogonal"] = corner_index
        layout.addWidget(self._route_options)

        controls = QWidget()
        controls.setObjectName("theme_settings")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        thickness = QWidget()
        thickness.setObjectName("theme_settings")
        thickness_layout = QVBoxLayout(thickness)
        thickness_layout.setContentsMargins(0, 0, 0, 0)
        thickness_layout.setSpacing(5)
        thickness_label = QLabel("Thickness")
        thickness_label.setProperty("controlLabel", True)
        thickness_layout.addWidget(thickness_label)
        (
            thickness_row,
            self._thickness_group,
            self._thickness_buttons,
        ) = self._choice_row(
            (
                ("Thin", "thin"),
                ("Normal", "normal"),
                ("Thick", "thick"),
            ),
            "Connection thickness",
            lambda value: self._set_draft(connection_thickness=value),
        )
        self._thickness_buttons["thin"].setToolTip("1.1 px at 100% zoom")
        self._thickness_buttons["normal"].setToolTip("1.5 px at 100% zoom")
        self._thickness_buttons["thick"].setToolTip("2.2 px at 100% zoom")
        thickness_layout.addWidget(thickness_row)
        controls_layout.addWidget(thickness, 1)

        anchors = QWidget()
        anchors.setObjectName("theme_settings")
        anchors_layout = QVBoxLayout(anchors)
        anchors_layout.setContentsMargins(0, 0, 0, 0)
        anchors_layout.setSpacing(5)
        anchors_label = QLabel("Node anchors")
        anchors_label.setProperty("controlLabel", True)
        anchors_layout.addWidget(anchors_label)
        (
            anchor_row,
            self._anchor_group,
            self._anchor_buttons,
        ) = self._choice_row(
            (
                ("Perimeter", "perimeter"),
                ("Side centers", "side_centers"),
            ),
            "Connection node anchors",
            lambda value: self._set_draft(connection_anchor_mode=value),
        )
        self._anchor_buttons["perimeter"].setToolTip(
            "Connect at the nearest point on the node"
        )
        self._anchor_buttons["side_centers"].setToolTip(
            "Connect only from the center of a node side"
        )
        anchors_layout.addWidget(anchor_row)
        controls_layout.addWidget(anchors, 1)

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
        self._drafts[self._scope] = self._draft
        self._manager.preview(self._draft)
        self._sync_controls()

    def _on_font_changed(self, index):
        value = self._font_combo.itemData(index)
        if value is None:
            return
        self._font_draft = str(value)
        self._manager.preview_font_family(self._font_draft)
        self._sync_controls()

    def _set_motion_draft(self, value):
        self._motion_draft = self._manager.preview_motion_mode(value)
        self._sync_controls()

    def _switch_scope(self, scope):
        if scope not in self._drafts or scope == self._scope:
            return
        if scope == "project" and self._project_store is None:
            return
        self._drafts[self._scope] = self._draft
        self._scope = scope
        self._draft = self._drafts[scope]
        self._manager.preview(self._draft)
        self._sync_controls()

    def _reset_tone(self):
        self._set_draft(tone="dark_2")

    def _reset_font(self):
        self._font_draft = SYSTEM_DEFAULT_FONT
        self._manager.reset_font_family()
        self._sync_controls()

    def _reset_accent(self):
        self._set_draft(accent_seed=DEFAULT_ACCENT)

    def _reset_motion(self):
        self._set_motion_draft(DEFAULT_MOTION_MODE)

    def _reset_connections(self):
        defaults = ThemeManager.defaults()
        self._set_draft(
            connection_style=defaults.connection_style,
            connection_thickness=defaults.connection_thickness,
            connection_pattern=defaults.connection_pattern,
            connection_curve_formula=defaults.connection_curve_formula,
            connection_corner_style=defaults.connection_corner_style,
            connection_anchor_mode=defaults.connection_anchor_mode,
        )

    def _reset_grid(self):
        self._set_draft(grid_intensity="normal")

    def _reset_all(self):
        self._draft = ThemeManager.defaults()
        self._drafts[self._scope] = self._draft
        self._manager.preview(self._draft)
        self._font_draft = SYSTEM_DEFAULT_FONT
        self._manager.reset_font_family()
        self._motion_draft = DEFAULT_MOTION_MODE
        self._manager.reset_motion_mode()
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
            + list(self._corner_buttons.values())
            + list(self._grid_buttons.values())
            + list(self._scope_buttons.values())
            + list(self._curve_formula_buttons.values())
            + list(self._thickness_buttons.values())
            + list(self._anchor_buttons.values())
            + list(self._motion_buttons.values())
        ):
            blockers.append(QSignalBlocker(button))
        blockers.append(QSignalBlocker(self._font_combo))

        self._scope_buttons[self._scope].setChecked(True)
        self._motion_buttons[self._motion_draft].setChecked(True)
        self._tone_buttons[self._draft.tone].setChecked(True)
        font_index = self._font_combo.findData(self._font_draft)
        if font_index < 0:
            font_index = self._font_combo.findData(SYSTEM_DEFAULT_FONT)
            self._font_draft = SYSTEM_DEFAULT_FONT
        self._font_combo.setCurrentIndex(font_index)
        for color, button in self._accent_buttons.items():
            button.setChecked(self._draft.accent_seed == color)
        self._style_buttons[self._draft.connection_style].setChecked(True)
        self._grid_buttons[self._draft.grid_intensity].setChecked(True)

        self._thickness_buttons[self._draft.connection_thickness].setChecked(True)
        self._curve_formula_buttons[
            self._draft.connection_curve_formula
        ].setChecked(True)
        self._corner_buttons[self._draft.connection_corner_style].setChecked(True)
        self._anchor_buttons[self._draft.connection_anchor_mode].setChecked(True)

        self._route_options.setCurrentIndex(
            self._route_option_indexes[self._draft.connection_style]
        )

        self._custom_color_button.setText(
            f"Custom color…   {self._draft.accent_seed.upper()}"
        )
        for button in self._style_buttons.values():
            button.set_preview_appearance(
                CONNECTION_WIDTHS[self._draft.connection_thickness],
                self._draft.connection_pattern,
                self._draft.connection_curve_formula,
                self._draft.connection_corner_style,
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
        self._close_button.refresh_icon()
        self._style_swatch_buttons()
        for button in self._style_buttons.values():
            button.update()

    def _apply_and_accept(self):
        self._color_timer.stop()
        self._flush_custom_color()
        self._drafts[self._scope] = self._draft
        global_settings = self._manager.validate(
            self._drafts["global"]
        )
        project_settings = self._manager.validate(
            self._drafts["project"]
        )
        try:
            if self._project_store is not None:
                self._project_store.save_project_appearance(
                    self._scope,
                    {
                        field: getattr(project_settings, field)
                        for field in AppearanceSettings.__dataclass_fields__
                    },
                )
            self._manager.commit(global_settings)
            self._manager.commit_font_family(self._font_draft)
            self._manager.commit_motion_mode(self._motion_draft)
            self._manager.preview(
                project_settings
                if self._scope == "project"
                else global_settings
            )
        except Exception as error:
            self._manager.preview(self._original_active)
            self._manager.preview_font_family(self._original_font_family)
            self._manager.preview_motion_mode(self._original_motion_mode)
            QMessageBox.critical(
                self,
                "Appearance Settings",
                f"Could not save appearance settings:\n{error}",
            )
            return
        self._applied = True
        super().accept()

    def reject(self):
        self._color_timer.stop()
        self._pending_color = None
        if not self._applied:
            self._manager.preview(self._original_active)
            self._manager.preview_font_family(self._original_font_family)
            self._manager.preview_motion_mode(self._original_motion_mode)
            self._draft = self._original_active
        super().reject()

    def closeEvent(self, event):
        if not self._applied:
            self._manager.preview(self._original_active)
            self._manager.preview_font_family(self._original_font_family)
            self._manager.preview_motion_mode(self._original_motion_mode)
        super().closeEvent(event)
