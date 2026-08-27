from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtWidgets import QApplication, QStyle

from .palette import Palette
from .theme_manager import CONNECTION_WIDTHS, GRID_OPACITIES, get_theme_manager


class ThemeBridge(QObject):
    """Live QML view of the active Python theme."""

    paletteChanged = Signal()
    canvasAppearanceChanged = Signal()
    fontChanged = Signal()
    motionChanged = Signal()

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self._manager = manager or get_theme_manager()
        application = QApplication.instance()
        style = (
            application.style()
            if application is not None and hasattr(application, "style")
            else None
        )
        self._system_motion_enabled = bool(
            style is None
            or style.styleHint(QStyle.StyleHint.SH_Widget_Animate)
        )
        self._manager.paletteChanged.connect(self.paletteChanged.emit)
        self._manager.canvasAppearanceChanged.connect(
            self.canvasAppearanceChanged.emit
        )
        self._manager.fontChanged.connect(self.fontChanged.emit)
        self._manager.motionChanged.connect(self.motionChanged.emit)

    def _effective_motion_mode(self):
        mode = self._manager.motion_mode
        if mode == "system":
            return "full" if self._system_motion_enabled else "off"
        return mode

    def _duration(self, full, reduced):
        mode = self._effective_motion_mode()
        if mode == "off":
            return 0
        return int(reduced if mode == "reduced" else full)

    motionMode = Property(
        str, lambda self: self._manager.motion_mode, notify=motionChanged
    )
    effectiveMotionMode = Property(
        str, _effective_motion_mode, notify=motionChanged
    )
    motionEnabled = Property(
        bool,
        lambda self: self._effective_motion_mode() == "full",
        notify=motionChanged,
    )
    colorMotionEnabled = Property(
        bool,
        lambda self: self._effective_motion_mode() != "off",
        notify=motionChanged,
    )
    reducedMotion = Property(
        bool,
        lambda self: self._effective_motion_mode() == "reduced",
        notify=motionChanged,
    )
    durationPress = Property(
        int, lambda self: self._duration(80, 60), notify=motionChanged
    )
    durationState = Property(
        int, lambda self: self._duration(140, 80), notify=motionChanged
    )
    durationPanel = Property(
        int, lambda self: self._duration(220, 100), notify=motionChanged
    )
    durationExit = Property(
        int, lambda self: self._duration(80, 60), notify=motionChanged
    )

    bgCanvas = Property(str, lambda self: Palette.BG_CANVAS, notify=paletteChanged)
    bgPanel = Property(str, lambda self: Palette.BG_PANEL, notify=paletteChanged)
    bgNode = Property(str, lambda self: Palette.BG_NODE, notify=paletteChanged)
    bgInput = Property(str, lambda self: Palette.BG_INPUT, notify=paletteChanged)
    bgTitleBar = Property(str, lambda self: Palette.BG_TITLE_BAR, notify=paletteChanged)
    bgPopover = Property(str, lambda self: Palette.BG_POPOVER, notify=paletteChanged)
    bgControl = Property(str, lambda self: Palette.BG_CONTROL, notify=paletteChanged)
    bgControlHover = Property(
        str, lambda self: Palette.BG_CONTROL_HOVER, notify=paletteChanged
    )
    bgControlPressed = Property(
        str, lambda self: Palette.BG_CONTROL_PRESSED, notify=paletteChanged
    )
    overlayDim = Property(str, lambda self: Palette.OVERLAY_DIM, notify=paletteChanged)

    accentMain = Property(str, lambda self: Palette.ACCENT_MAIN, notify=paletteChanged)
    accentHover = Property(str, lambda self: Palette.ACCENT_HOVER, notify=paletteChanged)
    accentLow = Property(str, lambda self: Palette.ACCENT_LOW, notify=paletteChanged)
    accentHigh = Property(str, lambda self: Palette.ACCENT_HIGH, notify=paletteChanged)
    accentUltra = Property(str, lambda self: Palette.ACCENT_ULTRA, notify=paletteChanged)
    onAccent = Property(str, lambda self: Palette.ON_ACCENT, notify=paletteChanged)

    textMain = Property(str, lambda self: Palette.TEXT_MAIN, notify=paletteChanged)
    textDim = Property(str, lambda self: Palette.TEXT_DIM, notify=paletteChanged)
    textMuted = Property(str, lambda self: Palette.TEXT_MUTED, notify=paletteChanged)
    textDisabled = Property(
        str, lambda self: Palette.TEXT_DISABLED, notify=paletteChanged
    )
    textAccent = Property(str, lambda self: Palette.TEXT_ACCENT, notify=paletteChanged)

    tagStarred = Property(str, lambda self: Palette.TAG_STARRED, notify=paletteChanged)
    tagDefault = Property(str, lambda self: Palette.TAG_DEFAULT, notify=paletteChanged)
    tagSelectedBg = Property(
        str, lambda self: Palette.TAG_SELECTED_BG, notify=paletteChanged
    )

    borderDefault = Property(
        str, lambda self: Palette.BORDER_DEFAULT, notify=paletteChanged
    )
    borderSubtle = Property(
        str, lambda self: Palette.BORDER_SUBTLE, notify=paletteChanged
    )
    borderHover = Property(str, lambda self: Palette.BORDER_HOVER, notify=paletteChanged)
    borderSelected = Property(
        str, lambda self: Palette.BORDER_SELECTED, notify=paletteChanged
    )
    borderTitleBar = Property(
        str, lambda self: Palette.BORDER_TITLE_BAR, notify=paletteChanged
    )
    resizeHandle = Property(
        str, lambda self: Palette.RESIZE_HANDLE, notify=paletteChanged
    )

    gridSub = Property(str, lambda self: Palette.GRID_SUB, notify=paletteChanged)
    gridMain = Property(str, lambda self: Palette.GRID_MAIN, notify=paletteChanged)
    gridIntensity = Property(
        str,
        lambda self: self._manager.settings.grid_intensity,
        notify=canvasAppearanceChanged,
    )
    gridOpacity = Property(
        float,
        lambda self: GRID_OPACITIES[self._manager.settings.grid_intensity],
        notify=canvasAppearanceChanged,
    )
    gridEnabled = Property(
        bool,
        lambda self: self._manager.settings.grid_intensity != "off",
        notify=canvasAppearanceChanged,
    )

    textFontFamily = Property(
        str,
        lambda self: self._manager.resolved_text_font_family,
        notify=fontChanged,
    )

    connectionStyle = Property(
        str,
        lambda self: self._manager.settings.connection_style,
        notify=canvasAppearanceChanged,
    )
    connectionCurved = Property(
        bool,
        lambda self: self._manager.settings.connection_style == "curved",
        notify=canvasAppearanceChanged,
    )
    connectionPattern = Property(
        str,
        lambda self: self._manager.settings.connection_pattern,
        notify=canvasAppearanceChanged,
    )
    connectionCurveFormula = Property(
        str,
        lambda self: self._manager.settings.connection_curve_formula,
        notify=canvasAppearanceChanged,
    )
    connectionCornerStyle = Property(
        str,
        lambda self: self._manager.settings.connection_corner_style,
        notify=canvasAppearanceChanged,
    )
    connectionAnchorMode = Property(
        str,
        lambda self: self._manager.settings.connection_anchor_mode,
        notify=canvasAppearanceChanged,
    )
    connectionStrokeWidth = Property(
        float,
        lambda self: CONNECTION_WIDTHS[self._manager.settings.connection_thickness],
        notify=canvasAppearanceChanged,
    )
    connectionHighlightWidth = Property(
        float,
        lambda self: CONNECTION_WIDTHS[self._manager.settings.connection_thickness] + 0.6,
        notify=canvasAppearanceChanged,
    )

    greenSecure = Property(str, lambda self: Palette.GREEN_SECURE, notify=paletteChanged)
    successHover = Property(
        str, lambda self: Palette.SUCCESS_HOVER, notify=paletteChanged
    )
    dangerHover = Property(str, lambda self: Palette.DANGER_HOVER, notify=paletteChanged)
    danger = Property(str, lambda self: Palette.DANGER, notify=paletteChanged)
    success = Property(str, lambda self: Palette.SUCCESS, notify=paletteChanged)

    whiteAlpha05 = Property(
        str, lambda self: Palette.WHITE_ALPHA_05, notify=paletteChanged
    )
    whiteAlpha10 = Property(
        str, lambda self: Palette.WHITE_ALPHA_10, notify=paletteChanged
    )
    whiteAlpha15 = Property(
        str, lambda self: Palette.WHITE_ALPHA_15, notify=paletteChanged
    )
    whiteAlpha85 = Property(
        str, lambda self: Palette.WHITE_ALPHA_85, notify=paletteChanged
    )

    btnApply = Property(str, lambda self: Palette.BTN_APPLY, notify=paletteChanged)
    btnApplyBorder = Property(
        str, lambda self: Palette.BTN_APPLY_BORDER, notify=paletteChanged
    )
    btnApplyText = Property(
        str, lambda self: Palette.BTN_APPLY_TEXT, notify=paletteChanged
    )
    btnApplyHover = Property(
        str, lambda self: Palette.BTN_APPLY_HOVER, notify=paletteChanged
    )
    btnCancel = Property(str, lambda self: Palette.BTN_CANCEL, notify=paletteChanged)
    btnCancelBorder = Property(
        str, lambda self: Palette.BTN_CANCEL_BORDER, notify=paletteChanged
    )
    btnCancelText = Property(
        str, lambda self: Palette.BTN_CANCEL_TEXT, notify=paletteChanged
    )
    btnCancelHover = Property(
        str, lambda self: Palette.BTN_CANCEL_HOVER, notify=paletteChanged
    )

    sliderTrack = Property(str, lambda self: Palette.SLIDER_TRACK, notify=paletteChanged)
    sliderHandle = Property(
        str, lambda self: Palette.SLIDER_HANDLE, notify=paletteChanged
    )
    sliderHandleHover = Property(
        str, lambda self: Palette.SLIDER_HANDLE_HOVER, notify=paletteChanged
    )
