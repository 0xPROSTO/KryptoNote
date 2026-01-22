from .BaseNode import BaseNode
from .MediaViewerDialog import MediaViewerDialog

import os
import tempfile
from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QFileDialog
from PyQt6.QtGui import QColor, QPixmap, QImage, QDesktopServices
from PyQt6.QtCore import Qt, QUrl

class MediaNode(BaseNode):
    def __init__(self, item_id, x, y, w, h, thumbnail_bytes, storage, media_type):
        super().__init__(item_id, x, y, w, h, storage)
        self.media_type = media_type
        self.pix_item = None
        self.full_pixmap = None

        if thumbnail_bytes:
            image = QImage.fromData(thumbnail_bytes)
            self.full_pixmap = QPixmap.fromImage(image)
            self.pix_item = QGraphicsPixmapItem(self.full_pixmap, self)
            self.pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        label_text = f"[{media_type.upper()}] Encrypted"
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor("#00FF00"))

        self.update_content_layout()

    def update_content_layout(self):
        if self.pix_item and self.full_pixmap:
            w = self.rect().width() - 20
            h = self.rect().height() - 40

            scaled = self.full_pixmap.scaled(int(w), int(h),
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
            self.pix_item.setPixmap(scaled)

            off_x = (self.rect().width() - scaled.width()) / 2
            off_y = (self.rect().height() - 30 - scaled.height()) / 2
            self.pix_item.setPos(off_x, off_y)

        self.label.setPos(10, self.rect().height() - 25)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse(): return
        self.open_content()

    def extend_context_menu(self, menu):
        open_action = menu.addAction("Открыть")
        open_action.triggered.connect(self.open_content)

        save_action = menu.addAction(f"Экспорт на диск")
        save_action.triggered.connect(self.export_file)

    def open_content(self):
        try:
            print("Decrypting full data...")
            decrypted_data = self.storage.get_full_data(self.item_id)

            if not decrypted_data:
                print("Error: No data found")
                return

            if self.media_type == "image":
                image = QImage.fromData(decrypted_data)
                pixmap = QPixmap.fromImage(image)
                viewer = MediaViewerDialog(pixmap)
                viewer.exec()

            elif self.media_type == "video":
                try:
                    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                    with os.fdopen(fd, 'wb') as tmp:
                        tmp.write(decrypted_data)

                    print(f"Opening video in system player: {temp_path}")
                    QDesktopServices.openUrl(QUrl.fromLocalFile(temp_path))

                except Exception as e:
                    print(f"Video error: {e}")
        except Exception as e:
            print(f"Video error: {e}")

    def export_file(self):
        default_ext = ".jpg" if self.media_type == "image" else ".mp4"
        path, _ = QFileDialog.getSaveFileName(None, "Сохранить файл", "secret_file" + default_ext)
        if path:
            data = self.storage.get_full_data(self.item_id)
            with open(path, "wb") as f:
                f.write(data)