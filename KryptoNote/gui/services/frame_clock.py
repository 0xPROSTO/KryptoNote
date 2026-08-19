"""Adaptive GUI-thread frame clock for QQuickWidget-based motion."""

import math

from PySide6.QtCore import (
    QElapsedTimer,
    QObject,
    Property,
    QTimer,
    Qt,
    Signal,
    Slot,
)


class HighRefreshFrameClock(QObject):
    """Drive imperative QML motion above QQuickWidget's 60 Hz animation timer.

    QQuickWidget uses Qt Quick's basic render loop, so its normal animation
    driver is timer-based and typically advances every 16 ms. This clock uses a
    precise timer sized from the current screen refresh rate and reports the
    measured delta time to QML.
    """

    tick = Signal(float)
    activeChanged = Signal()
    refreshRateChanged = Signal()
    intervalMsChanged = Signal()

    MIN_REFRESH_RATE = 30.0
    MAX_REFRESH_RATE = 120.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._refresh_rate = 60.0
        self._interval_ms = self._interval_for_rate(self._refresh_rate)
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._on_timeout)

    @Property(bool, notify=activeChanged)
    def active(self):
        return self._active

    @Property(float, notify=refreshRateChanged)
    def refreshRate(self):
        return self._refresh_rate

    @Property(int, notify=intervalMsChanged)
    def intervalMs(self):
        return self._interval_ms

    @Slot(bool)
    def setActive(self, active):
        active = bool(active)
        if self._active == active:
            return
        self._active = active
        if active:
            self._elapsed.start()
            self._timer.start()
        else:
            self._timer.stop()
            self._elapsed.invalidate()
        self.activeChanged.emit()

    @Slot(float)
    def setRefreshRate(self, refresh_rate):
        try:
            refresh_rate = float(refresh_rate)
        except (TypeError, ValueError):
            refresh_rate = 60.0
        if not math.isfinite(refresh_rate) or refresh_rate <= 0:
            refresh_rate = 60.0
        refresh_rate = min(
            self.MAX_REFRESH_RATE,
            max(self.MIN_REFRESH_RATE, refresh_rate),
        )
        interval_ms = self._interval_for_rate(refresh_rate)
        rate_changed = not math.isclose(
            refresh_rate, self._refresh_rate, rel_tol=0.0, abs_tol=0.01
        )
        interval_changed = interval_ms != self._interval_ms
        self._refresh_rate = refresh_rate
        self._interval_ms = interval_ms
        if interval_changed:
            self._timer.setInterval(interval_ms)
            self.intervalMsChanged.emit()
        if rate_changed:
            self.refreshRateChanged.emit()

    def set_screen(self, screen):
        if screen is not None:
            self.setRefreshRate(screen.refreshRate())

    @classmethod
    def _interval_for_rate(cls, refresh_rate):
        # QQuickWidget renders through an extra offscreen pass.  Driving its
        # GUI thread above 120 Hz only queues work on high-refresh displays.
        # Measured delta time keeps motion speed stable at the capped rate.
        minimum_interval = math.ceil(1000.0 / cls.MAX_REFRESH_RATE)
        return max(minimum_interval, int(1000.0 / float(refresh_rate)))

    @Slot()
    def _on_timeout(self):
        if not self._active:
            return
        elapsed_ns = self._elapsed.nsecsElapsed()
        self._elapsed.restart()
        fallback = self._interval_ms / 1000.0
        frame_time = fallback if elapsed_ns <= 0 else elapsed_ns / 1_000_000_000.0
        self.tick.emit(min(frame_time, 0.05))
