"""Runtime theme generation and global appearance persistence."""

from dataclasses import dataclass, replace
from typing import Mapping

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ...core.constants import (
    DEFAULT_VACUUM_THRESHOLD_BYTES,
    VACUUM_THRESHOLD_OPTIONS_BYTES,
)
from ...core.connection_geometry import (
    CONNECTION_ANCHOR_MODES,
    CONNECTION_CORNER_STYLES,
    CONNECTION_CURVE_FORMULAS,
    CONNECTION_STYLES,
    DEFAULT_CONNECTION_ANCHOR_MODE,
    DEFAULT_CONNECTION_CORNER_STYLE,
    DEFAULT_CONNECTION_CURVE_FORMULA,
    DEFAULT_CONNECTION_PATTERN,
    DEFAULT_CONNECTION_STYLE,
    corner_style_from_legacy_radius,
)
from .palette import DEFAULT_DARK_2, Palette
from .typography import (
    SYSTEM_DEFAULT_FONT,
    Typography,
    resolve_font_family,
)


DEFAULT_TONE = "dark_2"
DEFAULT_ACCENT = "#e6158b"
DEFAULT_CONNECTION_THICKNESS = "normal"
DEFAULT_GRID_INTENSITY = "normal"
DEFAULT_MOTION_MODE = "system"

TONE_IDS = (
    "dark_1", "dark_4", "dark_2", "dark_3",
    "light_0", "light_1", "light_2", "light_3",
)
CONNECTION_THICKNESSES = ("thin", "normal", "thick")
GRID_INTENSITIES = ("off", "subtle", "normal", "strong", "maximum")
MOTION_MODES = ("system", "full", "reduced", "off")

TONE_LABELS = {
    "dark_1": "Void",
    "dark_4": "Midnight",
    "dark_2": "ZrX",
    "dark_3": "Graphite",
    "light_0": "Ash",
    "light_1": "Mist",
    "light_2": "Notebook",
    "light_3": "Paper",
}
TONE_ANCHORS = {
    "dark_1": "#040506",
    "dark_4": "#0b0d10",
    "dark_2": DEFAULT_DARK_2["BG_CANVAS"],
    "dark_3": "#24272b",
    "light_0": "#b8bec6",
    "light_1": "#d5dae0",
    "light_2": "#e8e2d5",
    "light_3": "#eff1f3",
}
ACCENT_PRESETS = {
    "ZrX": "#e6158b",
    "Obsidian": "#7f6df2",
    "Cobalt": "#2f6fce",
    "Teal": "#168b8f",
    "Pearl": "#d6d9de",
    "Carbon": "#35383d",
}

