from PySide6.QtGui import QFont, QFontDatabase


SYSTEM_DEFAULT_FONT = "__system__"
SYSTEM_DEFAULT_FONT_LABEL = "System default"
UNIVERSAL_FONT_FAMILIES = (
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "Arial",
    "Segoe UI",
    "Ubuntu",
    "Inter",
)


def available_font_families():
    try:
        families = QFontDatabase.families()
    except Exception:
        families = []
    return sorted(
        {str(family).strip() for family in families if str(family).strip()},
        key=str.casefold,
    )


def system_font_family():
    try:
        family = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.GeneralFont
        ).family()
    except Exception:
        family = ""
    return str(family or "Sans Serif")


def resolve_font_family(value):
    requested = str(value or SYSTEM_DEFAULT_FONT).strip()
    families = available_font_families()
    family_set = set(families)
    if requested == SYSTEM_DEFAULT_FONT:
        requested = system_font_family()
    if requested in family_set:
        return requested
    fallback = system_font_family()
    if fallback in family_set:
        return fallback
    for candidate in UNIVERSAL_FONT_FAMILIES:
        if candidate in family_set:
            return candidate
    return requested or fallback or "Sans Serif"


class Typography:
    FONT_DISPLAY = "Segoe UI Semibold"
    FONT_BODY = "Segoe UI"
    FONT_MONO = "Consolas"
    SIZE_H1 = 14
    SIZE_H2 = 12
    SIZE_BODY = 10
    SIZE_SMALL = 9

    @staticmethod
    def available_font_choices():
        """Return (display label, persisted value) pairs for global settings."""
        families = available_font_families()
        choices = [(SYSTEM_DEFAULT_FONT_LABEL, SYSTEM_DEFAULT_FONT)]
        added = set()
        for family in UNIVERSAL_FONT_FAMILIES:
            if family in families and family not in added:
                choices.append((family, family))
                added.add(family)
        for family in families:
            if family not in added:
                choices.append((family, family))
        return choices

    @staticmethod
    def current_text_family():
        try:
            from .theme_manager import get_theme_manager

            return get_theme_manager().resolved_text_font_family
        except Exception:
            return resolve_font_family(SYSTEM_DEFAULT_FONT)

    @staticmethod
    def get_font(size_key="SIZE_BODY", bold=False, italic=False, mono=False):
        font = QFont(Typography.FONT_MONO if mono else Typography.FONT_BODY)
        size = getattr(Typography, size_key, Typography.SIZE_BODY)
        font.setPointSize(size)
        font.setBold(bold)
        font.setItalic(italic)
        if size_key == "SIZE_H1" or size_key == "SIZE_H2":
            font.setFamily(Typography.FONT_DISPLAY)

        return font
