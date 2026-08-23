"""Shared platform-aware dragging for frameless top-level widgets."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QMenuBar,
    QTextEdit,
    QWidget,
)

from KryptoNote.gui.widgets.dialog_motion import DialogMotionMixin


class FramelessWindowDragMixin(DialogMotionMixin):
    """Add an explicit title-handle drag gesture.

    Wayland does not provide reliable global pointer coordinates for clients.
    The hit test therefore stays in the local widget coordinate space and the
    compositor-owned ``startSystemMove()`` path is attempted directly on the
    press.  Manual top-level movement is retained only for xcb and win32.
    """

    _DRAG_INTERACTIVE_TYPES = (
        QAbstractButton,
        QAbstractItemView,
        QAbstractScrollArea,
        QAbstractSlider,
        QAbstractSpinBox,
        QComboBox,
        QLineEdit,
        QMenuBar,
        QTextEdit,
    )

    @staticmethod
    def _platform_name():
        try:
            return str(QGuiApplication.platformName()).lower()
        except RuntimeError:
            return "windows" if sys.platform == "win32" else "unknown"

    @classmethod
    def uses_custom_chrome(cls):
        """Keep the custom frameless chrome only on Windows.

        Wayland compositors own client-window movement and decoration.  Linux
        dialogs therefore use the native title bar; this avoids relying on
        global pointer coordinates or a compositor-specific startSystemMove
        gesture.  Windows retains the existing frameless appearance and
        explicit drag path.
        """

        return cls._platform_name() in {
            "windows",
            "win32",
        }

    def configure_dialog_chrome(self, title=None):
        """Apply platform-safe flags before a dialog is shown."""

        self._setup_dialog_motion()

        if self.uses_custom_chrome():
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            return

        native_flags = (
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowFlags(native_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        if title:
            self.setWindowTitle(str(title))

    def _setup_window_drag(self, drag_height: int = 64, drag_handles=None) -> None:
        self._window_drag_height = max(1, int(drag_height))
        self._window_drag_handles = []
        self._window_drag_handle_ids = set()
        self._window_dragging = False
        self._window_drag_native = False
        self._window_drag_last_global = QPoint()
        self._window_drag_platform = self._window_platform_name()
        self._window_drag_enabled = self.uses_custom_chrome()
        if not self._window_drag_enabled:
            # Native Linux decorations/compositor movement own the gesture;
            # do not install an event filter that could swallow title events.
            return
        self.installEventFilter(self)
        for handle in drag_handles or ():
            self._register_window_drag_handle(handle)

    def _register_window_drag_handle(self, handle):
        if not isinstance(handle, QWidget):
            return
        if id(handle) in self._window_drag_handle_ids:
            return
        self._window_drag_handles.append(handle)
        self._window_drag_handle_ids.add(id(handle))
        handle.installEventFilter(self)
        for child in handle.findChildren(QWidget):
            child.installEventFilter(self)

    @staticmethod
    def _window_platform_name():
        try:
            return str(QGuiApplication.platformName()).lower()
        except RuntimeError:
            return "windows" if sys.platform == "win32" else "unknown"

    @staticmethod
    def _event_local_position(event):
        try:
            return event.position().toPoint()
        except AttributeError:
            try:
                return event.pos()
            except AttributeError:
                return QPoint()

    @staticmethod
    def _event_global_position(event):
        try:
            return event.globalPosition().toPoint()
        except AttributeError:
            try:
                return event.globalPos()
            except AttributeError:
                return None

    def _event_window_position(self, watched, event):
        local_pos = self._event_local_position(event)
        if isinstance(watched, QWidget) and watched is not self:
            return watched.mapTo(self, local_pos)
        return local_pos

    def _legacy_map_from_global(self, global_pos):
        """Compatibility helper; never used for the drag-region hit test."""

        return self.mapFromGlobal(global_pos)

    def _window_drag_is_interactive(self, watched) -> bool:
        cursor = watched
        while isinstance(cursor, QWidget):
            if isinstance(cursor, self._DRAG_INTERACTIVE_TYPES):
                return True
            if cursor is self:
                break
            cursor = cursor.parentWidget()
        return False

    def _window_drag_handle_for(self, watched, local_pos):
        if not self._window_drag_handles:
            return None
        cursor = watched if isinstance(watched, QWidget) else None
        while isinstance(cursor, QWidget):
            if id(cursor) in self._window_drag_handle_ids:
                handle = cursor
                handle_pos = handle.mapFrom(self, local_pos)
                if handle.rect().contains(handle_pos):
                    return handle
            if cursor is self:
                break
            cursor = cursor.parentWidget()

        # A child may have been created after setup; the local geometry check
        # keeps the explicit handle contract intact without global coordinates.
        for handle in self._window_drag_handles:
            handle_pos = handle.mapFrom(self, local_pos)
            if handle.rect().contains(handle_pos):
                return handle
        return None

    def _manual_drag_allowed(self):
        platform = getattr(self, "_window_drag_platform", None)
        if platform is None:
            # Legacy/unit callers can invoke the helper without setup.  Their
            # explicit manual movement request is still honoured; real dialog
            # instances always set the platform during _setup_window_drag.
            return True
        # Unit probes and legacy callers may invoke the manual helper without
        # running _setup_window_drag first; keep that path deterministic.
        if platform == "unknown":
            platform = "windows" if sys.platform == "win32" else "xcb"
        return platform in {"xcb", "windows", "win32"}

    def _start_window_drag(self, event):
        self._window_dragging = False
        self._window_drag_native = False
        handle = self.windowHandle()
        if handle is not None:
            start_system_move = getattr(handle, "startSystemMove", None)
            if callable(start_system_move):
                try:
                    self._window_drag_native = bool(start_system_move())
                except (RuntimeError, TypeError):
                    self._window_drag_native = False
        if self._window_drag_native:
            self._window_dragging = True
            return True

        # Direct top-level move is intentionally never attempted on Wayland.
        if not self._manual_drag_allowed():
            return False
        global_pos = self._event_global_position(event)
        if global_pos is None:
            return False
        self._window_drag_last_global = QPoint(global_pos)
        self._window_dragging = True
        return True

    def _apply_manual_window_drag(self, global_pos: QPoint) -> None:
        if not self._manual_drag_allowed():
            return
        delta = global_pos - self._window_drag_last_global
        if not delta.isNull():
            self.move(self.pos() + delta)
            self._window_drag_last_global = QPoint(global_pos)

    def _stop_window_drag(self) -> None:
        self._window_dragging = False
        self._window_drag_native = False

    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget):
                # Only registered title handles and their descendants are
                # eligible; this hook keeps late-created close buttons safe.
                for handle in self._window_drag_handles:
                    if child is handle or handle.isAncestorOf(child):
                        child.installEventFilter(self)
                        break
            return super().eventFilter(watched, event)

        if event_type == QEvent.Type.MouseButtonPress:
            if (
                event.button() == Qt.MouseButton.LeftButton
                and not self._window_drag_is_interactive(watched)
            ):
                local_pos = self._event_window_position(watched, event)
                if self._window_drag_handle_for(watched, local_pos) is not None:
                    if self._start_window_drag(event):
                        event.accept()
                        return True

        elif event_type == QEvent.Type.MouseMove:
            if self._window_dragging and event.buttons() & Qt.MouseButton.LeftButton:
                if not self._window_drag_native and self._manual_drag_allowed():
                    global_pos = self._event_global_position(event)
                    if global_pos is not None:
                        self._apply_manual_window_drag(global_pos)
                event.accept()
                return True

        elif event_type == QEvent.Type.MouseButtonRelease:
            if self._window_dragging:
                self._stop_window_drag()
                event.accept()
                return True

        return super().eventFilter(watched, event)
