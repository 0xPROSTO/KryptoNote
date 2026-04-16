from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QBrush, QPainter, QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QDialog,
    QVBoxLayout,
    QGraphicsView,
    QGraphicsScene,
    QPushButton,
    QGraphicsItem,
)


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


class LargeImageItem(QGraphicsItem):
    """Custom item for very large images that exceed GPU texture limits (rendering on CPU)."""

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image
        self._rect = QRectF(0, 0, image.width(), image.height())

    def boundingRect(self):
        return self._rect

    def paint(self, painter, option, widget):
        if self.image.isNull():
            return

        exposed = option.exposedRect.intersected(self._rect)
        if not exposed.isEmpty():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(exposed, self.image, exposed)


class MediaViewerDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image
        self.setWindowTitle("Secure Viewer")

        screen = QGuiApplication.primaryScreen()
        screen_geom = screen.availableGeometry()

        limit_w = screen_geom.width() * 0.8
        limit_h = screen_geom.height() * 0.8

        img_w = image.width()
        img_h = image.height()
        aspect_ratio = img_w / img_h

        target_w = img_w
        target_h = img_h

        if target_w > limit_w:
            target_w = limit_w
            target_h = target_w / aspect_ratio

        if target_h > limit_h:
            target_h = limit_h
            target_w = target_h * aspect_ratio

        x = screen_geom.x() + (screen_geom.width() - target_w) // 2
        y = screen_geom.y() + (screen_geom.height() - target_h) // 2

        self.setGeometry(int(x), int(y), int(target_w), int(target_h))

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

        self.pix_item = None

        if self.image.width() > 8192 or self.image.height() > 8192:
            self.pix_item = LargeImageItem(self.image)

        else:
            pixmap = QPixmap.fromImage(self.image)
            if not pixmap.isNull():
                self.pix_item = QGraphicsPixmapItem(pixmap)
                self.pix_item.setTransformationMode(
                    Qt.TransformationMode.SmoothTransformation
                )

            else:
                self.pix_item = LargeImageItem(self.image)

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
