from .base import BaseNode
from KryptoNote.gui.widgets.dialogs.MediaViewerDialog import MediaViewerDialog
from KryptoNote.gui.widgets.viewers import SecureVideoPlayer

from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QFileDialog, QInputDialog
from PyQt6.QtGui import QColor, QPixmap, QImage, QFont
from PyQt6.QtCore import Qt

from KryptoNote.config import Config


class MediaNode(BaseNode):
    def __init__(self, item_id, x, y, w, h, title, thumbnail_bytes, repo, media_type, is_chunked, total_size):
        super().__init__(item_id, x, y, w, h, repo)
        self.media_type = media_type
        self.is_chunked = is_chunked
        self.total_size = total_size
        self.node_title = title if title else "Untitled"
        self.pix_item = None
        self.full_pixmap = None

        if thumbnail_bytes:
            image = QImage.fromData(thumbnail_bytes)
            self.full_pixmap = QPixmap.fromImage(image)
            self.pix_item = QGraphicsPixmapItem(self.full_pixmap, self)
            self.pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        self.title_item = QGraphicsTextItem(self.node_title, self)
        self.title_item.setDefaultTextColor(QColor(Config.COLOR_TEXT_TITLE))
        font = self.title_item.font()
        font.setBold(True)
        self.title_item.setFont(font)

        label_text = f"[{media_type.upper()}] Encrypted"
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(Config.COLOR_SECURE_LABEL))
        label_font = QFont()
        label_font.setPointSize(8)
        self.label.setFont(label_font)

        self.update_content_layout()

    def update_content_layout(self):
        self.title_item.setPos(5, 0)
        title_h = self.title_item.boundingRect().height()

        footer_h = self.label.boundingRect().height()
        self.label.setPos(5, self.rect().height() - footer_h - 2)

        if self.pix_item and self.full_pixmap:
            available_h = self.rect().height() - title_h - footer_h - 10
            available_w = self.rect().width() - 20

            if available_h > 10 and available_w > 10:
                scaled = self.full_pixmap.scaled(int(available_w), int(available_h),
                                                 Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                self.pix_item.setPixmap(scaled)

                off_x = (self.rect().width() - scaled.width()) / 2
                off_y = title_h + 5 + (available_h - scaled.height()) / 2
                self.pix_item.setPos(off_x, off_y)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse(): return
        self.open_content()

    def extend_context_menu(self, menu):
        open_action = menu.addAction("Открыть")
        open_action.triggered.connect(self.open_content)

        rename_action = menu.addAction("Переименовать")
        rename_action.triggered.connect(self.rename_node)

        menu.addSeparator()
        save_action = menu.addAction(f"Экспорт на диск")
        save_action.triggered.connect(self.export_file)

    def rename_node(self):
        new_title, ok = QInputDialog.getText(None, "Rename", "Новое название:", text=self.node_title)
        if ok:
            self.node_title = new_title.strip() or "Untitled"
            self.title_item.setPlainText(self.node_title)
            self.repo.update_item_title(self.item_id, self.node_title)
            self.update_content_layout()

    def open_content(self):
        if self.media_type == "image":
            data = self.repo.get_full_data(self.item_id)
            if data:
                image = QImage.fromData(data)
                pixmap = QPixmap.fromImage(image)
                viewer = MediaViewerDialog(pixmap)
                viewer.exec()

        elif self.media_type == "video":
            if self.is_chunked:
                try:
                    player = SecureVideoPlayer(self.repo, self.item_id, self.total_size, Config.CHUNK_SIZE, self.node_title)
                    player.exec()
                except Exception as e:
                    print(e)

    def export_file(self):
        default_ext = ".jpg" if self.media_type == "image" else ".mp4"
        path, _ = QFileDialog.getSaveFileName(None, "Сохранить файл", self.node_title + default_ext)
        if path:
            if self.is_chunked:
                with open(path, "wb") as f:
                    num_chunks = (self.total_size // Config.CHUNK_SIZE) + 1
                    for i in range(num_chunks):
                        data = self.repo.get_chunk(self.item_id, i)
                        if data: f.write(data)
            else:
                data = self.repo.get_full_data(self.item_id)
                with open(path, "wb") as f:
                    f.write(data)