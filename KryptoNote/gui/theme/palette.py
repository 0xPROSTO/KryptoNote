class Palette:

    # NEUTRAL RAMP (dark -> light)
    # Keep these explicit: alpha overlays made adjacent surfaces collapse into
    # the same tone, especially inside menus and popovers.
    NEUTRAL_950 = "#121212"
    NEUTRAL_900 = "#161616"
    NEUTRAL_850 = "#1a1a1a"
    NEUTRAL_800 = "#1e1e1e"
    NEUTRAL_750 = "#232425"
    NEUTRAL_700 = "#26282b"
    NEUTRAL_650 = "#2d3034"
    NEUTRAL_600 = "#35393e"
    NEUTRAL_550 = "#40454b"
    NEUTRAL_500 = "#555b62"

    # SEMANTIC SURFACES
    BG_CANVAS = NEUTRAL_950
    BG_INPUT = NEUTRAL_900
    BG_TITLE_BAR = NEUTRAL_850
    BG_PANEL = NEUTRAL_800
    BG_POPOVER = NEUTRAL_750
    BG_NODE = NEUTRAL_700
    BG_CONTROL = NEUTRAL_650
    BG_CONTROL_HOVER = NEUTRAL_600
    BG_CONTROL_PRESSED = NEUTRAL_550
    OVERLAY_BASE_RGB = (0, 0, 0)
    OVERLAY_DIM_ALPHA = 153
    OVERLAY_DIM = "#99000000"
    BORDER_SUBTLE = "#303337"
    BORDER_DEFAULT = "#3a3e43"
    BORDER_HOVER = NEUTRAL_500
    BORDER_SELECTED = "#e6158b"  # Vibrant Magenta

    # ACCENT (Vibrant Magenta Palette)
    ACCENT_MAIN = "#e6158b"  # Magenta (Primary)
    ACCENT_HOVER = "#cc1279"  # Darker magenta for hover states
    ACCENT_LOW = "#3a1025"  # Deep muted magenta for backgrounds
    ACCENT_HIGH = "#ff33a1"  # Bright Magenta
    ACCENT_ULTRA = "#ff99cc"  # Light pink highlight
    ON_ACCENT = "#000000"

    # UTILITY (Softened for the new Pro style)
    # TAGS
    TAG_STARRED = "#f2b84b"
    TAG_DEFAULT = "#7b8cff"
    TAG_SELECTED_BG = "#332d20"

    DANGER = "#b82a2a"
    DANGER_HOVER = "#d43f3f"
    SUCCESS = "#2a8a2a"
    SUCCESS_HOVER = "#3eb03e"

    # BUTTONS (Muted/Soft for non-jarring UI)
    BTN_APPLY = "#1e3a24"  # Muted Deep Green
    BTN_APPLY_HOVER = "#2a5a32"
    BTN_APPLY_BORDER = "#2a5a32"
    BTN_APPLY_TEXT = "#99ff99"
    BTN_CANCEL = "#3a1e1e"  # Muted Deep Red
    BTN_CANCEL_HOVER = "#5a2a2a"
    BTN_CANCEL_BORDER = "#5a2a2a"
    BTN_CANCEL_TEXT = "#ff9999"

    # TEXT
    TEXT_MAIN = "#efefef"  # Near white
    TEXT_DIM = "#bbbbbb"  # Secondary text
    TEXT_MUTED = "#92979f"  # Readable tertiary text
    TEXT_DISABLED = "#666666"  # Disabled controls only
    TEXT_ACCENT = "#e6158b"  # Magenta highlights

    # TITLE BAR
    BORDER_TITLE_BAR = BORDER_SUBTLE
    BTN_HOVER_DEFAULT = BG_CONTROL_HOVER

    # SYSTEM & STATUS
    GREEN_SECURE = "#00FF00"

    # GRID
    GRID_MAIN = "#252525"
    GRID_SUB = "#1a1a1a"

    # UI ELEMENTS (SLIDERS, HANDLES)
    SLIDER_TRACK = "#e0e0e0"
    SLIDER_HANDLE = "#ffffff"
    SLIDER_HANDLE_HOVER = "#f0f0f0"
    RESIZE_HANDLE = TEXT_MUTED

    # TRANSPARENT OVERLAYS
    # QColor/QML-compatible ARGB. Fractional CSS rgba() is parsed as black.
    WHITE_ALPHA_05 = "#0dffffff"
    WHITE_ALPHA_10 = "#1affffff"
    WHITE_ALPHA_15 = "#26ffffff"
    WHITE_ALPHA_85 = "#d9ffffff"

    # Theme-aware aliases. Existing WHITE_ALPHA names remain for QML
    # compatibility; light themes intentionally turn them into dark overlays.
    INTERACTION_ALPHA_05 = WHITE_ALPHA_05
    INTERACTION_ALPHA_10 = WHITE_ALPHA_10
    INTERACTION_ALPHA_15 = WHITE_ALPHA_15
    FOREGROUND_ALPHA_85 = WHITE_ALPHA_85

    @classmethod
    def apply(cls, values):
        """Apply validated semantic colors in-place."""
        for name, value in values.items():
            if not name.startswith("_"):
                setattr(cls, name, value)

    @classmethod
    def overlay_rgba(cls, alpha):
        red, green, blue = cls.OVERLAY_BASE_RGB
        safe_alpha = max(0, min(255, int(alpha)))
        return f"rgba({red}, {green}, {blue}, {safe_alpha})"