LIGHT_THEME_PROFILES = {
    "light_0": {
        "BG_CANVAS": "#b8bec6",
        "BG_INPUT": "#c2c7ce",
        "BG_TITLE_BAR": "#a9b0b9",
        "BG_PANEL": "#b0b7bf",
        "BG_POPOVER": "#cbd0d6",
        "BG_NODE": "#c5cad1",
        "BG_CONTROL": "#9fa8b2",
        "BG_CONTROL_HOVER": "#919ca7",
        "BG_CONTROL_PRESSED": "#838f9a",
        "BORDER_SUBTLE": "#9da6af",
        "BORDER_DEFAULT": "#87929d",
        "BORDER_HOVER": "#687684",
        "RESIZE_HANDLE": "#596b7c",
        "GRID_SUB": "#aeb5bd",
        "GRID_MAIN": "#98a2ac",
        "TEXT_MAIN": "#11161b",
        "TEXT_DIM": "#192127",
        "TEXT_MUTED": "#20272e",
    },
    "light_1": {
        "BG_CANVAS": "#d5dae0",
        "BG_INPUT": "#dce1e6",
        "BG_TITLE_BAR": "#c3cad1",
        "BG_PANEL": "#ccd2d8",
        "BG_POPOVER": "#e2e6ea",
        "BG_NODE": "#c7cfd7",
        "BG_CONTROL": "#b8c1ca",
        "BG_CONTROL_HOVER": "#aab5bf",
        "BG_CONTROL_PRESSED": "#9ca8b4",
        "BORDER_SUBTLE": "#b6bfc8",
        "BORDER_DEFAULT": "#9ca8b4",
        "BORDER_HOVER": "#748392",
        "RESIZE_HANDLE": "#617487",
        "GRID_SUB": "#c7cdd4",
        "GRID_MAIN": "#b4bdc6",
        "TEXT_MAIN": "#151a1f",
        "TEXT_DIM": "#263039",
        "TEXT_MUTED": "#303841",
    },
    "light_2": {
        "BG_CANVAS": "#e8e2d5",
        "BG_INPUT": "#eee8dc",
        "BG_TITLE_BAR": "#d4ccbd",
        "BG_PANEL": "#ddd6c8",
        "BG_POPOVER": "#f4efe5",
        "BG_NODE": "#ddd3bf",
        "BG_CONTROL": "#c9bfad",
        "BG_CONTROL_HOVER": "#b9ad99",
        "BG_CONTROL_PRESSED": "#aa9d87",
        "BORDER_SUBTLE": "#c4baa8",
        "BORDER_DEFAULT": "#aa9d88",
        "BORDER_HOVER": "#7e705a",
        "RESIZE_HANDLE": "#75674f",
        "GRID_SUB": "#dbd4c7",
        "GRID_MAIN": "#c5bcab",
        "TEXT_MAIN": "#211e19",
        "TEXT_DIM": "#352f27",
        "TEXT_MUTED": "#393227",
    },
    "light_3": {
        "BG_CANVAS": "#eff1f3",
        "BG_INPUT": "#e9ecef",
        "BG_TITLE_BAR": "#dfe3e7",
        "BG_PANEL": "#e5e8eb",
        "BG_POPOVER": "#f7f8f9",
        "BG_NODE": "#e1e5e8",
        "BG_CONTROL": "#d1d7dc",
        "BG_CONTROL_HOVER": "#c2cad1",
        "BG_CONTROL_PRESSED": "#b2bcc5",
        "BORDER_SUBTLE": "#c7cdd3",
        "BORDER_DEFAULT": "#aeb7c0",
        "BORDER_HOVER": "#7e8b97",
        "RESIZE_HANDLE": "#697b8b",
        "GRID_SUB": "#e3e6e9",
        "GRID_MAIN": "#cbd1d6",
        "TEXT_MAIN": "#1d2227",
        "TEXT_DIM": "#384149",
        "TEXT_MUTED": "#404a53",
    },
}
CONNECTION_WIDTHS = {"thin": 1.1, "normal": 1.5, "thick": 2.2}
GRID_OPACITIES = {
    "off": 0.0,
    "subtle": 0.5,
    "normal": 1.0,
    "strong": 1.0,
    "maximum": 1.0,
}
GRID_COLOR_MIXES = {
    "off": 0.0,
    "subtle": 0.0,
    "normal": 0.0,
    "strong": 0.28,
    "maximum": 0.55,
}


@dataclass(frozen=True)
class AppearanceSettings:
    tone: str = DEFAULT_TONE
    accent_seed: str = DEFAULT_ACCENT
    connection_style: str = DEFAULT_CONNECTION_STYLE
    connection_thickness: str = DEFAULT_CONNECTION_THICKNESS
    connection_pattern: str = DEFAULT_CONNECTION_PATTERN
    connection_curve_formula: str = DEFAULT_CONNECTION_CURVE_FORMULA
    connection_corner_style: str = DEFAULT_CONNECTION_CORNER_STYLE
    connection_anchor_mode: str = DEFAULT_CONNECTION_ANCHOR_MODE
    grid_intensity: str = DEFAULT_GRID_INTENSITY

    def updated(self, **changes):
        return replace(self, **changes)


def _normalise_color(value, fallback=DEFAULT_ACCENT):
    color = QColor(str(value))
    if not color.isValid():
        color = QColor(fallback)
    return color.name(QColor.NameFormat.HexRgb).lower()


def _mix(first, second, amount):
    amount = max(0.0, min(1.0, float(amount)))
    a, b = QColor(first), QColor(second)
    return QColor(
        round(a.red() + (b.red() - a.red()) * amount),
        round(a.green() + (b.green() - a.green()) * amount),
        round(a.blue() + (b.blue() - a.blue()) * amount),
    ).name(QColor.NameFormat.HexRgb)


