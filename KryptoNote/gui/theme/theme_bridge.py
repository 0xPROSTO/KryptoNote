from PySide6.QtCore import QObject, Property

from .palette import Palette


class ThemeBridge(QObject):
    """Exposes the Python Palette as QML context properties.

    Register as contextProperty("Theme") so QML can use
    Theme.bgCanvas, Theme.accentMain, etc. instead of hardcoded hex values.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    # ── Background ──────────────────────────────────────────────────

    @Property(str, constant=True)
    def bgCanvas(self):
        return Palette.BG_CANVAS

    @Property(str, constant=True)
    def bgPanel(self):
        return Palette.BG_PANEL

    @Property(str, constant=True)
    def bgNode(self):
        return Palette.BG_NODE

    @Property(str, constant=True)
    def bgInput(self):
        return Palette.BG_INPUT

    @Property(str, constant=True)
    def bgTitleBar(self):
        return Palette.BG_TITLE_BAR

    # ── Accent ──────────────────────────────────────────────────────

    @Property(str, constant=True)
    def accentMain(self):
        return Palette.ACCENT_MAIN

    @Property(str, constant=True)
    def accentHover(self):
        return Palette.ACCENT_HOVER

    @Property(str, constant=True)
    def accentLow(self):
        return Palette.ACCENT_LOW

    # ── Text ────────────────────────────────────────────────────────

    @Property(str, constant=True)
    def textMain(self):
        return Palette.TEXT_MAIN

    @Property(str, constant=True)
    def textDim(self):
        return Palette.TEXT_DIM

    @Property(str, constant=True)
    def textMuted(self):
        return Palette.TEXT_MUTED

    # ── Borders ─────────────────────────────────────────────────────

    @Property(str, constant=True)
    def borderDefault(self):
        return Palette.BORDER_DEFAULT

    @Property(str, constant=True)
    def borderHover(self):
        return Palette.BORDER_HOVER

    @Property(str, constant=True)
    def borderTitleBar(self):
        return Palette.BORDER_TITLE_BAR

    # ── Grid ────────────────────────────────────────────────────────

    @Property(str, constant=True)
    def gridSub(self):
        return Palette.GRID_SUB

    @Property(str, constant=True)
    def gridMain(self):
        return Palette.GRID_MAIN

    # ── Status Colors ───────────────────────────────────────────────

    @Property(str, constant=True)
    def greenSecure(self):
        return Palette.GREEN_SECURE

    @Property(str, constant=True)
    def successHover(self):
        return Palette.SUCCESS_HOVER

    @Property(str, constant=True)
    def dangerHover(self):
        return Palette.DANGER_HOVER

    # ── White Alpha ─────────────────────────────────────────────────

    @Property(str, constant=True)
    def whiteAlpha05(self):
        return Palette.WHITE_ALPHA_05

    @Property(str, constant=True)
    def whiteAlpha10(self):
        return Palette.WHITE_ALPHA_10

    @Property(str, constant=True)
    def whiteAlpha15(self):
        return Palette.WHITE_ALPHA_15

    @Property(str, constant=True)
    def whiteAlpha85(self):
        return Palette.WHITE_ALPHA_85

    # ── Buttons ─────────────────────────────────────────────────────

    @Property(str, constant=True)
    def btnApply(self):
        return Palette.BTN_APPLY

    @Property(str, constant=True)
    def btnApplyBorder(self):
        return Palette.BTN_APPLY_BORDER

    @Property(str, constant=True)
    def btnApplyText(self):
        return Palette.BTN_APPLY_TEXT

    @Property(str, constant=True)
    def btnApplyHover(self):
        return Palette.BTN_APPLY_HOVER

    @Property(str, constant=True)
    def btnCancel(self):
        return Palette.BTN_CANCEL

    @Property(str, constant=True)
    def btnCancelBorder(self):
        return Palette.BTN_CANCEL_BORDER

    @Property(str, constant=True)
    def btnCancelText(self):
        return Palette.BTN_CANCEL_TEXT

    @Property(str, constant=True)
    def btnCancelHover(self):
        return Palette.BTN_CANCEL_HOVER

    # ── Slider ──────────────────────────────────────────────────────

    @Property(str, constant=True)
    def sliderTrack(self):
        return Palette.SLIDER_TRACK

    @Property(str, constant=True)
    def sliderHandle(self):
        return Palette.SLIDER_HANDLE

    @Property(str, constant=True)
    def sliderHandleHover(self):
        return Palette.SLIDER_HANDLE_HOVER
