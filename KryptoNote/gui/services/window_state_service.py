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
        restored = False
        if geometry:
            fallback_geometry = window.saveGeometry()
            restored = window.restoreGeometry(geometry)
            if not restored or window.width() <= minimum_restored_width:
                window.restoreGeometry(fallback_geometry)
                restored = False
            else:
                state = self._settings.value("windowState")
                if state:
                    window.restoreState(state)

        self._restore_panel_layout(window)
        return restored

    def save(self, window):
        self._settings.setValue("geometry", window.saveGeometry())
        self._settings.setValue("windowState", window.saveState())
        root = self._qml_root(window)
        if root is not None:
            self._settings.beginGroup("panelLayout")
            self._settings.setValue(
                "searchWidth", float(root.property("searchPanelPreferredWidth") or 0)
            )
            self._settings.setValue(
                "textEditorWidth", float(root.property("textEditorPreferredWidth") or 0)
            )
            media_resized = bool(root.property("mediaPanelUserResized"))
            self._settings.setValue("mediaUserResized", media_resized)
            self._settings.setValue(
                "mediaWidthRatio",
                float(root.property("mediaPanelPreferredRatio") or 0)
                if media_resized
                else 0,
            )
            self._settings.endGroup()
        self._settings.sync()

    def _restore_panel_layout(self, window):
        root = self._qml_root(window)
        if root is None:
            return
        self._settings.beginGroup("panelLayout")
        search_width = self._float_value("searchWidth")
        editor_width = self._float_value("textEditorWidth")
        media_ratio = self._float_value("mediaWidthRatio")
        media_resized = str(
            self._settings.value("mediaUserResized", False)
        ).strip().lower() in {"1", "true", "yes"}
        self._settings.endGroup()
        restore = getattr(root, "restorePanelLayout", None)
        if callable(restore):
            restore(search_width, editor_width, media_ratio, media_resized)

    def _float_value(self, key):
        try:
            return float(self._settings.value(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _qml_root(window):
        view = getattr(window, "view", None)
        return view.rootObject() if view is not None else None
