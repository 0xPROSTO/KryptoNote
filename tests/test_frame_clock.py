from PySide6.QtCore import QCoreApplication, Qt

from KryptoNote.gui.services.frame_clock import HighRefreshFrameClock


def _clock():
    QCoreApplication.instance() or QCoreApplication([])
    return HighRefreshFrameClock()


def _tick_once(clock):
    clock._active = True
    clock._elapsed.start()
    clock._on_timeout()


def test_frame_clock_emits_one_measured_tick_without_forced_repaint():
    clock = _clock()
    frame_times = []
    clock.tick.connect(frame_times.append)

    _tick_once(clock)

    assert len(frame_times) == 1
    assert 0 < frame_times[0] <= 0.05
    assert not hasattr(clock, "_update_callback")


def test_frame_clock_caps_a_240_hz_screen_at_an_approximately_120_hz_cadence():
    clock = _clock()

    clock.setRefreshRate(240.0)

    assert clock.refreshRate == 120.0
    assert clock.intervalMs == 8
    assert clock._timer.timerType() == Qt.TimerType.PreciseTimer
