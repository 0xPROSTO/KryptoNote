from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QObject
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect

from KryptoNote.gui.theme.palette import Palette


class DimOverlay(QFrame):
    def __init__(self, parent=None, block_input=False, auto_show=True):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

        if not block_input:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.setStyleSheet(
            "DimOverlay { "
            f"background-color: {Palette.overlay_rgba(Palette.OVERLAY_DIM_ALPHA)}; "
            "}"
        )

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._delete_on_finished_connected = False
        self._hide_on_finished_connected = False

        if auto_show:
            self.show()
            self.fade_in()
        else:
            self.hide()

    def fade_in(self):
        self.set_input_blocked(True)
        self.show()
        self.raise_()
        self.anim.stop()
        if self._delete_on_finished_connected:
            try:
                self.anim.finished.disconnect(self.deleteLater)
            except RuntimeError:
                pass
            self._delete_on_finished_connected = False
        if getattr(self, '_hide_on_finished_connected', False):
            try:
                self.anim.finished.disconnect(self.hide)
            except RuntimeError:
                pass
            self._hide_on_finished_connected = False
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

    def fade_out(self, delete_on_finish=True):
        # The visual fade is not allowed to keep the application input-blocked
        # after the owner has released the overlay.
        self.set_input_blocked(False)
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        if delete_on_finish:
            if getattr(self, '_hide_on_finished_connected', False):
                try:
                    self.anim.finished.disconnect(self.hide)
                except RuntimeError:
                    pass
                self._hide_on_finished_connected = False
            if not self._delete_on_finished_connected:
                self.anim.finished.connect(self.deleteLater)
                self._delete_on_finished_connected = True
        else:
            if self._delete_on_finished_connected:
                try:
                    self.anim.finished.disconnect(self.deleteLater)
                except RuntimeError:
                    pass
                self._delete_on_finished_connected = False
            if not getattr(self, '_hide_on_finished_connected', False):
                self.anim.finished.connect(self.hide)
                self._hide_on_finished_connected = True

        self.anim.start()

    def set_input_blocked(self, blocked):
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not bool(blocked),
        )

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)


class WindowOverlayManager(QObject):
    """Owns one reusable dim layer shared by every window-level overlay."""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent or parent_widget)
        self._owners = {}
        self._overlay = DimOverlay(
            parent_widget,
            block_input=True,
            auto_show=False,
        )

    @property
    def overlay(self):
        return self._overlay

    @property
    def active(self):
        return bool(self._owners)

    @property
    def owners(self):
        """Return a snapshot useful for diagnosing stale overlay owners."""

        return dict(self._owners)

    def acquire(self, owner, alpha=Palette.OVERLAY_DIM_ALPHA):
        if not owner:
            raise ValueError("Overlay owner cannot be empty")
        self._owners[str(owner)] = max(
            Palette.OVERLAY_DIM_ALPHA,
            min(255, int(alpha)),
        )
        self._refresh()

    def release(self, owner):
        self._owners.pop(str(owner), None)
        self._refresh()

    def clear(self):
        self._owners.clear()
        self._refresh()

    def _refresh(self):
        if self._owners:
            alpha = max(self._owners.values())
            self._overlay.setStyleSheet(
                "DimOverlay { "
                f"background-color: {Palette.overlay_rgba(alpha)}; "
                "}"
            )
            self._overlay.set_input_blocked(True)
            self._overlay.fade_in()
            return
        if self._overlay.isVisible():
            self._overlay.fade_out(delete_on_finish=False)
        else:
            self._overlay.set_input_blocked(False)
