from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QWidget, QFrame, QGraphicsOpacityEffect


class DimOverlay(QFrame):
    def __init__(self, parent=None, block_input=False, auto_show=True):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

        if not block_input:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.setStyleSheet("DimOverlay { background-color: rgba(0, 0, 0, 80); }")

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._delete_on_finished_connected = False

        if auto_show:
            self.show()
            self.fade_in()
        else:
            self.hide()

    def fade_in(self):
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

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)
