"""Native canvas toast kept above the QWidget dim layer."""

from __future__ import annotations

import time

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    Property,
    QPropertyAnimation,
    QTimer,
    Qt,
    Slot,
)
from PySide6.QtGui import QFont, QPainter, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
)

from KryptoNote.gui.theme.palette import Palette
from KryptoNote.gui.widgets.dialog_motion import (
    widget_motion_duration,
    widget_motion_enabled,
    widget_spatial_motion_enabled,
)


class _ElidedLabel(QLabel):
    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        text = self.fontMetrics().elidedText(
            self.text(),
            Qt.TextElideMode.ElideRight,
            max(0, self.contentsRect().width()),
        )
        painter.drawText(
            self.contentsRect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )


class CanvasToastOverlay(QFrame):
    """Click-through semantic feedback above dim, below top-level dialogs."""

    HOLD_MILLISECONDS = 2600
    BOTTOM_MARGIN = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvas_toast_overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(38)
        self.hide()

        self._vertical_offset = 0.0
        self._kind = "success"
        self._last_message = ""
        self._last_kind = ""
        self._last_shown_at = 0.0
        self._enter_group = None
        self._exit_group = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 0, 12, 0)
        layout.setSpacing(10)

        self._dot = QFrame(self)
        self._dot.setObjectName("canvas_toast_dot")
        self._dot.setFixedSize(7, 7)
        layout.addWidget(self._dot)

        self._label = _ElidedLabel(self)
        self._label.setFont(QFont("Segoe UI Semibold", 9))
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._label, 1)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(self.HOLD_MILLISECONDS)
        self._hold_timer.timeout.connect(self._start_exit)

        if parent is not None:
            parent.installEventFilter(self)
        self.refresh_theme()

    def _get_vertical_offset(self):
        return self._vertical_offset

    def _set_vertical_offset(self, value):
        self._vertical_offset = float(value)
        self._reposition()

    verticalOffset = Property(
        float,
        _get_vertical_offset,
        _set_vertical_offset,
    )

    @Slot(str, str)
    def show_message(self, message, kind="success"):
        message = str(message or "").strip()
        if not message:
            return
        kind = str(kind or "success").strip().lower()
        if kind not in {"success", "warning", "error"}:
            kind = "success"

        now = time.monotonic()
        if (
            message == self._last_message
            and kind == self._last_kind
            and now - self._last_shown_at < 0.25
        ):
            return
        self._last_message = message
        self._last_kind = kind
        self._last_shown_at = now

        self._stop_group("_enter_group")
        self._stop_group("_exit_group")
        self._hold_timer.stop()
        self._kind = kind
        self._label.setText(message)
        self.setAccessibleName(message)
        self._resize_for_message(message)
        self.refresh_theme()

        spatial = widget_spatial_motion_enabled(self)
        self._vertical_offset = 6.0 if spatial else 0.0
        self._opacity_effect.setOpacity(
            0.0 if widget_motion_enabled(self) else 1.0
        )
        self._reposition()
        self.show()
        self.raise_()

        if widget_motion_enabled(self):
            group = QParallelAnimationGroup(self)
            opacity = QPropertyAnimation(
                self._opacity_effect,
                b"opacity",
                group,
            )
            opacity.setStartValue(self._opacity_effect.opacity())
            opacity.setEndValue(1.0)
            opacity.setDuration(widget_motion_duration(self, "state"))
            opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(opacity)
            if spatial:
                offset = QPropertyAnimation(self, b"verticalOffset", group)
                offset.setStartValue(self._vertical_offset)
                offset.setEndValue(0.0)
                offset.setDuration(widget_motion_duration(self, "state"))
                offset.setEasingCurve(QEasingCurve.Type.OutCubic)
                group.addAnimation(offset)
            self._enter_group = group
            group.start()
        else:
            self._vertical_offset = 0.0
            self._reposition()
        self._hold_timer.start()

    @Slot()
    def refresh_theme(self):
        semantic = {
            "error": Palette.DANGER_HOVER,
            "warning": Palette.TAG_STARRED,
            "success": Palette.SUCCESS_HOVER,
        }.get(self._kind, Palette.SUCCESS_HOVER)
        self.setStyleSheet(
            "QFrame#canvas_toast_overlay {"
            f"background:{Palette.BG_POPOVER};"
            f"border:1px solid {semantic};"
            "border-radius:7px;"
            "}"
            "QFrame#canvas_toast_dot {"
            f"background:{semantic};"
            "border:none;"
            "border-radius:3px;"
            "}"
            "QLabel {"
            f"color:{Palette.TEXT_MAIN};"
            "background:transparent;"
            "border:none;"
            "}"
        )

    def _resize_for_message(self, message):
        text_width = self._label.fontMetrics().horizontalAdvance(message)
        self.setFixedWidth(max(180, min(420, text_width + 44)))
        self._reposition()

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(
            round((parent.width() - self.width()) / 2),
            round(
                parent.height()
                - self.height()
                - self.BOTTOM_MARGIN
                + self._vertical_offset
            ),
        )

    def _start_exit(self):
        self._stop_group("_enter_group")
        self._stop_group("_exit_group")
        if not self.isVisible():
            return
        if not widget_motion_enabled(self):
            self._finish_exit()
            return

        group = QParallelAnimationGroup(self)
        opacity = QPropertyAnimation(
            self._opacity_effect,
            b"opacity",
            group,
        )
        opacity.setStartValue(self._opacity_effect.opacity())
        opacity.setEndValue(0.0)
        opacity.setDuration(widget_motion_duration(self, "exit"))
        opacity.setEasingCurve(QEasingCurve.Type.InCubic)
        group.addAnimation(opacity)
        if widget_spatial_motion_enabled(self):
            offset = QPropertyAnimation(self, b"verticalOffset", group)
            offset.setStartValue(self._vertical_offset)
            offset.setEndValue(-4.0)
            offset.setDuration(widget_motion_duration(self, "exit"))
            offset.setEasingCurve(QEasingCurve.Type.InCubic)
            group.addAnimation(offset)
        group.finished.connect(self._finish_exit)
        self._exit_group = group
        group.start()

    def _finish_exit(self):
        self.hide()
        self._opacity_effect.setOpacity(0.0)
        self._vertical_offset = 0.0
        self._reposition()
        self._stop_group("_exit_group")

    def _stop_group(self, attribute):
        group = getattr(self, attribute, None)
        if group is None:
            return
        setattr(self, attribute, None)
        group.stop()
        group.deleteLater()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._reposition()
        return super().eventFilter(watched, event)
