from PyQt6.QtWidgets import QGraphicsPixmapItem, QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene
from PyQt6.QtGui import QColor, QBrush, QPainter
from PyQt6.QtCore import Qt


class ZoomableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        event.accept()


class MediaViewerDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secure Viewer")
        self.resize(1000, 800)
        self.setStyleSheet("background-color: #121212;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#000000")))

        self.view = ZoomableView(self.scene)
        layout.addWidget(self.view)

        self.pix_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pix_item)

        self.view.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)