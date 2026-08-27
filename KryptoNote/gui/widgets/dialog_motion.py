"""Shared, interruption-safe motion for application dialogs."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    Property,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QStyle,
    QWidget,
)


ENTER_SCALE = 0.92
ENTER_OPACITY = 0.0
EXIT_SCALE = 0.94


def _system_motion_enabled(widget=None) -> bool:
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


def widget_motion_mode(widget=None) -> str:
    """Resolve the global preference against the platform animation hint."""

    from KryptoNote.gui.theme.theme_manager import get_theme_manager

    mode = get_theme_manager().motion_mode
    if mode == "system":
        return "full" if _system_motion_enabled(widget) else "off"
    return mode


def widget_motion_enabled(widget=None) -> bool:
    """Whether brief opacity/color feedback may animate."""

    return widget_motion_mode(widget) != "off"


def widget_spatial_motion_enabled(widget=None) -> bool:
    """Whether centred scale motion may animate."""

    return widget_motion_mode(widget) == "full"


def widget_motion_duration(widget, kind) -> int:
    mode = widget_motion_mode(widget)
    if mode == "off":
        return 0
    full = {
        "press": 80,
        "state": 140,
        "panel": 220,
        "exit": 80,
        "dialog_enter": 180,
        "dialog_exit": 180,
    }
    reduced = {
        "press": 60,
        "state": 80,
        "panel": 100,
        "exit": 60,
        "dialog_enter": 100,
        "dialog_exit": 100,
    }
    palette = reduced if mode == "reduced" else full
    return palette.get(str(kind), palette["state"])


class _DialogMotionSurface(QWidget):
    """Transient native surface used while the real dialog stays transparent."""

    def __init__(self, pixmap):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self._pixmap = pixmap
        self._scale = 1.0
        self._surface_opacity = 1.0
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
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

    def _get_surface_opacity(self):
        return self._surface_opacity

    def _set_surface_opacity(self, value):
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._surface_opacity) <= 0.0001:
            return
        self._surface_opacity = value
        self.update()

    surfaceOpacity = Property(
        float,
        _get_surface_opacity,
        _set_surface_opacity,
    )

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )
        painter.setOpacity(self._surface_opacity)
        target_width = self.width() * self._scale
        target_height = self.height() * self._scale
        target = QRectF(
            (self.width() - target_width) / 2.0,
            (self.height() - target_height) / 2.0,
            target_width,
            target_height,
        )
        painter.drawPixmap(
            target,
            self._pixmap,
            QRectF(self._pixmap.rect()),
        )


class DialogMotionMixin:
    """Animate a captured top-level surface together with the dim layer.

    The real dialog owns modality and input but stays transparent during motion.
    A click-through transient surface carries the centred scale/fade, avoiding
    both native-window movement and unreliable top-level graphics effects.
    """

    def _setup_dialog_motion(self):
        if getattr(self, "_dialog_motion_ready", False):
            return
        self._dialog_motion_ready = True
        self._dialog_motion_phase = "idle"
        self._dialog_motion_group = None
        self._dialog_motion_window = None
        self._dialog_motion_proxy = None
        self._dialog_motion_prepared = False
        self._dialog_motion_pending_result = None
        self._dialog_motion_bypass = False
        self._dialog_motion_present_callback = None
        self._dialog_motion_present_notified = False
        self._dialog_motion_dismiss_callback = None
        self._dialog_motion_dismiss_notified = False

    def set_dialog_motion_present_callback(self, callback):
        """Run callback once when the dialog is actually presented."""

        self._setup_dialog_motion()
        self._dialog_motion_present_callback = (
            callback if callable(callback) else None
        )

    def _dialog_motion_notify_present(self):
        if self._dialog_motion_present_notified:
            return
        self._dialog_motion_present_notified = True
        callback = self._dialog_motion_present_callback
        if callback is not None:
            callback()

    def set_dialog_motion_dismiss_callback(self, callback):
        """Run callback once when an allowed dismissal begins."""

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

    def _dialog_motion_spatial_allowed(self):
        return widget_spatial_motion_enabled(self)

    def _dialog_motion_stop_group(self):
        group = getattr(self, "_dialog_motion_group", None)
        if group is None:
            return
        group.stop()
        group.deleteLater()
        self._dialog_motion_group = None

    def _dialog_motion_native_surface(self):
        surface = getattr(self, "_dialog_motion_window", None)
        if surface is not None:
            return surface
        try:
            self.createWinId()
            surface = self.windowHandle()
        except RuntimeError:
            surface = None
        self._dialog_motion_window = surface
        return surface

    def _dialog_motion_sync_proxy_geometry(self):
        proxy = getattr(self, "_dialog_motion_proxy", None)
        if proxy is None:
            return
        try:
            proxy.setGeometry(self.frameGeometry())
        except RuntimeError:
            self._dialog_motion_proxy = None

    def _dialog_motion_clear_proxy(self):
        proxy = getattr(self, "_dialog_motion_proxy", None)
        self._dialog_motion_proxy = None
        if proxy is None:
            return
        try:
            proxy.hide()
            proxy.deleteLater()
        except RuntimeError:
            pass

    def _dialog_motion_prepare_proxy(self, scale, opacity):
        self._dialog_motion_clear_proxy()
        self.ensurePolished()
        layout = self.layout()
        if layout is not None:
            layout.activate()
        pixmap = self.grab()
        if pixmap.isNull():
            return None

        proxy = _DialogMotionSurface(pixmap)
        proxy.scale = float(scale)
        proxy.surfaceOpacity = float(opacity)
        proxy.setGeometry(self.frameGeometry())
        try:
            proxy.createWinId()
            proxy_window = proxy.windowHandle()
            dialog_window = self._dialog_motion_native_surface()
            if proxy_window is not None and dialog_window is not None:
                proxy_window.setTransientParent(dialog_window)
        except RuntimeError:
            proxy.deleteLater()
            return None
        self._dialog_motion_proxy = proxy
        return proxy

    def _dialog_motion_show_proxy(self):
        proxy = getattr(self, "_dialog_motion_proxy", None)
        if proxy is None:
            return
        self._dialog_motion_sync_proxy_geometry()
        try:
            proxy.show()
            proxy.raise_()
        except RuntimeError:
            self._dialog_motion_proxy = None

    def _dialog_motion_restore_visuals(self):
        surface = self._dialog_motion_native_surface()
        if surface is not None:
            try:
                # Reveal the real dialog before removing the identical proxy;
                # overlap is harmless and avoids a compositor-sized blank frame.
                surface.setOpacity(1.0)
            except RuntimeError:
                self._dialog_motion_window = None
        self._dialog_motion_clear_proxy()
        self._dialog_motion_prepared = False

    def _dialog_motion_prepare_for_show(self):
        self._setup_dialog_motion()
        self._dialog_motion_stop_group()
        self._dialog_motion_pending_result = None
        self._dialog_motion_present_notified = False
        self._dialog_motion_dismiss_notified = False

        if not self._dialog_motion_allowed():
            self._dialog_motion_phase = "idle"
            self._dialog_motion_restore_visuals()
            return False

        self.ensurePolished()
        surface = self._dialog_motion_native_surface()
        if surface is None:
            self._dialog_motion_phase = "idle"
            return False

        start_scale = (
            ENTER_SCALE if self._dialog_motion_spatial_allowed() else 1.0
        )
        start_opacity = (
            ENTER_OPACITY if self._dialog_motion_spatial_allowed() else 0.0
        )
        self._dialog_motion_prepare_proxy(start_scale, start_opacity)
        try:
            surface.setOpacity(0.0)
        except RuntimeError:
            self._dialog_motion_window = None
            self._dialog_motion_phase = "idle"
            return False

        self._dialog_motion_prepared = True
        self._dialog_motion_phase = "prepared"
        return True

    def show(self):
        self._dialog_motion_prepare_for_show()
        return super().show()

    def open(self):
        self._dialog_motion_prepare_for_show()
        return super().open()

    def exec(self):
        self._dialog_motion_prepare_for_show()
        return super().exec()

    def _dialog_motion_start_group(
        self,
        *,
        end_opacity,
        end_scale,
        duration,
        easing,
        finished,
    ):
        surface = self._dialog_motion_native_surface()
        proxy = self._dialog_motion_proxy
        if surface is None and proxy is None:
            return False

        group = QParallelAnimationGroup(self)
        opacity_target = proxy if proxy is not None else surface
        opacity_property = (
            b"surfaceOpacity" if proxy is not None else b"opacity"
        )
        opacity_animation = QPropertyAnimation(
            opacity_target,
            opacity_property,
            group,
        )
        opacity_animation.setStartValue(
            float(
                proxy.surfaceOpacity
                if proxy is not None
                else surface.opacity()
            )
        )
        opacity_animation.setEndValue(float(end_opacity))
        opacity_animation.setDuration(int(duration))
        opacity_animation.setEasingCurve(easing)
        group.addAnimation(opacity_animation)

        if proxy is not None and end_scale is not None:
            scale_animation = QPropertyAnimation(proxy, b"scale", group)
            scale_animation.setStartValue(float(proxy.scale))
            scale_animation.setEndValue(float(end_scale))
            scale_animation.setDuration(int(duration))
            scale_animation.setEasingCurve(easing)
            group.addAnimation(scale_animation)

        group.finished.connect(finished)
        self._dialog_motion_group = group
        group.start()
        return True

    def showEvent(self, event):
        self._setup_dialog_motion()
        animate = self._dialog_motion_prepared
        if not animate:
            animate = self._dialog_motion_prepare_for_show()

        self._dialog_motion_phase = "enter" if animate else "idle"
        super().showEvent(event)
        if animate:
            self._dialog_motion_begin_enter()
        else:
            self._dialog_motion_notify_present()

    def _dialog_motion_begin_enter(self):
        if self._dialog_motion_phase != "enter" or not self.isVisible():
            return
        self._dialog_motion_stop_group()
        self._dialog_motion_show_proxy()
        started = self._dialog_motion_start_group(
            end_opacity=1.0,
            end_scale=(
                1.0 if self._dialog_motion_spatial_allowed() else None
            ),
            duration=widget_motion_duration(self, "dialog_enter"),
            easing=QEasingCurve.Type.OutQuad,
            finished=self._dialog_motion_finish_enter,
        )
        # Both animations start synchronously, before control returns to the
        # event loop, so neither surface can establish a frame alone.
        self._dialog_motion_notify_present()
        if not started:
            self._dialog_motion_finish_enter()

    def _dialog_motion_finish_enter(self):
        if self._dialog_motion_phase != "enter":
            return
        group = self._dialog_motion_group
        self._dialog_motion_group = None
        if group is not None:
            group.deleteLater()
        self._dialog_motion_restore_visuals()
        self._dialog_motion_phase = "idle"

    def _dialog_motion_request_done(self, result):
        self._setup_dialog_motion()
        result = int(result)
        if self._dialog_motion_bypass:
            super().done(result)
            return
        if self._dialog_motion_phase == "exit":
            return
        if not self.isVisible() or not self._dialog_motion_allowed():
            self._dialog_motion_notify_dismiss()
            self._dialog_motion_finish_done(result)
            return

        self._dialog_motion_pending_result = result
        self._dialog_motion_phase = "exit"
        self._dialog_motion_stop_group()
        surface = self._dialog_motion_native_surface()
        if surface is None:
            self._dialog_motion_notify_dismiss()
            self._dialog_motion_finish_done(result)
            return

        proxy = self._dialog_motion_proxy
        if proxy is None:
            proxy = self._dialog_motion_prepare_proxy(1.0, 1.0)
        if proxy is not None:
            self._dialog_motion_show_proxy()
            try:
                surface.setOpacity(0.0)
            except RuntimeError:
                self._dialog_motion_window = None
        end_scale = None
        if proxy is not None and self._dialog_motion_spatial_allowed():
            end_scale = min(EXIT_SCALE, float(proxy.scale))
        started = self._dialog_motion_start_group(
            end_opacity=0.0,
            end_scale=end_scale,
            duration=widget_motion_duration(self, "dialog_exit"),
            easing=QEasingCurve.Type.InOutCubic,
            finished=self._dialog_motion_finish_exit,
        )
        self._dialog_motion_notify_dismiss()
        if not started:
            self._dialog_motion_finish_done(result)

    def _dialog_motion_finish_exit(self):
        if self._dialog_motion_phase != "exit":
            return
        result = self._dialog_motion_pending_result
        self._dialog_motion_pending_result = None
        group = self._dialog_motion_group
        self._dialog_motion_group = None
        if group is not None:
            group.deleteLater()
        self._dialog_motion_finish_done(result)

    def _dialog_motion_finish_done(self, result):
        self._dialog_motion_stop_group()
        self._dialog_motion_pending_result = None
        self._dialog_motion_phase = "idle"
        self._dialog_motion_bypass = True
        try:
            super().done(int(result))
        finally:
            self._dialog_motion_bypass = False
            # Reset only after QDialog emitted finished and hid the native
            # surface; resetting while visible causes a one-frame flash.
            self._dialog_motion_restore_visuals()

    def accept(self):
        self._dialog_motion_request_done(QDialog.DialogCode.Accepted)

    def reject(self):
        self._dialog_motion_request_done(QDialog.DialogCode.Rejected)

    def done(self, result):
        self._dialog_motion_request_done(result)

    def closeEvent(self, event):
        self._setup_dialog_motion()
        if self._dialog_motion_bypass:
            super().closeEvent(event)
            return
        if not self._dialog_motion_allowed():
            self._dialog_motion_notify_dismiss()
            super().closeEvent(event)
            return
        event.ignore()
        self._dialog_motion_request_done(QDialog.DialogCode.Rejected)
