from PyQt6.QtWidgets import (QGraphicsPixmapItem, QDialog, QVBoxLayout,
                             QGraphicsView, QGraphicsScene, QPushButton)
from PyQt6.QtGui import QColor, QBrush, QPainter
from PyQt6.QtCore import Qt, QTimer


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

        self.setStyleSheet("""
            QDialog { background-color: #050505; }
            QPushButton { 
                background-color: rgba(30, 30, 30, 160); 
                color: rgba(255, 255, 255, 200); 
                border: 1px solid rgba(255, 255, 255, 30); 
                font-size: 16px;
                border-radius: 8px; 
            }
            QPushButton:hover { 
                background-color: rgba(80, 80, 80, 220); 
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#050505")))

        self.view = ZoomableView(self.scene)
        self.view.setStyleSheet("border: none;")
        layout.addWidget(self.view)

        self.pixmap = pixmap
        self.pix_item = QGraphicsPixmapItem(self.pixmap)
        self.pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene.addItem(self.pix_item)

        self.current_rotation = 0

        self.btn_rot_left = QPushButton("⟲", self)
        self.btn_rot_left.setToolTip("Rotate Left")
        self.btn_rot_left.setFixedSize(45, 45)
        self.btn_rot_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rot_left.clicked.connect(self.rotate_left)

        self.btn_fit = QPushButton("⛶", self)
        self.btn_fit.setToolTip("Fit to Window")
        self.btn_fit.setFixedSize(45, 45)
        self.btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fit.clicked.connect(self.fit_image)

        self.btn_rot_right = QPushButton("⟳", self)
        self.btn_rot_right.setToolTip("Rotate Right")
        self.btn_rot_right.setFixedSize(45, 45)
        self.btn_rot_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rot_right.clicked.connect(self.rotate_right)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        btn_w = 45
        gap = 10
        total_w = (btn_w * 3) + (gap * 2)
        start_x = (self.width() - total_w) // 2
        y = self.height() - btn_w - 40

        self.btn_rot_left.move(start_x, y)
        self.btn_fit.move(start_x + btn_w + gap, y)
        self.btn_rot_right.move(start_x + (btn_w + gap) * 2, y)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_image)

    def fit_image(self):
        self.view.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def rotate_left(self):
        self.current_rotation = (self.current_rotation - 90) % 360
        self.apply_rotation()

    def rotate_right(self):
        self.current_rotation = (self.current_rotation + 90) % 360
        self.apply_rotation()

    def apply_rotation(self):
        center = self.pix_item.boundingRect().center()
        self.pix_item.setTransformOriginPoint(center)
        self.pix_item.setRotation(self.current_rotation)
        self.fit_image()