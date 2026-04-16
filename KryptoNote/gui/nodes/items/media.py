from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QColor, QPixmap, QImage, QImageReader
from PySide6.QtWidgets import (
    QGraphicsTextItem,
    QGraphicsPixmapItem,
    QFileDialog,
    QInputDialog,
)

from KryptoNote.config import Config
from KryptoNote.gui.theme import Theme
from KryptoNote.gui.widgets.dialogs.media_viewer_dialog import MediaViewerDialog
from KryptoNote.gui.widgets.viewers import SecureVideoPlayer
from .base import BaseNode


class MediaNode(BaseNode):
    def __init__(
            self,
            item_id,
            x,
            y,
            w,
            h,
            title,
            thumbnail_bytes,
            service,
            media_type,
            is_chunked,
            total_size,
    ):
        super().__init__(item_id, x, y, w, h, service)
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
            self.pix_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation
            )

        self.title_item = QGraphicsTextItem(self.node_title, self)
        self.title_item.setDefaultTextColor(QColor(Theme.Palette.TEXT_MAIN))
        self.title_item.setFont(Theme.Typography.get_font("SIZE_H2", bold=True))
        label_text = f"[{media_type.upper()}] Encrypted"
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor(Theme.Palette.ACCENT_MAIN))
        self.label.setFont(Theme.Typography.get_font("SIZE_SMALL"))
        self.update_content_layout()

    def update_content_layout(self):
        self.title_item.setPos(10, 5)
        title_h = self.title_item.boundingRect().height()
        footer_h = self.label.boundingRect().height()
        self.label.setPos(10, self.rect().height() - footer_h - 5)
        if self.pix_item and self.full_pixmap:
            available_h = self.rect().height() - title_h - footer_h - 10
            available_w = self.rect().width() - 20
            if available_h > 10 and available_w > 10:
                scaled = self.full_pixmap.scaled(
                    int(available_w),
                    int(available_h),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                self.pix_item.setPixmap(scaled)
                off_x = (self.rect().width() - scaled.width()) / 2
                off_y = title_h + 5 + (available_h - scaled.height()) / 2
                self.pix_item.setPos(off_x, off_y)

    def mouseDoubleClickEvent(self, event):
        if self.resizer.isUnderMouse():
            return
        self.open_content()

    def extend_context_menu(self, menu):
        open_action = menu.addAction("Open")
        open_action.triggered.connect(self.open_content)
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(self.rename_node)
        menu.addSeparator()
        save_action = menu.addAction(f"Export to Disk")
        save_action.triggered.connect(self.export_file)

    def rename_node(self):
        new_title, ok = QInputDialog.getText(
            None, "Rename", "New Title:", text=self.node_title
        )
        if ok:
            self.node_title = new_title.strip() or "Untitled"
            self.title_item.setPlainText(self.node_title)
            self.service.update_item_title(self.item_id, self.node_title)
            self.update_content_layout()

    def open_content(self):
        if self.media_type == "image":
            data = self.service.get_full_data(self.item_id)
            if data:
                buffer = QBuffer()
                buffer.setData(data)
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)

                reader = QImageReader(buffer)
                reader.setAutoTransform(True)
                image = reader.read()

                if not image.isNull():
                    viewer = MediaViewerDialog(image)
                    viewer.exec()

        elif self.media_type == "video":
            if self.is_chunked:
                try:
                    player = SecureVideoPlayer(
                        self.service,
                        self.item_id,
                        self.total_size,
                        Config.CHUNK_SIZE,
                        self.node_title,
                    )
                    player.exec()

                except Exception as e:
                    print(e)

    def export_file(self):
        default_ext = ".jpg" if self.media_type == "image" else ".mp4"
        path, _ = QFileDialog.getSaveFileName(
            None, "Save File", self.node_title + default_ext
        )
        if path:
            if self.is_chunked:
                with open(path, "wb") as f:
                    num_chunks = (self.total_size // Config.CHUNK_SIZE) + 1
                    for i in range(num_chunks):
                        data = self.service.get_chunk(self.item_id, i)
                        if data:
                            f.write(data)

            else:
                data = self.service.get_full_data(self.item_id)
                if data is not None:
                    with open(path, "wb") as f:
                        f.write(data)
