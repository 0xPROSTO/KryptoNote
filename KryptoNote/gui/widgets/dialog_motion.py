"""Shared, interruption-safe motion for application dialogs."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    Property,
    QPropertyAnimation,
    QRectF,
    QTimer,
    Qt,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QDialog, QStyle, QWidget


ENTER_DURATION_MS = 170
ENTER_SCALE_DURATION_MS = 170
EXIT_DURATION_MS = 110
ENTER_SCALE = 0.965
EXIT_SCALE = 0.985


def widget_motion_enabled(widget=None) -> bool:
    """Return the platform style's animation preference."""

    application = QApplication.instance()
    if application is None:
        return True
    style = widget.style() if widget is not None else application.style()
    if style is None:
        return True
    return bool(
        style.styleHint(
            QStyle.StyleHint.SH_Widget_Animate,
            None,
            widget,
        )
    )


class _DialogSnapshot(QWidget):
    """Paint a captured dialog surface scaled around its visual centre."""

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._scale = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _get_scale(self):
        return self._scale

    def _set_scale(self, value):
        value = max(0.01, min(1.0, float(value)))
        if abs(value - self._scale) <= 0.0001:
            return
        self._scale = value
        self.update()

    scale = Property(float, _get_scale, _set_scale)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        target_width = self.width() * self._scale
        target_height = self.height() * self._scale
        target = QRectF(
            (self.width() - target_width) / 2.0,
            (self.height() - target_height) / 2.0,
            target_width,
            target_height,
        )
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))


