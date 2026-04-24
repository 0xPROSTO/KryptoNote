from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QFont
from PySide6.QtWidgets import QWidget

from KryptoNote.gui.theme.palette import Palette


class ProgressBarWidget(QWidget):
    """
    A progress bar designed to sit inside the QStatusBar.
    """

    BAR_HEIGHT = 3
    ANIM_DURATION = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._visible_progress = 0.0
        self._message = ""
        self._active = False

        self.setFixedHeight(self.BAR_HEIGHT)
        self.setVisible(False)


        self._progress_anim = QPropertyAnimation(self, b"visible_progress", self)
        self._progress_anim.setDuration(self.ANIM_DURATION)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)


        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(600)
        self._hide_timer.timeout.connect(self._do_hide)


        from PySide6.QtWidgets import QGraphicsOpacityEffect
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(200)
        self._fade_out_connected = False

    # --- Qt Property for animation ---
    def _get_visible_progress(self):
        return self._visible_progress

    def _set_visible_progress(self, val):
        self._visible_progress = val
        self.update()

    visible_progress = Property(float, _get_visible_progress, _set_visible_progress)

    # --- Public API ---

    def start(self, message="", indeterminate=False):
        self._active = True
        self._progress = 0.0
        self._visible_progress = 0.0
        self._message = message
        self._indeterminate = indeterminate
        self._indeterminate_offset = 0.0
        self._hide_timer.stop()
        
        self._fade_anim.stop()
        if getattr(self, '_fade_out_connected', False):
            self._fade_anim.finished.disconnect(self._on_fade_out_finished)
            self._fade_out_connected = False
            
        self.setVisible(True)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        
        if indeterminate and not hasattr(self, '_indet_timer'):
            self._indet_timer = QTimer(self)
            self._indet_timer.timeout.connect(self._update_indeterminate)
            self._indet_timer.start(30)
        elif indeterminate and hasattr(self, '_indet_timer'):
            self._indet_timer.start(30)
            
        self.update()

    def _update_indeterminate(self):
        self._indeterminate_offset += 2.0
        if self._indeterminate_offset > 40.0:
            self._indeterminate_offset = 0.0
        self.update()

    def set_progress(self, value: float, message: str = ""):
        """
        Update progress (0.0 to 1.0).
        Updates instantly without animation to avoid Qt crashes in tight loops.
        """
        if not self._active:
            self.start(message)

        self._progress = max(0.0, min(1.0, value))
        if message:
            self._message = message

        self._progress_anim.stop()
        self._visible_progress = self._progress
        self.update()

    def finish(self, message=""):
        self._indeterminate = False
        if hasattr(self, '_indet_timer'):
            self._indet_timer.stop()
        if message:
            self._message = message
        self.set_progress(1.0)
        self._active = False
        self._hide_timer.start()

    def cancel(self):
        self._indeterminate = False
        if hasattr(self, '_indet_timer'):
            self._indet_timer.stop()
        self._active = False
        self._progress = 0.0
        self._visible_progress = 0.0
        self._hide_timer.stop()
        
        self._fade_anim.stop()
        if getattr(self, '_fade_out_connected', False):
            self._fade_anim.finished.disconnect(self._on_fade_out_finished)
            self._fade_out_connected = False
            
        self._opacity_effect.setOpacity(0.0)
        self.setVisible(False)

    @property
    def message(self):
        return self._message

    # --- Internal ---

    def _do_hide(self):
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        
        if not getattr(self, '_fade_out_connected', False):
            self._fade_anim.finished.connect(self._on_fade_out_finished)
            self._fade_out_connected = True
            
        self._fade_anim.start()

    def _on_fade_out_finished(self):
        if getattr(self, '_fade_out_connected', False):
            self._fade_anim.finished.disconnect(self._on_fade_out_finished)
            self._fade_out_connected = False
            
        if self._opacity_effect.opacity() == 0.0:
            self.setVisible(False)
            self._progress = 0.0
            self._visible_progress = 0.0
            self._message = ""
            self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()


        painter.fillRect(0, 0, w, h, QColor(Palette.BG_PANEL))


        if getattr(self, "_indeterminate", False):

            stripe_width = 20
            painter.setPen(Qt.PenStyle.NoPen)
            for x in range(int(-self._indeterminate_offset), w, stripe_width * 2):
                painter.fillRect(x, 0, stripe_width, h, QColor(Palette.ACCENT_MAIN))
                painter.fillRect(x + stripe_width, 0, stripe_width, h, QColor(Palette.ACCENT_HIGH))
        elif self._visible_progress > 0:
            fill_w = int(w * self._visible_progress)
            gradient = QLinearGradient(0, 0, fill_w, 0)
            gradient.setColorAt(0.0, QColor(Palette.ACCENT_MAIN))
            gradient.setColorAt(1.0, QColor(Palette.ACCENT_HIGH))
            painter.fillRect(0, 0, fill_w, h, gradient)

        painter.end()