_PALETTE_ROLE_NAMES = (
    "NEUTRAL_950", "NEUTRAL_900", "NEUTRAL_850", "NEUTRAL_800",
    "NEUTRAL_750", "NEUTRAL_700", "NEUTRAL_650", "NEUTRAL_600",
    "NEUTRAL_550", "NEUTRAL_500", "BG_CANVAS", "BG_INPUT",
    "BG_TITLE_BAR", "BG_PANEL", "BG_POPOVER", "BG_NODE", "BG_CONTROL",
    "BG_CONTROL_HOVER", "BG_CONTROL_PRESSED", "OVERLAY_BASE_RGB",
    "OVERLAY_DIM", "BORDER_SUBTLE", "BORDER_DEFAULT", "BORDER_HOVER",
    "BORDER_SELECTED", "ACCENT_MAIN", "ACCENT_HOVER", "ACCENT_LOW",
    "ACCENT_HIGH", "ACCENT_ULTRA", "ON_ACCENT", "TAG_STARRED",
    "TAG_DEFAULT", "TAG_SELECTED_BG", "DANGER", "DANGER_HOVER",
    "SUCCESS", "SUCCESS_HOVER", "BTN_APPLY", "BTN_APPLY_HOVER",
    "BTN_APPLY_BORDER", "BTN_APPLY_TEXT", "BTN_CANCEL", "BTN_CANCEL_HOVER",
    "BTN_CANCEL_BORDER", "BTN_CANCEL_TEXT", "TEXT_MAIN", "TEXT_DIM",
    "TEXT_MUTED", "TEXT_DISABLED", "TEXT_ACCENT", "BORDER_TITLE_BAR",
    "BTN_HOVER_DEFAULT", "GREEN_SECURE", "GRID_MAIN", "GRID_SUB", "RESIZE_HANDLE",
    "SLIDER_TRACK", "SLIDER_HANDLE", "SLIDER_HANDLE_HOVER", "WHITE_ALPHA_05",
    "WHITE_ALPHA_10", "WHITE_ALPHA_15", "WHITE_ALPHA_85",
    "INTERACTION_ALPHA_05", "INTERACTION_ALPHA_10", "INTERACTION_ALPHA_15",
    "FOREGROUND_ALPHA_85",
)

# Immutable copy of the exact pre-settings appearance. ThemeManager uses it to
# guarantee that dark_2 with the default magenta is pixel-identical.
DEFAULT_DARK_2 = {name: getattr(Palette, name) for name in _PALETTE_ROLE_NAMES}
