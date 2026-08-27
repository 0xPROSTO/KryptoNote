from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect

from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.widgets.dialog_motion import (
    widget_motion_duration,
)


class DimOverlay(QFrame):
    def __init__(self, parent=None, block_input=False, auto_show=True):
        super().__init__(parent)
        self._input_blocked = False
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

        self.setStyleSheet(
            "DimOverlay { "
            f"background-color: {Palette.overlay_rgba(Palette.OVERLAY_DIM_ALPHA)}; "
            "}"
        )

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(widget_motion_duration(self, "panel"))
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._delete_on_finished_connected = False
        self._hide_on_finished_connected = False
        self.set_input_blocked(block_input)

        if auto_show:
            self.show()
            self.fade_in()
        else:
            self.hide()

    def prepare_show(self):
        self.anim.stop()
        self._disconnect_finish_actions()
        self.opacity_effect.setOpacity(0.0)
        self.set_input_blocked(True)
        self.show()
        self.raise_()

    def _disconnect_finish_actions(self):
        if self._delete_on_finished_connected:
            try:
                self.anim.finished.disconnect(self.deleteLater)
            except RuntimeError:
                pass
            self._delete_on_finished_connected = False
        if self._hide_on_finished_connected:
            try:
                self.anim.finished.disconnect(self.hide)
            except RuntimeError:
                pass
            self._hide_on_finished_connected = False

    def fade_in(self, duration_kind="panel", easing=None):
        self.set_input_blocked(True)
        self.show()
        self.raise_()
        self.anim.stop()
        self._disconnect_finish_actions()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.setDuration(
            widget_motion_duration(self, duration_kind)
        )
        if easing is None:
            easing = (
                QEasingCurve.Type.OutQuad
                if duration_kind == "dialog_enter"
                else QEasingCurve.Type.OutCubic
            )
        self.anim.setEasingCurve(easing)
        self.anim.start()

    def fade_out(
        self,
        delete_on_finish=True,
        keep_input_blocked=False,
        duration_kind="exit",
        easing=QEasingCurve.Type.InCubic,
    ):
        if not keep_input_blocked:
            self.set_input_blocked(False)
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.setDuration(
            widget_motion_duration(self, duration_kind)
        )
        self.anim.setEasingCurve(easing)
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
        self._input_blocked = bool(blocked)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not self._input_blocked,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_AcceptTouchEvents,
            self._input_blocked,
        )
        self.setMouseTracking(self._input_blocked)
        self.setTabletTracking(self._input_blocked)

    def event(self, event):
        if getattr(self, "_input_blocked", False) and event.type() in {
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
            QEvent.Type.TouchEnd,
            QEvent.Type.TouchCancel,
            QEvent.Type.TabletPress,
            QEvent.Type.TabletMove,
            QEvent.Type.TabletRelease,
            QEvent.Type.Gesture,
            QEvent.Type.GestureOverride,
            QEvent.Type.NativeGesture,
        }:
            event.accept()
            return True
        return super().event(event)

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)


class WindowOverlayManager(QObject):
    """Owns one reusable dim layer shared by every window-level overlay."""

    activeChanged = Signal(bool)

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent or parent_widget)
        self._owners = {}
        self._foreground_widgets = []
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
        self.prepare(owner, alpha)
        self.present(owner)

    def prepare(self, owner, alpha=Palette.OVERLAY_DIM_ALPHA):
        if not owner:
            raise ValueError("Overlay owner cannot be empty")
        was_active = self.active
        key = str(owner)
        self._owners[key] = {
            "alpha": max(
                Palette.OVERLAY_DIM_ALPHA,
                min(255, int(alpha)),
            ),
            "presented": False,
            "dismissing": False,
        }
        self._apply_alpha()
        if not was_active:
            self._overlay.prepare_show()
        else:
            self._overlay.set_input_blocked(True)
            self._overlay.show()
            self._overlay.raise_()
        self._raise_foreground()
        if was_active != self.active:
            self.activeChanged.emit(self.active)

    def present(self, owner, duration_kind="panel"):
        state = self._owners.get(str(owner))
        if state is None:
            return
        state["presented"] = True
        state["dismissing"] = False
        self._apply_alpha()
        self._overlay.fade_in(duration_kind=duration_kind)
        self._raise_foreground()

    def begin_dismiss(self, owner):
        state = self._owners.get(str(owner))
        if state is None or state["dismissing"]:
            return
        state["dismissing"] = True
        if any(
            not candidate["dismissing"]
            for candidate in self._owners.values()
            if candidate is not state
        ):
            self._apply_alpha(exclude_dismissing=True)
            self._overlay.fade_in()
        else:
            self._overlay.fade_out(
                delete_on_finish=False,
                keep_input_blocked=True,
                duration_kind="dialog_exit",
                easing=QEasingCurve.Type.InOutCubic,
            )
        self._raise_foreground()

    def release(self, owner):
        was_active = self.active
        self._owners.pop(str(owner), None)
        if self._owners:
            self._apply_alpha(exclude_dismissing=True)
            self._overlay.set_input_blocked(True)
            if any(not state["dismissing"] for state in self._owners.values()):
                self._overlay.fade_in()
            self._raise_foreground()
        else:
            self._overlay.set_input_blocked(False)
            if self._overlay.isVisible():
                animation_running = (
                    self._overlay.anim.state()
                    == QAbstractAnimation.State.Running
                )
                ending_at_zero = False
                if animation_running:
                    try:
                        ending_at_zero = (
                            float(self._overlay.anim.endValue()) <= 0.001
                        )
                    except (TypeError, ValueError):
                        ending_at_zero = False
                if self._overlay.opacity_effect.opacity() <= 0.001:
                    self._overlay.anim.stop()
                    self._overlay.hide()
                elif not ending_at_zero:
                    self._overlay.fade_out(delete_on_finish=False)
        if was_active != self.active:
            self.activeChanged.emit(self.active)

    def clear(self):
        was_active = self.active
        self._owners.clear()
        if self._overlay.isVisible():
            self._overlay.fade_out(delete_on_finish=False)
        else:
            self._overlay.set_input_blocked(False)
        if was_active:
            self.activeChanged.emit(False)

    def register_foreground(self, widget):
        if widget is None or widget in self._foreground_widgets:
            return
        self._foreground_widgets.append(widget)
        self._raise_foreground()

    def unregister_foreground(self, widget):
        try:
            self._foreground_widgets.remove(widget)
        except ValueError:
            pass

    def refresh_theme(self):
        self._apply_alpha()
        self._raise_foreground()

    def _raise_foreground(self):
        retained = []
        for widget in self._foreground_widgets:
            try:
                widget.raise_()
            except RuntimeError:
                continue
            retained.append(widget)
        self._foreground_widgets = retained

    def _apply_alpha(self, exclude_dismissing=False):
        states = list(self._owners.values())
        if exclude_dismissing:
            visible_states = [state for state in states if not state["dismissing"]]
            if visible_states:
                states = visible_states
        alpha = max(
            (state["alpha"] for state in states),
            default=Palette.OVERLAY_DIM_ALPHA,
        )
        self._overlay.setStyleSheet(
            "DimOverlay { "
            f"background-color: {Palette.overlay_rgba(alpha)}; "
            "}"
        )