class DialogMotionMixin:
    """Add centred fade/scale transitions to ``QDialog`` subclasses.

    A top-level ``QGraphicsEffect`` is deliberately not used here: on Windows
    its property can animate while the compositor still presents the native
    window at full size. A short-lived captured child surface makes the scale
    visible without changing the dialog geometry or triggering layout.
    """

    def _setup_dialog_motion(self):
        if getattr(self, "_dialog_motion_ready", False):
            return
        self._dialog_motion_ready = True
        self._dialog_motion_phase = "idle"
        self._dialog_motion_group = None
        self._dialog_motion_snapshot = None
        self._dialog_motion_hidden_children = []
        self._dialog_motion_focus_widget = None
        self._dialog_motion_pending_result = None
        self._dialog_motion_bypass = False
        self._dialog_motion_dismiss_callback = None
        self._dialog_motion_dismiss_notified = False

    def set_dialog_motion_dismiss_callback(self, callback):
        """Run ``callback`` once when an allowed dismissal begins."""

        self._setup_dialog_motion()
        self._dialog_motion_dismiss_callback = (
            callback if callable(callback) else None
        )

    def _dialog_motion_notify_dismiss(self):
        if self._dialog_motion_dismiss_notified:
            return
        self._dialog_motion_dismiss_notified = True
        callback = self._dialog_motion_dismiss_callback
        if callback is not None:
            callback()

    def _dialog_motion_allowed(self):
        application = QApplication.instance()
        return bool(
            application is not None
            and not application.closingDown()
            and self.windowFlags() & Qt.WindowType.FramelessWindowHint
            and widget_motion_enabled(self)
        )

    def _dialog_motion_stop_group(self):
        group = getattr(self, "_dialog_motion_group", None)
        if group is None:
            return
        group.stop()
        group.deleteLater()
        self._dialog_motion_group = None

    def _dialog_motion_prepare_snapshot(self, scale):
        self._dialog_motion_clear_snapshot()
        self.ensurePolished()
        pixmap = self.grab()
        if pixmap.isNull():
            return None

        self._dialog_motion_focus_widget = self.focusWidget()
        hidden_children = []
        direct_children = self.findChildren(
            QWidget,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        for child in direct_children:
            should_restore = not child.isHidden()
            if should_restore:
                child.hide()
            hidden_children.append((child, should_restore))
        self._dialog_motion_hidden_children = hidden_children

        snapshot = _DialogSnapshot(pixmap, self)
        snapshot.setGeometry(self.rect())
        snapshot.scale = scale
        snapshot.show()
        snapshot.raise_()
        self._dialog_motion_snapshot = snapshot
        return snapshot

    def _dialog_motion_clear_snapshot(self):
        snapshot = getattr(self, "_dialog_motion_snapshot", None)
        self._dialog_motion_snapshot = None
        if snapshot is not None:
            snapshot.hide()
            snapshot.deleteLater()

        hidden_children = getattr(
            self,
            "_dialog_motion_hidden_children",
            [],
        )
        self._dialog_motion_hidden_children = []
        for child, should_restore in hidden_children:
            if should_restore:
                try:
                    child.show()
                except RuntimeError:
                    pass

        focus_widget = getattr(self, "_dialog_motion_focus_widget", None)
        self._dialog_motion_focus_widget = None
        if focus_widget is not None:
            try:
                if focus_widget.isVisible() and focus_widget.isEnabled():
                    focus_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass

    def _dialog_motion_reset_visuals(self):
        self._dialog_motion_stop_group()
        self._dialog_motion_clear_snapshot()
        self.setWindowOpacity(1.0)

    def _dialog_motion_start_group(
        self,
        *,
        end_opacity,
        end_scale,
        opacity_duration,
        scale_duration,
        opacity_easing,
        scale_easing,
        finished,
    ):
        group = QParallelAnimationGroup(self)

        opacity_animation = QPropertyAnimation(
            self,
            b"windowOpacity",
            group,
        )
        opacity_animation.setStartValue(self.windowOpacity())
        opacity_animation.setEndValue(end_opacity)
        opacity_animation.setDuration(opacity_duration)
        opacity_animation.setEasingCurve(opacity_easing)
        group.addAnimation(opacity_animation)

        snapshot = self._dialog_motion_snapshot
        if snapshot is not None:
            scale_animation = QPropertyAnimation(snapshot, b"scale", group)
            scale_animation.setStartValue(snapshot.scale)
            scale_animation.setEndValue(end_scale)
            scale_animation.setDuration(scale_duration)
            scale_animation.setEasingCurve(scale_easing)
            group.addAnimation(scale_animation)

        group.finished.connect(finished)
        self._dialog_motion_group = group
        group.start()

    def showEvent(self, event):
        self._setup_dialog_motion()
        self._dialog_motion_stop_group()
        self._dialog_motion_clear_snapshot()
        self._dialog_motion_pending_result = None
        self._dialog_motion_dismiss_notified = False

        animate = self._dialog_motion_allowed()
        if animate:
            self._dialog_motion_phase = "enter"
            self.setWindowOpacity(0.0)
        else:
            self._dialog_motion_phase = "idle"
            self._dialog_motion_reset_visuals()

        super().showEvent(event)
        if animate:
            self._dialog_motion_prepare_snapshot(ENTER_SCALE)
            QTimer.singleShot(0, self._dialog_motion_begin_enter)

    def _dialog_motion_begin_enter(self):
        if self._dialog_motion_phase != "enter" or not self.isVisible():
            return
        self._dialog_motion_stop_group()
        self._dialog_motion_start_group(
            end_opacity=1.0,
            end_scale=1.0,
            opacity_duration=ENTER_DURATION_MS,
            scale_duration=ENTER_SCALE_DURATION_MS,
            opacity_easing=QEasingCurve.Type.OutCubic,
            scale_easing=QEasingCurve.Type.OutCubic,
            finished=self._dialog_motion_finish_enter,
        )

    def _dialog_motion_finish_enter(self):
        if self._dialog_motion_phase != "enter":
            return
        group = self._dialog_motion_group
        self._dialog_motion_group = None
        if group is not None:
            group.deleteLater()
        self.setWindowOpacity(1.0)
        self._dialog_motion_clear_snapshot()
        self._dialog_motion_phase = "idle"

    def _dialog_motion_request_done(self, result):
        self._setup_dialog_motion()
        result = int(result)
        if self._dialog_motion_bypass:
            super().done(result)
            return
        if self._dialog_motion_phase == "exit":
            return
        self._dialog_motion_notify_dismiss()
        if not self.isVisible() or not self._dialog_motion_allowed():
            self._dialog_motion_finish_done(result)
            return

        self._dialog_motion_pending_result = result
        self._dialog_motion_phase = "exit"
        self._dialog_motion_stop_group()
        if self._dialog_motion_snapshot is None:
            self._dialog_motion_prepare_snapshot(1.0)
        self._dialog_motion_start_group(
            end_opacity=0.0,
            end_scale=EXIT_SCALE,
            opacity_duration=EXIT_DURATION_MS,
            scale_duration=EXIT_DURATION_MS,
            opacity_easing=QEasingCurve.Type.InCubic,
            scale_easing=QEasingCurve.Type.InCubic,
            finished=self._dialog_motion_finish_exit,
        )

    def _dialog_motion_finish_exit(self):
        if self._dialog_motion_phase != "exit":
            return
        result = self._dialog_motion_pending_result
        self._dialog_motion_pending_result = None
        group = self._dialog_motion_group
        self._dialog_motion_group = None
        if group is not None:
            group.deleteLater()
        self.setWindowOpacity(0.0)
        self._dialog_motion_clear_snapshot()
        self._dialog_motion_phase = "idle"
        self._dialog_motion_finish_done(result)

    def _dialog_motion_finish_done(self, result):
        self._dialog_motion_stop_group()
        self._dialog_motion_clear_snapshot()
        self._dialog_motion_pending_result = None
        self._dialog_motion_phase = "idle"
        self._dialog_motion_bypass = True
        try:
            super().done(int(result))
        finally:
            self._dialog_motion_bypass = False
            try:
                self.setWindowOpacity(1.0)
            except RuntimeError:
                pass

    def accept(self):
        self._dialog_motion_request_done(QDialog.DialogCode.Accepted)

    def reject(self):
        self._dialog_motion_request_done(QDialog.DialogCode.Rejected)

    def done(self, result):
        self._dialog_motion_request_done(result)

    def closeEvent(self, event):
        self._setup_dialog_motion()
        if self._dialog_motion_bypass or not self._dialog_motion_allowed():
            super().closeEvent(event)
            return
        event.ignore()
        self._dialog_motion_request_done(QDialog.DialogCode.Rejected)