def relative_luminance(color):
    value = QColor(color)

    def channel(component):
        component /= 255.0
        return component / 12.92 if component <= 0.04045 else ((component + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(value.red())
        + 0.7152 * channel(value.green())
        + 0.0722 * channel(value.blue())
    )


def contrast_ratio(first, second):
    high, low = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _ensure_contrast(foreground, background, minimum):
    foreground = _normalise_color(foreground, "#000000")
    if contrast_ratio(foreground, background) >= minimum:
        return foreground
    black_ratio = contrast_ratio("#000000", background)
    white_ratio = contrast_ratio("#ffffff", background)
    target = "#000000" if black_ratio >= white_ratio else "#ffffff"
    for step in range(1, 101):
        candidate = _mix(foreground, target, step / 100.0)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return target


def _ensure_contrast_all(foreground, backgrounds, minimum):
    foreground = _normalise_color(foreground, "#000000")
    backgrounds = tuple(backgrounds)
    if all(
        contrast_ratio(foreground, background) >= minimum
        for background in backgrounds
    ):
        return foreground

    matches = []
    for target in ("#000000", "#ffffff"):
        for step in range(1, 101):
            candidate = _mix(foreground, target, step / 100.0)
            if all(
                contrast_ratio(candidate, background) >= minimum
                for background in backgrounds
            ):
                matches.append((step, candidate))
                break
    if matches:
        return min(matches, key=lambda item: item[0])[1]
    return max(
        ("#000000", "#ffffff"),
        key=lambda candidate: min(
            contrast_ratio(candidate, background)
            for background in backgrounds
        ),
    )


def _derive_accent(seed, palette):
    seed = _normalise_color(seed)
    surface_roles = (
        "BG_CANVAS", "BG_INPUT", "BG_TITLE_BAR", "BG_PANEL", "BG_POPOVER",
        "BG_NODE", "BG_CONTROL", "BG_CONTROL_HOVER", "BG_CONTROL_PRESSED",
    )
    surfaces = [palette[role] for role in surface_roles]
    main = _ensure_contrast_all(seed, surfaces, 3.0)
    hover_target = (
        "#ffffff"
        if relative_luminance(palette["BG_PANEL"]) < 0.5
        else "#000000"
    )
    hover = _ensure_contrast_all(_mix(main, hover_target, 0.12), surfaces, 3.0)
    accent_fills = (main, hover)
    on_accent = max(
        ("#000000", "#ffffff"),
        key=lambda candidate: min(
            contrast_ratio(candidate, fill) for fill in accent_fills
        ),
    )
    return {
        "ACCENT_MAIN": main,
        "ACCENT_HOVER": hover,
        "ACCENT_LOW": _mix(palette["BG_PANEL"], main, 0.18),
        "ACCENT_HIGH": _mix(main, "#ffffff", 0.18),
        "ACCENT_ULTRA": _mix(main, "#ffffff", 0.50),
        "ON_ACCENT": on_accent,
        "TEXT_ACCENT": main,
        "BORDER_SELECTED": main,
    }


def _dark_palette(tone):
    anchor = TONE_ANCHORS[tone]
    lift = "#aab2bc"
    values = dict(DEFAULT_DARK_2)
    ramps = (0.0, 0.025, 0.04, 0.055, 0.08, 0.10, 0.145, 0.19, 0.25, 0.34)
    neutrals = [_mix(anchor, lift, amount) for amount in ramps]
    for name, color in zip(
        ("NEUTRAL_950", "NEUTRAL_900", "NEUTRAL_850", "NEUTRAL_800", "NEUTRAL_750",
         "NEUTRAL_700", "NEUTRAL_650", "NEUTRAL_600", "NEUTRAL_550", "NEUTRAL_500"),
        neutrals,
    ):
        values[name] = color
    values.update({
        "BG_CANVAS": neutrals[0],
        "BG_INPUT": neutrals[1],
        "BG_TITLE_BAR": neutrals[2],
        "BG_PANEL": neutrals[3],
        "BG_POPOVER": neutrals[4],
        "BG_NODE": neutrals[5],
        "BG_CONTROL": neutrals[6],
        "BG_CONTROL_HOVER": neutrals[7],
        "BG_CONTROL_PRESSED": neutrals[8],
        "BORDER_SUBTLE": _mix(anchor, lift, 0.16),
        "BORDER_DEFAULT": _mix(anchor, lift, 0.22),
        "BORDER_HOVER": _mix(anchor, lift, 0.34),
        "BORDER_TITLE_BAR": _mix(anchor, lift, 0.16),
        "BTN_HOVER_DEFAULT": neutrals[7],
        "GRID_SUB": _mix(anchor, lift, 0.08),
        "GRID_MAIN": _mix(anchor, lift, 0.14),
        "OVERLAY_BASE_RGB": (0, 0, 0),
        "OVERLAY_DIM": "#99000000",
        "RESIZE_HANDLE": _mix(anchor, lift, 0.65),
    })
    surfaces = (
        values["BG_CANVAS"], values["BG_INPUT"], values["BG_TITLE_BAR"],
        values["BG_PANEL"], values["BG_POPOVER"], values["BG_NODE"],
        values["BG_CONTROL"], values["BG_CONTROL_HOVER"],
        values["BG_CONTROL_PRESSED"],
    )
    for role in ("TEXT_MAIN", "TEXT_DIM", "TEXT_MUTED"):
        values[role] = _ensure_contrast_all(values[role], surfaces, 4.5)

    return values


def _light_palette(tone):
    profile = LIGHT_THEME_PROFILES[tone]
    values = dict(DEFAULT_DARK_2)
    surface_names = (
        "BG_CANVAS", "BG_INPUT", "BG_TITLE_BAR", "BG_PANEL",
        "BG_POPOVER", "BG_NODE", "BG_CONTROL", "BG_CONTROL_HOVER",
        "BG_CONTROL_PRESSED",
    )
    surfaces = {name: profile[name] for name in surface_names}
    values.update(surfaces)
    values.update({
        "NEUTRAL_950": surfaces["BG_CANVAS"],
        "NEUTRAL_900": surfaces["BG_INPUT"],
        "NEUTRAL_850": surfaces["BG_TITLE_BAR"],
        "NEUTRAL_800": surfaces["BG_PANEL"],
        "NEUTRAL_750": surfaces["BG_POPOVER"],
        "NEUTRAL_700": surfaces["BG_NODE"],
        "NEUTRAL_650": surfaces["BG_CONTROL"],
        "NEUTRAL_600": surfaces["BG_CONTROL_HOVER"],
        "NEUTRAL_550": surfaces["BG_CONTROL_PRESSED"],
        "NEUTRAL_500": profile["BORDER_HOVER"],
        "BORDER_SUBTLE": profile["BORDER_SUBTLE"],
        "BORDER_DEFAULT": profile["BORDER_DEFAULT"],
        "BORDER_HOVER": profile["BORDER_HOVER"],
        "BORDER_TITLE_BAR": profile["BORDER_SUBTLE"],
        "BTN_HOVER_DEFAULT": surfaces["BG_CONTROL_HOVER"],
        "TEXT_MAIN": _ensure_contrast_all(
            profile["TEXT_MAIN"], surfaces.values(), 4.5
        ),
        "TEXT_DIM": _ensure_contrast_all(
            profile["TEXT_DIM"], surfaces.values(), 4.5
        ),
        "TEXT_MUTED": _ensure_contrast_all(
            profile["TEXT_MUTED"], surfaces.values(), 4.5
        ),
        "TEXT_DISABLED": _ensure_contrast(
            profile["TEXT_MUTED"], surfaces["BG_PANEL"], 4.5
        ),
        "GRID_SUB": profile["GRID_SUB"],
        "GRID_MAIN": profile["GRID_MAIN"],
        "RESIZE_HANDLE": profile["RESIZE_HANDLE"],
        "OVERLAY_BASE_RGB": (0, 0, 0),
        "OVERLAY_DIM": "#99000000",
        "WHITE_ALPHA_05": "#0d000000",
        "WHITE_ALPHA_10": "#1a000000",
        "WHITE_ALPHA_15": "#26000000",
        "WHITE_ALPHA_85": "#d9000000",
        "INTERACTION_ALPHA_05": "#0d000000",
        "INTERACTION_ALPHA_10": "#1a000000",
        "INTERACTION_ALPHA_15": "#26000000",
        "FOREGROUND_ALPHA_85": "#d9000000",
        "SLIDER_TRACK": profile["BORDER_DEFAULT"],
        "SLIDER_HANDLE": profile["BORDER_HOVER"],
        "SLIDER_HANDLE_HOVER": profile["TEXT_DIM"],
    })
    return values


class ThemeManager(QObject):
    paletteChanged = Signal()
    canvasAppearanceChanged = Signal()
    appearanceChanged = Signal(object)
    fontChanged = Signal()
    motionChanged = Signal()

    def __init__(self, store=None, parent=None):
        super().__init__(parent)
        self._store = (
            store
            if store is not None
            else QSettings("ZeroXware", "KryptoNote")
        )
        self._settings = AppearanceSettings()
        self._committed = self._settings
        self._font_family = SYSTEM_DEFAULT_FONT
        self._committed_font_family = SYSTEM_DEFAULT_FONT
        self._motion_mode = DEFAULT_MOTION_MODE
        self._committed_motion_mode = DEFAULT_MOTION_MODE
        self._vacuum_threshold_bytes = DEFAULT_VACUUM_THRESHOLD_BYTES

    @property
    def settings(self):
        return self._settings

    @property
    def committed_settings(self):
        return self._committed

    @property
    def font_family(self):
        """Persisted global text-node font choice."""
        return self._font_family

    @property
    def committed_font_family(self):
        return self._committed_font_family

    @property
    def resolved_text_font_family(self):
        return resolve_font_family(self._font_family)

    @property
    def motion_mode(self):
        """Persisted global motion preference."""
        return self._motion_mode

    @property
    def committed_motion_mode(self):
        return self._committed_motion_mode

    @property
    def vacuum_threshold_bytes(self):
        """Global threshold for automatic post-delete database compaction."""

        return self._vacuum_threshold_bytes

    @staticmethod
    def font_choices():
        return Typography.available_font_choices()

    @staticmethod
    def validate_font_family(value):
        value = str(value or SYSTEM_DEFAULT_FONT).strip()
        return value or SYSTEM_DEFAULT_FONT

    @staticmethod
    def validate_motion_mode(value):
        value = str(value or DEFAULT_MOTION_MODE).strip().lower()
        return value if value in MOTION_MODES else DEFAULT_MOTION_MODE

    @staticmethod
    def validate_vacuum_threshold_bytes(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return DEFAULT_VACUUM_THRESHOLD_BYTES
        return (
            value
            if value in VACUUM_THRESHOLD_OPTIONS_BYTES
            else DEFAULT_VACUUM_THRESHOLD_BYTES
        )

    @staticmethod
    def defaults():
        return AppearanceSettings()

    @staticmethod
    def validate(settings):
        if isinstance(settings, Mapping):
            legacy_corner_style = corner_style_from_legacy_radius(
                settings.get("connection_corner_radius")
            )
            settings = AppearanceSettings(**{
                key: settings.get(
                    key,
                    legacy_corner_style
                    if key == "connection_corner_style"
                    else getattr(AppearanceSettings(), key),
                )
                if key != "connection_corner_style"
                or settings.get(key) not in (None, "")
                else legacy_corner_style
                for key in AppearanceSettings.__dataclass_fields__
            })
        if not isinstance(settings, AppearanceSettings):
            settings = AppearanceSettings()
        connection_style = settings.connection_style
        if connection_style == "angled":
            connection_style = "orthogonal"
        curve_formula = settings.connection_curve_formula
        if curve_formula in ("s_curve", "arc"):
            curve_formula = DEFAULT_CONNECTION_CURVE_FORMULA
        return AppearanceSettings(
            tone=settings.tone if settings.tone in TONE_IDS else DEFAULT_TONE,
            accent_seed=_normalise_color(settings.accent_seed),
            connection_style=(
                connection_style
                if connection_style in CONNECTION_STYLES
                else DEFAULT_CONNECTION_STYLE
            ),
            connection_thickness=(
                settings.connection_thickness
                if settings.connection_thickness in CONNECTION_THICKNESSES
                else DEFAULT_CONNECTION_THICKNESS
            ),
            connection_pattern=DEFAULT_CONNECTION_PATTERN,
            connection_curve_formula=(
                curve_formula
                if curve_formula
                in CONNECTION_CURVE_FORMULAS
                else DEFAULT_CONNECTION_CURVE_FORMULA
            ),
            connection_corner_style=(
                settings.connection_corner_style
                if settings.connection_corner_style
                in CONNECTION_CORNER_STYLES
                else DEFAULT_CONNECTION_CORNER_STYLE
            ),
            connection_anchor_mode=(
                settings.connection_anchor_mode
                if settings.connection_anchor_mode in CONNECTION_ANCHOR_MODES
                else DEFAULT_CONNECTION_ANCHOR_MODE
            ),
            grid_intensity=(
                settings.grid_intensity
                if settings.grid_intensity in GRID_INTENSITIES
                else DEFAULT_GRID_INTENSITY
            ),
        )

    def load(self):
        self._store.beginGroup("appearance")
        values = {
            "tone": self._store.value("tone", DEFAULT_TONE),
            "accent_seed": self._store.value("accent_seed", DEFAULT_ACCENT),
            "connection_style": self._store.value("connection_style", DEFAULT_CONNECTION_STYLE),
            "connection_thickness": self._store.value(
                "connection_thickness", DEFAULT_CONNECTION_THICKNESS
            ),
            "connection_pattern": self._store.value(
                "connection_pattern", DEFAULT_CONNECTION_PATTERN
            ),
            "connection_curve_formula": self._store.value(
                "connection_curve_formula", DEFAULT_CONNECTION_CURVE_FORMULA
            ),
            "connection_corner_style": self._store.value(
                "connection_corner_style", None
            ),
            "connection_anchor_mode": self._store.value(
                "connection_anchor_mode", DEFAULT_CONNECTION_ANCHOR_MODE
            ),
            "connection_corner_radius": self._store.value(
                "connection_corner_radius", None
            ),
            "grid_intensity": self._store.value("grid_intensity", DEFAULT_GRID_INTENSITY),
        }
        self._store.endGroup()
        self._store.beginGroup("font")
        stored_font = self._store.value("family", SYSTEM_DEFAULT_FONT)
        self._store.endGroup()
        self._store.beginGroup("motion")
        stored_motion = self._store.value("mode", DEFAULT_MOTION_MODE)
        self._store.endGroup()
        self._store.beginGroup("maintenance")
        stored_vacuum_threshold = self._store.value(
            "vacuum_threshold_bytes",
            DEFAULT_VACUUM_THRESHOLD_BYTES,
        )
        self._store.endGroup()
        loaded = self.validate(values)
        self._committed = loaded
        self._font_family = self.validate_font_family(stored_font)
        self._committed_font_family = self._font_family
        self._motion_mode = self.validate_motion_mode(stored_motion)
        self._committed_motion_mode = self._motion_mode
        self._vacuum_threshold_bytes = self.validate_vacuum_threshold_bytes(
            stored_vacuum_threshold
        )
        self._apply(loaded)
        self.fontChanged.emit()
        self.motionChanged.emit()
        return loaded

    def preview(self, settings):
        settings = self.validate(settings)
        if settings == self._settings:
            return
        self._apply(settings)

    def commit(self, settings=None):
        if settings is not None:
            self.preview(settings)
        settings = self._settings
        self._store.beginGroup("appearance")
        for key in AppearanceSettings.__dataclass_fields__:
            self._store.setValue(key, getattr(settings, key))
        self._store.remove("connection_corner_radius")
        self._store.endGroup()
        self._store.sync()
        self._committed = settings
        return settings

    def preview_font_family(self, value):
        value = self.validate_font_family(value)
        if value == self._font_family:
            return self.resolved_text_font_family
        self._font_family = value
        self.fontChanged.emit()
        return self.resolved_text_font_family

    def commit_font_family(self, value=None):
        if value is not None:
            self.preview_font_family(value)
        self._store.beginGroup("font")
        self._store.setValue("family", self._font_family)
        self._store.endGroup()
        self._store.sync()
        self._committed_font_family = self._font_family
        return self._font_family

    def restore_committed_font_family(self):
        self.preview_font_family(self._committed_font_family)

    def reset_font_family(self):
        self.preview_font_family(SYSTEM_DEFAULT_FONT)

    def preview_motion_mode(self, value):
        value = self.validate_motion_mode(value)
        if value == self._motion_mode:
            return value
        self._motion_mode = value
        self.motionChanged.emit()
        return value

    def commit_motion_mode(self, value=None):
        if value is not None:
            self.preview_motion_mode(value)
        self._store.beginGroup("motion")
        self._store.setValue("mode", self._motion_mode)
        self._store.endGroup()
        self._store.sync()
        self._committed_motion_mode = self._motion_mode
        return self._motion_mode

    def restore_committed_motion_mode(self):
        self.preview_motion_mode(self._committed_motion_mode)

    def reset_motion_mode(self):
        self.preview_motion_mode(DEFAULT_MOTION_MODE)

    def commit_vacuum_threshold_bytes(self, value):
        value = self.validate_vacuum_threshold_bytes(value)
        self._store.beginGroup("maintenance")
        self._store.setValue("vacuum_threshold_bytes", value)
        self._store.endGroup()
        self._store.sync()
        self._vacuum_threshold_bytes = value
        return value

    def restore_committed(self):
        self.preview(self._committed)

    def reset_all(self):
        self.preview(self.defaults())

    def palette_for(self, settings=None):
        settings = self.validate(settings or self._settings)
        if settings.tone == DEFAULT_TONE:
            values = dict(DEFAULT_DARK_2)
        elif settings.tone.startswith("light_"):
            values = _light_palette(settings.tone)
        else:
            values = _dark_palette(settings.tone)

        if settings.tone != DEFAULT_TONE or settings.accent_seed != DEFAULT_ACCENT:
            values.update(_derive_accent(settings.accent_seed, values))
            values.update({
                "BTN_APPLY": values["ACCENT_MAIN"],
                "BTN_APPLY_HOVER": values["ACCENT_HOVER"],
                "BTN_APPLY_BORDER": values["ACCENT_MAIN"],
                "BTN_APPLY_TEXT": values["ON_ACCENT"],
            })

        grid_mix = GRID_COLOR_MIXES[settings.grid_intensity]
        if grid_mix:
            values["GRID_SUB"] = _mix(
                values["GRID_SUB"], values["TEXT_MAIN"], grid_mix * 0.7
            )
            values["GRID_MAIN"] = _mix(
                values["GRID_MAIN"], values["TEXT_MAIN"], grid_mix
            )
        return values

    def _apply(self, settings):
        previous = self._settings
        palette_changed = (
            previous.tone != settings.tone
            or previous.accent_seed != settings.accent_seed
            or previous.grid_intensity != settings.grid_intensity
        )
        canvas_changed = (
            previous.connection_style != settings.connection_style
            or previous.connection_thickness != settings.connection_thickness
            or previous.connection_pattern != settings.connection_pattern
            or previous.connection_curve_formula
            != settings.connection_curve_formula
            or previous.connection_corner_style
            != settings.connection_corner_style
            or previous.connection_anchor_mode
            != settings.connection_anchor_mode
            or previous.grid_intensity != settings.grid_intensity
        )
        self._settings = settings
        Palette.apply(self.palette_for(settings))
        self._apply_application_palette()
        if palette_changed:
            self.paletteChanged.emit()
        if canvas_changed:
            self.canvasAppearanceChanged.emit()
        self.appearanceChanged.emit(settings)

    @staticmethod
    def _apply_application_palette():
        app = QApplication.instance()
        if app is None:
            return
        palette = QPalette()
        role_colors = {
            QPalette.ColorRole.Window: Palette.BG_PANEL,
            QPalette.ColorRole.WindowText: Palette.TEXT_MAIN,
            QPalette.ColorRole.Base: Palette.BG_INPUT,
            QPalette.ColorRole.AlternateBase: Palette.BG_NODE,
            QPalette.ColorRole.ToolTipBase: Palette.BG_POPOVER,
            QPalette.ColorRole.ToolTipText: Palette.TEXT_MAIN,
            QPalette.ColorRole.Text: Palette.TEXT_MAIN,
            QPalette.ColorRole.Button: Palette.BG_CONTROL,
            QPalette.ColorRole.ButtonText: Palette.TEXT_MAIN,
            QPalette.ColorRole.BrightText: Palette.ACCENT_HIGH,
            QPalette.ColorRole.Highlight: Palette.ACCENT_MAIN,
            QPalette.ColorRole.HighlightedText: Palette.ON_ACCENT,
            QPalette.ColorRole.Link: Palette.ACCENT_MAIN,
            QPalette.ColorRole.LinkVisited: Palette.ACCENT_HOVER,
            QPalette.ColorRole.PlaceholderText: Palette.TEXT_MUTED,
        }
        for role, color in role_colors.items():
            palette.setColor(role, QColor(color))
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor(Palette.TEXT_DISABLED),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(Palette.TEXT_DISABLED),
        )
        app.setPalette(palette)


_theme_manager = None


def get_theme_manager():
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
