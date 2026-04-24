from PySide6.QtCore import QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton, QGraphicsColorizeEffect


class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.effect = QGraphicsColorizeEffect(self)
        self.effect.setColor(QColor("#151515"))
        self.effect.setStrength(0.0)
        self.setGraphicsEffect(self.effect)

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200)
        self.anim.valueChanged.connect(self.effect.setStrength)

    def setEnabled(self, enabled):
        if self.isEnabled() == enabled:
            return
        super().setEnabled(enabled)
        self.anim.stop()
        if enabled:
            self.anim.setStartValue(self.effect.strength())
            self.anim.setEndValue(0.0)
        else:
            self.anim.setStartValue(self.effect.strength())
            self.anim.setEndValue(1.0)
        self.anim.start()
