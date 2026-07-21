from PySide6.QtCore import QSettings


class WindowStateService:
    """Persist and restore main-window state outside the window class."""

    def __init__(
        self, organization="ZeroXware", application="KryptoNote", settings=None
    ):
        self._settings = (
            settings if settings is not None else QSettings(organization, application)
        )

    def restore(self, window, minimum_restored_width=800):
        geometry = self._settings.value("geometry")
        if not geometry:
            return False

        fallback_geometry = window.saveGeometry()
        restored = window.restoreGeometry(geometry)
        if not restored or window.width() <= minimum_restored_width:
            window.restoreGeometry(fallback_geometry)
            return False

        state = self._settings.value("windowState")
        if state:
            window.restoreState(state)
        return True

    def save(self, window):
        self._settings.setValue("geometry", window.saveGeometry())
        self._settings.setValue("windowState", window.saveState())
        self._settings.sync()
