from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


class DimOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 76);")  # ~30%
        self.show()

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)
