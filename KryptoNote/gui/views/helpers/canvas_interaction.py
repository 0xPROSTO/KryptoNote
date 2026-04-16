import time

from PySide6.QtCore import (
    QObject,
    Signal,
    QPointF,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    QAbstractAnimation,
    Qt,
)
from PySide6.QtWidgets import QGraphicsView


class InertiaHandler(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.pan_velocity = QPointF(0, 0)
        self.pan_remainder = QPointF(0, 0)
        self.last_move_timestamp = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._apply_inertia)

    def stop(self):
        self.timer.stop()
        self.pan_velocity = QPointF(0, 0)
        self.pan_remainder = QPointF(0, 0)

    def update_velocity(self, delta):
        self.last_move_timestamp = time.time()
        self.pan_velocity = self.pan_velocity * 0.4 + delta * 2.0

    def decay_velocity(self):
        self.pan_velocity *= 0.4

    def start_if_needed(self):
        if (time.time() - self.last_move_timestamp) > 0.08:
            self.pan_velocity = QPointF(0, 0)

        if self.pan_velocity.manhattanLength() > 2:
            self.timer.start()

    def _apply_inertia(self):
        self.pan_velocity *= 0.85
        speed = self.pan_velocity.manhattanLength()
        if speed < 1.0:
            self.timer.stop()
            self.pan_remainder = QPointF(0, 0)
            self._force_hover_update()
            return

        dx = self.pan_velocity.x() + self.pan_remainder.x()
        dy = self.pan_velocity.y() + self.pan_remainder.y()
        idx = int(dx)
        idy = int(dy)
        self.pan_remainder = QPointF(dx - idx, dy - idy)
        hbar = self.view.horizontalScrollBar()
        vbar = self.view.verticalScrollBar()
        hbar.setValue(hbar.value() - idx)
        vbar.setValue(vbar.value() - idy)
        self._force_hover_update()

    def _force_hover_update(self):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent

        pos = self.view.viewport().mapFromGlobal(self.view.cursor().pos())
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            pos,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        super(QGraphicsView, self.view).mouseMoveEvent(event)


class ZoomHandler(QObject):
    zoom_changed = Signal(float)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.target_scale = 1.0
        self.zoom_scene_pos = QPointF()
        self.zoom_viewport_pos = QPointF()
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.valueChanged.connect(self._apply_zoom)
        self.anim.finished.connect(self._on_zoom_finished)

    def scale_to(self, target, pos):
        if self.anim.state() != QAbstractAnimation.State.Running:
            self.zoom_viewport_pos = pos
            self.zoom_scene_pos = self.view.mapToScene(self.zoom_viewport_pos)
            self.target_scale = target
        else:
            self.target_scale = target

        self.target_scale = max(0.1, min(self.target_scale, 5.0))
        self.anim.stop()
        self.anim.setStartValue(self.view.transform().m11())
        self.anim.setEndValue(self.target_scale)
        self.anim.start()

    def _apply_zoom(self, scale_value):
        from PySide6.QtGui import QTransform

        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.view.setTransform(QTransform.fromScale(scale_value, scale_value))
        new_viewport_pos = self.view.mapFromScene(self.zoom_scene_pos)
        delta = new_viewport_pos - self.zoom_viewport_pos
        hbar = self.view.horizontalScrollBar()
        vbar = self.view.verticalScrollBar()
        hbar.setValue(hbar.value() + int(delta.x()))
        vbar.setValue(vbar.value() + int(delta.y()))
        self.view.update()
        self.zoom_changed.emit(scale_value)

    def _on_zoom_finished(self):
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._force_hover_update()

    def _force_hover_update(self):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent

        pos = self.view.viewport().mapFromGlobal(self.view.cursor().pos())
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            pos,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        super(QGraphicsView, self.view).mouseMoveEvent(event)
