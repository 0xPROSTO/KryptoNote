"""Thread-safe image provider for the currently open media preview."""

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class MediaPreviewProvider(QQuickImageProvider):
    """Expose one bounded decoded preview to embedded and detached QML views."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock = threading.RLock()
        self._image = QImage()
        self._revision = 0

    @property
    def revision(self):
        with self._lock:
            return self._revision

    def set_image(self, image):
        with self._lock:
            self._image = QImage(image) if image is not None else QImage()
            self._revision += 1
            return self._revision

    def clear(self):
        return self.set_image(QImage())

    def requestImage(self, _id_str, size, requested_size):
        with self._lock:
            image = QImage(self._image)
        if image.isNull():
            return image
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        if requested_size.isValid() and not requested_size.isEmpty():
            return image.scaled(
                requested_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return image
